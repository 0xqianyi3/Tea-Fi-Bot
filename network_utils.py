import random
import logging
from fake_useragent import UserAgent

logger = logging.getLogger('TeaFiAutoCheck')

def get_proxy(proxy_str=None):
    """从单个代理字符串读取代理，如果为空或无效则默认直连本地网络"""
    if proxy_str and proxy_str.strip():
        try:
            if proxy_str.startswith(('http://', 'https://', 'socks5://')):
                return {'http': proxy_str, 'https': proxy_str}
            logger.warning(f"无效的代理格式: {proxy_str}，使用直连本地网络")
        except Exception as e:
            logger.error(f"处理代理字符串出错: {str(e)}")
    logger.warning("代理字符串为空或无效，使用直连本地网络")
    return None  # 默认直连本地网络

def get_random_user_agent():
    """生成随机User-Agent"""
    ua = UserAgent()
    return ua.random
