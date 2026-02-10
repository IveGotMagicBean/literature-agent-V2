"""
PDF解析模块
提取文本和图片
"""

from typing import Dict, List
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import io


class PDFParser:
    """PDF解析器"""
    
    def __init__(self):
        self.current_doc = None
    
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
        
        texts = []
        figures = []
        figure_counter = 0
        total_pages = len(doc)  # 先获取页数
        
        for page_num in range(total_pages):
            page = doc[page_num]
            
            # 提取文本
            text = page.get_text()
            if text.strip():
                texts.append({
                    "page": page_num + 1,
                    "content": text
                })
            
            # 提取图片
            image_list = page.get_images(full=True)
            
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                
                try:
                    # 获取图片数据
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # 获取图片位置
                    img_rect = page.get_image_rects(xref)
                    bbox = img_rect[0] if img_rect else None
                    
                    figures.append({
                        "page": page_num + 1,
                        "index": figure_counter,
                        "data": image_bytes,
                        "ext": base_image["ext"],
                        "bbox": bbox,
                        "xref": xref
                    })
                    
                    figure_counter += 1
                    
                except Exception as e:
                    print(f"⚠️ 提取图片失败 (page {page_num + 1}, img {img_index}): {e}")
        
        doc.close()
        
        return {
            "pages": total_pages,  # 使用之前保存的页数
            "texts": texts,
            "figures": figures
        }
    
    def get_page_image(self, page_num: int, zoom: float = 2.0) -> bytes:
        """获取某一页的图片"""
        if not self.current_doc:
            return None
        
        page = self.current_doc[page_num - 1]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        return pix.tobytes("png")
