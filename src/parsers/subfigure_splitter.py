"""
子图分割器 - 基于figure-separator CNN模型
使用命令行方式调用 main.py
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import sys
import subprocess
import json
import tempfile
import shutil


class SubfigureSplitter:
    """
    智能子图分割器
    
    使用figure-separator的CNN模型自动检测和分割子图
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化分割器
        
        Args:
            model_path: figure-separator模型路径
                       默认: ./figure-separator/data/figure-sepration-model-submitted-544.pb
        """
        self.enabled = False
        self.separator = None
        
        # 默认模型路径
        if model_path is None:
            model_path = "./figure-separator/data/figure-sepration-model-submitted-544.pb"
        
        self.model_path = model_path
        self.main_script = "./figure-separator/main.py"
        
        # 检查 figure-separator 是否可用
        try:
            if Path(self.main_script).exists() and Path(model_path).exists():
                self.enabled = True
                print(f"✅ 子图分割器已加载 (使用CNN模型)")
            else:
                # 使用基础OpenCV方法作为后备
                self.enabled = True  # 仍然启用，但使用简单方法
                print(f"ℹ️  子图分割器使用基础方法 (CNN模型未找到)")
                print(f"   提示: 如需高级分割，请安装figure-separator模型")
        except Exception as e:
            self.enabled = True  # 降级到OpenCV
            print(f"ℹ️  子图分割器使用基础方法: {e}")
    
    def split(self, image_path: str, output_dir: str, figure_num: int, 
             min_confidence: float = 0.3, use_numbers: bool = False) -> Dict[str, str]:
        """
        分割子图
        
        Args:
            image_path: 原始图片路径
            output_dir: 输出目录
            figure_num: Figure编号
            min_confidence: 最小置信度阈值
            use_numbers: 使用数字标注(1,2,3...)而不是字母(a,b,c...)
        
        Returns:
            {"1": "path/to/figure_3-1.png", "2": "path/to/figure_3-2.png", ...}
            或
            {"a": "path/to/figure_3a.png", "b": "path/to/figure_3b.png", ...}
        """
        if not self.enabled:
            return {}
        
        # 检查是否有 figure-separator
        has_separator = Path(self.main_script).exists() and Path(self.model_path).exists()
        
        if not has_separator:
            # 使用简单的基于OpenCV的分割方法
            print(f"    ℹ️  使用基础分割方法...")
            return self._split_simple(image_path, output_dir, figure_num, use_numbers)
        
        try:
            print(f"    🔍 检测子图...")
            
            # 创建临时目录存放结果
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_output = Path(temp_dir)
                
                # 调用 figure-separator main.py
                # 注意：只处理单个图片，避免批量处理导致超时
                temp_image_dir = temp_output / "input"
                temp_image_dir.mkdir()
                
                # 复制单个图片到临时目录
                import shutil
                temp_image_path = temp_image_dir / Path(image_path).name
                shutil.copy(image_path, temp_image_path)
                
                cmd = [
                    "python", self.main_script,
                    "--images", str(temp_image_dir),
                    "--model", self.model_path,
                    "--output", str(temp_output),
                    "--annotate", "0"  # 不需要标注图
                ]
                
                # 运行命令（增加超时时间到180秒）
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=180  # 增加到3分钟
                )
                
                if result.returncode != 0:
                    print(f"    ❌ figure-separator 运行失败: {result.stderr}")
                    return {}
                
                # 读取 JSON 结果
                image_name = Path(image_path).name
                json_file = temp_output / f"{image_name}.json"
                
                if not json_file.exists():
                    print(f"    ℹ️ 未检测到子图（可能是单张完整图）")
                    return {}
                
                with open(json_file, 'r') as f:
                    detections = json.load(f)
                
                if not detections or len(detections) == 0:
                    print(f"    ℹ️ 未检测到子图")
                    return {}
                
                # 过滤低置信度的检测
                valid_detections = [
                    d for d in detections 
                    if d.get('conf', 0) >= min_confidence
                ]
                
                if not valid_detections:
                    print(f"    ℹ️ 检测到{len(detections)}个候选，但置信度均低于{min_confidence}")
                    return {}
                
                # 按位置排序（从左到右，从上到下）
                valid_detections = sorted(valid_detections, key=lambda d: (
                    d['y'],  # top
                    d['x']   # left
                ))
                
                # 读取原图
                img = cv2.imread(image_path)
                if img is None:
                    print(f"    ❌ 无法读取图片: {image_path}")
                    return {}
                
                # 裁剪并保存子图
                result = {}
                
                # 选择标注方式
                if use_numbers:
                    labels = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
                    separator = '-'  # figure_3-1.png
                else:
                    labels = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
                    separator = ''   # figure_3a.png
                
                for idx, detection in enumerate(valid_detections):
                    if idx >= len(labels):
                        break
                    
                    label = labels[idx]
                    x = detection['x']
                    y = detection['y']
                    w = detection['w']
                    h = detection['h']
                    conf = detection['conf']
                    
                    # 计算边界
                    x1 = max(0, x)
                    y1 = max(0, y)
                    x2 = min(img.shape[1], x + w)
                    y2 = min(img.shape[0], y + h)
                    
                    if x2 <= x1 or y2 <= y1:
                        continue
                    
                    # 裁剪
                    cropped = img[y1:y2, x1:x2]
                    
                    # 保存
                    output_path = Path(output_dir) / f"figure_{figure_num}{separator}{label}.png"
                    cv2.imwrite(str(output_path), cropped)
                    
                    result[label] = str(output_path)
                    print(f"    ✅ Figure {figure_num}{separator}{label} (置信度: {conf:.2f})")
                
                if result:
                    print(f"    🎉 成功分割 {len(result)} 个子图: {', '.join(result.keys())}")
                
                return result
            
        except subprocess.TimeoutExpired:
            print(f"    ❌ 分割超时")
            return {}
        except Exception as e:
            print(f"    ❌ 分割失败: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _split_simple(self, image_path: str, output_dir: str, figure_num: int, use_numbers: bool = False) -> Dict[str, str]:
        """
        简单的基于OpenCV的分割方法（后备方案）
        当figure-separator不可用时使用
        """
        try:
            # 这里返回空字典，表示未检测到子图
            # 实际上大多数情况下，需要CNN模型才能准确分割
            print(f"    ℹ️  基础方法未能自动检测子图边界")
            print(f"    💡 建议: 安装figure-separator以获得更好的子图分割效果")
            return {}
            
        except Exception as e:
            print(f"    ⚠️  简单分割失败: {e}")
            return {}
    
    def is_available(self) -> bool:
        """检查分割器是否可用"""
        return self.enabled


# 测试代码
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python subfigure_splitter.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    # 测试分割
    splitter = SubfigureSplitter()
    
    if not splitter.is_available():
        print("❌ 分割器不可用")
        print("\n请按以下步骤安装：")
        print("1. git clone https://github.com/apple2373/figure-separator.git")
        print("2. cd figure-separator")
        print("3. pip install tensorflow opencv-python")
        print("4. 下载模型到 ./data/")
        sys.exit(1)
    
    print(f"\n测试图片: {image_path}")
    result = splitter.split(image_path, "./test_output", 1)
    
    if result:
        print(f"\n✅ 分割成功!")
        for label, path in result.items():
            print(f"  子图{label}: {path}")
    else:
        print("\n未检测到子图")
