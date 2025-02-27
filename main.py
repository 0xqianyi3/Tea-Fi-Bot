# main.py
import time
import json
import requests
from fake_useragent import UserAgent
import schedule
import logging
from datetime import datetime, timedelta
from utils.network_utils import get_proxy, get_random_user_agent
from utils.logger import setup_logger

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
            'sec-fetch-site': 'same-site'
        }
        login_response = requests.post(
            login_url,
            json=login_payload,
            headers=login_headers,
            proxies={'http': proxy, 'https': proxy},
            timeout=10
        )

        # 解析响应
        login_data = json.loads(login_response.text)
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
            'sec-fetch-site': 'same-site'
        }
        status_response = requests.get(
            f"{status_url}?address={address}",
            headers=status_headers,
            proxies={'http': proxy, 'https': proxy},
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
            logger.error(f"账户 {address} 查询签到状态失败: {status_data}")
            return datetime.utcnow() + timedelta(hours=24)  # 默认24小时后重试
    except Exception as e:
        logger.error(f"账户 {address} 查询签到状态出错: {str(e)}")
        return datetime.utcnow() + timedelta(hours=24)

# 签到函数（使用 wallet/check-in）
def check_in(address, proxy):
    """执行签到操作（使用 wallet/check-in）"""
    try:
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
            'sec-fetch-site': 'same-site'
        }
        checkin_response = requests.post(
            checkin_url,
            headers=checkin_headers,
            proxies={'http': proxy, 'https': proxy},
            timeout=10
        )

        # 解析响应
        checkin_data = json.loads(checkin_response.text)
        if checkin_response.status_code == 201:  # 签到成功
            logger.info(f"账户 {address} 签到成功，响应: {checkin_data}")
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
        if login(address, proxy):
            if check_in(address, proxy):
                time.sleep(300)  # 延迟5分钟
            else:
                logger.info(f"账户 {address} 签到失败，跳过延迟")

# 动态调度任务
def schedule_dynamic_tasks():
    """动态设置签到时间，按每个账户的倒计时调度"""
    addresses, proxies = read_files()
    for address, proxy in zip(addresses, proxies):
        next_time = get_checkin_status(address, proxy)
        schedule_time = next_time.strftime("%H:%M")
        schedule.every().day.at(schedule_time).do(lambda a=address, p=proxy: daily_task_for_account(a, p))
        logger.info(f"账户 {address} 计划于 {schedule_time} UTC 执行签到")

    logger.info("脚本启动，开始动态签到任务...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次

def daily_task_for_account(address, proxy):
    """为单个账户执行登录和签到"""
    if login(address, proxy):
        if check_in(address, proxy):
            time.sleep(300)  # 延迟5分钟

if __name__ == "__main__":
    schedule_dynamic_tasks()
