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

# 读取文件
def read_files():
    """读取钱包地址和代理地址文件"""
    try:
        with open('wallet_address.txt', 'r') as f:
            addresses = [line.strip() for line in f if line.strip()]
        with open('proxy.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        if len(addresses) != len(proxies):
            logger.error("钱包地址和代理数量不匹配！")
            raise ValueError("请确保wallet_address.txt和proxy.txt行数相同")
        return addresses, proxies
    except Exception as e:
        logger.error(f"读取文件出错: {str(e)}")
        raise

# 登录函数（直接用地址，无需私钥）
def login(address, proxy):
    """使用EVM地址登录（无签名）"""
    try:
        # 获取并记录使用的代理
        proxy_dict = {'http': proxy, 'https': proxy} if proxy else None
        logger.info(f"账户 {address} 使用代理: {proxy if proxy else '无代理'}")

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
            logger.error(f"账户 {address} 登录出错: 无效的JSON响应 - {login_response.text}")
            return False

        if login_response.status_code == 201:  # 登录成功
            logger.info(f"账户 {address} 登录成功，响应: {login_data}")
            return True
        else:
            logger.error(f"账户 {address} 登录失败: {login_data}")
            return False
    except Exception as e:
        logger.error(f"账户 {address} 登录出错: {str(e)}")
        return False

# 获取签到状态和倒计时
def get_checkin_status(address, proxy):
    """查询当前签到状态和下次可签到时间"""
    try:
        proxy_dict = {'http': proxy, 'https': proxy} if proxy else None
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
                    next_time = last_time + timedelta(hours=24)  # 假设24小时周期
                    # 延迟5分钟
                    next_time += timedelta(minutes=5)
                    logger.info(f"账户 {address} 下次可签到时间: {next_time}")
                    return next_time
                else:
                    logger.warning(f"账户 {address} 未找到上次签到时间，使用默认24小时后")
                    return datetime.utcnow() + timedelta(hours=24)
            else:
                error_msg = status_response.text if status_response.text else f"Status code: {status_response.status_code}"
                logger.error(f"账户 {address} 查询签到状态失败 (尝试 {attempt + 1}/3): {error_msg}")
                if attempt < 2:
                    time.sleep(5)  # 等待5秒后重试
                continue
        logger.error(f"账户 {address} 查询签到状态失败: 达到最大重试次数")
        return datetime.utcnow() + timedelta(hours=24)  # 默认24小时后重试
    except Exception as e:
        logger.error(f"账户 {address} 查询签到状态出错: {str(e)}")
        return datetime.utcnow() + timedelta(hours=24)

# 签到函数（使用 wallet/check-in）
def check_in(address, proxy):
    """执行签到操作（使用 wallet/check-in）"""
    try:
        proxy_dict = {'http': proxy, 'https': proxy} if proxy else None
        logger.info(f"账户 {address} 使用代理: {proxy if proxy else '无代理'}")

        # 先查询签到状态
        next_time = get_checkin_status(address, proxy)
        current_time = datetime.utcnow()
        if current_time < next_time:
            wait_seconds = (next_time - current_time).total_seconds()
            logger.info(f"账户 {address} 签到冷却中，等待 {wait_seconds/3600:.2f} 小时")
            return False

        # 发送签到请求
        checkin_url = f'https://api.tea-fi.com/wallet/check-in?address={address}'
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
        checkin_response = requests.post(
            checkin_url,
            headers=checkin_headers,
            proxies=proxy_dict,
            timeout=10
        )

        # 解析响应
        try:
            checkin_data = json.loads(checkin_response.text)
        except json.JSONDecodeError:
            logger.error(f"账户 {address} 签到出错: 无效的JSON响应 - {checkin_response.text}")
            return False

        if checkin_response.status_code == 201:  # 签到成功
            logger.info(f"账户 {address} 签到已完成，响应: {checkin_data}")
            logger.info(f"账户 {address} 下次签到时间: {next_time}")
            return True
        else:
            logger.error(f"账户 {address} 签到失败: {checkin_data}")
            return False
    except Exception as e:
        logger.error(f"账户 {address} 签到出错: {str(e)}")
        return False

# 每日循环任务
def daily_task():
    """每日执行登录和签到任务"""
    addresses, proxies = read_files()
    for address, proxy in zip(addresses, proxies):
        logger.info(f"开始处理账户 {address}")
        if login(address, proxy):
            if check_in(address, proxy):
                time.sleep(300)  # 延迟5分钟
            else:
                logger.info(f"账户 {address} 签到失败")
        else:
            logger.error(f"账户 {address} 登录失败，无法签到")

# 动态调度任务（立即执行一次签到，然后计划下次）
def schedule_dynamic_tasks():
    """动态设置签到时间，按每个账户的倒计时调度，并立即执行一次签到"""
    logger.info("脚本启动，开始处理所有账户的签到...")
    daily_task()  # 立即执行一次签到

    addresses, proxies = read_files()
    for address, proxy in zip(addresses, proxies):
        next_time = get_checkin_status(address, proxy)
        schedule_time = next_time.strftime("%H:%M")
        schedule.every().day.at(schedule_time).do(lambda a=address, p=proxy: daily_task_for_account(a, p))
        logger.info(f"账户 {address} 计划于 {schedule_time} UTC 执行下一次签到")

    logger.info("脚本启动完成，开始动态签到任务...")

def daily_task_for_account(address, proxy):
    """为单个账户执行登录和签到"""
    logger.info(f"开始处理账户 {address} 的定时任务")
    if login(address, proxy):
        if check_in(address, proxy):
            time.sleep(300)  # 延迟5分钟

if __name__ == "__main__":
    schedule_dynamic_tasks()
