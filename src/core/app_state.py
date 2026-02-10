"""
应用状态管理
统一管理全局状态和Agent实例
"""

from pathlib import Path
import toml
from typing import Optional


class AppState:
    """全局应用状态"""
    
    # Agent实例
    smart_agent: Optional[object] = None
    ppt_agent: Optional[object] = None
    report_agent: Optional[object] = None
    subfigure_agent: Optional[object] = None
    intent_router: Optional[object] = None
    
    # LLM实例
    llm: Optional[object] = None
    
    # 配置
    config: Optional[dict] = None
    
    @classmethod
    async def initialize(cls):
        """初始化应用状态"""
        # 创建必要目录
        Path("static").mkdir(exist_ok=True)
        Path("uploads").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)
        Path("data/images").mkdir(exist_ok=True)
        
        # 加载配置
        config_path = Path("config/config.toml")
        with open(config_path, "r") as f:
            cls.config = toml.load(f)
        
        # 创建LLM实例
        from src.core.llm_factory import create_llm
        cls.llm = create_llm(cls.config["llm"])
        
        # 创建Agent实例
        from src.agents.smart_agent import SmartAgent
        from src.agents.ppt_agent import EnhancedPPTAgent
        from src.agents.report_agent import EnhancedReportAgent
        from src.agents.subfigure_agent import SubfigureAnalyzer
        from src.agents.intent_router import IntentRouter
        
        data_dir = cls.config["system"]["data_dir"]
        cls.smart_agent = SmartAgent(cls.llm, data_dir)
        cls.ppt_agent = EnhancedPPTAgent(cls.llm, cls.smart_agent)
        cls.report_agent = EnhancedReportAgent(cls.llm, cls.smart_agent)
        cls.subfigure_agent = SubfigureAnalyzer(cls.llm, cls.smart_agent)
        cls.intent_router = IntentRouter(
            cls.llm,
            cls.smart_agent,
            cls.subfigure_agent,
            cls.ppt_agent,
            cls.report_agent
        )
        
        print(f"   LLM Provider: {cls.config['llm']['provider']}")
        print(f"   Data Directory: {data_dir}")
        print(f"   Auto Analyze: {cls.config['system']['auto_analyze']}")
    
    @classmethod
    async def cleanup(cls):
        """清理资源"""
        print("正在清理资源...")
    
    @classmethod
    def get_agent(cls):
        """获取智能Agent"""
        return cls.smart_agent
    
    @classmethod
    def get_router(cls):
        """获取意图路由器"""
        return cls.intent_router
