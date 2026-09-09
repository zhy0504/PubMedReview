# -*- coding: utf-8 -*-
"""
统一日志模块

提供标准化的日志功能，支持：
- 控制台彩色输出
- 文件日志持久化
- 日志级别控制
- 结构化日志格式
- 兼容现有print调用的渐进式迁移

使用方法:
    from logger import get_logger, console_print

    # 推荐方式：使用标准logger
    logger = get_logger(__name__)
    logger.info("信息消息")
    logger.error("错误消息")

    # 兼容方式：保持控制台输出风格
    console_print("用户可见消息", level="info")
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from functools import lru_cache


# 日志颜色定义（ANSI转义码）
class LogColors:
    """日志颜色常量"""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    LEVEL_COLORS = {
        logging.DEBUG: LogColors.GRAY,
        logging.INFO: LogColors.GREEN,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.BOLD + LogColors.RED,
    }

    def __init__(self, fmt: str = None, datefmt: str = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        target_record = record
        if self.use_colors:
            # 使用副本避免污染其他handler共享的LogRecord
            target_record = logging.makeLogRecord(record.__dict__.copy())
            color = self.LEVEL_COLORS.get(target_record.levelno, LogColors.RESET)
            target_record.levelname = f"{color}{target_record.levelname}{LogColors.RESET}"
            target_record.msg = f"{color}{target_record.msg}{LogColors.RESET}"
        return super().format(target_record)


class LoggerConfig:
    """日志配置管理"""

    _instance: Optional['LoggerConfig'] = None

    # 默认配置
    DEFAULT_LEVEL = logging.INFO
    DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_DIR = Path(__file__).parent.parent / "logs"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.level = self.DEFAULT_LEVEL
        self.log_dir = self.LOG_DIR
        self.file_logging_enabled = True
        self.console_colors_enabled = True
        self._initialized = True

        # 确保日志目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def set_level(self, level: int) -> None:
        """设置全局日志级别"""
        self.level = level
        # 更新root logger
        logging.root.setLevel(level)
        for handler in logging.root.handlers:
            handler.setLevel(level)
        # 更新所有已创建的命名logger
        for logger_obj in logging.Logger.manager.loggerDict.values():
            if isinstance(logger_obj, logging.Logger):
                logger_obj.setLevel(level)
                for handler in logger_obj.handlers:
                    handler.setLevel(level)


@lru_cache(maxsize=32)
def get_logger(name: str) -> logging.Logger:
    """
    获取命名日志器（带缓存）

    Args:
        name: 日志器名称，通常使用__name__

    Returns:
        配置好的Logger实例

    Example:
        logger = get_logger(__name__)
        logger.info("操作成功")
        logger.error("发生错误", exc_info=True)
    """
    config = LoggerConfig()
    logger = logging.getLogger(name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    logger.setLevel(config.level)
    # 允许传播到root，便于pytest caplog等外部日志捕获
    logger.propagate = True

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.level)
    console_formatter = ColoredFormatter(
        fmt=config.DEFAULT_FORMAT,
        datefmt=config.DEFAULT_DATE_FORMAT,
        use_colors=config.console_colors_enabled
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    if config.file_logging_enabled:
        log_file = config.log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(config.level)
        file_formatter = logging.Formatter(
            fmt=config.DEFAULT_FORMAT,
            datefmt=config.DEFAULT_DATE_FORMAT
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def console_print(
    message: str,
    level: str = "info",
    prefix: str = "",
    newline: bool = True
) -> None:
    """
    兼容print风格的控制台输出

    用于从print逐步迁移到日志系统的过渡方案。
    保持用户可见的控制台输出，同时记录到日志文件。

    Args:
        message: 消息内容
        level: 日志级别 (debug/info/warning/error/critical)
        prefix: 前缀符号 (如 "✓", "✗", "→")
        newline: 是否换行

    Example:
        console_print("检索完成", level="info", prefix="✓")
        console_print("发生错误", level="error", prefix="✗")
    """
    logger = get_logger("console")

    # 构建输出消息
    if prefix:
        message = f"{prefix} {message}"

    # 映射级别
    level_map = {
        "debug": logger.debug,
        "info": logger.info,
        "warning": logger.warning,
        "warn": logger.warning,
        "error": logger.error,
        "critical": logger.critical,
    }

    log_func = level_map.get(level.lower(), logger.info)
    log_func(message)


def set_debug_mode(enabled: bool = True) -> None:
    """启用或禁用调试模式"""
    config = LoggerConfig()
    config.set_level(logging.DEBUG if enabled else logging.INFO)


def set_quiet_mode(enabled: bool = True) -> None:
    """启用或禁用静默模式（仅显示警告及以上）"""
    config = LoggerConfig()
    config.set_level(logging.WARNING if enabled else logging.INFO)


# 便捷函数 - 用于快速日志记录
_default_logger: Optional[logging.Logger] = None

def _get_default_logger() -> logging.Logger:
    """获取默认日志器"""
    global _default_logger
    if _default_logger is None:
        _default_logger = get_logger("literature_review")
    return _default_logger


def debug(msg: str, *args, **kwargs) -> None:
    """记录调试信息"""
    _get_default_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    """记录一般信息"""
    _get_default_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    """记录警告信息"""
    _get_default_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    """记录错误信息"""
    _get_default_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    """记录严重错误"""
    _get_default_logger().critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs) -> None:
    """记录异常信息（自动包含堆栈跟踪）"""
    _get_default_logger().exception(msg, *args, **kwargs)


# 导出接口
__all__ = [
    'get_logger',
    'console_print',
    'set_debug_mode',
    'set_quiet_mode',
    'LoggerConfig',
    'LogColors',
    # 便捷函数
    'debug',
    'info',
    'warning',
    'error',
    'critical',
    'exception',
]
