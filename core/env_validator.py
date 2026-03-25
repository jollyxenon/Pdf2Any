import shutil
from config import logger

def validate_environment():
    """
    检查程序运行所需的底层二进制依赖库（例如 Pandoc）。
    """
    if shutil.which('pandoc') is None:
        logger.error("未检测到 Pandoc 命令行工具。")
        raise RuntimeError("未检测到 Pandoc 命令行工具。请安装 Pandoc 并将其配置到系统环境变量 PATH 中。")
    logger.info("环境校验通过：Pandoc 已就绪。")
