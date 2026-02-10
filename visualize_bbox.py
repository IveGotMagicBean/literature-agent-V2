"""
可视化诊断工具 - 查看bbox合并效果
帮助诊断为什么提取的图不完整
"""

import sys
from pathlib import Path
import fitz
from PIL import Image, ImageDraw, ImageFont
import io

sys.path.insert(0, str(Path(__file__).parent / "src"))

from parsers.pdf_parser_improved import ImprovedPDFParser


def visualize_bbox_merging(pdf_path: str, page_num: int = 1, output_dir: str = "bbox_debug"):
    """
    可视化bbox合并过程
    
    Args:
        pdf_path: PDF文件路径
        page_num: 要分析的页码（从1开始）
        output_dir: 输出目录
    """
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print("=" * 80)
    print(f"可视化bbox合并 - 第{page_num}页")
    print("=" * 80)
    
    # 打开PDF
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    
    # 获取页面图像（作为底图）
    mat = fitz.Matrix(2.0, 2.0)  # 2倍分辨率
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    base_img = Image.open(io.BytesIO(img_bytes))
    
    # 创建ImprovedPDFParser实例
    parser = ImprovedPDFParser(extraction_mode="region_crop")
    
    # 获取所有图像的bbox（合并前）
    print("\n📦 步骤1: 提取所有图像对象的bbox")
    image_list = page.get_images(full=True)
    original_bboxes = []
    
    for idx, img_info in enumerate(image_list):
        xref = img_info[0]
        try:
            img_rects = page.get_image_rects(xref)
            if img_rects:
                for rect in img_rects:
                    original_bboxes.append(rect)
                    width = rect.x1 - rect.x0
                    height = rect.y1 - rect.y0
                    print(f"  图像{idx}: 位置({rect.x0:.0f}, {rect.y0:.0f}), "
                          f"大小({width:.0f}x{height:.0f})")
        except:
            continue
    
    print(f"\n总共找到 {len(original_bboxes)} 个图像对象")
    
    # 合并bbox
    print("\n🔗 步骤2: 合并接近的bbox（阈值=80像素）")
    merged_bboxes = parser._merge_nearby_bboxes(original_bboxes, threshold=80.0)
    
    print(f"合并后剩余 {len(merged_bboxes)} 个区域")
    for idx, bbox in enumerate(merged_bboxes):
        width = bbox.x1 - bbox.x0
        height = bbox.y1 - bbox.y0
        area = width * height
        print(f"  区域{idx}: 位置({bbox.x0:.0f}, {bbox.y0:.0f}), "
              f"大小({width:.0f}x{height:.0f}), 面积{area:.0f}")
    
    # 可视化1: 原始bbox（红色）
    print("\n🎨 步骤3: 生成可视化图片")
    img1 = base_img.copy()
    draw1 = ImageDraw.Draw(img1, 'RGBA')
    
    for bbox in original_bboxes:
        # 缩放坐标（因为图像是2倍分辨率）
        x0, y0, x1, y1 = bbox.x0*2, bbox.y0*2, bbox.x1*2, bbox.y1*2
        # 半透明红色填充
        draw1.rectangle([x0, y0, x1, y1], 
                       fill=(255, 0, 0, 50),
                       outline=(255, 0, 0, 255),
                       width=3)
    
    output1 = output_path / f"page{page_num}_original_bboxes.png"
    img1.save(output1)
    print(f"  ✓ 原始bbox保存到: {output1}")
    
    # 可视化2: 合并后的bbox（绿色）
    img2 = base_img.copy()
    draw2 = ImageDraw.Draw(img2, 'RGBA')
    
    for idx, bbox in enumerate(merged_bboxes):
        x0, y0, x1, y1 = bbox.x0*2, bbox.y0*2, bbox.x1*2, bbox.y1*2
        # 半透明绿色填充
        draw2.rectangle([x0, y0, x1, y1],
                       fill=(0, 255, 0, 50),
                       outline=(0, 255, 0, 255),
                       width=4)
        
        # 添加编号
        draw2.text((x0+10, y0+10), f"区域{idx}", 
                  fill=(0, 255, 0, 255))
    
    output2 = output_path / f"page{page_num}_merged_bboxes.png"
    img2.save(output2)
    print(f"  ✓ 合并后bbox保存到: {output2}")
    
    # 可视化3: 对比图（原始=红色，合并=绿色）
    img3 = base_img.copy()
    draw3 = ImageDraw.Draw(img3, 'RGBA')
    
    # 原始（红色，细线）
    for bbox in original_bboxes:
        x0, y0, x1, y1 = bbox.x0*2, bbox.y0*2, bbox.x1*2, bbox.y1*2
        draw3.rectangle([x0, y0, x1, y1],
                       outline=(255, 0, 0, 180),
                       width=2)
    
    # 合并（绿色，粗线）
    for idx, bbox in enumerate(merged_bboxes):
        x0, y0, x1, y1 = bbox.x0*2, bbox.y0*2, bbox.x1*2, bbox.y1*2
        draw3.rectangle([x0, y0, x1, y1],
                       fill=(0, 255, 0, 30),
                       outline=(0, 255, 0, 255),
                       width=5)
        draw3.text((x0+10, y0+10), f"区域{idx}", 
                  fill=(0, 255, 0, 255))
    
    output3 = output_path / f"page{page_num}_comparison.png"
    img3.save(output3)
    print(f"  ✓ 对比图保存到: {output3}")
    
    # 提取并保存每个合并后的区域
    print(f"\n💾 步骤4: 提取合并后的区域")
    for idx, bbox in enumerate(merged_bboxes):
        # 扩展一点边距
        margin = 5
        expanded_bbox = fitz.Rect(
            max(0, bbox.x0 - margin),
            max(0, bbox.y0 - margin),
            min(page.rect.width, bbox.x1 + margin),
            min(page.rect.height, bbox.y1 + margin)
        )
        
        # 截图这个区域
        pix = page.get_pixmap(matrix=mat, clip=expanded_bbox)
        img_bytes = pix.tobytes("png")
        
        output_region = output_path / f"page{page_num}_region{idx}.png"
        with open(output_region, "wb") as f:
            f.write(img_bytes)
        
        size_kb = len(img_bytes) / 1024
        print(f"  ✓ 区域{idx}: {size_kb:.1f}KB -> {output_region}")
    
    doc.close()
    
    print("\n" + "=" * 80)
    print("📊 诊断总结:")
    print(f"  原始图像对象: {len(original_bboxes)} 个")
    print(f"  合并后区域: {len(merged_bboxes)} 个")
    print(f"  合并比例: {len(original_bboxes) - len(merged_bboxes)} 个被合并")
    print("\n💡 查看生成的图片:")
    print(f"  1. {output_path}/page{page_num}_original_bboxes.png - 红色=原始bbox")
    print(f"  2. {output_path}/page{page_num}_merged_bboxes.png - 绿色=合并后")
    print(f"  3. {output_path}/page{page_num}_comparison.png - 红色+绿色对比")
    print(f"  4. {output_path}/page{page_num}_region*.png - 提取的区域")
    print("\n🔍 如果合并不充分（子图分开了）:")
    print("   -> 增大合并阈值 threshold (当前80)")
    print("   -> 编辑 src/parsers/pdf_parser_improved.py 第183行")
    print("=" * 80)


