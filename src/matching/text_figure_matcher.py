"""
文本-图片匹配模块
建立文本描述和图片之间的精确映射
"""

from typing import Dict, List, Optional
from collections import defaultdict


class TextFigureMatcher:
    """文本和图片的匹配器"""
    
    def __init__(self):
        # 映射结构:
        # {
        #   "1": {"figure": {...}, "subfigures": {"a": {...}, "b": {...}}, "mentions": [...]},
        #   "2": {...}
        # }
        self.figure_map = {}
    
    def build_mapping(
        self,
        texts: List[Dict],  # [{"page": 1, "content": "..."}, ...]
        figures: List[Dict],  # [{"figure_number": 1, "path": "...", "subfigures": [...]}, ...]
        references: List[Dict]  # [{"figure": 1, "subfigure": "a", "context": "...", "page": 3}, ...]
    ):
        """
        构建文本和图片的映射
        
        Args:
            texts: 文本列表
            figures: 图片列表
            references: 从文本中提取的引用列表
        """
        # 1. 索引所有图片
        for fig in figures:
            fig_num = str(fig["figure_number"])
            
            self.figure_map[fig_num] = {
                "main": fig["main"],
                "subfigures": {},
                "mentions": []
            }
            
            # 索引子图
            for subfig in fig.get("subfigures", []):
                label = subfig["label"]
                self.figure_map[fig_num]["subfigures"][label] = subfig
        
        # 2. 添加引用信息
        for ref in references:
            fig_num = str(ref["figure"])
            subfig_label = ref.get("subfigure")
            
            if fig_num not in self.figure_map:
                # 图片未找到，跳过
                continue
            
            mention = {
                "page": ref.get("page"),
                "context": ref.get("context", ""),
                "subfigure": subfig_label,
                "text": ref.get("text", "")
            }
            
            self.figure_map[fig_num]["mentions"].append(mention)
    
    def find_figure(self, query: str) -> Optional[Dict]:
        """
        根据查询找到最相关的图片
        
        Args:
            query: 查询文本，如 "Figure 1a" 或 "哪张图展示了架构"
            
        Returns:
            {
                "figure_number": 1,
                "subfigure": "a",
                "path": "...",
                "contexts": ["...", "..."],
                "relevance_score": 0.95
            }
        """
        import re
        
        query_lower = query.lower()
        
        # 方法1: 直接提到图号
        # 匹配 "figure 1a", "fig 1a", "图1a" 等
        patterns = [
            r'[Ff]igure?\s+(\d+)\s*([a-z])?',
            r'[Ff]ig\.?\s+(\d+)\s*([a-z])?',
            r'图\s*(\d+)\s*([a-z])?'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                fig_num = match.group(1)
                subfig = match.group(2) if len(match.groups()) > 1 else None
                
                return self._get_figure_info(fig_num, subfig)
        
        # 方法2: 语义匹配（基于关键词）
        best_match = None
        best_score = 0.0
        
        for fig_num, fig_data in self.figure_map.items():
            for mention in fig_data["mentions"]:
                score = self._calculate_similarity(query_lower, mention["context"].lower())
                
                if score > best_score:
                    best_score = score
                    best_match = {
                        "figure_number": int(fig_num),
                        "subfigure": mention.get("subfigure"),
                        "mention": mention
                    }
        
        if best_score > 0.3:  # 阈值
            return self._get_figure_info(
                str(best_match["figure_number"]),
                best_match["subfigure"]
            )
        
        return None
    
    def _get_figure_info(self, fig_num: str, subfig_label: Optional[str]) -> Optional[Dict]:
        """获取图片详细信息"""
        if fig_num not in self.figure_map:
            return None
        
        fig_data = self.figure_map[fig_num]
        
        # 如果指定了子图
        if subfig_label and subfig_label in fig_data["subfigures"]:
            subfig = fig_data["subfigures"][subfig_label]
            
            # 收集相关上下文
            contexts = [
                m["context"] for m in fig_data["mentions"]
                if m.get("subfigure") == subfig_label
            ]
            
            return {
                "figure_number": int(fig_num),
                "subfigure": subfig_label,
                "path": subfig["path"],
                "label": subfig["full_label"],
                "contexts": contexts[:3],  # 最多3个上下文
                "type": "subfigure"
            }
        
        # 否则返回主图
        main_fig = fig_data["main"]
        
        # 收集所有上下文
        contexts = [m["context"] for m in fig_data["mentions"]]
        
        return {
            "figure_number": int(fig_num),
            "subfigure": None,
            "path": main_fig["path"],
            "label": main_fig["label"],
            "contexts": contexts[:3],
            "has_subfigures": main_fig.get("has_subfigures", False),
            "type": "main"
        }
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        简单的文本相似度计算（基于词袋模型）
        """
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if len(words1) == 0:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        # Jaccard相似度
        jaccard = len(intersection) / len(union) if len(union) > 0 else 0.0
        
        # 重叠比例
        overlap = len(intersection) / len(words1) if len(words1) > 0 else 0.0
        
        return (jaccard + overlap) / 2
    
    def get_all_figures(self) -> List[Dict]:
        """获取所有图片的列表"""
        all_figures = []
        
        for fig_num, fig_data in self.figure_map.items():
            # 主图
            main = fig_data["main"]
            all_figures.append({
                "figure_number": int(fig_num),
                "path": main["path"],
                "label": main["label"],
                "type": "main",
                "has_subfigures": len(fig_data["subfigures"]) > 0
            })
            
            # 子图
            for label, subfig in fig_data["subfigures"].items():
                all_figures.append({
                    "figure_number": int(fig_num),
                    "subfigure": label,
                    "path": subfig["path"],
                    "label": subfig["full_label"],
                    "type": "subfigure"
                })
        
        return sorted(all_figures, key=lambda x: (x["figure_number"], x.get("subfigure", "")))
    
    def get_figure_context(self, fig_num: int, subfig: Optional[str] = None) -> List[str]:
        """获取某个图片在文中的所有提及上下文"""
        fig_num_str = str(fig_num)
        
        if fig_num_str not in self.figure_map:
            return []
        
        fig_data = self.figure_map[fig_num_str]
        
        if subfig:
            # 只返回特定子图的上下文
            return [
                m["context"] for m in fig_data["mentions"]
                if m.get("subfigure") == subfig
            ]
        else:
            # 返回所有上下文
            return [m["context"] for m in fig_data["mentions"]]
