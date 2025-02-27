import logging

def setup_logger(log_file='log.txt'):
    """设置日志记录器，输出到文件和控制台"""
    logger = logging.getLogger('TeaFiAutoCheck')
    logger.setLevel(logging.INFO)

    # 移除默认的处理器，避免重复日志
    if logger.hasHandlers():
        logger.handlers.clear()

    # 文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger
