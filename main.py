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
from banner import show_banner  

# 显示banner
show_banner()

# 配置日志
logger = setup_logger('log.txt')

# 读取文件
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
        
        if len(proxies) < len(addresses):
            logger.warning(f"proxy.txt行数 ({len(proxies)}) 少于wallet_address.txt行数 ({len(addresses)})，缺少的代理将使用直连本地网络")
            proxies.extend([None] * (len(addresses) - len(proxies)))
        elif len(proxies) > len(addresses):
            logger.warning(f"proxy.txt行数 ({len(proxies)}) 多于wallet_address.txt行数 ({len(addresses)})，多余的代理将被忽略")
            proxies = proxies[:len(addresses)]

        return list(enumerate(addresses, 1)), proxies
    except Exception as e:
        logger.error(f"读取文件出错: {str(e)}")
        raise

# 登录函数
def login(account_id, address, proxy):
    """使用EVM地址登录（无签名），代理缺失时使用直连本地网络"""
    try:
        proxy_dict = get_proxy(proxy) if proxy else None
        logger.info(f"账户 {account_id} (地址: {address}) 使用代理: {proxy if proxy_dict else '直连本地网络'}")

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

        try:
            login_data = json.loads(login_response.text)
        except json.JSONDecodeError:
            logger.error(f"账户 {account_id} (地址: {address}) 登录出错: 无效的JSON响应 - {login_response.text}")
            return False

        if login_response.status_code == 201:
            logger.info(f"账户 {account_id} (地址: {address}) 登录成功")
            return True
        else:
            logger.error(f"账户 {account_id} (地址: {address}) 登录失败: {login_response.status_code} - {login_response.text}")
            return False
    except Exception as e:
        logger.error(f"账户 {account_id} (地址: {address}) 登录出错: {str(e)}")
        return False

# 签到函数
def check_in(account_id, address, proxy):
    """执行签到操作，返回更详细的状态"""
    try:
        proxy_dict = get_proxy(proxy) if proxy else None
        logger.info(f"账户 {account_id} (地址: {address}) 使用代理: {proxy if proxy_dict else '直连本地网络'}")

        checkin_url = f'https://api.tea-fi.com/wallet/check-in?address={address}'
        checkin_payload = {"action": 0}
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

        for attempt in range(3):
            checkin_response = requests.post(
                checkin_url,
                json=checkin_payload,
                headers=checkin_headers,
                proxies=proxy_dict,
                timeout=10
            )
            try:
                checkin_data = json.loads(checkin_response.text)
            except json.JSONDecodeError:
                logger.error(f"账户 {account_id} (地址: {address}) 签到出错 (尝试 {attempt + 1}/3): 无效的JSON响应 - {checkin_response.text}")
                if attempt < 2:
                    time.sleep(5)
                continue

            if checkin_response.status_code == 201:
                logger.info(f"账户 {account_id} (地址: {address}) 签到已完成")
                return "success"
            elif checkin_response.status_code == 400 and checkin_data.get('message') == 'Already checked in today':
                logger.info(f"账户 {account_id} (地址: {address}) 今日已签到，跳过")
                return "already_checked"
            elif checkin_response.status_code == 400:
                logger.info(f"账户 {account_id} (地址: {address}) 签到失败 (尝试 {attempt + 1}/3): 400 Bad Request - {checkin_data}")
                if attempt < 2:
                    time.sleep(5)
                continue
            else:
                logger.error(f"账户 {account_id} (地址: {address}) 签到失败 (尝试 {attempt + 1}/3): {checkin_response.status_code} - {checkin_data}")
                return "error"

        logger.error(f"账户 {account_id} (地址: {address}) 签到失败: 达到最大重试次数")
        return "failed"
    except Exception as e:
        logger.error(f"账户 {account_id} (地址: {address}) 签到出错: {str(e)}")
        return "failed"  # 修改为 "failed"，统一处理网络超时等失败情况

# 每日循环任务
def daily_task():
    """每日执行所有账户的轮流签到，失败后重试"""
    accounts, proxies = read_files()
    failed_accounts = []

    # 第一次尝试所有账户
    for account_id, address in accounts:
        logger.info(f"开始处理账户 {account_id}")
        if login(account_id, address, proxies[account_id - 1]):
            result = check_in(account_id, address, proxies[account_id - 1])
            if result == "success":
                logger.info(f"账户 {account_id} (地址: {address}) 签到已完成")
            elif result == "already_checked":
                logger.info(f"账户 {account_id} (地址: {address}) 今日已签到，无需重复签到")
            elif result in ["failed", "error"]:
                logger.info(f"账户 {account_id} (地址: {address}) 签到失败，等待重试")
                failed_accounts.append((account_id, address, proxies[account_id - 1]))
        else:
            logger.error(f"账户 {account_id} (地址: {address}) 登录失败，等待重试")
            failed_accounts.append((account_id, address, proxies[account_id - 1]))

    # 重试签到失败的账户（5次，每次间隔5秒）
    if failed_accounts:
        logger.info("开始重试签到失败的账户...")
        for _ in range(5):
            temp_failed = []
            for account_id, address, proxy in failed_accounts:
                logger.info(f"重试账户 {account_id} (第 {_ + 1}/5 次)")
                if login(account_id, address, proxy):
                    result = check_in(account_id, address, proxy)
                    if result == "success":
                        logger.info(f"账户 {account_id} (地址: {address}) 重试签到成功")
                    elif result == "already_checked":
                        logger.info(f"账户 {account_id} (地址: {address}) 今日已签到，无需重复签到")
                    elif result in ["failed", "error"]:
                        logger.info(f"账户 {account_id} (地址: {address}) 重试签到失败，加入下次重试")
                        temp_failed.append((account_id, address, proxy))
                else:
                    logger.error(f"账户 {account_id} (地址: {address}) 重试时登录失败，加入下次重试")
                    temp_failed.append((account_id, address, proxy))
            failed_accounts = temp_failed
            if not failed_accounts:
                break
            time.sleep(5)  # 每次重试间隔5秒
        if failed_accounts:
            logger.warning(f"账户 {[(acc_id, addr) for acc_id, addr, _ in failed_accounts]} 重试5次后仍失败")

    # 计划下次签到时间（北京时间次日10:00 AM）
    next_sign_time = datetime.now() + timedelta(days=1)
    next_sign_time = next_sign_time.replace(hour=10, minute=0, second=0, microsecond=0)
    if not failed_accounts:
        logger.info(f"所有账户处理完毕，计划下次签到时间: {next_sign_time.strftime('%Y-%m-%d %H:%M')}")
    else:
        logger.info(f"部分账户签到失败，计划下次签到时间: {next_sign_time.strftime('%Y-%m-%d %H:%M')}")

    schedule_time = next_sign_time.strftime("%H:%M")
    schedule.every().day.at(schedule_time).do(daily_task)

# 动态调度任务
def schedule_dynamic_tasks():
    """动态设置签到时间，并立即执行一次签到"""
    try:
        logger.info("脚本启动，开始处理所有账户的签到...")
        daily_task()

        logger.info("脚本启动完成，开始动态签到任务...")
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("脚本已手动停止，退出程序...")
        exit(0)

if __name__ == "__main__":
    schedule_dynamic_tasks()
