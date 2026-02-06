#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能文献系统CLI客户端
提供虚拟环境管理、依赖安装、项目启动、AI配置等功能
"""

import os
import sys
import subprocess
import venv
import shutil
import json
import yaml
import argparse
import platform
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


class IntelligentLiteratureCLI:
    """智能文献系统CLI客户端"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent  # 修正为真正的项目根目录
        self.venv_path = self.project_root / "venv"
        self.requirements_file = self.project_root / "requirements.txt"
        self.env_file = self.project_root / ".env"
        self.env_example_file = self.project_root / ".env.example"
        # 向后兼容属性: ai_config_file 现在指向 .env
        self.ai_config_file = self.env_file
        self.prompts_config_file = self.project_root / "prompts" / "prompts_config.yaml"
        self.data_dir = self.project_root / "data"

        # 确保必要的目录存在
        self.data_dir.mkdir(exist_ok=True)
        (self.project_root / "prompts").mkdir(exist_ok=True)

        # 支持的Python版本
        self.min_python_version = (3, 8)
        self.recommended_python_version = (3, 9)

    @staticmethod
    def _is_interactive_terminal() -> bool:
        """检测当前是否为可交互终端。"""
        stdin = getattr(sys, "stdin", None)
        return bool(stdin and hasattr(stdin, "isatty") and stdin.isatty())

    def _prompt_yes_no(self, message: str, default: bool = False) -> bool:
        """
        安全的Y/N提示。
        在非交互环境或读取输入失败时，返回默认值。
        """
        if not self._is_interactive_terminal():
            return default

        try:
            choice = input(message).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return default

        if not choice:
            return default
        return choice in {"y", "yes"}

    def _get_preferred_python(self) -> str:
        """优先返回虚拟环境Python；不存在时回退到当前解释器。"""
        if platform.system() == "Windows":
            venv_python = self.venv_path / "Scripts" / "python.exe"
        else:
            venv_python = self.venv_path / "bin" / "python"

        if venv_python.exists():
            return str(venv_python)
        return sys.executable
    
    def check_python_version(self) -> Tuple[bool, str]:
        """检查Python版本"""
        current_version = sys.version_info[:2]
        
        if current_version < self.min_python_version:
            return False, f"Python版本过低: {current_version[0]}.{current_version[1]} (最低要求: {self.min_python_version[0]}.{self.min_python_version[1]})"
        
        if current_version < self.recommended_python_version:
            return True, f"Python版本: {current_version[0]}.{current_version[1]} (推荐: {self.recommended_python_version[0]}.{self.recommended_python_version[1]})"
        
        return True, f"Python版本: {current_version[0]}.{current_version[1]} (推荐版本)"
    
    def detect_virtual_environment(self) -> Dict[str, Any]:
        """检测虚拟环境状态"""
        result = {
            "venv_exists": self.venv_path.exists(),
            "venv_active": hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix),
            "python_executable": sys.executable,
            "venv_python": None,
            "venv_path": str(self.venv_path),
            "platform": platform.system(),
            "status": "未创建"
        }
        
        if result["venv_exists"]:
            # 检测不同平台的Python可执行文件路径
            if platform.system() == "Windows":
                python_exe = self.venv_path / "Scripts" / "python.exe"
                pip_exe = self.venv_path / "Scripts" / "pip.exe"
            else:
                python_exe = self.venv_path / "bin" / "python"
                pip_exe = self.venv_path / "bin" / "pip"
            
            result["venv_python"] = str(python_exe) if python_exe.exists() else None
            result["venv_pip"] = str(pip_exe) if pip_exe.exists() else None
            
            if result["venv_active"] or sys.executable == str(python_exe):
                result["status"] = "已激活"
            elif result["venv_python"]:
                result["status"] = "已创建但未激活"
            else:
                result["status"] = "已创建但可能损坏"
        
        return result
    
    def create_virtual_environment(self) -> bool:
        """创建虚拟环境"""
        try:
            print(f"正在创建虚拟环境: {self.venv_path}")
            venv.create(self.venv_path, with_pip=True)
            print("虚拟环境创建成功")
            return True
        except Exception as e:
            print(f"创建虚拟环境失败: {e}")
            return False
    
    def activate_virtual_environment(self) -> Optional[str]:
        """生成虚拟环境激活命令"""
        if not self.venv_path.exists():
            print("虚拟环境不存在，请先创建虚拟环境")
            return None
        
        if platform.system() == "Windows":
            return str(self.venv_path / "Scripts" / "activate")
        else:
            return f"source {self.venv_path / 'bin' / 'activate'}"
    
    def get_requirements_status(self) -> Dict[str, Any]:
        """获取依赖包状态"""
        status = {
            "requirements_file": self.requirements_file,
            "file_exists": self.requirements_file.exists(),
            "packages": [],
            "missing_packages": [],
            "outdated_packages": [],
            "total_packages": 0
        }
        
        if not status["file_exists"]:
            return status
        
        try:
            with open(self.requirements_file, 'r', encoding='utf-8') as f:
                requirements = f.read().strip().split('\n')
            
            requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]
            status["total_packages"] = len(requirements)
            
            # 检查已安装的包
            installed_packages = self._get_installed_packages()
            
            for req in requirements:
                pkg_name, pkg_version = self._parse_requirement(req)
                status["packages"].append({
                    "name": pkg_name,
                    "required_version": pkg_version,
                    "installed": pkg_name in installed_packages,
                    "installed_version": installed_packages.get(pkg_name, {}).get("version"),
                    "up_to_date": self._check_version_up_to_date(pkg_version, installed_packages.get(pkg_name, {}).get("version"))
                })
                
                if pkg_name not in installed_packages:
                    status["missing_packages"].append(pkg_name)
                elif not status["packages"][-1]["up_to_date"]:
                    status["outdated_packages"].append(pkg_name)
        
        except Exception as e:
            print(f"读取依赖文件失败: {e}")
        
        return status
    
    def _get_installed_packages(self) -> Dict[str, Dict[str, str]]:
        """获取已安装的包信息"""
        try:
            python_exe = self._get_preferred_python()
            result = subprocess.run([python_exe, "-m", "pip", "list", "--format=json"],
                                  capture_output=True, text=True, check=True)
            packages = json.loads(result.stdout)
            return {pkg["name"].lower(): {"version": pkg["version"]} for pkg in packages}
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
            return {}
    
    def _parse_requirement(self, requirement: str) -> Tuple[str, Optional[str]]:
        """解析依赖包要求"""
        # 支持 name[extra]>=1.2、name==1.0、name 等常见格式
        match = re.match(r'^([a-zA-Z0-9_.-]+)(?:\[[^\]]+\])?\s*([><=!~]=?.*)?$', requirement.strip())
        if match:
            pkg_name = match.group(1).lower()
            version_spec = match.group(2)
            return pkg_name, version_spec
        return requirement.strip().lower(), None
    
    def _check_version_up_to_date(self, required_version: Optional[str], installed_version: Optional[str]) -> bool:
        """检查版本是否满足要求"""
        if not required_version or not installed_version:
            return True

        def parse_version(v: str) -> tuple:
            """将版本字符串解析为可比较的元组"""
            # 移除非数字后缀 (如 a1, b2, rc1)
            import re
            v = re.split(r'[a-zA-Z]', v)[0]
            parts = v.split('.')
            result = []
            for p in parts:
                try:
                    result.append(int(p))
                except ValueError:
                    result.append(0)
            # 确保至少有3个部分
            while len(result) < 3:
                result.append(0)
            return tuple(result)

        try:
            installed_tuple = parse_version(installed_version)

            # 简化的版本检查
            if required_version.startswith(">="):
                required_tuple = parse_version(required_version[2:])
                return installed_tuple >= required_tuple
            elif required_version.startswith("=="):
                required_tuple = parse_version(required_version[2:])
                return installed_tuple == required_tuple
            elif required_version.startswith("<="):
                required_tuple = parse_version(required_version[2:])
                return installed_tuple <= required_tuple
            elif required_version.startswith(">"):
                required_tuple = parse_version(required_version[1:])
                return installed_tuple > required_tuple
            elif required_version.startswith("<"):
                required_tuple = parse_version(required_version[1:])
                return installed_tuple < required_tuple
            elif required_version.startswith("!="):
                required_tuple = parse_version(required_version[2:])
                return installed_tuple != required_tuple
        except Exception:
            pass

        return True
    
    def install_dependencies(self, upgrade: bool = False) -> bool:
        """安装依赖包"""
        if not self.requirements_file.exists():
            print(f"依赖文件不存在: {self.requirements_file}")
            return False

        try:
            python_exe = self._get_preferred_python()
            print("正在安装依赖包...")
            cmd = [python_exe, "-m", "pip", "install", "-r", str(self.requirements_file)]
            if upgrade:
                cmd.append("--upgrade")
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("依赖包安装成功")
            return True
        except subprocess.CalledProcessError as e:
            print(f"依赖包安装失败: {e}")
            print(f"错误输出: {e.stderr}")
            return False
    
    def check_ai_config(self) -> Dict[str, Any]:
        """检查AI配置状态（从环境变量）"""
        # 导入新的配置模块
        try:
            src_path = str(self.project_root / "src")
            if src_path not in sys.path:
                sys.path.insert(0, src_path)
            from ai_config import get_ai_config
            ai_config = get_ai_config(force_reload=True)
        except ImportError:
            ai_config = None

        config_status = {
            "env_file": self.env_file,
            "file_exists": self.env_file.exists(),
            "services": [],
            "default_service": None,
            "valid_services": 0,
            "invalid_services": 0
        }

        if ai_config is None:
            return config_status

        # 获取所有服务配置
        for service_name in ai_config.list_services():
            service = ai_config.get_service(service_name)
            if service:
                placeholder_checker = getattr(ai_config, "_is_placeholder", None)
                is_placeholder = callable(placeholder_checker) and placeholder_checker(service.api_key)
                service_info = {
                    "name": service_name,
                    "status": service.status,
                    "api_type": service.api_type,
                    "has_api_key": bool(service.api_key) and not is_placeholder,
                    "has_base_url": bool(service.base_url),
                    "has_model": bool(service.model),
                    "api_key": service.api_key,
                    "base_url": service.base_url,
                    "default_model": service.model,
                    "timeout": service.timeout
                }

                if service_info["has_api_key"] and service.is_active():
                    service_info["valid"] = True
                    config_status["valid_services"] += 1
                else:
                    service_info["valid"] = False
                    config_status["invalid_services"] += 1

                config_status["services"].append(service_info)

        active = ai_config.get_active_service()
        if active:
            config_status["default_service"] = active.name

        return config_status
    
    def check_prompts_config(self) -> Dict[str, Any]:
        """检查提示词配置状态"""
        config_status = {
            "config_file": self.prompts_config_file,
            "file_exists": self.prompts_config_file.exists(),
            "prompt_types": [],
            "total_prompts": 0,
            "valid_prompts": 0
        }
        
        if not config_status["file_exists"]:
            return config_status
        
        try:
            with open(self.prompts_config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if isinstance(config_data, dict):
                for prompt_type, prompts in config_data.items():
                    type_info = {
                        "type": prompt_type,
                        "prompt_count": len(prompts) if isinstance(prompts, dict) else 0,
                        "valid_prompts": 0
                    }
                    
                    if isinstance(prompts, dict):
                        for prompt_name, prompt_content in prompts.items():
                            if isinstance(prompt_content, str) and prompt_content.strip():
                                type_info["valid_prompts"] += 1
                    
                    config_status["prompt_types"].append(type_info)
                    config_status["total_prompts"] += type_info["prompt_count"]
                    config_status["valid_prompts"] += type_info["valid_prompts"]
        
        except Exception as e:
            print(f"读取提示词配置文件失败: {e}")
        
        return config_status
    
    def setup_ai_config(self) -> bool:
        """设置AI配置（创建.env文件）"""
        print("AI配置设置向导")
        print("=" * 50)

        # 如果.env文件已存在，先备份
        if self.env_file.exists():
            backup_file = self.env_file.with_suffix(f'.env.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            shutil.copy2(self.env_file, backup_file)
            print(f"已备份现有配置文件: {backup_file}")

        # 复制.env.example到.env
        if self.env_example_file.exists():
            try:
                shutil.copy2(self.env_example_file, self.env_file)
                print(f"AI配置文件已创建: {self.env_file}")
                print("请编辑 .env 文件，添加您的API密钥和服务配置")
                print("\n配置项说明:")
                print("  - OPENAI_API_KEY: OpenAI API密钥")
                print("  - OPENAI_BASE_URL: API端点地址")
                print("  - DEFAULT_AI_SERVICE: 默认使用的服务")
                return True
            except Exception as e:
                print(f"创建配置文件失败: {e}")
                return False
        else:
            # 创建基础.env文件
            default_env = """# AI服务配置
# 请填入您的API密钥

# OpenAI配置
OPENAI_API_KEY=sk-your_key_here
OPENAI_BASE_URL=https://api.openai.com/
OPENAI_MODEL=gpt-4-turbo

# 默认服务
DEFAULT_AI_SERVICE=openai

# 通用设置
AI_REQUEST_TIMEOUT=300
AI_MAX_RETRIES=3
"""
            try:
                with open(self.env_file, 'w', encoding='utf-8') as f:
                    f.write(default_env)
                print(f"AI配置文件已创建: {self.env_file}")
                print("请编辑 .env 文件，添加您的API密钥")
                return True
            except Exception as e:
                print(f"创建AI配置文件失败: {e}")
                return False
    
    def setup_prompts_config(self) -> bool:
        """设置提示词配置"""
        print("提示词配置设置向导")
        print("=" * 50)
        
        # 创建默认提示词配置
        default_prompts = {
            "pubmed_search": {
                "default": "请搜索关于{query}的最新研究文献，重点关注过去5年的重要进展",
                "comprehensive": "请进行全面的文献检索，包括{query}相关的所有研究，并按重要性排序",
                "recent": "请搜索最近1-2年内关于{query}的最新研究进展"
            },
            "literature_filter": {
                "default": "请根据以下标准筛选文献：高质量、相关性、最新性",
                "strict": "请严格筛选文献，只保留高质量且高度相关的研究",
                "comprehensive": "请全面筛选文献，保留所有相关的研究，包括综述和原始研究"
            },
            "review_outline": {
                "default": "请基于以下文献生成一个全面的综述大纲，包括背景、方法、结果和讨论",
                "structured": "请生成结构化的综述大纲，包含明确的章节和子章节",
                "detailed": "请生成详细的综述大纲，每个部分都要有具体的内容要求"
            },
            "review_generation": {
                "default": "请基于以下大纲和文献，撰写一篇全面的学术综述",
                "academic": "请撰写一篇学术严谨的综述文章，包含完整的引用和参考文献",
                "concise": "请撰写一篇简洁的综述，突出最重要的发现和结论"
            }
        }
        
        # 确保prompts目录存在
        self.prompts_config_file.parent.mkdir(exist_ok=True)
        
        # 如果配置文件已存在，先备份
        if self.prompts_config_file.exists():
            backup_file = self.prompts_config_file.with_suffix(f'.yaml.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            shutil.copy2(self.prompts_config_file, backup_file)
            print(f"已备份现有提示词配置文件: {backup_file}")
        
        try:
            with open(self.prompts_config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_prompts, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"提示词配置文件已创建: {self.prompts_config_file}")
            print("您可以根据需要编辑提示词配置文件")
            return True
        except Exception as e:
            print(f"创建提示词配置文件失败: {e}")
            return False
    
    def start_project(self, mode: str = "interactive") -> bool:
        """启动项目"""
        venv_status = self.detect_virtual_environment()
        
        if not venv_status["venv_active"] and not venv_status.get("venv_python"):
            print("请先激活虚拟环境")
            activate_cmd = self.activate_virtual_environment()
            if activate_cmd:
                print(f"激活命令: {activate_cmd}")
            return False
        
        # 检查依赖
        req_status = self.get_requirements_status()
        if req_status["missing_packages"]:
            print(f"缺少依赖包: {', '.join(req_status['missing_packages'])}")
            should_install = self._prompt_yes_no("是否安装缺少的依赖包? (y/n): ", default=False)
            if should_install and not self.install_dependencies():
                return False
        
        # 检查AI配置
        ai_config = self.check_ai_config()
        if ai_config["valid_services"] == 0:
            print("没有有效的AI服务配置")
            should_setup = self._prompt_yes_no("是否配置AI服务? (y/n): ", default=False)
            if should_setup and not self.setup_ai_config():
                return False
        
        # 启动项目
        try:
            python_exe = self._get_preferred_python()
            if mode == "interactive":
                cmd = [python_exe, str(self.project_root / "src" / "start.py")]
            else:
                cmd = [python_exe, str(self.project_root / "src" / "intelligent_literature_system.py")]
            
            print(f"启动项目: {' '.join(cmd)}")
            result = subprocess.run(cmd)
            return result.returncode == 0
        except Exception as e:
            print(f"启动项目失败: {e}")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能文献系统CLI客户端")
    parser.add_argument("--check", action="store_true", help="检查系统状态")
    parser.add_argument("--setup-venv", action="store_true", help="创建虚拟环境")
    parser.add_argument("--install-deps", action="store_true", help="安装依赖包")
    parser.add_argument("--upgrade-deps", action="store_true", help="升级依赖包")
    parser.add_argument("--setup-ai", action="store_true", help="重置AI配置")
    parser.add_argument("--setup-prompts", action="store_true", help="设置提示词配置")
    parser.add_argument("--start", action="store_true", help="启动项目")
    parser.add_argument("--mode", choices=["interactive", "batch"], default="interactive", help="启动模式")
    
    args = parser.parse_args()
    
    cli = IntelligentLiteratureCLI()
    
    # 检查Python版本
    version_ok, version_msg = cli.check_python_version()
    print(f"Python版本检查: {version_msg}")
    if not version_ok:
        print("请升级Python版本后重试")
        return
    
    if args.check or len(sys.argv) == 1:
        # 显示系统状态
        print("\n" + "=" * 60)
        print("智能文献系统状态检查")
        print("=" * 60)
        
        # 虚拟环境状态
        venv_status = cli.detect_virtual_environment()
        print(f"\n虚拟环境状态: {venv_status['status']}")
        print(f"  虚拟环境路径: {cli.venv_path}")
        print(f"  当前Python解释器: {venv_status['python_executable']}")
        if venv_status['venv_python']:
            print(f"  虚拟环境Python: {venv_status['venv_python']}")
        
        # 依赖包状态
        req_status = cli.get_requirements_status()
        print(f"\n依赖包状态:")
        print(f"  依赖文件: {req_status['requirements_file']}")
        if req_status['file_exists']:
            print(f"  总包数: {req_status['total_packages']}")
            print(f"  缺少包: {len(req_status['missing_packages'])}")
            print(f"  过期包: {len(req_status['outdated_packages'])}")
        else:
            print("  依赖文件不存在")
        
        # AI配置状态
        ai_config = cli.check_ai_config()
        print(f"\nAI配置状态:")
        print(f"  配置文件: {ai_config['env_file']}")
        if ai_config['file_exists']:
            print(f"  有效服务: {ai_config['valid_services']}")
            print(f"  无效服务: {ai_config['invalid_services']}")
            if ai_config['default_service']:
                print(f"  默认服务: {ai_config['default_service']}")
        else:
            print("  AI配置文件不存在")
        
        # 提示词配置状态
        prompts_config = cli.check_prompts_config()
        print(f"\n提示词配置状态:")
        print(f"  配置文件: {prompts_config['config_file']}")
        if prompts_config['file_exists']:
            print(f"  提示词类型: {len(prompts_config['prompt_types'])}")
            print(f"  总提示词: {prompts_config['total_prompts']}")
            print(f"  有效提示词: {prompts_config['valid_prompts']}")
        else:
            print("  提示词配置文件不存在")
        
        print("\n" + "=" * 60)
        print("使用 --help 查看可用命令")
    
    if args.setup_venv:
        print("\n创建虚拟环境...")
        if cli.create_virtual_environment():
            print("虚拟环境创建成功")
            activate_cmd = cli.activate_virtual_environment()
            if activate_cmd:
                print(f"激活命令: {activate_cmd}")
        else:
            print("虚拟环境创建失败")
    
    if args.install_deps or args.upgrade_deps:
        print(f"\n{'安装' if args.install_deps else '升级'}依赖包...")
        cli.install_dependencies(upgrade=args.upgrade_deps)
    
    if args.setup_ai:
        print("\n重置AI配置...")
        cli.setup_ai_config()
    
    if args.setup_prompts:
        print("\n设置提示词配置...")
        cli.setup_prompts_config()
    
    if args.start:
        print(f"\n启动项目 ({args.mode}模式)...")
        cli.start_project(args.mode)


if __name__ == "__main__":
    main()
