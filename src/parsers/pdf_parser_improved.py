"""
改进的PDF解析模块 - 支持多种图片提取策略
解决散点、小碎片等问题
"""

from typing import Dict, List, Tuple, Optional
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import io
import numpy as np


class ImprovedPDFParser:
    """
    改进的PDF解析器
    
    支持三种图片提取策略：
    1. 区域截图法 (region_crop) - 推荐，最准确
    2. 图像合并法 (merge_images) - 适合复杂图表
    3. 原始提取法 (extract_raw) - 兼容模式
    """
    
    def __init__(self, extraction_mode: str = "region_crop"):
        """
        Args:
            extraction_mode: 提取模式
                - "region_crop": 基于bbox区域截图（推荐）
                - "merge_images": 智能合并碎片图像
                - "extract_raw": 原始提取方法
                - "hybrid": 混合模式（先尝试region_crop，失败则用merge_images）
        """
        self.current_doc = None
        self.extraction_mode = extraction_mode
        
        # 过滤参数
        self.min_image_size = 50000  # 最小图片大小(字节) - 50KB
        self.min_bbox_area = 10000   # 最小bbox面积(像素) - 100x100
        self.max_aspect_ratio = 5.0  # 最大宽高比，过滤异常细长的图
    
    def parse(self, pdf_path: str) -> Dict:
        """
        解析PDF
        
        Returns:
            {
                "pages": int,
                "texts": [{"page": 1, "content": "..."}, ...],
                "figures": [{"page": 1, "index": 0, "data": bytes, "bbox": (x,y,w,h)}, ...]
            }
        """
        doc = fitz.open(pdf_path)
        self.current_doc = doc
        
        texts = []
        figures = []
        total_pages = len(doc)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            
            # 提取文本
            text = page.get_text()
            if text.strip():
                texts.append({
                    "page": page_num + 1,
                    "content": text
                })
            
            # 根据模式提取图片
            if self.extraction_mode == "region_crop":
                page_figures = self._extract_by_region_crop(page, page_num + 1)
            elif self.extraction_mode == "merge_images":
                page_figures = self._extract_by_merging(page, page_num + 1)
            elif self.extraction_mode == "hybrid":
                # 先尝试区域截图
                page_figures = self._extract_by_region_crop(page, page_num + 1)
                # 如果没找到，尝试合并
                if not page_figures:
                    page_figures = self._extract_by_merging(page, page_num + 1)
            else:  # extract_raw
                page_figures = self._extract_raw_images(page, page_num + 1)
            
            figures.extend(page_figures)
        
        doc.close()
        self.current_doc = None
        
        return {
            "pages": total_pages,
            "texts": texts,
            "figures": figures
        }
    
    def _extract_by_region_crop(self, page, page_num: int) -> List[Dict]:
        """
        策略1: 基于bbox区域截图
        
        这是最准确的方法：
        1. 找到所有图像对象的bbox
        2. 将重叠/接近的bbox合并
        3. 对合并后的区域进行页面截图
        
        优点：能得到完整的图表，不会有碎片
        """
        figures = []
        
        # 获取所有图像对象的bbox
        image_bboxes = []
        image_list = page.get_images(full=True)
        
        for img_info in image_list:
            xref = img_info[0]
            try:
                img_rects = page.get_image_rects(xref)
                if img_rects:
                    for rect in img_rects:
                        # rect是fitz.Rect对象，包含(x0, y0, x1, y1)
                        image_bboxes.append(rect)
            except Exception as e:
                continue
        
        if not image_bboxes:
            return figures
        
        # 合并重叠或接近的bbox
        merged_bboxes = self._merge_nearby_bboxes(image_bboxes)
        
        # 过滤太小的区域
        filtered_bboxes = []
        for bbox in merged_bboxes:
            width = bbox.x1 - bbox.x0
            height = bbox.y1 - bbox.y0
            area = width * height
            
            # 过滤条件
            if area < self.min_bbox_area:
                continue
            
            # 过滤异常宽高比（太细长的）
            aspect_ratio = max(width, height) / max(min(width, height), 1)
            if aspect_ratio > self.max_aspect_ratio:
                continue
            
            filtered_bboxes.append(bbox)
        
        # 对每个区域进行截图
        for idx, bbox in enumerate(filtered_bboxes):
            try:
                # 扩展一点边距
                margin = 5
                expanded_bbox = fitz.Rect(
                    max(0, bbox.x0 - margin),
                    max(0, bbox.y0 - margin),
                    min(page.rect.width, bbox.x1 + margin),
                    min(page.rect.height, bbox.y1 + margin)
                )
                
                # 截图这个区域
                mat = fitz.Matrix(2.0, 2.0)  # 2倍分辨率
                pix = page.get_pixmap(matrix=mat, clip=expanded_bbox)
                img_bytes = pix.tobytes("png")
                
                # 再次检查大小
                if len(img_bytes) < self.min_image_size:
                    continue
                
                figures.append({
                    "page": page_num,
                    "index": idx,
                    "data": img_bytes,
                    "ext": "png",
                    "bbox": (bbox.x0, bbox.y0, bbox.x1 - bbox.x0, bbox.y1 - bbox.y0),
                    "extraction_method": "region_crop"
                })
                
            except Exception as e:
                print(f"⚠️ 区域截图失败 (page {page_num}, region {idx}): {e}")
                continue
        
        return figures
    
    def _merge_nearby_bboxes(self, bboxes: List, threshold: float = 80.0) -> List:
        """
        合并重叠或接近的bbox
        
        Args:
            bboxes: bbox列表
            threshold: 距离阈值，小于这个距离的bbox会被合并
                      默认80像素，适合学术论文中的子图间距
        """
        if not bboxes:
            return []
        
        # 转换为可修改的列表
        merged = [bbox for bbox in bboxes]
        
        changed = True
        while changed:
            changed = False
            new_merged = []
            used = set()
            
            for i, bbox1 in enumerate(merged):
                if i in used:
                    continue
                
                # 尝试找到可以合并的bbox
                current_bbox = bbox1
                for j in range(i + 1, len(merged)):
                    if j in used:
                        continue
                    
                    bbox2 = merged[j]
                    
                    # 检查是否重叠或接近
                    if self._is_nearby(current_bbox, bbox2, threshold):
                        # 合并
                        current_bbox = fitz.Rect(
                            min(current_bbox.x0, bbox2.x0),
                            min(current_bbox.y0, bbox2.y0),
                            max(current_bbox.x1, bbox2.x1),
                            max(current_bbox.y1, bbox2.y1)
                        )
                        used.add(j)
                        changed = True
                
                new_merged.append(current_bbox)
                used.add(i)
            
            merged = new_merged
        
        return merged
    
    def _is_nearby(self, bbox1, bbox2, threshold: float) -> bool:
        """判断两个bbox是否重叠或接近"""
        # 计算最小距离
        x_overlap = not (bbox1.x1 + threshold < bbox2.x0 or bbox2.x1 + threshold < bbox1.x0)
        y_overlap = not (bbox1.y1 + threshold < bbox2.y0 or bbox2.y1 + threshold < bbox1.y0)
        
        return x_overlap and y_overlap
    
    def _extract_by_merging(self, page, page_num: int) -> List[Dict]:
        """
        策略2: 智能合并图像碎片
        
        适用于PDF中图表被分解成多个小图的情况
        """
        figures = []
        image_list = page.get_images(full=True)
        
        # 收集所有图像及其位置
        image_data = []
        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = self.current_doc.extract_image(xref)
                img_bytes = base_image["image"]
                img_rects = page.get_image_rects(xref)
                
                if img_rects and len(img_bytes) > 5000:  # 至少5KB
                    image_data.append({
                        "bytes": img_bytes,
                        "ext": base_image["ext"],
                        "bbox": img_rects[0],
                        "xref": xref
                    })
            except:
                continue
        
        if not image_data:
            return figures
        
        # 按位置分组
        groups = self._group_nearby_images(image_data)
        
        # 对每组进行处理
        for idx, group in enumerate(groups):
            if len(group) == 1:
                # 单个图像，直接使用
                img_data = group[0]
                if len(img_data["bytes"]) >= self.min_image_size:
                    figures.append({
                        "page": page_num,
                        "index": idx,
                        "data": img_data["bytes"],
                        "ext": img_data["ext"],
                        "bbox": img_data["bbox"],
                        "extraction_method": "single_image"
                    })
            else:
                # 多个图像，使用区域截图
                all_bboxes = [img["bbox"] for img in group]
                merged_bbox = self._merge_bboxes_to_one(all_bboxes)
                
                try:
                    mat = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=mat, clip=merged_bbox)
                    img_bytes = pix.tobytes("png")
                    
                    if len(img_bytes) >= self.min_image_size:
                        figures.append({
                            "page": page_num,
                            "index": idx,
                            "data": img_bytes,
                            "ext": "png",
                            "bbox": merged_bbox,
                            "extraction_method": "merged_region"
                        })
                except:
                    continue
        
        return figures
    
    def _group_nearby_images(self, image_data: List[Dict], threshold: float = 50.0) -> List[List[Dict]]:
        """将接近的图像分组"""
        if not image_data:
            return []
        
        groups = [[image_data[0]]]
        
        for img in image_data[1:]:
            added = False
            for group in groups:
                # 检查是否与组中任意一个接近
                for existing_img in group:
                    if self._is_nearby(img["bbox"], existing_img["bbox"], threshold):
                        group.append(img)
                        added = True
                        break
                if added:
                    break
            
            if not added:
                groups.append([img])
        
        return groups
    
    def _merge_bboxes_to_one(self, bboxes: List) -> fitz.Rect:
        """将多个bbox合并为一个"""
        x0 = min(bbox.x0 for bbox in bboxes)
        y0 = min(bbox.y0 for bbox in bboxes)
        x1 = max(bbox.x1 for bbox in bboxes)
        y1 = max(bbox.y1 for bbox in bboxes)
        return fitz.Rect(x0, y0, x1, y1)
    
    def _extract_raw_images(self, page, page_num: int) -> List[Dict]:
        """
        策略3: 原始提取方法（兼容模式）
        
        直接提取PDF中的图像对象，加强过滤
        """
        figures = []
        image_list = page.get_images(full=True)
        
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            
            try:
                base_image = self.current_doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # 严格过滤：只保留大图
                if len(image_bytes) < self.min_image_size:
                    continue
                
                # 检查bbox面积
                img_rect = page.get_image_rects(xref)
                if img_rect:
                    bbox = img_rect[0]
                    width = bbox.x1 - bbox.x0
                    height = bbox.y1 - bbox.y0
                    area = width * height
                    
                    if area < self.min_bbox_area:
                        continue
                    
                    # 过滤异常宽高比
                    aspect_ratio = max(width, height) / max(min(width, height), 1)
                    if aspect_ratio > self.max_aspect_ratio:
                        continue
                
                figures.append({
                    "page": page_num,
                    "index": img_index,
                    "data": image_bytes,
                    "ext": base_image["ext"],
                    "bbox": img_rect[0] if img_rect else None,
                    "xref": xref,
                    "extraction_method": "raw_filtered"
                })
                
            except Exception as e:
                print(f"⚠️ 提取图片失败 (page {page_num}, img {img_index}): {e}")
        
        return figures
    
    def get_page_image(self, page_num: int, zoom: float = 2.0) -> bytes:
        """获取某一页的图片"""
        if not self.current_doc:
            return None
        
        page = self.current_doc[page_num - 1]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        return pix.tobytes("png")


# 使用示例和配置建议
"""
使用建议：

1. 对于大多数学术论文（推荐）：
   parser = ImprovedPDFParser(extraction_mode="region_crop")
   
2. 对于复杂图表（散点图、多子图等）：
   parser = ImprovedPDFParser(extraction_mode="hybrid")
   
3. 如果需要调整过滤参数：
   parser = ImprovedPDFParser(extraction_mode="region_crop")
   parser.min_image_size = 30000  # 降低到30KB
   parser.min_bbox_area = 5000    # 降低最小面积
   parser.max_aspect_ratio = 8.0  # 允许更细长的图

4. 查看提取方法：
   result = parser.parse("paper.pdf")
   for fig in result["figures"]:
       print(f"Page {fig['page']}: {fig.get('extraction_method', 'unknown')}")
"""
