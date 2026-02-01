#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户意图分析和检索词构建模块 v2.0
基于AI大模型分析用户输入，生成PubMed检索词和筛选条件
优化特性：智能缓存、异步处理、增强错误处理、配置管理优化
"""

import json
import os
import re
import time
import asyncio
import hashlib
import threading
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from ai_client import AIClient, ConfigManager, ChatMessage
from prompts_manager import PromptsManager
from shared_config import system_config
from dataclasses import dataclass, asdict


@dataclass
class AIModelConfig:
    """AI模型配置缓存"""
    config_name: str
    model_id: str
    parameters: Dict
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class IntentAnalysisCache:
    """意图分析结果缓存管理器"""
    
    def __init__(self, cache_size: int = 500, ttl: int = 3600):
        self.cache_size = cache_size
        self.ttl = ttl
        self.cache = {}
        self.access_times = {}
        self.lock = threading.Lock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def _generate_cache_key(self, user_input: str, model_id: str, parameters: Dict) -> str:
        """生成缓存键"""
        content = f"{user_input}:{model_id}:{json.dumps(parameters, sort_keys=True)}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get(self, user_input: str, model_id: str, parameters: Dict) -> Optional['SearchCriteria']:
        """获取缓存的意图分析结果"""
        cache_key = self._generate_cache_key(user_input, model_id, parameters)
        
        with self.lock:
            if cache_key in self.cache:
                cache_data = self.cache[cache_key]
                if time.time() - cache_data['timestamp'] < self.ttl:
                    self.access_times[cache_key] = time.time()
                    self.stats['hits'] += 1
                    return cache_data['criteria']
                else:
                    # 清除过期缓存
                    del self.cache[cache_key]
                    if cache_key in self.access_times:
                        del self.access_times[cache_key]
                    self.stats['evictions'] += 1
        
        self.stats['misses'] += 1
        return None
    
    def put(self, user_input: str, model_id: str, parameters: Dict, criteria: 'SearchCriteria'):
        """缓存意图分析结果"""
        # 如果缓存大小为0，表示禁用缓存
        if self.cache_size <= 0:
            return

        cache_key = self._generate_cache_key(user_input, model_id, parameters)

        with self.lock:
            # LRU缓存清理
            if len(self.cache) >= self.cache_size and self.access_times:
                oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
                del self.cache[oldest_key]
                del self.access_times[oldest_key]
                self.stats['evictions'] += 1
            
            self.cache[cache_key] = {
                'criteria': criteria,
                'timestamp': time.time(),
                'user_input': user_input,
                'model_id': model_id,
                'parameters': parameters
            }
            self.access_times[cache_key] = time.time()
    
    def clear(self):
        """清除所有缓存"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                'cache_size': len(self.cache),
                'max_cache_size': self.cache_size,
                'hit_rate': hit_rate,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions']
            }


