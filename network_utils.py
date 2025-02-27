import random
from fake_useragent import UserAgent

def get_proxy():
    """从proxy.txt随机读取一个代理"""
    try:
        with open('proxy.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        if not proxies:
            return None
        return {'http': random.choice(proxies), 'https': random.choice(proxies)}
    except Exception as e:
        print(f"读取代理文件出错: {str(e)}")
        return None

def get_random_user_agent():
    """生成随机User-Agent"""
    ua = UserAgent()
    return ua.random
