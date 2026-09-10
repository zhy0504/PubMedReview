"""Shared workflow state and cache services for CLI and local workbench."""

import json
import os
import tempfile
import threading
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def content_key(namespace, *values):
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)
    return namespace + "_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class StateManager:
    """状态管理器 - 支持断点续传"""
    def __init__(self, state_file: str = "system_state.json"):
        self.state_file = Path(state_file)
        self.current_state = {}
        self.lock = threading.Lock()
    
    def save_state(self, state_data: Dict):
        """保存当前状态"""
        with self.lock:
            self.current_state.update(state_data)
            self.current_state['timestamp'] = datetime.now().isoformat()
            
            try:
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(dir=self.state_file.parent, suffix='.tmp')
                try:
                    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                        json.dump(self.current_state, stream, ensure_ascii=False, indent=2)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, self.state_file)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            except Exception as e:
                print(f"状态保存失败: {e}")
    
    def load_state(self) -> Dict:
        """加载之前的状态"""
        with self.lock:
            if self.state_file.exists():
                try:
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        self.current_state = json.load(f)
                except Exception as e:
                    print(f"状态加载失败: {e}")
                    self.current_state = {}
            return self.current_state.copy()
    
    def can_resume(self) -> bool:
        """检查是否可以恢复"""
        state = self.load_state()
        return len(state) > 0 and state.get('processing', False)
    
    def clear_state(self):
        """清除状态"""
        with self.lock:
            self.current_state = {}
            if self.state_file.exists():
                self.state_file.unlink()


class IntelligentCache:
    """智能缓存系统"""
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.search_cache = {}
        self.ai_response_cache = {}
        self.cache_ttl = 3600  # 1小时缓存
    
    def get_cached_search(self, query: str, max_results: int) -> Optional[Dict]:
        """获取缓存的搜索结果"""
        cache_key = f"{query}_{max_results}"
        if cache_key in self.search_cache:
            cache_data = self.search_cache[cache_key]
            # 检查缓存是否过期
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if (datetime.now() - cache_time).total_seconds() < self.cache_ttl:
                return cache_data
            else:
                del self.search_cache[cache_key]
        return None
    
    def cache_search_result(self, query: str, max_results: int, results: List):
        """缓存搜索结果"""
        cache_key = f"{query}_{max_results}"
        self.search_cache[cache_key] = {
            'results': results,
            'timestamp': datetime.now().isoformat(),
            'count': len(results)
        }
    
    def get_cached_ai_response(self, prompt_hash: str) -> Optional[str]:
        """获取缓存的AI响应"""
        cached_data = self.ai_response_cache.get(prompt_hash)
        
        if cached_data and isinstance(cached_data, dict):
            timestamp = cached_data.get('timestamp')
            if timestamp and (datetime.now() - datetime.fromisoformat(timestamp)).total_seconds() >= self.cache_ttl:
                self.ai_response_cache.pop(prompt_hash, None)
                return None
            response = cached_data.get('response')
            return response
        elif cached_data is not None:
            return cached_data
        
        return None
    
    def cache_ai_response(self, prompt_hash: str, response: str):
        """缓存AI响应"""
        self.ai_response_cache[prompt_hash] = {
            'response': response,
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_cache(self):
        """清除缓存"""
        self.search_cache.clear()
        self.ai_response_cache.clear()
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink()

