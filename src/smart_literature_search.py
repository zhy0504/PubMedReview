#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能文献检索和筛选系统
整合用户意图分析、PubMed检索、期刊数据匹配和结果导出功能
"""

import sys
import os
import argparse
from datetime import datetime
from typing import List, Dict, Optional

# 导入自定义模块
from data_processor import JournalDataProcessor
from intent_analyzer import IntentAnalyzer, SearchCriteria
from pubmed_search import PubMedSearcher
from literature_filter import LiteratureFilter
from review_outline_generator import ReviewOutlineGenerator


class SmartLiteratureSearchSystem:
    """智能文献检索系统"""
    
    def __init__(self, ai_config_name: str = None, interactive_ai: bool = True):
        """
        初始化系统
        
        Args:
            ai_config_name: AI配置名称
            interactive_ai: 是否交互式配置AI模型
        """
        self.ai_config_name = ai_config_name
        self.interactive_ai = interactive_ai
        
        # 初始化各个组件
        self.data_processor = None
        self.intent_analyzer = None
        self.pubmed_searcher = None
        self.literature_filter = None
        self.outline_generator = None  # 新增大纲生成器
        
        # 系统状态
        self.data_ready = False
        
    def initialize_system(self):
        """初始化系统组件"""
        print("正在初始化智能文献检索系统...")
        
        # 1. 检查和处理期刊数据
        self._ensure_journal_data()
        
        # 2. 初始化意图分析器
        try:
            self.intent_analyzer = IntentAnalyzer(
                self.ai_config_name, 
                interactive=self.interactive_ai
            )
            print("✓ AI意图分析器初始化完成")
        except Exception as e:
            print(f"✗ AI意图分析器初始化失败: {e}")
            print("提示: 请确保已正确配置AI接口 (运行 python ai_client.py 进行配置)")
            return False
        
        # 3. 初始化PubMed搜索器
        self.pubmed_searcher = PubMedSearcher()
        print("✓ PubMed搜索器初始化完成")
        
        # 4. 初始化文献筛选器
        try:
            self.literature_filter = LiteratureFilter()
            print("✓ 文献筛选器初始化完成")
        except Exception as e:
            print(f"✗ 文献筛选器初始化失败: {e}")
            return False
        
        # 5. 初始化综述大纲生成器
        try:
            self.outline_generator = ReviewOutlineGenerator(self.ai_config_name)
            print("✓ 综述大纲生成器初始化完成")
        except Exception as e:
            print(f"✗ 综述大纲生成器初始化失败: {e}")
            print("提示: 大纲生成功能将不可用，但文献检索功能正常")
        
        self.data_ready = True
        print("🎉 系统初始化完成!\n")
        return True
    
    def _ensure_journal_data(self):
        """确保期刊数据已处理"""
        zky_file = "data/processed_zky_data.csv"
        jcr_file = "data/processed_jcr_data.csv"
        
        if not (os.path.exists(zky_file) and os.path.exists(jcr_file)):
            print("检测到期刊数据未处理，正在处理...")
            try:
                self.data_processor = JournalDataProcessor()
                self.data_processor.process_separate()
                print("✓ 期刊数据处理完成")
            except Exception as e:
                print(f"✗ 期刊数据处理失败: {e}")
                return False
        else:
            print("✓ 期刊数据已就绪")
        
        return True
    
    def search_literature(self, user_input: str, max_results: int = 100) -> Optional[tuple]:
        """
        智能文献检索 - 自动输出CSV和JSON两种格式
        
        Args:
            user_input: 用户输入的检索需求
            max_results: 最大检索结果数
            
        Returns:
            (csv_path, json_path) 元组，包含两种格式的文件路径
        """
        if not self.data_ready:
            print("系统未初始化，请先运行 initialize_system()")
            return None
        
        print(f"[FIND] 开始智能文献检索")
        print(f"用户需求: {user_input}")
        print("=" * 60)
        
        # 步骤1: 意图分析
        print("\n[LIST] 步骤1: 分析用户意图...")
        try:
            criteria = self.intent_analyzer.analyze_intent(user_input)
            self.intent_analyzer.print_analysis_result(criteria)
        except Exception as e:
            print(f"意图分析失败: {e}")
            # 使用基础搜索条件
            criteria = SearchCriteria(query=user_input)
        
        # 步骤2: 构建检索词并搜索
        print("\n[SEARCH] 步骤2: 执行PubMed检索...")
        query = self.intent_analyzer.build_pubmed_query(criteria)
        print(f"最终检索词: {query}")
        
        try:
            # 第一次检索：不获取摘要，只获取基本信息
            pmids = self.pubmed_searcher.search_articles(
                query=query,
                max_results=max_results,
                sort_by='relevance'
            )
            
            if not pmids:
                print("未找到任何文献")
                return None
            
            print(f"找到 {len(pmids)} 篇文献")
            
            # 获取基本信息（不包含摘要）
            print("获取文献基本信息...")
            basic_articles = self._fetch_basic_info(pmids)
            
        except Exception as e:
            print(f"PubMed检索失败: {e}")
            return None
        
        # 步骤3: 文献筛选（只筛选期刊相关条件）
        print(f"\n[STAT] 步骤3: 筛选期刊条件...")
        try:
            filtered_articles = self.literature_filter.filter_articles(basic_articles, criteria)
            
            if not filtered_articles:
                print("没有文献通过期刊筛选条件")
                return None
            
            self.literature_filter.print_filter_statistics(
                len(basic_articles), len(filtered_articles), criteria
            )
            
        except Exception as e:
            print(f"文献筛选失败: {e}")
            return None
        
        # 步骤4: 获取筛选后文献的摘要
        print(f"\n[FILE] 步骤4: 获取筛选后文献的详细信息...")
        try:
            filtered_pmids = [article['pmid'] for article in filtered_articles]
            detailed_articles = self.pubmed_searcher.fetch_article_details(filtered_pmids)
            
            # 合并筛选信息和详细信息
            enhanced_articles = self._merge_article_info(filtered_articles, detailed_articles)
            
        except Exception as e:
            print(f"获取详细信息失败: {e}")
            enhanced_articles = filtered_articles
        
        # 步骤5: 分析和导出结果
        print(f"\n[TREND] 步骤5: 分析和导出结果...")
        self.literature_filter.analyze_filtered_results(enhanced_articles)
        
        # 生成输出文件名（包含用户输入关键词）
        output_file = self._generate_filename(user_input)
        
        # 生成带文件夹路径的输出文件名
        literature_output_path = os.path.join("output", "文献检索结果", output_file)
        
        # 同时导出JSON和CSV两种格式
        json_path = self.literature_filter.export_filtered_results(
            enhanced_articles, 'json', literature_output_path
        )
        csv_path = self.literature_filter.export_filtered_results(
            enhanced_articles, 'csv', literature_output_path
        )
        
        print(f"\n🎉 检索完成! 共找到 {len(enhanced_articles)} 篇符合条件的文献")
        print(f"[FILE] JSON格式: {json_path}")
        print(f"[STAT] CSV格式: {csv_path}")
        
        # 返回两种格式的文件路径
        return csv_path, json_path
    
    def generate_review_outline(self, json_file_path: str, research_topic: str) -> Optional[str]:
        """
        基于检索结果生成综述大纲
        
        Args:
            json_file_path: 文献检索结果JSON文件路径
            research_topic: 研究主题
            total_word_count: 目标总字数
            
        Returns:
            生成的大纲文件路径
        """
        if not self.outline_generator:
            print("[FAIL] 综述大纲生成器未初始化")
            return None
        
        try:
            print(f"[FIND] 正在基于文献数据生成综述大纲...")
            print(f"主题: {research_topic}")
            print("=" * 60)
            
            # 生成大纲
            outline = self.outline_generator.generate_outline_from_json(
                json_file_path, research_topic
            )
            
            # 生成输出文件名和路径
            import re
            safe_topic = re.sub(r'[^\w\s-]', '', research_topic).replace(' ', '_')[:20]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            outline_filename = f"综述大纲—{safe_topic}-{timestamp}.md"
            outline_file = os.path.join("output", "综述大纲", outline_filename)
            
            # 保存大纲
            self.outline_generator.save_outline(outline, outline_file)
            
            print(f"\n[NOTE] 大纲生成完成!")
            print(f"大纲已保存到: {outline_file}")
            
            return outline_file
            
        except Exception as e:
            print(f"[FAIL] 大纲生成失败: {e}")
            return None
    
    def search_and_generate_outline(self, user_input: str, max_results: int = 100) -> Optional[str]:
        """
        一键完成文献检索和综述大纲生成
        
        Args:
            user_input: 用户输入的检索需求
            max_results: 最大检索结果数
            
        Returns:
            大纲文件路径
        """
        # 步骤1: 进行文献检索（同时生成JSON和CSV）
        search_result = self.search_literature(user_input, max_results)
        
        if not search_result:
            print("[FAIL] 文献检索失败，无法生成大纲")
            return None
        
        # 处理返回结果（现在总是返回两个路径）
        if isinstance(search_result, tuple):
            csv_file, json_file = search_result
        else:
            # 向后兼容，如果只返回单个文件
            csv_file = json_file = search_result
        
        # 步骤2: 使用JSON文件生成综述大纲
        if self.outline_generator and json_file:
            print(f"\n[NOTE] 开始生成综述大纲...")
            print(f"[FILE] 使用数据文件: {json_file}")
            outline_file = self.generate_review_outline(json_file, user_input)
            
            if outline_file:
                print(f"\n🎉 完整流程完成!")
                print(f"[STAT] CSV数据文件: {csv_file}")
                print(f"[FILE] JSON数据文件: {json_file}")
                print(f"[NOTE] 综述大纲文件: {outline_file}")
                return outline_file
            else:
                print("[FAIL] 大纲生成失败")
                return None
        else:
            print("[WARN]  大纲生成器不可用")
            return None
    
    def _generate_filename(self, user_input: str) -> str:
        """
        根据用户输入生成智能文件名
        
        Args:
            user_input: 用户输入的检索需求
            
        Returns:
            生成的文件名（不含扩展名）
        """
        import re
        from datetime import datetime
        
        # 生成时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 提取关键医学术语和重要词汇
        medical_keywords = {
            # 常见疾病
            '糖尿病': 'diabetes', '高血压': 'hypertension', '癌症': 'cancer',
            '肿瘤': 'tumor', '心脏病': 'cardiac', '阿尔茨海默': 'alzheimer',
            '结核病': 'tuberculosis', '结核': 'tuberculosis', '肺炎': 'pneumonia',
            '哮喘': 'asthma', '抑郁症': 'depression', '焦虑': 'anxiety',
            '脑梗': 'stroke', '中风': 'stroke', '冠心病': 'coronary',
            # 治疗方法
            '治疗': 'treatment', '药物': 'drug', '疫苗': 'vaccine',
            '手术': 'surgery', '放疗': 'radiotherapy', '化疗': 'chemotherapy',
            # 生物医学
            '免疫': 'immune', '基因': 'gene', '蛋白质': 'protein',
            '细胞': 'cell', '分子': 'molecular', '病毒': 'virus',
            # 感染相关
            '感染': 'infection', '潜伏': 'latent', '病原': 'pathogen'
        }
        
        # 特殊术语处理（影响因子、分区等）
        special_terms = {
            'IF': 'if', 'JCR': 'jcr', 'Q1': 'q1', 'Q2': 'q2', 'Q3': 'q3', 'Q4': 'q4',
            '影响因子': 'if', '中科院': 'cas', '分区': 'zone', '期刊': 'journal',
            '高影响因子': 'high_if', '顶级期刊': 'top_journal', '高分': 'high_score'
        }
        
        # 分别收集不同类型的关键词
        medical_terms = []  # 医学术语
        condition_terms = []  # 条件术语（时间、分区、影响因子等）
        
        input_upper = user_input.upper()
        input_lower = user_input.lower()
        
        # 1. 优先提取医学术语
        for chinese_term, english_term in medical_keywords.items():
            if chinese_term in user_input or english_term in input_lower:
                if english_term not in medical_terms:  # 避免重复
                    medical_terms.append(english_term)
                if len(medical_terms) >= 2:  # 最多保留2个医学术语
                    break
        
        # 2. 提取特殊术语（影响因子、分区等）
        for special_term, english_term in special_terms.items():
            if special_term in user_input or special_term.upper() in input_upper:
                if english_term not in condition_terms:  # 避免重复
                    condition_terms.append(english_term)
        
        # 3. 提取数字条件（如 IF>5, 近5年等）
        number_patterns = [
            (r'IF\s*[>≥]\s*(\d+(?:\.\d+)?)', lambda m: f'if_gt_{m.group(1).replace(".", "_")}'),
            (r'IF\s*[<≤]\s*(\d+(?:\.\d+)?)', lambda m: f'if_lt_{m.group(1).replace(".", "_")}'),
            (r'影响因子\s*[>≥大于]\s*(\d+(?:\.\d+)?)', lambda m: f'if_gt_{m.group(1).replace(".", "_")}'),
            (r'近(\d+)年', lambda m: f'recent_{m.group(1)}y'),
            (r'最近(\d+)年', lambda m: f'last_{m.group(1)}y'),
            (r'(\d+)区', lambda m: f'zone_{m.group(1)}'),
            (r'Q(\d)', lambda m: f'q{m.group(1)}')
        ]
        
        for pattern, formatter in number_patterns:
            matches = re.finditer(pattern, user_input, re.IGNORECASE)
            for match in matches:
                formatted_term = formatter(match)
                if formatted_term not in condition_terms:  # 避免重复
                    condition_terms.append(formatted_term)
        
        # 4. 智能去重和组合关键词
        # 移除重复的基础词（如当有if_gt_5时移除if）
        filtered_condition_terms = []
        for term in condition_terms:
            has_more_specific = False
            for other_term in condition_terms:
                if other_term != term and other_term.startswith(term + '_'):
                    has_more_specific = True
                    break
            if not has_more_specific:
                filtered_condition_terms.append(term)
        
        # 组合：医学术语（最多2个）+ 条件术语（最多2个）
        keywords = medical_terms[:2] + filtered_condition_terms[:2]
        
        # 5. 如果没有找到任何专业术语，提取普通关键词
        if not keywords:
            # 移除常见的连接词和标点
            stop_words = {'的', '在', '中', '和', '与', '或', '及', '是', '了', '有', '对', '为', 
                         'the', 'in', 'of', 'and', 'or', 'for', 'with', 'by', 'a', 'an', 'to',
                         '要求', '期刊', '文献', '研究', '最新', '相关'}
            
            # 清理文本，保留中英文和数字，但移除特殊符号
            cleaned_input = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', user_input)
            words = [w.strip() for w in cleaned_input.split() if w.strip()]
            
            for word in words:
                if len(word) > 1 and word.lower() not in stop_words:
                    if any('\u4e00' <= c <= '\u9fff' for c in word):
                        # 中文词汇，取前4个字符
                        keywords.append(word[:4])
                    else:
                        # 英文词汇，取前8个字符
                        keywords.append(word[:8].lower())
                    
                    if len(keywords) >= 3:
                        break
        
        # 组合文件名 - 直接使用主题词+时间戳
        # 简化用户输入为合法的文件名
        safe_topic = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', user_input).strip()
        safe_topic = re.sub(r'\s+', '_', safe_topic)  # 替换空格为下划线
        
        # 限制长度避免文件名过长
        if len(safe_topic) > 30:
            safe_topic = safe_topic[:30]
        
        # 如果处理后为空，使用默认名称
        if not safe_topic:
            safe_topic = "literature_search"
        
        filename = f"{safe_topic}_{timestamp}"
        
        return filename
    
    def _fetch_basic_info(self, pmids: List[str]) -> List[Dict]:
        """获取基本信息（不含摘要）"""
        articles = []
        
        # 简化版获取信息，主要获取PMID, 标题, 期刊, ISSN等
        for pmid in pmids:
            article = {
                'pmid': pmid,
                'title': '',
                'journal': '',
                'issn': '',
                'eissn': '',
                'publication_date': '',
                'doi': '',
                'authors': [],
                'authors_str': '',
                'keywords': [],
                'keywords_str': '',
                'abstract': ''  # 初始为空
            }
            articles.append(article)
        
        # 尝试批量获取基本信息
        try:
            detailed_articles = self.pubmed_searcher.fetch_article_details(pmids)
            
            # 创建PMID到文章的映射
            pmid_to_article = {article['pmid']: article for article in detailed_articles}
            
            # 更新基本信息
            for article in articles:
                pmid = article['pmid']
                if pmid in pmid_to_article:
                    detailed_article = pmid_to_article[pmid]
                    article.update({
                        'title': detailed_article.get('title', ''),
                        'journal': detailed_article.get('journal', ''),
                        'issn': detailed_article.get('issn', ''),
                        'eissn': detailed_article.get('eissn', ''),
                        'publication_date': detailed_article.get('publication_date', ''),
                        'doi': detailed_article.get('doi', ''),
                        'authors': detailed_article.get('authors', []),
                        'authors_str': detailed_article.get('authors_str', ''),
                        'keywords': detailed_article.get('keywords', []),
                        'keywords_str': detailed_article.get('keywords_str', '')
                    })
        
        except Exception as e:
            print(f"获取基本信息时出错: {e}")
        
        return articles
    
    def _merge_article_info(self, filtered_articles: List[Dict], 
                          detailed_articles: List[Dict]) -> List[Dict]:
        """合并筛选信息和详细信息"""
        # 创建PMID到详细信息的映射
        pmid_to_detailed = {article['pmid']: article for article in detailed_articles}
        
        merged_articles = []
        for filtered_article in filtered_articles:
            pmid = filtered_article['pmid']
            
            # 从详细信息中获取摘要
            if pmid in pmid_to_detailed:
                detailed_article = pmid_to_detailed[pmid]
                filtered_article['abstract'] = detailed_article.get('abstract', '')
            
            merged_articles.append(filtered_article)
        
        return merged_articles
    
    def interactive_search(self):
        """交互式检索"""
        if not self.data_ready:
            if not self.initialize_system():
                return
        
        print("[AI] 智能文献检索系统")
        print("输入 'quit' 退出，'help' 查看帮助，'config' 管理AI配置")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n请描述您的文献检索需求: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'quit':
                    print("感谢使用智能文献检索系统!")
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                if user_input.lower() == 'config':
                    self._manage_ai_config()
                    continue
                
                # 获取检索参数
                max_results = self._get_max_results()
                
                # 询问是否需要生成综述大纲（默认为是）
                generate_outline = True  # 默认生成大纲
                if self.outline_generator:
                    outline_choice = input("\n是否生成综述大纲? (y/n) [y]: ").strip().lower()
                    generate_outline = outline_choice not in ['n', 'no']  # 默认为是，只有明确说不才不生成
                
                # 执行检索或一键检索+大纲生成
                if generate_outline:
                    outline_file = self.search_and_generate_outline(user_input, max_results)
                    if outline_file:
                        print(f"\n[OK] 文献检索和大纲生成完成!")
                        print(f"[NOTE] 综述大纲已保存到: {outline_file}")
                    else:
                        print("\n[FAIL] 大纲生成失败")
                else:
                    # 普通文献检索（现在同时生成JSON和CSV）
                    search_result = self.search_literature(user_input, max_results)
                    
                    if search_result:
                        # 处理返回结果
                        if isinstance(search_result, tuple):
                            csv_file, json_file = search_result
                            print(f"\n[OK] 检索成功!")
                            print(f"[STAT] CSV格式: {csv_file}")
                            print(f"[FILE] JSON格式: {json_file}")
                        else:
                            # 向后兼容
                            csv_file = json_file = search_result
                            print(f"\n[OK] 检索成功! 结果已保存到: {search_result}")
                        
                        # 询问是否基于检索结果生成大纲（默认为是）
                        if self.outline_generator and json_file:
                            post_outline = input("\n是否基于检索结果生成综述大纲? (y/n) [y]: ").strip().lower()
                            if post_outline not in ['n', 'no']:  # 默认为是
                                outline_file = self.generate_review_outline(json_file, user_input)
                                if outline_file:
                                    print(f"[NOTE] 综述大纲已保存到: {outline_file}")
                    else:
                        print("\n[FAIL] 检索失败或无结果")
                
            except KeyboardInterrupt:
                print("\n\n用户中断程序")
                break
            except Exception as e:
                print(f"\n处理过程中出现错误: {e}")
    
    def _get_max_results(self) -> int:
        """获取最大结果数"""
        while True:
            try:
                max_str = input("最大检索结果数 [50]: ").strip()
                if not max_str:
                    return 50
                max_results = int(max_str)
                if max_results > 0:
                    return max_results
                else:
                    print("请输入正整数")
            except ValueError:
                print("请输入有效数字")
    
    def _manage_ai_config(self):
        """管理AI配置"""
        print("\n[CONFIG]  AI配置管理")
        print("1. 查看当前缓存配置")
        print("2. 清除缓存配置")
        print("3. 重新配置AI模型")
        print("4. 返回")
        
        choice = input("请选择 (1-4): ").strip()
        
        if choice == '1':
            IntentAnalyzer.show_cached_config()
        elif choice == '2':
            if self.intent_analyzer:
                self.intent_analyzer.clear_config_cache()
            else:
                # 直接清除缓存文件
                try:
                    if os.path.exists(IntentAnalyzer.CONFIG_CACHE_FILE):
                        os.remove(IntentAnalyzer.CONFIG_CACHE_FILE)
                        print("[OK] 配置缓存已清除")
                    else:
                        print("ℹ️  没有找到配置缓存文件")
                except Exception as e:
                    print(f"[FAIL] 清除配置缓存失败: {e}")
        elif choice == '3':
            print("[CONFIG]  重新配置AI模型...")
            try:
                self.intent_analyzer = IntentAnalyzer(
                    self.ai_config_name, 
                    interactive=True
                )
                print("[OK] AI模型配置完成")
            except Exception as e:
                print(f"[FAIL] AI模型配置失败: {e}")
        elif choice == '4':
            return
        else:
            print("[FAIL] 无效选择")
    
    def _show_help(self):
        """显示帮助信息"""
        print("""
