#!/usr/bin/env python3
"""
PDF图片提取诊断工具
用于排查图片提取不完整、重复等问题
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parsers.pdf_parser import PDFParser
from parsers.figure_parser import FigureReferenceExtractor

def diagnose_pdf(pdf_path: str):
    """诊断PDF图片提取"""
    
    print("=" * 80)
    print(f"诊断文件: {pdf_path}")
    print("=" * 80)
    print()
    
    # 1. 解析PDF
    print("📄 步骤1: 解析PDF")
    print("-" * 80)
    parser = PDFParser()
    pdf_data = parser.parse(pdf_path)
    
    print(f"总页数: {pdf_data['pages']}")
    print(f"提取的原始图片数: {len(pdf_data['figures'])}")
    print()
    
    # 2. 显示所有图片信息
    print("🖼️ 步骤2: 原始图片详情")
    print("-" * 80)
    for idx, fig in enumerate(pdf_data['figures']):
        size_kb = len(fig['data']) / 1024
        print(f"  [{idx}] 页{fig['page']:2d} | {size_kb:6.1f} KB | {fig['ext'].upper()}")
    print()
    
    # 3. 分析文本引用
    print("🔗 步骤3: 文本中的Figure引用")
    print("-" * 80)
    
    extractor = FigureReferenceExtractor()
    figure_references = {}  # {figure_num: [pages]}
    
    for text_data in pdf_data['texts']:
        page = text_data['page']
        refs = extractor.extract_references(text_data['content'])
        
        for ref in refs:
            fig_num = ref['figure']
            if fig_num not in figure_references:
                figure_references[fig_num] = []
            if page not in figure_references[fig_num]:
                figure_references[fig_num].append(page)
    
    if figure_references:
        for fig_num in sorted(figure_references.keys()):
            pages = sorted(figure_references[fig_num])
            print(f"  Figure {fig_num}: 在第 {pages} 页被引用")
    else:
        print("  ⚠️  未找到任何Figure引用！")
        print("  可能原因:")
        print("    - 文本提取失败")
        print("    - 使用了非标准的图片引用格式")
        print("    - 图片没有在文本中被引用")
    print()
    
    # 4. 匹配分析
    print("🎯 步骤4: 图片匹配分析")
    print("-" * 80)
    
    # 统计每页有多少张图
    images_per_page = {}
    for idx, fig in enumerate(pdf_data['figures']):
        page = fig['page']
        if page not in images_per_page:
            images_per_page[page] = []
        images_per_page[page].append({
            'id': idx,
            'size': len(fig['data'])
        })
    
    print("每页图片分布:")
    for page in sorted(images_per_page.keys()):
        imgs = images_per_page[page]
        print(f"  第{page:2d}页: {len(imgs)} 张图片", end='')
        if len(imgs) > 0:
            sizes = [f"{img['size']/1024:.0f}KB" for img in imgs]
            print(f" ({', '.join(sizes)})")
        else:
            print()
    print()
    
    # 5. 匹配模拟
    print("🔍 步骤5: 模拟匹配过程")
    print("-" * 80)
    
    matched_figures = {}
    
    for fig_num in sorted(figure_references.keys()):
        pages = figure_references[fig_num]
        first_mention = min(pages)
        
        # 搜索范围
        search_pages = [first_mention - 1, first_mention, first_mention + 1]
        search_pages = [p for p in search_pages if p > 0]
        
        print(f"Figure {fig_num}:")
        print(f"  首次提及: 第{first_mention}页")
        print(f"  搜索范围: {search_pages}")
        
        # 找候选图片
        candidates = []
        for page in search_pages:
            if page in images_per_page:
                candidates.extend(images_per_page[page])
        
        if not candidates:
            print(f"  ❌ 未找到候选图片")
            continue
        
        # 过滤小图
        large_imgs = [img for img in candidates if img['size'] > 10000]
        if not large_imgs:
            large_imgs = candidates
        
        # 选最大的
        best = max(large_imgs, key=lambda x: x['size'])
        matched_figures[fig_num] = best
        
        print(f"  ✅ 匹配到图片ID={best['id']} (大小={best['size']/1024:.0f}KB)")
        print()
    
    # 6. 总结
    print("=" * 80)
    print("📊 诊断总结")
    print("=" * 80)
    print(f"PDF总页数: {pdf_data['pages']}")
    print(f"原始图片数: {len(pdf_data['figures'])}")
    print(f"文本引用的Figure数: {len(figure_references)}")
    print(f"成功匹配的Figure数: {len(matched_figures)}")
    print()
    
    # 7. 问题诊断
    if len(matched_figures) < len(figure_references):
        print("⚠️  存在问题:")
        missing = set(figure_references.keys()) - set(matched_figures.keys())
        print(f"  未匹配的Figure: {sorted(missing)}")
        print()
    
    if len(figure_references) == 0:
        print("❌ 严重问题: 未找到任何Figure引用")
        print()
        print("建议:")
        print("  1. 检查PDF文本提取是否正常")
        print("  2. 查看文本中是否使用非标准的图片引用")
        print("  3. 尝试手动搜索 'Figure' 或 'Fig' 关键字")
        print()
        
        # 尝试打印前几页文本样本
        print("前3页文本样本:")
        for i, text_data in enumerate(pdf_data['texts'][:3]):
            print(f"\n第{text_data['page']}页 (前200字符):")
            print(text_data['content'][:200])
    
    if len(matched_figures) < len(pdf_data['figures']):
        unmatched_count = len(pdf_data['figures']) - len(matched_figures)
        print(f"ℹ️  有 {unmatched_count} 张图片未被匹配")
        print("  可能原因:")
        print("    - 这些图片是logo、小图标等")
        print("    - 这些图片没有在文本中被引用")
        print("    - 图片在文本引用之前的页面")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python diagnose_figure_extraction.py <pdf_path>")
        print()
        print("示例:")
        print("  python diagnose_figure_extraction.py paper.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        print(f"错误: 文件不存在: {pdf_path}")
        sys.exit(1)
    
    diagnose_pdf(pdf_path)
