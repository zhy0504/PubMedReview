# -*- coding: utf-8 -*-
"""
日志模块单元测试
"""

import logging
import pytest
from pathlib import Path

from logger import (
    get_logger,
    console_print,
    set_debug_mode,
    set_quiet_mode,
    LoggerConfig,
    info,
    error,
    warning,
)


class TestGetLogger:
    """get_logger测试"""

    def test_returns_logger(self):
        """测试返回Logger实例"""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_logger_cached(self):
        """测试Logger被缓存"""
        logger1 = get_logger("cached_module")
        logger2 = get_logger("cached_module")
        assert logger1 is logger2

    def test_different_names_different_loggers(self):
        """测试不同名称返回不同Logger"""
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")
        assert logger1 is not logger2


class TestLoggerConfig:
    """LoggerConfig测试"""

    def test_singleton(self):
        """测试单例模式"""
        config1 = LoggerConfig()
        config2 = LoggerConfig()
        assert config1 is config2

    def test_log_dir_exists(self):
        """测试日志目录存在"""
        config = LoggerConfig()
        assert config.log_dir.exists()


class TestConsolePrint:
    """console_print测试"""

    def test_basic_print(self, caplog):
        """测试基本输出"""
        with caplog.at_level(logging.INFO):
            console_print("测试消息")
        assert "测试消息" in caplog.text

    def test_with_prefix(self, caplog):
        """测试带前缀输出"""
        with caplog.at_level(logging.INFO):
            console_print("成功", prefix="✓")
        assert "✓" in caplog.text
        assert "成功" in caplog.text

    def test_error_level(self, caplog):
        """测试错误级别"""
        with caplog.at_level(logging.ERROR):
            console_print("错误消息", level="error")
        assert "错误消息" in caplog.text


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_info(self, caplog):
        """测试info函数"""
        with caplog.at_level(logging.INFO):
            info("信息消息")
        assert "信息消息" in caplog.text

    def test_error(self, caplog):
        """测试error函数"""
        with caplog.at_level(logging.ERROR):
            error("错误消息")
        assert "错误消息" in caplog.text

    def test_warning(self, caplog):
        """测试warning函数"""
        with caplog.at_level(logging.WARNING):
            warning("警告消息")
        assert "警告消息" in caplog.text


class TestModeSwitch:
    """模式切换测试"""

    def test_debug_mode(self):
        """测试调试模式"""
        set_debug_mode(True)
        config = LoggerConfig()
        assert config.level == logging.DEBUG
        set_debug_mode(False)

    def test_quiet_mode(self):
        """测试静默模式"""
        set_quiet_mode(True)
        config = LoggerConfig()
        assert config.level == logging.WARNING
        set_quiet_mode(False)