def test_different_thresholds(pdf_path: str, page_num: int = 1):
    """测试不同的合并阈值"""
    
    print("=" * 80)
    print(f"测试不同的合并阈值 - 第{page_num}页")
    print("=" * 80)
    
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    
    parser = ImprovedPDFParser(extraction_mode="region_crop")
    
    # 获取原始bbox
    image_list = page.get_images(full=True)
    original_bboxes = []
    
    for img_info in image_list:
        xref = img_info[0]
        try:
            img_rects = page.get_image_rects(xref)
            if img_rects:
                original_bboxes.extend(img_rects)
        except:
            continue
    
    print(f"\n原始图像对象: {len(original_bboxes)} 个\n")
    
    # 测试不同阈值
    thresholds = [10, 20, 40, 80, 120, 160, 200]
    
    print(f"{'阈值':<10} {'合并后区域数':<15} {'效果':<30}")
    print("-" * 60)
    
    for threshold in thresholds:
        merged = parser._merge_nearby_bboxes(original_bboxes, threshold=threshold)
        reduction = len(original_bboxes) - len(merged)
        
        if len(merged) == len(original_bboxes):
            effect = "❌ 没有合并"
        elif len(merged) == 1:
            effect = "✓ 全部合并为1个"
        elif reduction < len(original_bboxes) * 0.3:
            effect = "⚠️ 合并较少"
        else:
            effect = "✓ 合并良好"
        
        print(f"{threshold:<10} {len(merged):<15} {effect:<30}")
    
    doc.close()
    
    print("\n💡 建议:")
    print("  - 学术论文（子图间距适中）: threshold=80-120")
    print("  - 子图间距很大: threshold=120-200")
    print("  - 子图紧密排列: threshold=40-80")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  可视化合并过程:")
        print("    python visualize_bbox.py <pdf文件> [页码]")
        print("  测试不同阈值:")
        print("    python visualize_bbox.py <pdf文件> [页码] --test-thresholds")
        print("\n示例:")
        print("  python visualize_bbox.py paper.pdf 3")
        print("  python visualize_bbox.py paper.pdf 3 --test-thresholds")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    page_num = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 1
    
    if not Path(pdf_path).exists():
        print(f"错误: 文件不存在: {pdf_path}")
        sys.exit(1)
    
    if "--test-thresholds" in sys.argv:
        test_different_thresholds(pdf_path, page_num)
    else:
        visualize_bbox_merging(pdf_path, page_num)
