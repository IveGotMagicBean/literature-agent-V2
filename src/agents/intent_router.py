"""
智能Agent路由器
根据用户输入自动识别意图并调用合适的工具
"""

from pathlib import Path
from typing import Dict, List, Optional, Generator
import re
import json


class IntentRouter:
    """意图识别和路由"""
    
    def __init__(self, llm, smart_agent, subfig_analyzer, ppt_agent, report_agent):
        self.llm = llm
        self.smart_agent = smart_agent
        self.subfig_analyzer = subfig_analyzer
        self.ppt_agent = ppt_agent
        self.report_agent = report_agent
    
    def route(self, user_input: str) -> Generator[Dict, None, None]:
        """
        智能路由用户请求
        
        Returns:
            Generator yielding events: {"type": "...", "content": "..."}
        """
        
        yield {"type": "thinking", "content": "🤔 正在理解你的需求..."}
        
        # 1. 识别意图
        intent = self._identify_intent(user_input)
        
        yield {"type": "thinking", "content": f"✓ 识别意图: {intent['action']}"}
        
        # 2. 根据意图路由到不同的处理器
        if intent['action'] == 'analyze_subfigures':
            yield from self._handle_subfigure_analysis(intent, user_input)
        
        elif intent['action'] == 'generate_subfigure_report':
            yield from self._handle_subfigure_report(intent, user_input)
        
        elif intent['action'] == 'generate_subfigure_ppt':
            yield from self._handle_subfigure_ppt(intent, user_input)
        
        elif intent['action'] == 'generate_report':
            yield from self._handle_general_report(intent, user_input)
        
        elif intent['action'] == 'generate_ppt':
            yield from self._handle_general_ppt(intent, user_input)
        
        elif intent['action'] == 'query_figure':
            # 普通图片查询，交给原有的query方法
            yield from self.smart_agent.query(user_input)
        
        else:
            # 一般问答
            yield from self.smart_agent.query(user_input)
    
    def _identify_intent(self, user_input: str) -> Dict:
        """识别用户意图"""
        
        user_lower = user_input.lower()
        
        # 提取Figure编号 - 改进的正则，支持多种格式
        fig_patterns = [
            r'figure\s*(\d+)',
            r'fig\.?\s*(\d+)',
            r'图\s*(\d+)',
            r'(\d+)[a-z]',  # 如 "1a", "2b"
        ]
        
        fig_num = None
        for pattern in fig_patterns:
            fig_match = re.search(pattern, user_lower)
            if fig_match:
                fig_num = int(fig_match.group(1))
                break
        
        # 提取子图标签 - 改进的正则
        subfig_patterns = [
            r'(\d+)\s*([a-z])',  # "1a", "2 b"
            r'[图figure]\s*\d+\s*([a-z])',  # "figure 1a", "图1a"
            r'子图\s*([a-z0-9])',  # "子图a", "子图1"
            r'([a-f])\s*(?:部分|子图)',  # "a部分", "a子图"
        ]
        
        subfig_label = None
        for pattern in subfig_patterns:
            subfig_match = re.search(pattern, user_lower)
            if subfig_match:
                groups = subfig_match.groups()
                subfig_label = groups[-1] if groups else None
                break
        
        # 关键词匹配 - 扩展关键词列表
        keywords = {
            'subfigure_analysis': [
                '子图', 'subfigure', 'sub-figure', 'sub figure',
                '每个', '所有子图', '拆分', '各个',
                '单独', '分别', '详细', '解说'
            ],
            'report': [
                '报告', 'report', '总结', '文档', 
                '分析报告', '解说', '说明'
            ],
            'ppt': [
                'ppt', 'powerpoint', '幻灯片', 'slides', 
                '演示', '汇报', 'presentation'
            ],
            'generate': [
                '生成', 'generate', '创建', 'create', 
                '做一个', '给我', '做个', '帮我做', '专门'
            ],
            'view': [
                '看', '查看', '主要', '显示', 
                'show', 'view', '讲', '是什么'
            ],
        }
        
        # 检查关键词
        has_subfig_keyword = any(kw in user_lower for kw in keywords['subfigure_analysis'])
        has_report_keyword = any(kw in user_lower for kw in keywords['report'])
        has_ppt_keyword = any(kw in user_lower for kw in keywords['ppt'])
        has_generate_keyword = any(kw in user_lower for kw in keywords['generate'])
        has_view_keyword = any(kw in user_lower for kw in keywords['view'])
        
        # 决策逻辑 - 优先级从高到低
        
        # 1. 明确提到子图+报告+figure编号
        if has_subfig_keyword and has_report_keyword and fig_num:
            return {
                'action': 'generate_subfigure_report',
                'figure_num': fig_num,
                'format': 'PDF'
            }
        
        # 2. 明确提到子图+PPT+figure编号
        elif has_subfig_keyword and has_ppt_keyword and fig_num:
            return {
                'action': 'generate_subfigure_ppt',
                'figure_num': fig_num
            }
        
        # 3. "对figureX做报告" + 包含子图相关词
        elif fig_num and has_report_keyword and (has_subfig_keyword or has_generate_keyword):
            return {
                'action': 'generate_subfigure_report',
                'figure_num': fig_num,
                'format': 'PDF'
            }
        
        # 4. "对figureX做PPT" + 包含子图相关词
        elif fig_num and has_ppt_keyword and (has_subfig_keyword or has_generate_keyword):
            return {
                'action': 'generate_subfigure_ppt',
                'figure_num': fig_num
            }
        
        # 5. 提到子图+figure编号（分析子图）
        elif has_subfig_keyword and fig_num:
            return {
                'action': 'analyze_subfigures',
                'figure_num': fig_num,
                'subfigure_label': subfig_label
            }
        
        # 6. 如果有子图标签（如"1a"），即使没有子图关键词也认为是子图查询
        elif subfig_label and fig_num:
            return {
                'action': 'analyze_subfigures',
                'figure_num': fig_num,
                'subfigure_label': subfig_label
            }
        
        # 7. 生成+报告
        elif has_generate_keyword and has_report_keyword:
            return {
                'action': 'generate_report',
                'format': 'PDF'
            }
        
        # 8. 生成+PPT
        elif has_generate_keyword and has_ppt_keyword:
            return {
                'action': 'generate_ppt'
            }
        
        # 9. 只提到PPT
        elif has_ppt_keyword:
            return {
                'action': 'generate_ppt'
            }
        
        # 10. figure编号（普通查询）
        elif fig_num:
            return {
                'action': 'query_figure',
                'figure_num': fig_num,
                'subfigure_label': subfig_label
            }
        
        # 11. 一般查询
        else:
            return {'action': 'general_query'}
    
    def _handle_subfigure_analysis(self, intent: Dict, user_input: str) -> Generator[Dict, None, None]:
        """处理子图分析请求"""
        
        fig_num = intent['figure_num']
        subfig_label = intent.get('subfigure_label')
        
        try:
            if subfig_label:
                # 分析单个子图
                yield {"type": "thinking", "content": f"🔍 正在分析子图 {fig_num}{subfig_label}..."}
                
                result = self.subfig_analyzer.analyze_subfigure(fig_num, subfig_label)
                
                # 返回图片
                yield {
                    "type": "figure",
                    "data": {
                        "path": result['path'],
                        "label": f"Figure {fig_num}{subfig_label}",
                        "page": None
                    }
                }
                
                # 返回分析结果
                answer = f"""**图表类型**: {result['chart_type']}

**详细分析**:
{result['analysis']}

**文中描述**:
{result['context'] if result['context'] else '（未找到明确的文中描述）'}
"""
                yield {"type": "answer", "content": answer}
            
            else:
                # 分析所有子图
                yield {"type": "thinking", "content": f"🔍 正在分析 Figure {fig_num} 的所有子图..."}
                
                results = self.subfig_analyzer.analyze_all_subfigures(fig_num)
                
                if not results:
                    yield {"type": "answer", "content": f"Figure {fig_num} 没有找到子图或分析失败。"}
                    return
                
                # 返回所有子图
                for result in results:
                    yield {
                        "type": "figure",
                        "data": {
                            "path": result['path'],
                            "label": f"Figure {result['figure']}{result['subfigure']}",
                            "page": None
                        }
                    }
                
                # 汇总分析
                summary = f"**Figure {fig_num} 包含 {len(results)} 个子图**:\n\n"
                for result in results:
                    summary += f"**子图 {result['figure']}{result['subfigure']}** ({result['chart_type']})\n"
                    summary += f"{result['analysis'][:200]}...\n\n"
                
                summary += f"\n💡 **提示**: 你可以说 \"对Figure {fig_num}的子图生成报告\" 来获取详细的PDF报告。"
                
                yield {"type": "answer", "content": summary}
        
        except Exception as e:
            yield {"type": "error", "content": f"分析失败: {str(e)}"}
    
    def _handle_subfigure_report(self, intent: Dict, user_input: str) -> Generator[Dict, None, None]:
        """处理子图报告生成请求"""
        
        fig_num = intent['figure_num']
        output_format = intent.get('format', 'PDF')
        
        try:
            yield {"type": "thinking", "content": f"📝 正在生成 Figure {fig_num} 子图分析报告..."}
            
            # 先检查是否能拆分出子图
            yield {"type": "thinking", "content": f"🔍 检查 Figure {fig_num} 的子图..."}
            
            subfigs = self.subfig_analyzer.ensure_subfigures_split(fig_num)
            
            if not subfigs:
                # 没有子图，给出提示
                yield {"type": "thinking", "content": f"⚠️ Figure {fig_num} 未检测到子图"}
                
                answer = f"""**Figure {fig_num} 未检测到子图**

可能的原因：
1. 这个Figure本身就是单张图，不包含子图
2. figure-separator未安装或未启用

💡 **建议**:
- 如果这是单张图，可以说"生成阅读报告"来生成包含所有Figure的报告
- 如果需要子图拆分功能，请安装figure-separator

当前Figure {fig_num}的路径: {self.smart_agent.figure_map[fig_num]["path"]}
"""
                yield {"type": "answer", "content": answer}
                
                # 返回主图
                yield {
                    "type": "figure",
                    "data": {
                        "path": self.smart_agent.figure_map[fig_num]["path"],
                        "label": f"Figure {fig_num} (完整图)",
                        "page": self.smart_agent.figure_map[fig_num].get("page")
                    }
                }
                return
            
            # 有子图，继续生成报告
            yield {"type": "thinking", "content": f"✓ 检测到 {len(subfigs)} 个子图，开始生成报告..."}
            
            # 使用subfigure_agent生成报告
            try:
                file_path = self.subfig_analyzer.generate_report(fig_num, output_format)
            except AttributeError:
                # 如果没有generate_report方法，先简化处理
                yield {"type": "error", "content": "子图报告生成功能开发中"}
                return
            
            yield {"type": "thinking", "content": f"✅ 报告生成完成!"}
            
            # 返回下载链接
            answer = f"""**Figure {fig_num} 子图分析报告已生成！**

📄 格式: {output_format}
📁 路径: {file_path}
🔢 包含: {len(subfigs)} 个子图的详细分析

报告包含：
- 每个子图的类型识别
- 详细内容分析
- 文中描述提取

点击下载链接获取完整报告。
"""
            
            yield {"type": "answer", "content": answer}
            yield {
                "type": "download",
                "data": {
                    "path": file_path,
                    "url": f"/api/download?path={file_path}"
                }
            }
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {"type": "error", "content": f"报告生成失败: {str(e)}"}

    
    def _handle_subfigure_ppt(self, intent: Dict, user_input: str) -> Generator[Dict, None, None]:
        """处理子图PPT生成请求"""
        
        fig_num = intent['figure_num']
        
        try:
            yield {"type": "thinking", "content": f"📊 正在生成 Figure {fig_num} 子图分析PPT..."}
            
            # 导入生成函数
            from subfigure_generator import generate_subfigure_ppt
            
            # 生成PPT
            file_path = generate_subfigure_ppt(self.subfig_analyzer, fig_num)
            
            yield {"type": "thinking", "content": f"✅ PPT生成完成!"}
            
            # 返回下载链接
            answer = f"""**Figure {fig_num} 子图分析PPT已生成！**

📊 文件: {Path(file_path).name}
📁 路径: {file_path}

PPT包含：
- 标题页
- 每个子图单独一页
- 左侧展示图片，右侧展示详细分析

非常适合用于组会汇报！
"""
            
            yield {"type": "answer", "content": answer}
            yield {
                "type": "download",
                "data": {
                    "path": file_path,
                    "url": f"/api/download?path={file_path}"
                }
            }
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {"type": "error", "content": f"PPT生成失败: {str(e)}"}
    
    def _handle_general_report(self, intent: Dict, user_input: str) -> Generator[Dict, None, None]:
        """处理一般报告生成"""
        
        output_format = intent.get('format', 'PDF')
        
        try:
            yield {"type": "thinking", "content": f"📝 正在生成阅读报告..."}
            
            file_path = self.report_agent.generate(
                report_type="详细报告",
                output_format=output_format,
                include_figures=True,
                max_figures=5
            )
            
            yield {"type": "thinking", "content": f"✅ 报告生成完成!"}
            
            answer = f"""**阅读报告已生成！**

📄 格式: {output_format}
📁 路径: {file_path}

报告包含：
- 基本信息
- 研究背景与动机
- 研究方法
- 实验与结果
- 讨论与结论
- 关键图表（带图片）
"""
            
            yield {"type": "answer", "content": answer}
            yield {
                "type": "download",
                "data": {
                    "path": file_path,
                    "url": f"/api/download?path={file_path}"
                }
            }
        
        except Exception as e:
            yield {"type": "error", "content": f"报告生成失败: {str(e)}"}
    
    def _handle_general_ppt(self, intent: Dict, user_input: str) -> Generator[Dict, None, None]:
        """处理一般PPT生成"""
        
        try:
            yield {"type": "thinking", "content": f"📊 正在生成PPT..."}
            
            file_path = self.ppt_agent.generate(
                template="学术风格",
                language="中文",
                include_figures=True,
                max_figures=5
            )
            
            yield {"type": "thinking", "content": f"✅ PPT生成完成!"}
            
            answer = f"""**PPT已生成！**

📊 文件: {Path(file_path).name}
📁 路径: {file_path}

PPT包含：
- 标题页
- 研究背景
- 研究动机
- 方法
- 关键图表（3-5页）
- 结果
- 结论
"""
            
            yield {"type": "answer", "content": answer}
            yield {
                "type": "download",
                "data": {
                    "path": file_path,
                    "url": f"/api/download?path={file_path}"
                }
            }
        
        except Exception as e:
            yield {"type": "error", "content": f"PPT生成失败: {str(e)}"}


__all__ = ["IntentRouter"]