class ConfigManagerPool:
    """配置管理器池 - 避免重复初始化"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.config_managers = {}
            self.ai_clients = {}
            self.adapters = {}
            self.lock = threading.Lock()
            self._initialized = True
    
    def get_config_manager(self, config_file: str = None) -> ConfigManager:
        """获取配置管理器实例（config_file参数已废弃）"""
        with self.lock:
            cache_key = "default"
            if cache_key not in self.config_managers:
                self.config_managers[cache_key] = ConfigManager()
            return self.config_managers[cache_key]

    def get_ai_client(self, config_file: str = None,
                     enable_cache: bool = True, enable_retry: bool = True) -> AIClient:
        """获取AI客户端实例（config_file参数已废弃）"""
        key = f"default:{enable_cache}:{enable_retry}"
        with self.lock:
            if key not in self.ai_clients:
                self.ai_clients[key] = AIClient(enable_cache, enable_retry)
            return self.ai_clients[key]
    
    def clear_all(self):
        """清除所有缓存的实例"""
        with self.lock:
            self.config_managers.clear()
            self.ai_clients.clear()
            self.adapters.clear()


@dataclass
class SearchCriteria:
    """搜索条件数据类"""
    query: str  # PubMed检索词
    year_start: Optional[int] = None  # 起始年份
    year_end: Optional[int] = None  # 结束年份
    min_if: Optional[float] = None  # 最小影响因子
    max_if: Optional[float] = None  # 最大影响因子
    cas_zones: List[int] = None  # 中科院分区限制 [1,2,3,4]
    jcr_quartiles: List[str] = None  # JCR分区限制 ["Q1","Q2","Q3","Q4"]
    keywords: List[str] = None  # 关键词过滤
    
    def __post_init__(self):
        if self.cas_zones is None:
            self.cas_zones = []
        if self.jcr_quartiles is None:
            self.jcr_quartiles = []
        if self.keywords is None:
            self.keywords = []


class IntentAnalyzer:
    """用户意图分析器 v2.0 - 优化版"""
    
    CONFIG_CACHE_FILE = "ai_model_cache.json"
    
    def __init__(self, config_name: str = None, interactive: bool = True, 
                 enable_cache: bool = True, enable_async: bool = True, 
                 validate_cache: bool = True):
        """
        初始化意图分析器
        
        Args:
            config_name: AI配置名称，如果为None则使用第一个可用配置
            interactive: 是否交互式选择模型和参数
            enable_cache: 是否启用意图分析缓存
            enable_async: 是否启用异步处理能力
            validate_cache: 是否验证缓存模型的有效性
        """
        # 使用配置管理器池避免重复初始化
        self.config_pool = ConfigManagerPool()
        self.config_manager = self.config_pool.get_config_manager()
        self.ai_client = self.config_pool.get_ai_client()
        
        self.config_name = config_name
        self.interactive = interactive
        self.enable_cache = enable_cache
        self.enable_async = enable_async
        self.validate_cache = validate_cache  # 添加缓存验证控制参数
        self.model_id = None
        self.model_parameters = {
            "temperature": 0.1, 
            "stream": True,  # 启用流式输出
            "max_tokens": None  # 不限制token数量
        }
        
        # 初始化智能缓存
        self.analysis_cache = IntentAnalysisCache(cache_size=500, ttl=3600) if enable_cache else None
        
        # 初始化提示词管理器
        self.prompts_manager = PromptsManager()
        
        # 性能统计
        self.performance_stats = {
            'total_analyses': 0,
            'cache_hits': 0,
            'ai_calls': 0,
            'total_latency': 0.0,
            'errors': 0
        }
        
        # 线程池用于异步处理
        self.thread_pool = ThreadPoolExecutor(max_workers=4) if enable_async else None
        
        # 选择AI配置
        self.config = self._select_config()
        if self.config:
            self.adapter = self.ai_client.create_adapter(self.config)
            
            if self.interactive:
                # 交互式选择模型和参数（支持缓存）
                self._interactive_setup_with_cache()
            else:
                # 非交互模式：总是询问是否使用缓存模型
                self._non_interactive_setup_with_cache()
        else:
            raise RuntimeError("未找到可用的AI配置")
    
    def _non_interactive_setup_with_cache(self):
        """非交互模式下的缓存配置处理"""
        print("\n[AI] AI意图分析器设置")
        print("=" * 30)
        
        # 尝试加载缓存配置
        cached_config = self._load_cached_config()
        
        if cached_config:
            print(f"[OK] 发现上次配置:")
            print(f"   配置: {cached_config.config_name}")
            print(f"   模型: {cached_config.model_id}")
            print(f"   参数: temperature={cached_config.parameters.get('temperature', 0.1)}, max_tokens={cached_config.parameters.get('max_tokens', 'None')}")
            
            # 非交互模式下自动使用缓存配置
            self.model_id = cached_config.model_id
            self.model_parameters.update(cached_config.parameters)
            print(f"[OK] 自动使用缓存配置: {self.model_id}")
            print("保持当前参数配置")
            return
        
        # 如果没有缓存，获取新模型
        print("[FIND] 从端点获取可用模型...")
        self.model_id = self._get_default_model()
        if self.model_id:
            print(f"[OK] 获取到模型: {self.model_id}")
            print("使用默认参数")
            
            # 保存新配置到缓存
            new_config = AIModelConfig(
                config_name=self.config.name,
                model_id=self.model_id,
                parameters={**self.model_parameters, 'stream': True}  # 确保流式输出
            )
            self._save_config_cache(new_config)
        else:
            print("\n" + "="*60)
            print("[ERROR] AI节点连接失败")
            print("="*60)
            print("无法从远端获取AI模型列表，这通常表示：")
            print("1. AI服务配置可能有误（API密钥、端点URL等）")
            print("2. 网络连接问题或服务不可用")
            print("3. API配额已用完或权限不足")
            print("\n请检查您的AI配置文件 (.env) 并确保：")
            print("- API密钥正确且有效")
            print("- 端点URL正确") 
            print("- 网络连接正常")
            print("="*60)
            print("\n按任意键退出程序...")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass
            import sys
            sys.exit(1)
    
    def _load_cached_config(self) -> Optional[AIModelConfig]:
        """加载缓存的AI配置并验证有效性"""
        if os.path.exists(self.CONFIG_CACHE_FILE):
            try:
                with open(self.CONFIG_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('config_name') == self.config.name:
                        # 检查缓存时间（默认7天过期）
                        cached_at = data.get('cached_at', 0)
                        cache_age_days = (time.time() - cached_at) / (24 * 3600)
                        
                        if cache_age_days > 7:
                            print(f"[INFO] 缓存已过期 ({cache_age_days:.1f}天)，将重新获取模型")
                            os.remove(self.CONFIG_CACHE_FILE)
                            return None
                        
                        # 创建AIModelConfig对象时过滤掉时间戳字段
                        config_data = {k: v for k, v in data.items() if k != 'cached_at'}
                        cached_config = AIModelConfig.from_dict(config_data)
                        
                        # 根据配置决定是否验证缓存模型的有效性
                        if self.validate_cache:
                            if self._validate_cached_model(cached_config):
                                print(f"[OK] 缓存模型验证通过 (缓存时间: {cache_age_days:.1f}天)")
                                return cached_config
                            else:
                                print(f"[WARN] 缓存模型 {cached_config.model_id} 已失效，将重新获取")
                                # 删除无效的缓存文件
                                os.remove(self.CONFIG_CACHE_FILE)
                                return None
                        else:
                            print(f"[INFO] 跳过缓存验证，直接使用缓存模型 {cached_config.model_id} (缓存时间: {cache_age_days:.1f}天)")
                            return cached_config
            except Exception as e:
                print(f"加载配置缓存失败: {e}")
                # 删除损坏的缓存文件
                try:
                    os.remove(self.CONFIG_CACHE_FILE)
                except (OSError, PermissionError):
                    pass
        return None
    
    def _validate_cached_model(self, cached_config: AIModelConfig) -> bool:
        """验证缓存模型是否仍然有效"""
        try:
            print(f"[VALIDATE] 验证缓存模型 {cached_config.model_id} 的有效性...")
            
            # 1. 首先检查模型是否还在可用模型列表中
            available_models = self.adapter.get_available_models()
            if not available_models:
                print("[VALIDATE] 无法获取模型列表，跳过缓存验证")
                return False
            
            # 检查模型ID是否在可用列表中
            cached_model_available = any(
                model.id == cached_config.model_id for model in available_models
            )
            
            if not cached_model_available:
                print(f"[VALIDATE] 模型 {cached_config.model_id} 不在可用模型列表中")
                return False

            # 2. 发送简单测试请求验证模型是否真正可用
            print(f"[VALIDATE] 测试模型 {cached_config.model_id} 的API连接...")
            test_messages = [ChatMessage(role="user", content="hi")]
            test_params = {
                "temperature": 0.1,
                "max_tokens": 5,
                "stream": False
            }

            response = self.adapter.send_message(
                test_messages,
                cached_config.model_id,
                test_params
            )

            if response and len(str(response).strip()) > 0:
                print(f"[VALIDATE] 模型 {cached_config.model_id} 验证成功")
                return True
            else:
                print(f"[VALIDATE] 模型 {cached_config.model_id} 响应无效")
                return False
                
        except Exception as e:
            print(f"[VALIDATE] 模型验证失败: {e}")
            return False
    
    def _save_config_cache(self, model_config: AIModelConfig):
        """保存AI配置到缓存"""
        try:
            # 确保stream参数始终为True
            model_config.parameters['stream'] = True
            
            # 添加缓存时间戳
            cache_data = model_config.to_dict()
            cache_data['cached_at'] = time.time()  # 添加缓存时间戳
            
            with open(self.CONFIG_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置缓存失败: {e}")
    
    def _interactive_setup_with_cache(self):
        """支持缓存的交互式设置模型和参数"""
        print("\n[AI] AI意图分析器设置")
        print("=" * 30)
        
        # 尝试加载缓存配置
        cached_config = self._load_cached_config()
        
        if cached_config:
            print(f"[OK] 发现上次配置:")
            print(f"   配置: {cached_config.config_name}")
            print(f"   模型: {cached_config.model_id}")
            print(f"   参数: temperature={cached_config.parameters.get('temperature', 0.1)}, "
                  f"max_tokens={cached_config.parameters.get('max_tokens', 'None')}")
            
            use_cached = input("\n是否使用上次的配置? (y/n) [y]: ").strip().lower()
            
            if use_cached in ['', 'y', 'yes']:
                self.model_id = cached_config.model_id
                self.model_parameters = cached_config.parameters
                print("[OK] 使用缓存配置")
                
                # 即使使用缓存配置，也询问是否要重新调节参数
                print(f"\n当前模型: {self.model_id}")
                config_params = input("是否重新配置模型参数? (y/n) [n]: ").strip().lower()
                
                if config_params in ['y', 'yes']:
                    # 重新配置参数
                    self.model_parameters = self.ai_client.configure_parameters(
                        self.adapter, self.model_id
                    )
                    # 保存新配置到缓存
                    new_config = AIModelConfig(
                        config_name=self.config.name,
                        model_id=self.model_id,
                        parameters={**self.model_parameters, 'stream': True}  # 确保流式输出
                    )
                    self._save_config_cache(new_config)
                    print("[SAVE] 新参数配置已保存")
                else:
                    print("保持当前参数配置")
                
                return
            else:
                print("[CONFIG]  重新配置...")
        
        # 进行新的配置
        self._perform_interactive_setup()
        
        # 保存新配置到缓存
        new_config = AIModelConfig(
            config_name=self.config.name,
            model_id=self.model_id,
            parameters={**self.model_parameters, 'stream': True}  # 确保流式输出
        )
        self._save_config_cache(new_config)
        print("[SAVE] 配置已保存，下次将自动使用")
    
    def _perform_interactive_setup(self):
        """执行交互式配置过程"""
        # 选择模型
        self.model_id = self._get_default_model()
        if not self.model_id:
            print("[WARN]  重试获取模型")
            self.model_id = self._get_default_model()
            if not self.model_id:
                print("\n" + "="*60)
                print("[ERROR] AI节点连接失败")
                print("="*60)
                print("无法从远端获取AI模型列表，这通常表示：")
                print("1. AI服务配置可能有误（API密钥、端点URL等）")
                print("2. 网络连接问题或服务不可用")
                print("3. API配额已用完或权限不足")
                print("\n请检查您的AI配置文件 (.env) 并确保：")
                print("- API密钥正确且有效")
                print("- 端点URL正确") 
                print("- 网络连接正常")
                print("="*60)
                print("\n按任意键退出程序...")
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    pass
                import sys
                sys.exit(1)
        
        # 询问是否配置参数
        print(f"\n当前模型: {self.model_id}")
        config_params = input("是否配置模型参数? (y/n) [n]: ").strip().lower()
        
        if config_params in ['y', 'yes']:
            # 配置参数
            self.model_parameters = self.ai_client.configure_parameters(
                self.adapter, self.model_id
            )
        else:
            print("使用默认参数")
        
        print("[OK] AI分析器设置完成\n")
    
    def clear_config_cache(self):
        """清除配置缓存"""
        try:
            if os.path.exists(self.CONFIG_CACHE_FILE):
                os.remove(self.CONFIG_CACHE_FILE)
                print("[OK] 配置缓存已清除")
            else:
                print("ℹ️  没有找到配置缓存文件")
        except Exception as e:
            print(f"[FAIL] 清除配置缓存失败: {e}")
    
    @classmethod
    def show_cached_config(cls):
        """显示当前缓存的配置"""
        if os.path.exists(cls.CONFIG_CACHE_FILE):
            try:
                with open(cls.CONFIG_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"\n[LIST] 当前缓存配置:")
                    print(f"   配置: {data.get('config_name', 'unknown')}")
                    print(f"   模型: {data.get('model_id', 'unknown')}")
                    params = data.get('parameters', {})
                    print(f"   参数: temperature={params.get('temperature', 'unknown')}, "
                          f"max_tokens={params.get('max_tokens', 'unknown')}")
            except Exception as e:
                print(f"[FAIL] 读取缓存配置失败: {e}")
        else:
            print("ℹ️  没有找到配置缓存文件")
    
    def _select_config(self):
        """选择AI配置"""
        configs = self.config_manager.list_configs()
        
        if not configs:
            return None
        
        if self.config_name:
            return self.config_manager.get_config(self.config_name)
        else:
            # 使用第一个可用配置
            return self.config_manager.get_config(configs[0])
    
    def _get_default_model(self):
        """从端点获取模型并让用户选择"""
        try:
            models = self.adapter.get_available_models()
            if not models:
                print("[FAIL] 端点未返回可用模型")
                return None
            
            # 查找优先模型的索引
            preferred_model = system_config.PREFERRED_MODEL.lower()
            preferred_index = None
            for i, model in enumerate(models):
                if preferred_model in model.id.lower():
                    preferred_index = i + 1  # 显示的序号是从1开始的
                    break
            
            print(f"\n{'='*50}")
            print(f"[FIND] 从端点获取到 {len(models)} 个可用模型:")
            print('='*50)
            for i, model in enumerate(models, 1):
                prefix = "🌟 " if preferred_index == i else "  "
                print(f"{prefix}{i}. {model.id}")
            print('='*50)
            
            # 设置默认选项提示
            default_choice = f"[{preferred_index}]" if preferred_index else "[1]"
            default_index = preferred_index - 1 if preferred_index else 0
            
            while True:
                try:
                    choice = input(f"\n请选择模型 (1-{len(models)}) {default_choice}: ").strip()
                    if not choice:
                        selected_index = default_index  # 默认选择
                    else:
                        selected_index = int(choice) - 1
                    
                    if 0 <= selected_index < len(models):
                        selected_model = models[selected_index]
                        print(f"[OK] 已选择模型: {selected_model.id}")
                        return selected_model.id
                    else:
                        print(f"请输入 1-{len(models)} 之间的数字")
                except (ValueError, EOFError):
                    # 如果是无输入环境或输入错误，使用默认选择
                    selected_model = models[default_index]
                    print(f"[OK] 自动选择默认模型: {selected_model.id}")
                    return selected_model.id
                    
        except Exception as e:
            print(f"\n[ERROR] 获取AI模型失败: {e}")
            print("这通常表示AI服务连接问题，请检查您的AI配置")
            return None
    
    def analyze_intent(self, user_input: str) -> SearchCriteria:
        """
        分析用户意图，生成搜索条件 - 优化版
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            SearchCriteria: 解析后的搜索条件
        """
        start_time = time.time()
        self.performance_stats['total_analyses'] += 1
        
        # 检查缓存
        if self.enable_cache and self.analysis_cache:
            cached_result = self.analysis_cache.get(user_input, self.model_id, self.model_parameters)
            if cached_result:
                self.performance_stats['cache_hits'] += 1
                return cached_result
        
        # 构建提示词
        prompt = self._build_analysis_prompt(user_input)
        
        # 构建消息
        messages = [ChatMessage(role="user", content=prompt)]
        
        # 调用AI分析
        try:
            response = self.adapter.send_message(
                messages, 
                self.model_id, 
                self.model_parameters
            )
            
            self.performance_stats['ai_calls'] += 1
            
            # 直接处理响应解析，不依赖format_response方法
            ai_response = self._extract_response_content(response)
            
            # 如果响应为空，使用基础策略
            if not ai_response or ai_response.strip() == "":
                print(f"解析AI响应失败: 服务器返回空响应")
                print(f"AI响应内容: (空)")
                return SearchCriteria(query=user_input)
            
            criteria = self._parse_ai_response_with_validation(ai_response, user_input)
            
            # 缓存结果
            if self.enable_cache and self.analysis_cache and not criteria.query == user_input:
                self.analysis_cache.put(user_input, self.model_id, self.model_parameters, criteria)
            
            # 更新性能统计
            latency = time.time() - start_time
            self.performance_stats['total_latency'] += latency
            
            return criteria
            
        except Exception as e:
            self.performance_stats['errors'] += 1
            print(f"AI分析失败: {e}")
            # 返回基础搜索条件
            return SearchCriteria(query=user_input)
    
    async def analyze_intent_async(self, user_input: str) -> SearchCriteria:
        """
        异步分析用户意图
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            SearchCriteria: 解析后的搜索条件
        """
        if not self.enable_async or not self.thread_pool:
            # 如果未启用异步，直接调用同步方法
            return self.analyze_intent(user_input)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, self.analyze_intent, user_input)
    
    def analyze_batch_intents(self, user_inputs: List[str]) -> List[SearchCriteria]:
        """
        批量分析用户意图
        
        Args:
            user_inputs: 用户输入文本列表
            
        Returns:
            List[SearchCriteria]: 解析后的搜索条件列表
        """
        if not self.enable_async or not self.thread_pool:
            # 同步批量处理
            return [self.analyze_intent(input_text) for input_text in user_inputs]
        
        # 异步批量处理
        futures = []
        for input_text in user_inputs:
            future = self.thread_pool.submit(self.analyze_intent, input_text)
            futures.append(future)
        
        results = []
        for future in futures:
            try:
                result = future.result(timeout=60)  # 60秒超时
                results.append(result)
            except Exception as e:
                print(f"批量分析失败: {e}")
                # 返回基础搜索条件
                results.append(SearchCriteria(query=input_text))
        
        return results
    
    def _build_analysis_prompt(self, user_input: str) -> str:
        """构建分析提示词"""
        # 尝试从配置文件加载提示词
        try:
            prompt_template = self.prompts_manager.get_intent_analysis_prompt(user_input)
            if prompt_template and len(prompt_template.strip()) > 100:  # 确保不是空的或太短的模板
                return prompt_template
        except Exception as e:
            print(f"[WARN]  使用配置文件提示词失败，使用默认提示词: {e}")
        
        # 回退到默认提示词
        return self._build_default_analysis_prompt(user_input)
    
    def _build_default_analysis_prompt(self, user_input: str) -> str:
        """构建默认分析提示词（兼容性保证）"""
        from datetime import datetime
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month
        
        prompt = f"""
