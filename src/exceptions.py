#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一异常处理模块
定义系统中使用的所有自定义异常类和错误处理工具
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCategory(Enum):
    """错误类别枚举"""
    CONFIGURATION = "配置错误"
    NETWORK = "网络错误"
    API = "API错误"
    DATA = "数据错误"
    FILE = "文件错误"
    VALIDATION = "验证错误"
    SYSTEM = "系统错误"
    USER = "用户错误"


class ErrorSeverity(Enum):
    """错误严重程度"""
    INFO = "信息"
    WARNING = "警告"
    ERROR = "错误"
    CRITICAL = "严重"


class LiteratureSystemError(Exception):
    """
    智能文献系统基础异常类
    所有自定义异常的基类
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        component: str = "System",
        solution: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.component = component
        self.solution = solution
        self.details = details or {}

        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """格式化错误消息"""
        return f"[{self.component}] {self.category.value}: {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "component": self.component,
            "solution": self.solution,
            "details": self.details
        }


class ConfigurationError(LiteratureSystemError):
    """配置错误异常"""

    def __init__(
        self,
        message: str,
        component: str = "Configuration",
        solution: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            component=component,
            solution=solution or "请检查配置文件是否正确",
            **kwargs
        )


class NetworkError(LiteratureSystemError):
    """网络错误异常"""

    def __init__(
        self,
        message: str,
        component: str = "Network",
        solution: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK,
            component=component,
            solution=solution or "请检查网络连接",
            **kwargs
        )


class APIError(LiteratureSystemError):
    """API调用错误异常"""

    def __init__(
        self,
        message: str,
        component: str = "API",
        status_code: Optional[int] = None,
        solution: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if status_code:
            details['status_code'] = status_code
        kwargs['details'] = details

        super().__init__(
            message=message,
            category=ErrorCategory.API,
            component=component,
            solution=solution or "请检查API配置和密钥",
            **kwargs
        )
        self.status_code = status_code


class DataError(LiteratureSystemError):
    """数据处理错误异常"""

    def __init__(
        self,
        message: str,
        component: str = "Data",
        solution: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.DATA,
            component=component,
            solution=solution or "请检查数据格式和完整性",
            **kwargs
        )


class FileOperationError(LiteratureSystemError):
    """文件操作错误异常"""

    def __init__(
        self,
        message: str,
        filepath: Optional[str] = None,
        component: str = "FileSystem",
        solution: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if filepath:
            details['filepath'] = filepath
        kwargs['details'] = details

        super().__init__(
            message=message,
            category=ErrorCategory.FILE,
            component=component,
            solution=solution or "请检查文件路径和权限",
            **kwargs
        )
        self.filepath = filepath


class ValidationError(LiteratureSystemError):
    """验证错误异常"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        component: str = "Validation",
        solution: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        kwargs['details'] = details

        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            component=component,
            solution=solution or "请检查输入数据的有效性",
            **kwargs
        )
        self.field = field


class AIServiceError(APIError):
    """AI服务错误异常"""

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        component: str = "AIService",
        solution: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if model_id:
            details['model_id'] = model_id
        kwargs['details'] = details

        super().__init__(
            message=message,
            component=component,
            solution=solution or "请检查AI服务配置和API密钥",
            **kwargs
        )
        self.model_id = model_id


class PubMedError(APIError):
    """PubMed API错误异常"""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        component: str = "PubMed",
        solution: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if query:
            details['query'] = query
        kwargs['details'] = details

        super().__init__(
            message=message,
            component=component,
            solution=solution or "请检查检索词格式或稍后重试",
            **kwargs
        )
        self.query = query


def handle_exception(
    exception: Exception,
    component: str = "System",
    show_traceback: bool = False
) -> Dict[str, Any]:
    """
    统一异常处理函数

    Args:
        exception: 捕获的异常
        component: 发生错误的组件名称
        show_traceback: 是否显示完整堆栈

    Returns:
        错误信息字典
    """
    import traceback

    if isinstance(exception, LiteratureSystemError):
        error_info = exception.to_dict()
    else:
        error_info = {
            "message": str(exception),
            "category": ErrorCategory.SYSTEM.value,
            "severity": ErrorSeverity.ERROR.value,
            "component": component,
            "solution": None,
            "details": {"exception_type": type(exception).__name__}
        }

    if show_traceback:
        error_info["traceback"] = traceback.format_exc()

    return error_info


def print_error(
    exception: Exception,
    component: str = "System",
    show_solution: bool = True
) -> None:
    """
    格式化打印错误信息

    Args:
        exception: 捕获的异常
        component: 发生错误的组件名称
        show_solution: 是否显示解决方案
    """
    if isinstance(exception, LiteratureSystemError):
        print(f"\n[ERROR] {exception.component}: {exception.message}")
        if show_solution and exception.solution:
            print(f"[INFO] 建议: {exception.solution}")
    else:
        print(f"\n[ERROR] {component}: {str(exception)}")
        print(f"[INFO] 异常类型: {type(exception).__name__}")
