# main.py
import time
import json
import requests
from fake_useragent import UserAgent
import schedule
import logging
from datetime import datetime, timedelta
from network_utils import get_proxy, get_random_user_agent
from logger import setup_logger

# 配置日志
logger = setup_logger('log.txt')

# 读取文件（容错处理代理行数不足）
def read_files():
    """读取钱包地址和代理地址文件，代理不足时使用直连本地网络"""
    try:
        with open('wallet_address.txt', 'r') as f:
            addresses = [line.strip() for line in f if line.strip()]
        with open('proxy.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        
        if not addresses:
            logger.error("wallet_address.txt为空！")
            raise ValueError("请确保wallet_address.txt至少包含一个地址")
        
        # 如果代理数量少于地址数量，补齐为None（直连本地网络）
        if len(proxies) < len(addresses):
            logger.warning(f"proxy.txt行数 ({len(proxies)}) 少于wallet_address.txt行数 ({len(addresses)})，缺少的代理将使用直连本地网络")
            proxies.extend([None] * (len(addresses) - len(proxies)))
        elif len(proxies) > len(addresses):
            logger.warning(f"proxy.txt行数 ({len(proxies)}) 多于wallet_address.txt行数 ({len(addresses)})，多余的代理将被忽略")
            proxies = proxies[:len(addresses)]

        return list(enumerate(addresses, 1)), proxies  # 返回带索引的地址列表 (index, address)
    except Exception as e:
        logger.error(f"读取文件出错: {str(e)}")
        raise

# 登录函数（直接用地址，无需私钥）
def login(account_id, address, proxy):
    """使用EVM地址登录（无签名），代理缺失时使用直连本地网络"""
    try:
        # 获取并记录使用的代理（或直连）
        proxy_dict = get_proxy(proxy) if proxy else None
        logger.info(f"账户 {account_id} (地址: {address}) 使用代理: {proxy if proxy_dict else '直连本地网络'}")

        # 发送登录请求
        login_url = 'https://api.tea-fi.com/wallets'
        login_payload = {'address': address}
        login_headers = {
            'User-Agent': get_random_user_agent(),
            'Content-Type': 'application/json',
            'accept': 'application/json, text/plain, */*',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'referer': 'https://app.tea-fi.com/',
            'origin': 'https://app.tea-fi.com'
        }
        login_response = requests.post(
            login_url,
            json=login_payload,
            headers=login_headers,
            proxies=proxy_dict,
            timeout=10
        )

        # 解析响应
        try:
            login_data = json.loads(login_response.text)
        except json.JSONDecodeError:
            logger.error(f"账户 {account_id} (地址: {address}) 登录出错: 无效的JSON响应 - {login_response.text}")
            return False

        if login_response.status_code == 201:  # 登录成功
            logger.info(f"账户 {account_id} (地址: {address}) 登录成功")
            return True
        else:
            logger.error(f"账户 {account_id} (地址: {address}) 登录失败: {login_response.status_code}")
            return False
    except Exception as e:
        logger.error(f"账户 {account_id} (地址: {address}) 登录出错: {str(e)}")
        return False

# 获取签到状态和倒计时（24小时冷却时间+5分钟缓冲，UTC）
def get_checkin_status(account_id, address, proxy):
    """查询当前签到状态和下次可签到时间（24小时冷却时间+5分钟缓冲，UTC）"""
    try:
        # 获取并记录使用的代理（或直连）
        proxy_dict = get_proxy(proxy) if proxy else None
        logger.info(f"账户 {account_id} (地址: {address}) 使用代理: {proxy if proxy_dict else '直连本地网络'}")

        status_url = 'https://api.tea-fi.com/wallet/check-in/current'
        status_headers = {
            'User-Agent': get_random_user_agent(),
            'Content-Type': 'application/json',
            'accept': 'application/json, text/plain, */*',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'referer': 'https://app.tea-fi.com/',
            'origin': 'https://app.tea-fi.com'
        }

        for attempt in range(3):  # 重试3次
            status_response = requests.get(
                f"{status_url}?address={address}",
                headers=status_headers,
                proxies=proxy_dict,
                timeout=10
            )
            if status_response.status_code == 200:
                status_data = json.loads(status_response.text)
                last_checkin = status_data.get('lastCheckIn', None)
                if last_checkin:
                    last_time = datetime.strptime(last_checkin, "%Y-%m-%dT%H:%M:%S.%fZ")
                    # 24小时冷却时间+5分钟缓冲
                    next_time = last_time + timedelta(hours=24, minutes=5)
                    current_time = datetime.utcnow()
                    remaining_minutes = (next_time - current_time).total_seconds() / 60  # 剩余分钟
                    logger.info(f"账户 {account_id} (地址: {address}) 下次可签到时间: {next_time}，剩余 {remaining_minutes:.2f} 分钟")
                    return next_time
                else:
                    logger.info(f"账户 {account_id} (地址: {address}) 未找到上次签到时间，允许立即签到")
                    return datetime.utcnow()  # 允许新账户立即签到
            else:
                error_msg = status_response.text if status_response.text else f"Status code: {status_response.status_code}"
                logger.error(f"账户 {account_id} (地址: {address}) 查询签到状态失败 (尝试 {attempt + 1}/3): {error_msg}")
                if attempt < 2:
                    time.sleep(5)  # 等待5秒后重试
                continue
        logger.error(f"账户 {account_id} (地址: {address}) 查询签到状态失败: 达到最大重试次数")
        return datetime.utcnow()  # 允许在新账户时立即签到
    except Exception as e:
        logger.error(f"账户 {account_id} (地址: {address}) 查询签到状态出错: {str(e)}")
        return datetime.utcnow()  # 允许在新账户时立即签到

# 签到函数（使用 wallet/check-in）
def check_in(account_id, address, proxy):
    """执行签到操作（使用 wallet/check-in），二次运行时显示已执行过签到"""
    try:
        # 获取并记录使用的代理（或直连）
        proxy_dict = get_proxy(proxy) if proxy else None
        logger.info(f"账户 {account_id} (地址: {address}) 使用代理: {proxy if proxy_dict else '直连本地网络'}")

        # 查询签到状态以检查冷却时间
        next_time = get_checkin_status(account_id, address, proxy)
        current_time = datetime.utcnow()

        # 检查是否已签到过（冷却时间内）
        if current_time < next_time:
            last_checkin = get_last_checkin(account_id, address, proxy)  # 获取上次签到时间
            if last_checkin:
                logger.info(f"账户 {account_id} (地址: {address}) 已执行过签到，跳过签到操作")
                return False  # 跳过签到，不显示冷却时间

        # 如果未签到过或冷却时间已结束，尝试签到
        if current_time >= next_time:
            # 发送签到请求（添加 action 参数）
            checkin_url = f'https://api.tea-fi.com/wallet/check-in?address={address}'
            checkin_payload = {"action": 0}  # 添加必要的请求体
            checkin_headers = {
                'User-Agent': get_random_user_agent(),
                'Content-Type': 'application/json',
                'accept': 'application/json, text/plain, */*',
                'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'referer': 'https://app.tea-fi.com/',
                'origin': 'https://app.tea-fi.com'
            }

            for attempt in range(3):  # 重试3次签到
                checkin_response = requests.post(
                    checkin_url,
                    json=checkin_payload,  # 添加请求体
                    headers=checkin_headers,
                    proxies=proxy_dict,
                    timeout=10
                )
                try:
                    checkin_data = json.loads(checkin_response.text)
                except json.JSONDecodeError:
                    logger.error(f"账户 {account_id} (地址: {address}) 签到出错 (尝试 {attempt + 1}/3): 无效的JSON响应 - {checkin_response.text}")
                    if attempt < 2:
                        time.sleep(5)  # 等待5秒后重试
                    continue
                    return False

                if checkin_response.status_code == 201:  # 签到成功
                    logger.info(f"账户 {account_id} (地址: {address}) 签到已完成")
                    return True
                elif checkin_response.status_code == 400:
                    logger.error(f"账户 {account_id} (地址: {address}) 签到失败 (尝试 {attempt + 1}/3): 400 Bad Request - {checkin_data if checkin_data else '无响应数据'}")
                    if attempt < 2:
                        time.sleep(5)  # 等待5秒后重试
                    continue
                else:
                    logger.error(f"账户 {account_id} (地址: {address}) 签到失败 (尝试 {attempt + 1}/3): {checkin_response.status_code} - {checkin_data if checkin_data else '无响应数据'}")
                    return False

            logger.error(f"账户 {account_id} (地址: {address}) 签到失败: 达到最大重试次数")
            return False
        return False  # 冷却时间内跳过签到，不显示冷却时间
    except Exception as e:
        logger.error(f"账户 {account_id} (地址: {address}) 签到出错: {str(e)}")
        return False

# 辅助函数：获取上次签到时间
def get_last_checkin(account_id, address, proxy):
    """查询当前账户的上次签到时间"""
    try:
        proxy_dict = get_proxy(proxy) if proxy else None
        status_url = 'https://api.tea-fi.com/wallet/check-in/current'
        status_headers = {
            'User-Agent': get_random_user_agent(),
            'Content-Type': 'application/json',
            'accept': 'application/json, text/plain, */*',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'referer': 'https://app.tea-fi.com/',
            'origin': 'https://app.tea-fi.com'
        }

        status_response = requests.get(
            f"{status_url}?address={address}",
            headers=status_headers,
            proxies=proxy_dict,
            timeout=10
        )
        if status_response.status_code == 200:
            status_data = json.loads(status_response.text)
            return status_data.get('lastCheckIn', None)
        return None
    except Exception as e:
        logger.error(f"账户 {account_id} (地址: {address}) 获取上次签到时间出错: {str(e)}")
        return None

# 每日循环任务（轮流签到，所有账户完成后统一显示下次签到时间）
def daily_task():
    """每日执行所有账户的轮流签到"""
    accounts, proxies = read_files()
    all_success = True  # 标记所有账户是否签到成功
    last_next_time = None  # 存储最后一个签到成功的下次时间
    for account_id, address in accounts:
        logger.info(f"开始处理账户 {account_id}")
        if login(account_id, address, proxies[account_id - 1]):
            if check_in(account_id, address, proxies[account_id - 1]):
                logger.info(f"账户 {account_id} (地址: {address}) 签到已完成")
                # 获取当前账户的下次签到时间（24小时后+5分钟）
                next_time = get_checkin_status(account_id, address, proxies[account_id - 1])
                last_next_time = next_time if last_next_time is None or next_time > last_next_time else last_next_time
            else:
                logger.info(f"账户 {account_id} (地址: {address}) 已执行过签到，跳过签到操作")
                all_success = False
                # 为失败账户设置默认下次时间（24小时后+5分钟）
                next_time = datetime.utcnow() + timedelta(hours=24, minutes=5)
                last_next_time = next_time if last_next_time is None else last_next_time
        else:
            logger.error(f"账户 {account_id} (地址: {address}) 登录失败，无法签到")
            all_success = False
            # 为登录失败账户设置默认下次时间（24小时后+5分钟）
            next_time = datetime.utcnow() + timedelta(hours=24, minutes=5)
            last_next_time = next_time if last_next_time is None else last_next_time

    # 所有账户签完后，动态计算下次签到时间（24小时后+5分钟）
    if last_next_time:
        logger.info(f"所有账户签到处理完成，计划下次签到时间: {last_next_time}")
        schedule_time = last_next_time.strftime("%H:%M")
        logger.info(f"所有账户计划于 {schedule_time} UTC 执行下一次签到")
    else:
        logger.warning("无法确定下次签到时间，使用默认24小时后+5分钟")
        next_sign_time = datetime.utcnow() + timedelta(hours=24, minutes=5)
        schedule_time = next_sign_time.strftime("%H:%M")
        logger.info(f"所有账户计划于 {schedule_time} UTC 执行下一次签到")

    # 计划下次签到（动态调整时间）
    schedule.every().day.at(schedule_time).do(daily_task)

# 动态调度任务（立即执行一次签到，然后每天循环）
def schedule_dynamic_tasks():
    """动态设置签到时间，按所有账户的轮流签到调度，并立即执行一次签到"""
    try:
        logger.info("脚本启动，开始处理所有账户的签到...")
        daily_task()  # 立即执行一次签到

        logger.info("脚本启动完成，开始动态签到任务...")

        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("脚本已手动停止，退出程序...")
        exit(0)

if __name__ == "__main__":
    schedule_dynamic_tasks()