你是一个医学文献检索专家，需要分析用户的检索需求并生成相应的PubMed检索词和筛选条件。

当前日期: {current_date.strftime('%Y年%m月%d日')} (第{current_year}年)
用户输入: "{user_input}"

请分析用户的意图并以JSON格式输出结果，包含以下字段：

1. **query**: PubMed检索词（使用布尔操作符AND、OR、NOT，使用MeSH词汇）
2. **year_start**: 起始年份（整数，如果用户提到了年份限制）
3. **year_end**: 结束年份（整数，如果用户提到了年份限制）  
4. **min_if**: 最小影响因子（浮点数，如果用户提到影响因子要求）
5. **max_if**: 最大影响因子（浮点数，如果用户提到影响因子要求）
6. **cas_zones**: 中科院分区限制（整数列表，1-4分区，如[1,2]表示1区和2区）
7. **jcr_quartiles**: JCR分区限制（字符串列表，如["Q1","Q2"]）
8. **keywords**: 关键词过滤列表（从用户输入中提取的重要关键词）

分析规则：
- 识别疾病名称、治疗方法、药物名称等医学概念
- 将中文医学术语转换为英文和MeSH术语
- 自动补充相关的同义词和相关术语
- **重要：基于当前日期({current_year}年{current_month}月)精确计算年份限制**
  - "近1年"：{current_year-1}-{current_year}年
  - "近年来"或"最近"：{current_year-2}-{current_year}年
  - "近3年"：{current_year-2}-{current_year}年
  - "近5年"：{current_year-4}-{current_year}年
  - "近10年"：{current_year-9}-{current_year}年
  - "最近几年"：{current_year-3}-{current_year}年
  - "过去5年"：{current_year-4}-{current_year}年
  - "2020年以来"：2020-{current_year}年
  - "疫情期间"或"COVID期间"：2020-{current_year}年