📖 使用帮助:

[FIND] 检索示例:
  "糖尿病治疗的最新研究，要求是近5年的高影响因子期刊文献"
  "COVID-19疫苗效力研究，2020年以来的文献"
  "高血压药物治疗，要求1区或2区期刊"

[CONFIG] 系统命令:
  help - 显示此帮助信息
  config - 管理AI模型配置（查看/清除缓存、重新配置）
  quit - 退出系统

[LIST] 配置缓存功能:
  - 首次使用会要求选择AI模型和参数
  - 配置会自动缓存，下次启动时询问是否复用
  - 可通过 'config' 命令管理缓存配置

[STAT] 筛选条件支持:
  - 年份限制: "近年来"、"近3年"、"2020年以来"等
  - 影响因子: "高影响因子"、"顶级期刊"等  
  - 中科院分区: "1区"、"高级期刊"等
  - JCR分区: "Q1期刊"等

[SAVE] 输出格式: JSON 和 CSV 两种格式可选
        """)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='智能文献检索和筛选系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python smart_literature_search.py                    # 交互式模式（自动输出CSV和JSON）
  python smart_literature_search.py -q "糖尿病治疗研究" # 直接检索模式（自动输出CSV和JSON）
  python smart_literature_search.py -q "COVID-19疫苗" -n 20  # 指定结果数量
  python smart_literature_search.py -q "高血压治疗" --generate-outline  # 一键检索+大纲生成
  python smart_literature_search.py --outline-from-file literature.json --outline-topic "糖尿病治疗"  # 从已有文件生成大纲
        """
    )
    
    parser.add_argument('-q', '--query', help='直接检索的查询语句')
    parser.add_argument('-n', '--max-results', type=int, default=50, 
                       help='最大结果数量 (默认: 50)')
    parser.add_argument('--ai-config', help='指定AI配置名称')
    parser.add_argument('--non-interactive-ai', action='store_true',
                       help='非交互式AI配置（使用默认模型和参数）')
    parser.add_argument('--init-only', action='store_true', 
                       help='仅初始化系统，不进行检索')
    
    # 大纲生成相关参数
    parser.add_argument('--generate-outline', action='store_true',
                       help='生成综述大纲（需要JSON格式输出）')
    parser.add_argument('--outline-from-file', help='从现有JSON文件生成大纲')
    parser.add_argument('--outline-topic', help='大纲主题（配合--outline-from-file使用）')
    
    args = parser.parse_args()
    
    try:
        # 创建系统实例
        system = SmartLiteratureSearchSystem(
            args.ai_config, 
            interactive_ai=not args.non_interactive_ai
        )
        
        if args.init_only:
            # 仅初始化
            system.initialize_system()
            return
        
        # 从现有文件生成大纲
        if args.outline_from_file:
            if not args.outline_topic:
                print("[FAIL] 使用 --outline-from-file 时必须提供 --outline-topic")
                sys.exit(1)
            
            if not system.initialize_system():
                sys.exit(1)
            
            outline_file = system.generate_review_outline(
                args.outline_from_file, args.outline_topic
            )
            
            if outline_file:
                print(f"\n[NOTE] 大纲生成完成! 文件: {outline_file}")
            else:
                print("\n[FAIL] 大纲生成失败")
                sys.exit(1)
            return
        
        if args.query:
            # 直接检索模式
            if not system.initialize_system():
                sys.exit(1)
            
            # 如果需要生成大纲，使用一键流程
            if args.generate_outline:
                outline_file = system.search_and_generate_outline(
                    args.query, args.max_results
                )
                
                if outline_file:
                    print(f"\n🎉 检索和大纲生成完成!")
                    print(f"[NOTE] 综述大纲文件: {outline_file}")
                else:
                    print("\n[FAIL] 检索或大纲生成失败")
                    sys.exit(1)
            else:
                # 普通检索（同时生成CSV和JSON）
                search_result = system.search_literature(
                    args.query, args.max_results
                )
                
                if search_result:
                    if isinstance(search_result, tuple):
                        csv_file, json_file = search_result
                        print(f"\n🎉 检索完成!")
                        print(f"[STAT] CSV格式: {csv_file}")
                        print(f"[FILE] JSON格式: {json_file}")
                    else:
                        # 向后兼容
                        print(f"\n🎉 检索完成! 结果文件: {search_result}")
                else:
                    print("\n[FAIL] 检索失败或无结果")
                    sys.exit(1)
        else:
            # 交互式模式
            system.interactive_search()
    
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"程序运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()