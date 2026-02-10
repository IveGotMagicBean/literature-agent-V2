"""
PDF图片提取诊断工具
用于分析为什么某些Figure没有被提取
"""

import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parsers.pdf_parser_improved import ImprovedPDFParser
from parsers.figure_parser import FigureReferenceExtractor


def diagnose_pdf(pdf_path: str):
    """诊断PDF图片提取问题"""
    
    print("=" * 80)
    print("PDF图片提取诊断工具")
    print("=" * 80)
    
    # 1. 使用改进版解析器提取
    parser = ImprovedPDFParser(extraction_mode="hybrid")
    result = parser.parse(pdf_path)
    
    print(f"\n📄 PDF基本信息:")
    print(f"  总页数: {result['pages']}")
    print(f"  提取图片数: {len(result['figures'])}")
    
    # 2. 显示所有提取的图片信息
    print(f"\n🖼️  所有提取的图片详情:")
    print(f"{'ID':<5} {'页码':<6} {'大小(KB)':<12} {'面积(像素²)':<15} {'提取方法':<20}")
    print("-" * 80)
    
    for idx, fig in enumerate(result['figures']):
        size_kb = len(fig['data']) / 1024
        bbox = fig.get('bbox')
        area = 0
        if bbox:
            if hasattr(bbox, 'x0'):  # fitz.Rect对象
                area = (bbox.x1 - bbox.x0) * (bbox.y1 - bbox.y0)
            else:  # tuple
                area = bbox[2] * bbox[3]
        
        method = fig.get('extraction_method', 'unknown')
        print(f"{idx:<5} {fig['page']:<6} {size_kb:<12.1f} {area:<15.0f} {method:<20}")
    
    # 3. 提取文本中的Figure引用
    print(f"\n📝 文本中的Figure引用:")
    extractor = FigureReferenceExtractor()
    
    figure_refs = {}
    for text_data in result.get('texts', []):
        page = text_data['page']
        refs = extractor.extract_references(text_data['content'])
        
        for ref in refs:
            fig_num = ref['figure']
            if fig_num not in figure_refs:
                figure_refs[fig_num] = []
            if page not in figure_refs[fig_num]:
                figure_refs[fig_num].append(page)
    
    print(f"  找到 {len(figure_refs)} 个Figure引用:")
    for fig_num in sorted(figure_refs.keys()):
        pages = figure_refs[fig_num]
        print(f"    Figure {fig_num}: 页 {pages}")
    
    # 4. 分析匹配问题
    print(f"\n⚠️  潜在问题分析:")
    
    if len(result['figures']) < len(figure_refs):
        print(f"  ⚠️  提取图片数({len(result['figures'])}) < 引用数({len(figure_refs)})")
        print(f"      可能的原因:")
        print(f"      1. 过滤参数太严格（min_image_size, min_bbox_area）")
        print(f"      2. 某些图片是组合图/子图")
        print(f"      3. PDF中图片是矢量图或特殊格式")
    
    # 5. 按页面统计
    print(f"\n📊 按页面统计图片分布:")
    page_images = {}
    for fig in result['figures']:
        page = fig['page']
        if page not in page_images:
            page_images[page] = []
        page_images[page].append(fig)
    
    for page in sorted(page_images.keys()):
        imgs = page_images[page]
        total_size = sum(len(img['data']) for img in imgs)
        print(f"  页{page}: {len(imgs)}张图片, 总大小{total_size/1024:.1f}KB")
    
    # 6. 建议
    print(f"\n💡 优化建议:")
    
    # 检查是否有很多小图被过滤
    all_sizes = [len(fig['data']) for fig in result['figures']]
    if all_sizes:
        min_size = min(all_sizes)
        avg_size = sum(all_sizes) / len(all_sizes)
        
        if min_size < 50000:  # 小于50KB
            print(f"  ✓ 已包含较小的图片(最小{min_size/1024:.1f}KB)，参数合理")
        else:
            print(f"  ⚠️  最小图片也有{min_size/1024:.1f}KB，可能过滤掉了一些图")
            print(f"      建议: 降低 min_image_size 参数")
    
    # 检查提取方法
    methods = [fig.get('extraction_method', 'unknown') for fig in result['figures']]
    method_counts = {}
    for m in methods:
        method_counts[m] = method_counts.get(m, 0) + 1
    
    print(f"\n  提取方法统计:")
    for method, count in method_counts.items():
        print(f"    {method}: {count}张")
    
    if method_counts.get('raw_filtered', 0) > 0:
        print(f"  ⚠️  有图片使用了raw_filtered方法，建议:")
        print(f"      1. 尝试 extraction_mode='region_crop'")
        print(f"      2. 降低过滤参数")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python diagnose_extraction.py <pdf文件路径>")
        print("示例: python diagnose_extraction.py data/example/example.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"错误: 文件不存在: {pdf_path}")
        sys.exit(1)
    
    diagnose_pdf(pdf_path)
