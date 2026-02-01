#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文献筛选程序
根据筛选条件过滤PubMed检索结果，匹配期刊数据
"""

import pandas as pd
import json
import gzip  # 替换pickle为更安全的json+gzip
import os
from typing import List, Dict, Optional, Tuple
from intent_analyzer import SearchCriteria
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import hashlib
from datetime import datetime, timedelta


# 常量定义 - 避免魔法数字
CACHE_EXPIRY_DAYS = 90  # 缓存过期天数
MAX_YEAR_OFFSET = 5  # 年份验证的未来偏移量


class FilterConfig:
    """筛选器配置类"""
    def __init__(self):
        self.max_workers = 4  # 最大工作线程数
        self.cache_size = 1000  # 缓存大小
        self.cache_ttl = 3600  # 缓存有效期（秒）
        self.batch_size = 200  # 批处理大小
        self.enable_parallel = True  # 启用并行处理
        self.enable_caching = True  # 启用缓存
        self.memory_limit_mb = 500  # 内存限制（MB）


class JournalInfoCache:
    """期刊信息缓存管理器"""
    def __init__(self, config: FilterConfig):
        self.config = config
        self.cache = {}
        self.access_times = {}
        self.lock = threading.Lock()
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}
    
    def _generate_key(self, issn: str, eissn: str) -> str:
        """生成缓存键"""
        content = f"{issn}:{eissn}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get(self, issn: str, eissn: str) -> Optional[Dict]:
        """获取期刊信息"""
        if not self.config.enable_caching:
            return None
            
        key = self._generate_key(issn, eissn)
        
        with self.lock:
            if key in self.cache:
                # 检查是否过期
                if time.time() - self.access_times[key] < self.config.cache_ttl:
                    self.access_times[key] = time.time()
                    self.stats['hits'] += 1
                    return self.cache[key]
                else:
                    # 过期删除
                    del self.cache[key]
                    del self.access_times[key]
                    self.stats['evictions'] += 1
            
            self.stats['misses'] += 1
            return None
    
    def put(self, issn: str, eissn: str, info: Dict):
        """存储期刊信息"""
        # 缓存禁用检查：enable_caching=False 或 cache_size<=0
        if not self.config.enable_caching or self.config.cache_size <= 0:
            return

        key = self._generate_key(issn, eissn)

        with self.lock:
            # 检查缓存大小
            if len(self.cache) >= self.config.cache_size and self.access_times:
                # LRU淘汰
                oldest_key = min(self.access_times.keys(), key=self.access_times.get)
                del self.cache[oldest_key]
                del self.access_times[oldest_key]
                self.stats['evictions'] += 1

            self.cache[key] = info
            self.access_times[key] = time.time()
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'cache_size': len(self.cache),
            'max_cache_size': self.config.cache_size,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'evictions': self.stats['evictions'],
            'hit_rate': hit_rate
        }


class LiteratureFilter:
    """文献筛选器"""
    
    def __init__(self, zky_data_path: str = "data/processed_zky_data.csv", 
                 jcr_data_path: str = "data/processed_jcr_data.csv",
                 config: FilterConfig = None):
        """
        初始化文献筛选器
        
        Args:
            zky_data_path: 中科院数据文件路径
            jcr_data_path: JCR数据文件路径
            config: 筛选器配置
        """
        self.zky_data_path = zky_data_path
        self.jcr_data_path = jcr_data_path
        self.config = config or FilterConfig()
        
        # 初始化缓存
        self.journal_cache = JournalInfoCache(self.config)
        
        # 性能统计
        self.performance_stats = {
            'total_articles_processed': 0,
            'total_filter_time': 0,
            'cache_hits': 0,
            'parallel_batches': 0,
            'memory_usage_mb': 0,
            'errors': 0
        }
        
        # 加载期刊数据
        self.zky_data = self._load_zky_data_optimized()
        self.jcr_data = self._load_jcr_data_optimized()
        
        # 创建ISSN到期刊信息的映射（支持缓存）
        self.issn_to_journal_info = self._load_or_build_journal_mapping()
        
        print(f"已加载中科院数据: {len(self.zky_data)} 条记录")
        print(f"已加载JCR数据: {len(self.jcr_data)} 条记录")
        print(f"期刊映射表: {len(self.issn_to_journal_info)} 条记录")
        print(f"并行处理: {'启用' if self.config.enable_parallel else '禁用'}")
        print(f"缓存系统: {'启用' if self.config.enable_caching else '禁用'}")
    
    def _load_zky_data_optimized(self) -> pd.DataFrame:
        """优化的中科院数据加载方法"""
        try:
            if not os.path.exists(self.zky_data_path):
                print(f"中科院数据文件不存在: {self.zky_data_path}")
                return pd.DataFrame()
            
            # 使用分块读取减少内存使用
            chunks = []
            for chunk in pd.read_csv(self.zky_data_path, encoding='utf-8', chunksize=1000):
                # 数据清洗和优化
                chunk = self._clean_journal_data(chunk)
                chunks.append(chunk)
                
                # 内存检查
                if self._check_memory_limit():
                    print("内存使用接近限制，停止加载数据")
                    break
            
            if chunks:
                df = pd.concat(chunks, ignore_index=True)
                print(f"成功加载中科院数据: {len(df)} 条记录")
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            print(f"加载中科院数据失败: {e}")
            self.performance_stats['errors'] += 1
            return pd.DataFrame()
    
    def _load_zky_data(self) -> pd.DataFrame:
        """兼容性方法 - 已废弃，请使用 _load_zky_data_optimized"""
        import warnings
        warnings.warn("_load_zky_data 已废弃，请使用 _load_zky_data_optimized", DeprecationWarning, stacklevel=2)
        return self._load_zky_data_optimized()
    
    def _load_jcr_data_optimized(self) -> pd.DataFrame:
        """优化的JCR数据加载方法"""
        try:
            if not os.path.exists(self.jcr_data_path):
                print(f"JCR数据文件不存在: {self.jcr_data_path}")
                return pd.DataFrame()
            
            # 使用分块读取减少内存使用
            chunks = []
            for chunk in pd.read_csv(self.jcr_data_path, encoding='utf-8', chunksize=1000):
                # 数据清洗和优化
                chunk = self._clean_journal_data(chunk)
                chunks.append(chunk)
                
                # 内存检查
                if self._check_memory_limit():
                    print("内存使用接近限制，停止加载数据")
                    break
            
            if chunks:
                df = pd.concat(chunks, ignore_index=True)
                print(f"成功加载JCR数据: {len(df)} 条记录")
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            print(f"加载JCR数据失败: {e}")
            self.performance_stats['errors'] += 1
            return pd.DataFrame()
    
    def _load_jcr_data(self) -> pd.DataFrame:
        """兼容性方法 - 已废弃，请使用 _load_jcr_data_optimized"""
        import warnings
        warnings.warn("_load_jcr_data 已废弃，请使用 _load_jcr_data_optimized", DeprecationWarning, stacklevel=2)
        return self._load_jcr_data_optimized()
    
    def _clean_journal_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗期刊数据"""
        try:
            # 标准化ISSN格式
            if 'ISSN' in df.columns:
                df['ISSN'] = df['ISSN'].astype(str).str.strip()
                df['ISSN'] = df['ISSN'].replace('nan', '')
            
            if 'EISSN' in df.columns:
                df['EISSN'] = df['EISSN'].astype(str).str.strip()
                df['EISSN'] = df['EISSN'].replace('nan', '')
            
            # 处理数值字段
            numeric_columns = ['影响因子', '中科院分区']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        except Exception as e:
            print(f"数据清洗失败: {e}")
            return df
    
    def _check_memory_limit(self) -> bool:
        """检查内存使用是否接近限制"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.performance_stats['memory_usage_mb'] = memory_mb
            return memory_mb > self.config.memory_limit_mb * 0.8
        except ImportError:
            return False
        except Exception:
            return False
    
    def _build_journal_mapping_optimized(self) -> Dict[str, Dict]:
        """优化的ISSN到期刊信息映射构建方法"""
        start_time = time.time()
        mapping = {}
        
        print("[INFO] 开始构建期刊映射表...")
        
        # 并行处理中科院数据
        if not self.zky_data.empty:
            print(f"[INFO] 处理中科院数据 ({len(self.zky_data)} 条记录)...")
            zky_mapping = self._process_dataframe_parallel(self.zky_data, 'zky')
            mapping.update(zky_mapping)
            print(f"[INFO] 中科院数据处理完成，生成 {len(zky_mapping)} 个映射条目")
        
        # 并行处理JCR数据
        if not self.jcr_data.empty:
            print(f"[INFO] 处理JCR数据 ({len(self.jcr_data)} 条记录)...")
            jcr_mapping = self._process_dataframe_parallel(self.jcr_data, 'jcr')
            # 合并信息，不覆盖已有数据
            print(f"[INFO] 合并JCR数据到映射表...")
            for issn, info in jcr_mapping.items():
                if issn in mapping:
                    mapping[issn].update({k: v for k, v in info.items() if v is not None})
                else:
                    mapping[issn] = info
            print(f"[INFO] JCR数据处理完成，生成 {len(jcr_mapping)} 个映射条目")
        
        build_time = time.time() - start_time
        print(f"[OK] 期刊映射构建完成，总计 {len(mapping)} 个映射条目，耗时: {build_time:.2f}秒")
        
        return mapping
    
    def _process_dataframe_parallel(self, df: pd.DataFrame, data_type: str) -> Dict[str, Dict]:
        """并行处理DataFrame构建映射"""
        mapping = {}
        
        if self.config.enable_parallel and len(df) > 1000:
            # 分块并行处理
            chunk_size = min(1000, len(df) // self.config.max_workers)
            chunks = [df[i:i + chunk_size] for i in range(0, len(df), chunk_size)]
            
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = []
                for chunk in chunks:
                    future = executor.submit(self._process_chunk, chunk, data_type)
                    futures.append(future)
                
                for future in as_completed(futures):
                    try:
                        chunk_mapping = future.result()
                        mapping.update(chunk_mapping)
                    except Exception as e:
                        print(f"处理数据块失败: {e}")
                        self.performance_stats['errors'] += 1
        else:
            # 串行处理
            mapping = self._process_chunk(df, data_type)
        
        return mapping
    
    def _process_chunk(self, df: pd.DataFrame, data_type: str) -> Dict[str, Dict]:
        """处理数据块 - 完全向量化版本"""
        mapping = {}
        
        if data_type == 'zky':
            # 处理中科院数据
            if 'ISSN' in df.columns:
                issns = df['ISSN'].astype(str).str.strip()
                cas_zones = df['中科院分区'] if '中科院分区' in df.columns else None
                
                # 过滤有效的ISSN
                valid_mask = (issns != '') & (issns != 'nan') & issns.notna()
                valid_issns = issns[valid_mask]
                
                if cas_zones is not None:
                    valid_cas_zones = cas_zones[valid_mask]
                    for issn, cas_zone in zip(valid_issns, valid_cas_zones):
                        mapping[issn] = {
                            'cas_zone': cas_zone if pd.notna(cas_zone) else None,
                            'impact_factor': None,
                            'jcr_quartile': None
                        }
                else:
                    for issn in valid_issns:
                        mapping[issn] = {
                            'cas_zone': None,
                            'impact_factor': None,
                            'jcr_quartile': None
                        }
            
            # 处理EISSN
            if 'EISSN' in df.columns:
                eissns = df['EISSN'].astype(str).str.strip()
                cas_zones = df['中科院分区'] if '中科院分区' in df.columns else None
                
                valid_mask = (eissns != '') & (eissns != 'nan') & eissns.notna()
                valid_eissns = eissns[valid_mask]
                
                if cas_zones is not None:
                    valid_cas_zones = cas_zones[valid_mask]
                    for eissn, cas_zone in zip(valid_eissns, valid_cas_zones):
                        mapping[eissn] = {
                            'cas_zone': cas_zone if pd.notna(cas_zone) else None,
                            'impact_factor': None,
                            'jcr_quartile': None
                        }
                else:
                    for eissn in valid_eissns:
                        mapping[eissn] = {
                            'cas_zone': None,
                            'impact_factor': None,
                            'jcr_quartile': None
                        }
                        
        else:  # jcr数据
            # 处理JCR数据
            if 'ISSN' in df.columns:
                issns = df['ISSN'].astype(str).str.strip()
                impact_factors = df['影响因子'] if '影响因子' in df.columns else None
                jcr_quartiles = df['JCR分区'] if 'JCR分区' in df.columns else None
                
                valid_mask = (issns != '') & (issns != 'nan') & issns.notna()
                valid_issns = issns[valid_mask]
                
                if impact_factors is not None and jcr_quartiles is not None:
                    valid_ifs = impact_factors[valid_mask]
                    valid_quartiles = jcr_quartiles[valid_mask]
                    for issn, impact_factor, jcr_quartile in zip(valid_issns, valid_ifs, valid_quartiles):
                        mapping[issn] = {
                            'cas_zone': None,
                            'impact_factor': impact_factor if pd.notna(impact_factor) else None,
                            'jcr_quartile': jcr_quartile if pd.notna(jcr_quartile) else None
                        }
                else:
                    for issn in valid_issns:
                        mapping[issn] = {
                            'cas_zone': None,
                            'impact_factor': None,
                            'jcr_quartile': None
                        }
            
            # 处理EISSN
            if 'EISSN' in df.columns:
                eissns = df['EISSN'].astype(str).str.strip()
                impact_factors = df['影响因子'] if '影响因子' in df.columns else None
                jcr_quartiles = df['JCR分区'] if 'JCR分区' in df.columns else None
                
                valid_mask = (eissns != '') & (eissns != 'nan') & eissns.notna()
                valid_eissns = eissns[valid_mask]
                
                if impact_factors is not None and jcr_quartiles is not None:
                    valid_ifs = impact_factors[valid_mask]
                    valid_quartiles = jcr_quartiles[valid_mask]
                    for eissn, impact_factor, jcr_quartile in zip(valid_eissns, valid_ifs, valid_quartiles):
                        mapping[eissn] = {
                            'cas_zone': None,
                            'impact_factor': impact_factor if pd.notna(impact_factor) else None,
                            'jcr_quartile': jcr_quartile if pd.notna(jcr_quartile) else None
                        }
                else:
                    for eissn in valid_eissns:
                        mapping[eissn] = {
                            'cas_zone': None,
                            'impact_factor': None,
                            'jcr_quartile': None
                        }
        
        return mapping
    
    def _build_journal_mapping(self) -> Dict[str, Dict]:
        """兼容性方法 - 已废弃，请使用 _build_journal_mapping_optimized"""
        import warnings
        warnings.warn("_build_journal_mapping 已废弃，请使用 _build_journal_mapping_optimized", DeprecationWarning, stacklevel=2)
        return self._build_journal_mapping_optimized()
    
    def _get_mapping_cache_path(self) -> str:
        """获取期刊映射表缓存文件路径"""
        return "cache/journal_mapping_cache.json.gz"  # 使用安全的json+gzip格式
    
    def _get_data_files_hash(self) -> str:
        """计算数据文件的哈希值，用于检测文件是否有更新"""
        hash_obj = hashlib.sha256()  # 使用更安全的SHA256算法

        # 计算中科院数据文件的哈希
        if os.path.exists(self.zky_data_path):
            with open(self.zky_data_path, 'rb') as f:
                hash_obj.update(f.read())

        # 计算JCR数据文件的哈希
        if os.path.exists(self.jcr_data_path):
            with open(self.jcr_data_path, 'rb') as f:
                hash_obj.update(f.read())

        return hash_obj.hexdigest()
    
    def _load_mapping_cache(self) -> Optional[Dict[str, Dict]]:
        """加载期刊映射表缓存（使用安全的json格式）"""
        cache_path = self._get_mapping_cache_path()

        if not os.path.exists(cache_path):
            return None

        try:
            # 使用gzip+json替代pickle，避免反序列化攻击
            with gzip.open(cache_path, 'rt', encoding='utf-8') as f:
                cache_data = json.load(f)

            # 检查缓存的数据版本
            current_hash = self._get_data_files_hash()
            cached_hash = cache_data.get('data_hash', '')
            cached_time = cache_data.get('cached_at', 0)

            # 检查缓存是否过期
            cache_age_days = (time.time() - cached_time) / (24 * 3600)

            if current_hash != cached_hash:
                print(f"[CACHE] 数据文件已更新，缓存失效")
                return None
            elif cache_age_days > CACHE_EXPIRY_DAYS:
                print(f"[CACHE] 缓存已过期 ({cache_age_days:.1f}天)，将重新构建")
                return None
            else:
                print(f"[CACHE] 使用期刊映射表缓存 (缓存时间: {cache_age_days:.1f}天)")
                return cache_data['mapping']

        except (json.JSONDecodeError, gzip.BadGzipFile) as e:
            print(f"[CACHE] 缓存文件损坏，将重新构建: {e}")
            return None
        except Exception as e:
            print(f"[CACHE] 加载缓存失败: {e}")
            return None
    
    def _save_mapping_cache(self, mapping: Dict[str, Dict]):
        """保存期刊映射表缓存（使用安全的json格式）"""
        cache_path = self._get_mapping_cache_path()

        # 确保缓存目录存在
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        try:
            cache_data = {
                'mapping': mapping,
                'data_hash': self._get_data_files_hash(),
                'cached_at': time.time(),
                'version': '2.0'  # 更新版本号表示格式变更
            }

            # 使用gzip+json替代pickle，避免反序列化攻击
            with gzip.open(cache_path, 'wt', encoding='utf-8') as f:
                json.dump(cache_data, f)

            print(f"[CACHE] 期刊映射表缓存已保存")

        except Exception as e:
            print(f"[CACHE] 保存缓存失败: {e}")
    
    def _load_or_build_journal_mapping(self) -> Dict[str, Dict]:
        """加载或构建期刊映射表（支持缓存）"""
        # 尝试加载缓存
        cached_mapping = self._load_mapping_cache()
        if cached_mapping is not None:
            return cached_mapping
        
        # 缓存不存在或失效，重新构建
        print("[INFO] 构建新的期刊映射表...")
        mapping = self._build_journal_mapping_optimized()
        
        # 保存到缓存
        self._save_mapping_cache(mapping)
        
        return mapping
    
    def clear_mapping_cache(self):
        """清理期刊映射表缓存"""
        cache_path = self._get_mapping_cache_path()
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                print("[CACHE] 期刊映射表缓存已清理")
            except Exception as e:
                print(f"[CACHE] 清理缓存失败: {e}")
        else:
            print("[CACHE] 缓存文件不存在")
    
    def get_journal_info_optimized(self, issn: str, eissn: str) -> Dict:
        """
        优化的期刊信息获取方法，支持缓存
        
        Args:
            issn: 期刊ISSN
            eissn: 期刊eISSN
            
        Returns:
            期刊信息字典
        """
        # 检查缓存
        cached_info = self.journal_cache.get(issn, eissn)
        if cached_info:
            self.performance_stats['cache_hits'] += 1
            return cached_info
        
        journal_info = {
            'cas_zone': None,
            'impact_factor': None,
            'jcr_quartile': None
        }
        
        # 优先使用ISSN查找
        if issn and issn.strip():
            clean_issn = issn.strip()
            if clean_issn in self.issn_to_journal_info:
                info = self.issn_to_journal_info[clean_issn]
                journal_info.update({k: v for k, v in info.items() if v is not None})
        
        # 如果ISSN没找到或信息不完整，尝试eISSN
        if eissn and eissn.strip():
            clean_eissn = eissn.strip()
            if clean_eissn in self.issn_to_journal_info:
                info = self.issn_to_journal_info[clean_eissn]
                # 只更新为None的字段
                for key, value in info.items():
                    if journal_info[key] is None and value is not None:
                        journal_info[key] = value
        
        # 缓存结果
        self.journal_cache.put(issn, eissn, journal_info)
        
        return journal_info
    
    def get_journal_info(self, issn: str, eissn: str) -> Dict:
        """兼容性方法 - 已废弃，请使用 get_journal_info_optimized"""
        import warnings
        warnings.warn("get_journal_info 已废弃，请使用 get_journal_info_optimized", DeprecationWarning, stacklevel=2)
        return self.get_journal_info_optimized(issn, eissn)
    
    def filter_articles_optimized(self, articles: List[Dict], criteria: SearchCriteria) -> List[Dict]:
        """
        优化的文献筛选方法，支持并行处理
        
        Args:
            articles: 文献列表
            criteria: 筛选条件
            
        Returns:
            过滤后的文献列表
        """
        start_time = time.time()
        
        print(f"\n开始筛选文献，原始文献数: {len(articles)}")
        print(f"并行处理: {'启用' if self.config.enable_parallel else '禁用'}")
        
        # 显示筛选条件（排除已在PubMed检索中应用的条件）
        pubmed_filters = (criteria.year_start or criteria.year_end or criteria.keywords)
        journal_filters = (criteria.min_if or criteria.max_if or 
                          criteria.cas_zones or criteria.jcr_quartiles)
        
        if pubmed_filters:
            print(f"[PubMed] 已在检索中应用的条件:")
            if criteria.year_start or criteria.year_end:
                print(f"  - 年份: {criteria.year_start or '不限'}-{criteria.year_end or '不限'}")
            if criteria.keywords:
                print(f"  - 关键词: {criteria.keywords}")
        
        if journal_filters:
            print(f"[FILTER] 期刊筛选条件:")
            if criteria.min_if or criteria.max_if:
                print(f"  - 影响因子: {criteria.min_if or '不限'}-{criteria.max_if or '不限'}")
            if criteria.cas_zones:
                print(f"  - 中科院分区: {criteria.cas_zones}")
            if criteria.jcr_quartiles:
                print(f"  - JCR分区: {criteria.jcr_quartiles}")
        
        if not pubmed_filters and not journal_filters:
            print("筛选条件: 无")
        
        filtered_articles = []
        
        if self.config.enable_parallel and len(articles) > self.config.batch_size:
            # 并行处理
            filtered_articles = self._filter_articles_parallel(articles, criteria)
        else:
            # 串行处理
            filtered_articles = self._filter_articles_serial(articles, criteria)
        
        # 更新性能统计
        filter_time = time.time() - start_time
        self.performance_stats['total_filter_time'] += filter_time
        self.performance_stats['total_articles_processed'] += len(articles)
        
        print(f"筛选后文献数: {len(filtered_articles)}")
        print(f"筛选耗时: {filter_time:.2f}秒")
        
        # 显示错误统计
        if self.performance_stats['errors'] > 0:
            print(f"[WARN] 处理过程中发生 {self.performance_stats['errors']} 个错误")
            print(f"[INFO] 已保留所有文献，包括处理失败的文献")
        
        # 统计处理状态
        normal_articles = sum(1 for a in filtered_articles if '_processing_error' not in a)
        error_articles = sum(1 for a in filtered_articles if '_processing_error' in a)
        journal_error_articles = sum(1 for a in filtered_articles if '_journal_info_error' in a)
        
        if error_articles > 0:
            print(f"[STAT] 处理状态: 正常 {normal_articles} 篇, 错误 {error_articles} 篇")
        if journal_error_articles > 0:
            print(f"[STAT] 期刊信息获取失败: {journal_error_articles} 篇")
        
        return filtered_articles
    
    def _filter_articles_parallel(self, articles: List[Dict], criteria: SearchCriteria) -> List[Dict]:
        """并行筛选文献"""
        filtered_articles = []
        
        # 分批处理
        batch_size = self.config.batch_size
        batches = [articles[i:i + batch_size] for i in range(0, len(articles), batch_size)]
        
        print(f"分 {len(batches)} 批并行处理，每批 {batch_size} 篇")
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # 提交所有批次任务
            future_to_batch = {
                executor.submit(self._process_batch, batch, criteria): batch 
                for batch in batches
            }
            
            # 收集结果
            for future in as_completed(future_to_batch):
                try:
                    batch_results = future.result()
                    filtered_articles.extend(batch_results)
                    self.performance_stats['parallel_batches'] += 1
                except Exception as e:
                    print(f"处理批次失败: {e}")
                    self.performance_stats['errors'] += 1
        
        return filtered_articles
    
    def _filter_articles_serial(self, articles: List[Dict], criteria: SearchCriteria) -> List[Dict]:
        """串行筛选文献"""
        filtered_articles = []
        
        for article in articles:
            try:
                if self._meets_criteria(article, criteria):
                    enhanced_article = self._enhance_article_info(article)
                    filtered_articles.append(enhanced_article)
            except Exception as e:
                # 错误处理：即使增强信息失败，也保留原始文献
                pmid = article.get('pmid', '未知')
                title = article.get('title', '未知标题')[:50]
                
                print(f"[WARN] 文献处理失败 (PMID: {pmid}): {e}")
                print(f"[INFO] 保留原始文献: {title}...")
                
                # 记录错误但保留文献
                self.performance_stats['errors'] += 1
                
                # 即使增强失败，也要保留满足条件的文献
                try:
                    # 简化的条件检查（不依赖期刊信息）
                    if self._meets_criteria_basic(article, criteria):
                        # 直接使用原始文献，不添加期刊信息
                        filtered_articles.append(article)
                except Exception as e2:
                    print(f"[ERROR] 文献条件检查也失败 (PMID: {pmid}): {e2}")
                    # 最终保障：无论如何都保留文献
                    article_copy = article.copy()
                    article_copy['_processing_error'] = str(e)
                    filtered_articles.append(article_copy)
        
        return filtered_articles
    
    def _process_batch(self, batch: List[Dict], criteria: SearchCriteria) -> List[Dict]:
        """处理一个批次的文献"""
        batch_results = []
        
        for article in batch:
            try:
                if self._meets_criteria(article, criteria):
                    enhanced_article = self._enhance_article_info(article)
                    batch_results.append(enhanced_article)
            except Exception as e:
                # 错误处理：即使增强信息失败，也保留原始文献
                pmid = article.get('pmid', '未知')
                title = article.get('title', '未知标题')[:50]  # 限制标题长度
                
                print(f"[WARN] 文献处理失败 (PMID: {pmid}): {e}")
                print(f"[INFO] 保留原始文献: {title}...")
                
                # 记录错误但保留文献
                self.performance_stats['errors'] += 1
                
                # 即使增强失败，也要保留满足条件的文献
                try:
                    # 简化的条件检查（不依赖期刊信息）
                    if self._meets_criteria_basic(article, criteria):
                        # 直接使用原始文献，不添加期刊信息
                        batch_results.append(article)
                except Exception as e2:
                    print(f"[ERROR] 文献条件检查也失败 (PMID: {pmid}): {e2}")
                    # 最终保障：无论如何都保留文献
                    article_copy = article.copy()
                    article_copy['_processing_error'] = str(e)
                    batch_results.append(article_copy)
        
        return batch_results
    
    def filter_articles(self, articles: List[Dict], criteria: SearchCriteria) -> List[Dict]:
        """兼容性方法 - 已废弃，请使用 filter_articles_optimized"""
        import warnings
        warnings.warn("filter_articles 已废弃，请使用 filter_articles_optimized", DeprecationWarning, stacklevel=2)
        return self.filter_articles_optimized(articles, criteria)
    
    def _meets_criteria_basic(self, article: Dict, criteria: SearchCriteria) -> bool:
        """基本条件检查（不依赖期刊信息）"""
        
          
          
        return True
    
    def _meets_criteria(self, article: Dict, criteria: SearchCriteria) -> bool:
        """检查文献是否满足筛选条件"""
        
        # 快速检查：如果没有设置任何筛选条件，直接返回True
        if (not criteria.min_if and not criteria.max_if and 
            not criteria.cas_zones and not criteria.jcr_quartiles):
            return True
        
        # 获取期刊信息
        issn = article.get('issn', '')
        eissn = article.get('eissn', '')
        journal_info = self.get_journal_info_optimized(issn, eissn)
        
          
        # 检查影响因子限制
        impact_factor = journal_info.get('impact_factor')
        if impact_factor:
            if criteria.min_if and impact_factor < criteria.min_if:
                return False
            if criteria.max_if and impact_factor > criteria.max_if:
                return False
        else:
            # 如果要求有影响因子但没有数据，则排除
            if criteria.min_if or criteria.max_if:
                return False
        
        # 检查中科院分区限制
        if criteria.cas_zones:
            cas_zone = journal_info.get('cas_zone')
            if not cas_zone:
                return False
            try:
                cas_zone_int = int(cas_zone)
                if cas_zone_int not in criteria.cas_zones:
                    return False
            except (ValueError, TypeError):
                return False
        
        # 检查JCR分区限制
        if criteria.jcr_quartiles:
            jcr_quartile = journal_info.get('jcr_quartile')
            if not jcr_quartile or str(jcr_quartile) not in criteria.jcr_quartiles:
                return False
        
          
        return True
    
    def _extract_year(self, pub_date: str) -> Optional[int]:
        """从发表日期中提取年份"""
        if not pub_date:
            return None

        # 尝试提取4位数字年份
        year_match = re.search(r'(\d{4})', str(pub_date))
        if year_match:
            year = int(year_match.group(1))
            # 合理的年份范围 - 使用动态计算避免硬编码
            current_year = datetime.now().year
            if 1900 <= year <= current_year + MAX_YEAR_OFFSET:
                return year

        return None
    
    def _enhance_article_info(self, article: Dict) -> Dict:
        """增强文献信息，添加期刊数据"""
        enhanced = article.copy()
        
        try:
            # 获取期刊信息
            issn = article.get('issn', '')
            eissn = article.get('eissn', '')
            journal_info = self.get_journal_info_optimized(issn, eissn)
            
            # 安全地添加期刊信息
            enhanced['cas_zone'] = journal_info.get('cas_zone') if journal_info else None
            enhanced['impact_factor'] = journal_info.get('impact_factor') if journal_info else None
            enhanced['jcr_quartile'] = journal_info.get('jcr_quartile') if journal_info else None
            
        except Exception as e:
            # 期刊信息增强失败，但不影响文献本身
            pmid = article.get('pmid', '未知')
            print(f"[WARN] 期刊信息增强失败 (PMID: {pmid}): {e}")
            
            # 设置默认值
            enhanced['cas_zone'] = None
            enhanced['impact_factor'] = None
            enhanced['jcr_quartile'] = None
            enhanced['_journal_info_error'] = str(e)
        
        return enhanced
    
    def print_filter_statistics(self, original_count: int, filtered_count: int, criteria: SearchCriteria):
        """打印筛选统计信息"""
        print(f"\n=== 筛选统计 ===")
        print(f"原始文献数: {original_count}")
        print(f"筛选后文献数: {filtered_count}")
        print(f"筛选率: {filtered_count/original_count*100:.1f}%" if original_count > 0 else "0%")
        
        # 分别显示PubMed检索条件和期刊筛选条件
        pubmed_filters = (criteria.year_start or criteria.year_end or criteria.keywords)
        journal_filters = (criteria.min_if or criteria.max_if or 
                          criteria.cas_zones or criteria.jcr_quartiles)
        
        if pubmed_filters:
            print("\n[PubMed] 已在检索中应用的条件:")
            if criteria.year_start or criteria.year_end:
                print(f"  - 年份: {criteria.year_start or '不限'} - {criteria.year_end or '不限'}")
            if criteria.keywords:
                print(f"  - 关键词: {criteria.keywords}")
        
        if journal_filters:
            print("\n[FILTER] 期刊筛选条件:")
            if criteria.min_if or criteria.max_if:
                print(f"  - 影响因子: {criteria.min_if or '不限'} - {criteria.max_if or '不限'}")
            if criteria.cas_zones:
                print(f"  - 中科院分区: {criteria.cas_zones}")
            if criteria.jcr_quartiles:
                print(f"  - JCR分区: {criteria.jcr_quartiles}")
        
        if not pubmed_filters and not journal_filters:
            print("\n筛选条件: 无")
            
        print("=" * 30)
    
    def export_filtered_results(self, articles: List[Dict], output_format: str = 'json', 
                              output_file: str = None) -> str:
        """
        导出筛选结果
        
        Args:
            articles: 筛选后的文献列表
            output_format: 输出格式 ('json' 或 'csv')
            output_file: 输出文件名
            
        Returns:
            输出文件路径
        """
        if not articles:
            print("没有文献数据可导出")
            return ""
        
        # 生成输出文件名
        if not output_file:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"literature_search_{timestamp}"
        
        # 按摘要排序：有摘要的排在前面
        sorted_articles = sorted(articles, key=lambda x: (
            0 if x.get('abstract') and x.get('abstract').strip() else 1,  # 有摘要的排前面
            x.get('pmid', '')  # 同等情况下按PMID排序
        ))
        
        # 准备导出数据
        export_data = []
        for i, article in enumerate(sorted_articles, 1):
            pmid = article.get('pmid', '')
            pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}" if pmid else ""
            
            export_item = {
                '序号': i,
                '文献标题': article.get('title', ''),
                'PMID': pmid,
                '文献地址': pubmed_url,
                '中科院分区': article.get('cas_zone', ''),
                '影响因子': article.get('impact_factor', ''),
                'JCR分区': article.get('jcr_quartile', ''),
                '摘要': article.get('abstract', ''),
                '作者': article.get('authors_str', ''),
                '期刊': article.get('journal', ''),
                '发表日期': article.get('publication_date', ''),
                'DOI': article.get('doi', '')
            }
            export_data.append(export_item)
        
        # 获取统计分析数据
        analysis_stats = self.analyze_filtered_results(sorted_articles)
        
        # 导出文件
        try:
            if output_format.lower() == 'json':
                output_path = f"{output_file}.json"
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'export_info': {
                            'total_count': len(export_data),
                            'export_time': pd.Timestamp.now().isoformat(),
                            'has_abstract_count': sum(1 for a in sorted_articles if a.get('abstract') and a.get('abstract').strip())
                        },
                        'statistics': analysis_stats,  # 添加统计分析数据
                        'articles': export_data
                    }, f, ensure_ascii=False, indent=2)
                    
            elif output_format.lower() == 'csv':
                output_path = f"{output_file}.csv"
                df = pd.DataFrame(export_data)
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                
                # 为CSV格式创建单独的统计报告文件
                if analysis_stats:
                    stats_path = f"{output_file}_statistics.txt"
                    self._export_statistics_report(analysis_stats, stats_path)
                    print(f"统计分析已导出到: {stats_path}")
            
            else:
                raise ValueError(f"不支持的输出格式: {output_format}")
            
            print(f"筛选结果已导出到: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"导出失败: {e}")
            return ""
    
    def _export_statistics_report(self, analysis_stats: Dict, file_path: str):
        """导出统计分析报告到文本文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 50 + "\n")
                f.write("文献筛选结果统计分析报告\n")
                f.write("=" * 50 + "\n\n")
                
                # 总体统计
                if "总体统计" in analysis_stats:
                    stats = analysis_stats["总体统计"]
                    f.write("[STAT] 总体统计:\n")
                    f.write(f"  总文献数: {stats.get('总文献数', 0)}\n")
                    f.write(f"  有摘要文献数: {stats.get('有摘要文献数', 0)}\n\n")
                    
                    if "覆盖率统计" in stats:
                        f.write("[TREND] 覆盖率统计:\n")
                        for key, value in stats["覆盖率统计"].items():
                            f.write(f"  {key}: {value}\n")
                        f.write("\n")
                
                # 年份分布
                if "年份分布" in analysis_stats and analysis_stats["年份分布"]:
                    f.write("📅 年份分布:\n")
                    for year, count in sorted(analysis_stats["年份分布"].items()):
                        f.write(f"  {year}: {count}篇\n")
                    f.write("\n")
                
                # 中科院分区分布
                if "中科院分区分布" in analysis_stats and analysis_stats["中科院分区分布"]:
                    f.write("🏆 中科院分区分布:\n")
                    for zone, count in analysis_stats["中科院分区分布"].items():
                        f.write(f"  {zone}: {count}篇\n")
                    f.write("\n")
                
                # JCR分区分布
                if "JCR分区分布" in analysis_stats and analysis_stats["JCR分区分布"]:
                    f.write("[LIST] JCR分区分布:\n")
                    for quartile in ['Q1', 'Q2', 'Q3', 'Q4']:
                        if quartile in analysis_stats["JCR分区分布"]:
                            count = analysis_stats["JCR分区分布"][quartile]
                            f.write(f"  {quartile}: {count}篇\n")
                    f.write("\n")
                
                # 影响因子统计
                if "影响因子统计" in analysis_stats and analysis_stats["影响因子统计"]:
                    f.write("[STAT] 影响因子统计:\n")
                    for key, value in analysis_stats["影响因子统计"].items():
                        f.write(f"  {key}: {value}\n")
                    f.write("\n")
                
                f.write("=" * 50 + "\n")
                f.write(f"报告生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                
        except Exception as e:
            print(f"导出统计报告失败: {e}")
    
    def analyze_filtered_results(self, articles: List[Dict]) -> Dict:
        """分析筛选结果，返回统计数据"""
        if not articles:
            print("没有文献数据可分析")
            return {}
        
        total = len(articles)
        print(f"\n=== 筛选结果分析 ===")
        
        # 统计期刊信息覆盖率
        has_cas = sum(1 for a in articles if a.get('cas_zone') is not None)
        has_if = sum(1 for a in articles if a.get('impact_factor') is not None)
        has_jcr = sum(1 for a in articles if a.get('jcr_quartile') is not None)
        has_abstract = sum(1 for a in articles if a.get('abstract') and a.get('abstract').strip())
        
        coverage_stats = {
            "中科院分区覆盖率": f"{has_cas}/{total} ({has_cas/total*100:.1f}%)",
            "影响因子覆盖率": f"{has_if}/{total} ({has_if/total*100:.1f}%)", 
            "JCR分区覆盖率": f"{has_jcr}/{total} ({has_jcr/total*100:.1f}%)",
            "摘要覆盖率": f"{has_abstract}/{total} ({has_abstract/total*100:.1f}%)"
        }
        
        print("期刊信息覆盖率:")
        print(f"  中科院分区: {coverage_stats['中科院分区覆盖率']}")
        print(f"  影响因子: {coverage_stats['影响因子覆盖率']}")
        print(f"  JCR分区: {coverage_stats['JCR分区覆盖率']}")
        print(f"  摘要: {coverage_stats['摘要覆盖率']}")
        
        # 统计年份分布
        years = []
        for article in articles:
            year = self._extract_year(article.get('publication_date', ''))
            if year:
                years.append(year)
        
        year_distribution = {}
        if years:
            print(f"\n年份分布:")
            year_counts = pd.Series(years).value_counts().sort_index()
            for year, count in year_counts.items():
                year_distribution[str(year)] = int(count)  # 转换为普通int类型
                print(f"  {year}: {count}篇")
        
        # 统计中科院分区分布
        cas_zones = [a.get('cas_zone') for a in articles if a.get('cas_zone') is not None]
        cas_distribution = {}
        if cas_zones:
            print(f"\n中科院分区分布:")
            zone_counts = pd.Series(cas_zones).value_counts().sort_index()
            for zone, count in zone_counts.items():
                cas_distribution[f"{zone}区"] = int(count)  # 转换为普通int类型
                print(f"  {zone}区: {count}篇")
        
        # 统计JCR分区分布
        jcr_quartiles = [a.get('jcr_quartile') for a in articles if a.get('jcr_quartile') is not None]
        jcr_distribution = {}
        if jcr_quartiles:
            print(f"\nJCR分区分布:")
            quartile_counts = pd.Series(jcr_quartiles).value_counts()
            for quartile in ['Q1', 'Q2', 'Q3', 'Q4']:
                if quartile in quartile_counts:
                    jcr_distribution[quartile] = int(quartile_counts[quartile])  # 转换为普通int类型
                    print(f"  {quartile}: {quartile_counts[quartile]}篇")
        
        # 影响因子统计
        impact_factors = [a.get('impact_factor') for a in articles 
                         if a.get('impact_factor') is not None]
        impact_factor_stats = {}
        if impact_factors:
            print(f"\n影响因子统计:")
            impact_factor_stats = {
                "最小值": round(min(impact_factors), 3),
                "最大值": round(max(impact_factors), 3),
                "平均值": round(sum(impact_factors)/len(impact_factors), 3),
                "中位数": round(sorted(impact_factors)[len(impact_factors)//2], 3)
            }
            for key, value in impact_factor_stats.items():
                print(f"  {key}: {value}")
        
        print("=" * 40)
        
        # 返回完整的统计分析数据
        return {
            "总体统计": {
                "总文献数": total,
                "有摘要文献数": has_abstract,
                "覆盖率统计": coverage_stats
            },
            "年份分布": year_distribution,
            "中科院分区分布": cas_distribution,
            "JCR分区分布": jcr_distribution,
            "影响因子统计": impact_factor_stats
        }


    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        cache_stats = self.journal_cache.get_stats() if hasattr(self, 'journal_cache') else {}
        
        return {
            'total_articles_processed': self.performance_stats['total_articles_processed'],
            'total_filter_time': self.performance_stats['total_filter_time'],
            'average_filter_time': self.performance_stats['total_filter_time'] / max(self.performance_stats['total_articles_processed'], 1),
            'cache_hits': self.performance_stats['cache_hits'],
            'parallel_batches': self.performance_stats['parallel_batches'],
            'memory_usage_mb': self.performance_stats['memory_usage_mb'],
            'errors': self.performance_stats['errors'],
            'cache_stats': cache_stats
        }
    
    def print_performance_report(self):
        """打印性能报告"""
        report = self.get_performance_report()
        
        print("\n=== 文献过滤器性能报告 ===")
        print(f"处理文献总数: {report['total_articles_processed']}")
        print(f"总筛选时间: {report['total_filter_time']:.2f}秒")
        print(f"平均筛选时间: {report['average_filter_time']:.4f}秒/篇")
        print(f"缓存命中次数: {report['cache_hits']}")
        print(f"并行处理批次数: {report['parallel_batches']}")
        print(f"内存使用: {report['memory_usage_mb']:.2f}MB")
        print(f"错误次数: {report['errors']}")
        
        if 'cache_stats' in report:
            cache_stats = report['cache_stats']
            print(f"缓存大小: {cache_stats['cache_size']}/{cache_stats['max_cache_size']}")
            print(f"缓存命中率: {cache_stats['hit_rate']:.2%}")
        
        print("=" * 30)
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清理缓存
            if hasattr(self, 'journal_cache'):
                self.journal_cache.cache.clear()
                self.journal_cache.access_times.clear()
            
            # 打印性能报告
            if self.performance_stats['total_articles_processed'] > 0:
                self.print_performance_report()
                
        except Exception as e:
            print(f"清理资源时出错: {e}")


def test_literature_filter():
    """测试文献筛选器"""
    # 创建测试数据
    test_articles = [
        {
            'pmid': '12345',
            'title': 'Diabetes treatment with new drug',
            'issn': '0007-9235',  # CA-A CANCER JOURNAL影响因子232.4, Q1
            'eissn': '1542-4863',
            'publication_date': '2023-01-15',
            'abstract': 'This study investigates diabetes treatment...',
            'keywords_str': 'diabetes, treatment, drug'
        },
        {
            'pmid': '67890', 
            'title': 'COVID-19 vaccine effectiveness',
            'issn': '1234-5678',  # 假设的低影响因子期刊
            'eissn': '',
            'publication_date': '2021-05-20',
            'abstract': 'COVID-19 vaccine study...',
            'keywords_str': 'COVID-19, vaccine, effectiveness'
        }
    ]
    
    # 创建筛选条件
    from intent_analyzer import SearchCriteria
    criteria = SearchCriteria(
        query="diabetes treatment",
        year_start=2020,
        year_end=2024,
        min_if=5.0,
        jcr_quartiles=['Q1']
    )
    
    # 测试筛选
    filter_obj = LiteratureFilter()
    filtered = filter_obj.filter_articles(test_articles, criteria)
    
    filter_obj.print_filter_statistics(len(test_articles), len(filtered), criteria)
    filter_obj.analyze_filtered_results(filtered)
    
    # 测试导出
    if filtered:
        filter_obj.export_filtered_results(filtered, 'json', 'test_filtered')




if __name__ == "__main__":
    test_literature_filter()