- 影响因子：高影响因子=5.0以上，顶级期刊=10.0以上
- **重要分区规则：**
  - 仅当用户明确提到"中科院分区"或"CAS分区"时，才输出cas_zones
  - 仅当用户明确提到"JCR分区"或"JCR quartile"时，才输出jcr_quartiles
  - 用户仅说"高影响因子"或"顶级期刊"时，只输出min_if，不要自动添加分区限制
  - 用户明确说"中科院1区"时，只输出cas_zones: [1]，不要添加jcr_quartiles
  - 用户明确说"JCR Q1"时，只输出jcr_quartiles: ["Q1"]，不要添加cas_zones

示例1 - 仅影响因子要求：
用户输入："糖尿病治疗的最新研究，要求是近5年的高影响因子期刊文献"
基于当前日期({current_year}年)，"近5年"应解析为{current_year-4}-{current_year}年
输出：
```json
{{
  "query": "(diabetes mellitus[MeSH Terms] OR diabetes[Title/Abstract]) AND (treatment[MeSH Terms] OR therapy[Title/Abstract] OR therapeutic[Title/Abstract])",
  "year_start": {current_year-4},
  "year_end": {current_year},
  "min_if": 5.0,
  "keywords": ["diabetes", "treatment", "therapy", "diabetes mellitus"]
}}
```

