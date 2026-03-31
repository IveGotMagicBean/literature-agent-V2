"""
智能图片解析模块
- 识别Figure编号和子图标签
- 更准确的子图分割
"""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re


class FigureParser:
    """图片解析器"""
    
    def __init__(self, min_subfigure_size: int = 150):
        """
        Args:
            min_subfigure_size: 子图最小尺寸(像素)
        """
        self.min_size = min_subfigure_size
    
    def parse_figure(self, image_path: str, figure_number: int, page: int) -> Dict:
        """
        解析一张图片
        
        Args:
            image_path: 图片路径
            figure_number: 图片编号
            page: 页码
            
        Returns:
            {
                "main": {"path": str, "label": "Figure 1", ...},
                "subfigures": [
                    {"path": str, "label": "1a", "bbox": (x,y,w,h), ...},
                    ...
                ]
            }
        """
        img = cv2.imread(image_path)
        if img is None:
            return {"main": None, "subfigures": []}
        
        height, width = img.shape[:2]
        
        # 检测子图
        subfigures = self._detect_subfigures(img, image_path, figure_number)
        
        main_info = {
            "path": image_path,
            "label": f"Figure {figure_number}",
            "figure_number": figure_number,
            "page": page,
            "width": width,
            "height": height,
            "has_subfigures": len(subfigures) > 0
        }
        
        return {
            "main": main_info,
            "subfigures": subfigures
        }
    
    def _detect_subfigures(self, img: np.ndarray, image_path: str, figure_number: int) -> List[Dict]:
        """检测子图"""
        height, width = img.shape[:2]
        
        # 图片太小不分割
        if width < 500 or height < 500:
            return []
        
        # 方法1: 检测标签 (a), (b), (c)
        subfigs_by_labels = self._detect_by_labels(img, image_path, figure_number)
        if subfigs_by_labels:
            return subfigs_by_labels
        
        # 方法2: 网格分割
        subfigs_by_grid = self._detect_by_grid(img, image_path, figure_number)
        if subfigs_by_grid:
            return subfigs_by_grid
        
        return []
    
    def _detect_by_labels(self, img: np.ndarray, image_path: str, figure_number: int) -> List[Dict]:
        """
        通过检测标签文字 (a), (b), (c) 来定位子图
        这是最准确的方法
        """
        # TODO: 这需要OCR，暂时跳过
        # 后续可以添加 EasyOCR/PaddleOCR 检测 (a) (b) (c) 等标签
        return []
    
    def _detect_by_grid(self, img: np.ndarray, image_path: str, figure_number: int) -> List[Dict]:
        """
        基于网格的子图检测
        假设子图排列成规则的网格（如2x2, 1x3等）
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # 检测分隔线
        grid_info = self._find_grid_lines(gray)
        
        if not grid_info:
            return []
        
        h_lines = grid_info["h_lines"]
        v_lines = grid_info["v_lines"]
        
        # 计算可能的子图数量
        expected_count = (len(h_lines) - 1) * (len(v_lines) - 1)
        labels = self._generate_labels(expected_count)
        
        # 构建子图区域
        subfigures = []
        label_idx = 0
        
        for i in range(len(h_lines) - 1):
            for j in range(len(v_lines) - 1):
                y1, y2 = h_lines[i], h_lines[i + 1]
                x1, x2 = v_lines[j], v_lines[j + 1]
                
                w, h = x2 - x1, y2 - y1
                
                # 过滤太小的区域
                if w < self.min_size or h < self.min_size:
                    continue
                
                # 确保不会索引越界
                if label_idx >= len(labels):
                    break
                
                # 保存子图
                subfig_path = self._save_subfigure(
                    image_path, (x1, y1, w, h), 
                    f"{figure_number}{labels[label_idx]}"
                )
                
                if subfig_path:
                    subfigures.append({
                        "path": subfig_path,
                        "label": labels[label_idx],
                        "full_label": f"Figure {figure_number}{labels[label_idx]}",
                        "figure_number": figure_number,
                        "bbox": (x1, y1, w, h)
                    })
                    label_idx += 1
        
        return subfigures if len(subfigures) >= 2 else []
    
    def _find_grid_lines(self, gray_img: np.ndarray) -> Optional[Dict]:
        """
        找到图片中的网格分隔线
        
        Returns:
            {"h_lines": [y1, y2, ...], "v_lines": [x1, x2, ...]} 或 None
        """
        height, width = gray_img.shape
        
        # 水平投影：在每一行求平均灰度值
        h_projection = np.mean(gray_img, axis=1)
        
        # 垂直投影：在每一列求平均灰度值
        v_projection = np.mean(gray_img, axis=0)
        
        # 找到低谷（可能的分隔线）
        h_valleys = self._find_valleys(h_projection, min_distance=height // 10)
        v_valleys = self._find_valleys(v_projection, min_distance=width // 10)
        
        # 构建分隔线坐标（包括边界）
        h_lines = [0] + h_valleys + [height]
        v_lines = [0] + v_valleys + [width]
        
        # 至少要有一条分隔线（不包括边界）
        if len(h_valleys) == 0 and len(v_valleys) == 0:
            return None
        
        return {"h_lines": h_lines, "v_lines": v_lines}
    
    def _find_valleys(self, projection: np.ndarray, min_distance: int) -> List[int]:
        """
        在投影中找到谷底（低灰度区域）
        
        Args:
            projection: 投影数组
            min_distance: 谷底之间的最小距离
        """
        # 归一化
        proj = projection.copy()
        proj = (proj - proj.min()) / (proj.max() - proj.min() + 1e-6)
        
        # 应用阈值：找到低于平均值的区域
        threshold = np.mean(proj) * 0.8
        
        valleys = []
        in_valley = False
        valley_start = 0
        
        for i, val in enumerate(proj):
            if val < threshold and not in_valley:
                in_valley = True
                valley_start = i
            elif val >= threshold and in_valley:
                in_valley = False
                valley_center = (valley_start + i) // 2
                valleys.append(valley_center)
        
        # 过滤太近的谷底
        if len(valleys) <= 1:
            return valleys
        
        filtered = [valleys[0]]
        for v in valleys[1:]:
            if v - filtered[-1] >= min_distance:
                filtered.append(v)
        
        return filtered
    
    def _save_subfigure(self, image_path: str, bbox: Tuple, label: str) -> Optional[str]:
        """保存子图"""
        try:
            img = Image.open(image_path)
            x, y, w, h = bbox
            
            # 裁剪
            cropped = img.crop((x, y, x + w, y + h))
            
            # 保存路径
            parent_dir = Path(image_path).parent
            output_path = parent_dir / f"subfig_{label}.png"
            
            cropped.save(output_path)
            return str(output_path)
        except Exception as e:
            print(f"⚠️ 保存子图失败: {e}")
            return None
    
    def _generate_labels(self, count: int) -> List[str]:
        """生成标签: a, b, c, ..."""
        return [chr(ord('a') + i) for i in range(min(count, 26))]


class FigureReferenceExtractor:
    """从文本中提取图片引用"""
    
    # 匹配模式（按优先级排序）
    PATTERNS = [
        # === 带子图的引用 ===
        # Figure 1a, Figure 1.a, Figure 1(a)
        (r'[Ff]igure?\s+(\d+)\s*[\.\(]?\s*([a-z])\s*[\)]?', True),
        # Fig. 1a, Fig 1a
        (r'[Ff]ig\.?\s+(\d+)\s*[\.\(]?\s*([a-z])\s*[\)]?', True),
        # 图1a, 图1-a - 中文带子图
        (r'图\s*(\d+)\s*[-\.\(]?\s*([a-z])\s*[\)]?', True),
        
        # === 主图引用 ===
        # "see Figure 1", "in Figure 1", "as Figure 1"
        (r'(?:see|in|as|from|of)\s+[Ff]igure?\s+(\d+)(?!\s*[a-z])', False),
        # Figure 1 (标准格式)
        (r'[Ff]igure?\s+(\d+)(?!\s*[a-z])', False),
        # Figure 1: 或 Figure 1.
        (r'[Ff]igure?\s+(\d+)\s*[:\.]\s*', False),
        # FIGURE 1 (全大写)
        (r'FIGURE\s+(\d+)(?!\s*[a-z])', False),
        # (Figure 1) 或 [Figure 1]
        (r'[\(\[]Figure\s+(\d+)[\)\]]', False),
        # Fig. 1, Fig 1
        (r'[Ff]ig\.?\s+(\d+)(?!\s*[a-z])', False),
        # 图1 - 中文不带子图
        (r'图\s*(\d+)(?!\s*[a-z])', False),
    ]
    
    @staticmethod
    def extract_references(text: str) -> List[Dict]:
        """
        从文本中提取所有图片引用
        
        Returns:
            [
                {"text": "Figure 1a", "figure": 1, "subfigure": "a", "start": 10, "end": 19},
                ...
            ]
        """
        references = []
        
        for pattern, has_subfigure in FigureReferenceExtractor.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                figure_num = int(match.group(1))
                
                # 判断是否有子图
                if has_subfigure and len(match.groups()) > 1:
                    subfigure = match.group(2)
                else:
                    subfigure = None
                
                references.append({
                    "text": match.group(0),
                    "figure": figure_num,
                    "subfigure": subfigure,
                    "start": match.start(),
                    "end": match.end()
                })
        
        # 去重并按位置排序
        seen = set()
        unique_refs = []
        for ref in sorted(references, key=lambda x: x["start"]):
            key = (ref["figure"], ref["subfigure"])
            if key not in seen:
                unique_refs.append(ref)
                seen.add(key)
        
        return unique_refs
    
    @staticmethod
    def get_context(text: str, ref: Dict, context_size: int = 100) -> str:
        """获取引用周围的上下文"""
        start = max(0, ref["start"] - context_size)
        end = min(len(text), ref["end"] + context_size)
        return text[start:end].strip()