示例2 - 仅中科院分区要求：
用户输入："高血压治疗，中科院1区和2区期刊"
输出：
```json
{{
  "query": "(hypertension[MeSH Terms] OR high blood pressure[Title/Abstract]) AND (treatment[MeSH Terms] OR therapy[Title/Abstract])",
  "cas_zones": [1, 2],
  "keywords": ["hypertension", "treatment", "high blood pressure"]
}}
```

示例3 - 仅JCR分区要求：
用户输入："癌症免疫治疗研究，要求JCR Q1期刊"
输出：
```json
{{
  "query": "(cancer[MeSH Terms] OR neoplasms[MeSH Terms]) AND (immunotherapy[MeSH Terms] OR immune therapy[Title/Abstract])",
  "jcr_quartiles": ["Q1"],
  "keywords": ["cancer", "immunotherapy", "immune therapy"]
}}
```

请对上述用户输入进行分析并输出JSON格式结果，确保年份计算准确：
"""
        return prompt
    
    def _extract_response_content(self, response: Dict[str, Any]) -> str:
        """直接从响应中提取内容，不依赖外部format_response"""
        if 'error' in response:
            return f"错误: {response['error']}"
        
        try:
            if self.adapter.config.api_type.lower() == 'openai':
                choices = response.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content', '')
                    if isinstance(content, list):
                        content = ' '.join(str(item) for item in content)
                    elif not isinstance(content, str):
                        content = str(content)
                    return content.strip()
            
            elif self.adapter.config.api_type.lower() == 'gemini':
                candidates = response.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        text = parts[0].get('text', '')
                        if isinstance(text, list):
                            text = ' '.join(str(item) for item in text)
                        elif not isinstance(text, str):
                            text = str(text)
                        return text.strip()
            
        except (KeyError, IndexError, TypeError) as e:
            print(f"响应内容提取失败: {e}")
            return ""
        
        # 如果无法解析，返回空字符串
        return ""

    def _parse_ai_response_with_validation(self, ai_response: str, original_input: str) -> SearchCriteria:
        """解析AI响应 - 增强验证和错误恢复"""
        try:
            # 提取JSON部分 - 优化正则表达式
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = ai_response.strip()
            
            # 清理JSON字符串
            json_str = self._clean_json_string(json_str)
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 验证数据完整性
            validated_data = self._validate_search_criteria(data, original_input)
            
            return SearchCriteria(
                query=validated_data.get('query', original_input),
                year_start=validated_data.get('year_start'),
                year_end=validated_data.get('year_end'),
                min_if=validated_data.get('min_if'),
                max_if=validated_data.get('max_if'),
                cas_zones=validated_data.get('cas_zones', []),
                jcr_quartiles=validated_data.get('jcr_quartiles', []),
                keywords=validated_data.get('keywords', [])
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"解析AI响应失败: {e}")
            print(f"AI响应内容: {ai_response[:500]}...")
            
            # 尝试使用更宽松的解析策略
            return self._fallback_parse_response(ai_response, original_input)
    
    def _clean_json_string(self, json_str: str) -> str:
        """清理JSON字符串"""
        # 移除注释
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 修复常见的JSON格式问题
        json_str = json_str.replace("'", '"')  # 单引号转双引号
        json_str = re.sub(r',\s*}', '}', json_str)  # 移除尾随逗号
        json_str = re.sub(r',\s*]', ']', json_str)  # 移除数组尾随逗号
        
        return json_str.strip()
    
    def _validate_search_criteria(self, data: Dict, original_input: str) -> Dict:
        """验证和修复搜索条件数据"""
        validated = {}
        
        # 验证query字段
        query = data.get('query', '').strip()
        if not query or len(query) < 3:
            # 如果query为空或太短，使用原始输入
            validated['query'] = original_input
        else:
            validated['query'] = query
        
        # 验证年份范围
        year_start = data.get('year_start')
        year_end = data.get('year_end')
        current_year = datetime.now().year
        
        # 确保年份是整数类型
        if year_start is not None:
            try:
                year_start = int(year_start)
            except (ValueError, TypeError):
                year_start = None
        
        if year_end is not None:
            try:
                year_end = int(year_end)
            except (ValueError, TypeError):
                year_end = None
        
        # 验证年份逻辑
        if year_start and year_end:
            if year_start > year_end:
                # 交换起始和结束年份
                year_start, year_end = year_end, year_start
            if year_end > current_year + 1:
                year_end = current_year
        
        validated['year_start'] = year_start
        validated['year_end'] = year_end
        
        # 验证影响因子
        min_if = data.get('min_if')
        max_if = data.get('max_if')

        # 类型转换：确保 min_if 和 max_if 是数值类型
        if min_if is not None:
            try:
                min_if = float(min_if)
                # 单独校验 min_if 范围
                if min_if < 0:
                    min_if = 0
                if min_if > 100:
                    min_if = 100
            except (ValueError, TypeError):
                min_if = None

        if max_if is not None:
            try:
                max_if = float(max_if)
                # 单独校验 max_if 范围
                if max_if < 0:
                    max_if = 0
                if max_if > 100:
                    max_if = 100
            except (ValueError, TypeError):
                max_if = None

        # 当两者都存在时，确保 min <= max
        if min_if is not None and max_if is not None:
            if min_if > max_if:
                min_if, max_if = max_if, min_if
        
        validated['min_if'] = min_if
        validated['max_if'] = max_if
        
        # 验证分区信息
        cas_zones = data.get('cas_zones', [])
        if isinstance(cas_zones, list):
            # 确保转换为整数并验证范围
            validated_cas_zones = []
            for zone in cas_zones:
                try:
                    zone_int = int(zone)
                    if 1 <= zone_int <= 4:
                        validated_cas_zones.append(zone_int)
                except (ValueError, TypeError):
                    continue
            validated['cas_zones'] = validated_cas_zones
        else:
            validated['cas_zones'] = []
        
        jcr_quartiles = data.get('jcr_quartiles', [])
        if isinstance(jcr_quartiles, list):
            valid_quartiles = ['Q1', 'Q2', 'Q3', 'Q4']
            validated['jcr_quartiles'] = [q for q in jcr_quartiles if q in valid_quartiles]
        else:
            validated['jcr_quartiles'] = []
        
        # 验证关键词
        keywords = data.get('keywords', [])
        if isinstance(keywords, list):
            validated['keywords'] = [kw.strip() for kw in keywords if kw.strip()]
        else:
            validated['keywords'] = []
        
        return validated
    
    def _fallback_parse_response(self, ai_response: str, original_input: str) -> SearchCriteria:
        """回退解析策略"""
        # 尝试提取query字段
        query_match = re.search(r'"query"\s*:\s*"([^"]+)"', ai_response)
        if query_match:
            query = query_match.group(1)
        else:
            # 尝试从文本中提取查询词
            query = self._extract_basic_query(ai_response)
        
        # 尝试提取年份信息
        year_start = None
        year_end = None
        year_matches = re.findall(r'(20\d{2})', ai_response)
        if year_matches:
            years = sorted(set(int(y) for y in year_matches))
            if len(years) >= 2:
                year_start = min(years)
                year_end = max(years)
        
        return SearchCriteria(
            query=query or original_input,
            year_start=year_start,
            year_end=year_end
        )
    
    def _extract_basic_query(self, response: str) -> str:
        """从响应中提取基础查询词"""
        # 简单的关键词提取逻辑
        lines = response.split('\n')
        for line in lines:
            if 'query' in line.lower() and ':' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    return parts[1].strip().strip('"')
        
        return response[:100]  # 返回前100字符作为查询词
    
    def build_pubmed_query(self, criteria: SearchCriteria) -> str:
        """构建完整的PubMed查询字符串"""
        query_parts = [criteria.query]
        
        # 添加年份限制
        if criteria.year_start or criteria.year_end:
            year_filter = ""
            if criteria.year_start and criteria.year_end:
                year_filter = f"(\"{criteria.year_start}\"[Date - Publication] : \"{criteria.year_end}\"[Date - Publication])"
            elif criteria.year_start:
                year_filter = f"\"{criteria.year_start}\"[Date - Publication] : 3000[Date - Publication]"
            elif criteria.year_end:
                year_filter = f"1800[Date - Publication] : \"{criteria.year_end}\"[Date - Publication]"
            
            if year_filter:
                query_parts.append(year_filter)
        
        # 组合所有查询部分
        final_query = " AND ".join(f"({part})" for part in query_parts if part.strip())
        
        return final_query
    
    def print_analysis_result(self, criteria: SearchCriteria):
        """打印分析结果"""
        print("\n=== 意图分析结果 ===")
        print(f"PubMed检索词: {criteria.query}")
        
        if criteria.year_start or criteria.year_end:
            year_range = f"{criteria.year_start or '不限'} - {criteria.year_end or '不限'}"
            print(f"年份限制: {year_range}")
        
        if criteria.min_if or criteria.max_if:
            if_range = f"{criteria.min_if or '不限'} - {criteria.max_if or '不限'}"
            print(f"影响因子范围: {if_range}")
        
        # 分别显示分区信息，避免混淆
        if criteria.cas_zones:
            print(f"中科院分区限制: {', '.join(map(str, criteria.cas_zones))}区")
        
        if criteria.jcr_quartiles:
            print(f"JCR分区限制: {', '.join(criteria.jcr_quartiles)}")
        
        if criteria.keywords:
            print(f"关键词: {', '.join(criteria.keywords)}")
        
        print(f"完整检索词: {self.build_pubmed_query(criteria)}")
        print("=" * 40)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        total_analyses = self.performance_stats['total_analyses']
        
        report = {
            'performance_stats': self.performance_stats.copy(),
            'cache_enabled': self.enable_cache,
            'async_enabled': self.enable_async,
            'cache_stats': self.analysis_cache.get_stats() if self.analysis_cache else {},
            'analysis_rate': 0,
            'cache_hit_rate': 0,
            'error_rate': 0,
            'average_latency': 0
        }
        
        if total_analyses > 0:
            report['cache_hit_rate'] = (self.performance_stats['cache_hits'] / total_analyses) * 100
            report['error_rate'] = (self.performance_stats['errors'] / total_analyses) * 100
            report['average_latency'] = self.performance_stats['total_latency'] / total_analyses
        
        return report
    
    def print_performance_report(self):
        """打印性能报告"""
        report = self.get_performance_report()
        stats = report['performance_stats']
        
        print("\n=== 意图分析器性能报告 ===")
        print(f"总分析次数: {stats['total_analyses']}")
        print(f"缓存命中: {stats['cache_hits']}")
        print(f"AI调用次数: {stats['ai_calls']}")
        print(f"错误次数: {stats['errors']}")
        print(f"缓存命中率: {report['cache_hit_rate']:.1f}%")
        print(f"错误率: {report['error_rate']:.1f}%")
        print(f"平均延迟: {report['average_latency']:.2f}秒")
        
        if report['cache_stats']:
            cache_stats = report['cache_stats']
            print(f"缓存大小: {cache_stats['cache_size']}/{cache_stats['max_cache_size']}")
            print(f"缓存命中率: {cache_stats['hit_rate']*100:.1f}%")
        
        print("=" * 40)
    
    def clear_cache(self):
        """清除所有缓存"""
        if self.analysis_cache:
            self.analysis_cache.clear()
        
        # 清除配置缓存
        try:
            if os.path.exists(self.CONFIG_CACHE_FILE):
                os.remove(self.CONFIG_CACHE_FILE)
        except Exception as e:
            print(f"清除配置缓存失败: {e}")
        
        print("所有缓存已清除")
    
    def optimize_for_batch(self, expected_batch_size: int):
        """为批量处理优化缓存大小"""
        if self.analysis_cache:
            # 根据批量大小动态调整缓存
            new_cache_size = max(500, expected_batch_size * 2)
            self.analysis_cache.cache_size = new_cache_size
            print(f"缓存大小已调整为: {new_cache_size}")
    
    def __del__(self):
        """析构函数，清理资源"""
        if hasattr(self, 'thread_pool') and self.thread_pool:
            self.thread_pool.shutdown(wait=False)


def test_intent_analyzer():
    """测试意图分析器 - 优化版"""
    try:
        print("初始化意图分析器...")
        analyzer = IntentAnalyzer(interactive=False, enable_cache=True, enable_async=True)
        
        # 测试用例
        test_inputs = [
            "糖尿病治疗的最新研究，要求是近5年的高影响因子期刊文献",
            "新冠肺炎COVID-19疫苗效果研究，2020-2023年，中科院1区期刊",
            "机器学习在医学影像诊断中的应用，影响因子大于3，JCR Q1-Q2期刊",
            "阿尔茨海默病新药物治疗进展"
        ]
        
        print("\n=== 测试同步分析 ===")
        for i, user_input in enumerate(test_inputs, 1):
            print(f"\n测试用例 {i}: {user_input}")
            criteria = analyzer.analyze_intent(user_input)
            analyzer.print_analysis_result(criteria)
        
        # 测试缓存效果
        print("\n=== 测试缓存效果 ===")
        start_time = time.time()
        for i, user_input in enumerate(test_inputs, 1):
            print(f"\n缓存测试 {i}: {user_input}")
            criteria = analyzer.analyze_intent(user_input)  # 应该命中缓存
        cache_time = time.time() - start_time
        print(f"缓存分析总耗时: {cache_time:.2f}秒")
        
        # 测试批量处理
        print("\n=== 测试批量处理 ===")
        analyzer.optimize_for_batch(len(test_inputs))
        start_time = time.time()
        batch_results = analyzer.analyze_batch_intents(test_inputs)
        batch_time = time.time() - start_time
        print(f"批量分析总耗时: {batch_time:.2f}秒")
        print(f"平均每个分析: {batch_time/len(test_inputs):.2f}秒")
        
        # 显示性能报告
        analyzer.print_performance_report()
        
        # 测试异步处理（如果支持）
        if analyzer.enable_async:
            print("\n=== 测试异步处理 ===")
            import asyncio
            
            async def test_async():
                start_time = time.time()
                tasks = [analyzer.analyze_intent_async(input_text) for input_text in test_inputs]
                results = await asyncio.gather(*tasks)
                async_time = time.time() - start_time
                print(f"异步分析总耗时: {async_time:.2f}秒")
                return results
            
            asyncio.run(test_async())
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_intent_analyzer()