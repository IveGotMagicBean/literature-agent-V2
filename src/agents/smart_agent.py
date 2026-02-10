"""
智能图片匹配 - 基于文本引用而非提取顺序
解决PDF提取顺序混乱、小图标噪声等问题
"""

from pathlib import Path
from typing import Dict, List, Optional, Generator
import sys
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.pdf_parser_improved import ImprovedPDFParser
from parsers.figure_parser import FigureReferenceExtractor
from parsers.subfigure_splitter import SubfigureSplitter


class SmartAgent:
    """智能文献助手 - 基于引用匹配图片 + 子图分割"""
    
    def __init__(self, llm, data_dir: str = "./data"):
        self.llm = llm
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 使用改进版PDF解析器 - 智能提取完整图表，避免碎片
        self.pdf_parser = ImprovedPDFParser(extraction_mode="hybrid")
        
        # 优化后的过滤参数 - 更宽松，避免漏掉中等大小的图
        self.pdf_parser.min_image_size = 20000    # 降低到20KB（原30KB）
        self.pdf_parser.min_bbox_area = 5000      # 降低最小面积（原8000）
        self.pdf_parser.max_aspect_ratio = 8.0    # 放宽宽高比限制（原6.0）
        
        self.ref_extractor = FigureReferenceExtractor()
        
        # 初始化子图分割器
        self.splitter = SubfigureSplitter()
        
        # 数据
        self.texts = []
        self.all_images = []  # 所有提取的图片
        self.figure_map = {}  # Figure编号 -> {"path": "...", "page": X, "subfigures": {"a": "...", "b": "..."}}
        self.full_text = ""
    
    def load_pdf(self, pdf_path: str) -> Generator[Dict, None, None]:
        """加载PDF"""
        
        yield {"type": "status", "content": "📄 正在解析PDF..."}
        
        # 1. 解析PDF
        pdf_data = self.pdf_parser.parse(pdf_path)
        self.texts = pdf_data["texts"]
        self.full_text = "\n\n".join([t["content"] for t in self.texts[:20]])
        
        yield {"type": "status", "content": f"✅ 提取了 {pdf_data['pages']} 页文本"}
        
        # 2. 保存所有图片
        yield {"type": "status", "content": "🖼️ 正在提取图片..."}
        
        image_dir = self.data_dir / "images"
        image_dir.mkdir(exist_ok=True)
        
        self.all_images = []
        for idx, fig_data in enumerate(pdf_data["figures"]):
            fig_path = image_dir / f"raw_{idx}.{fig_data['ext']}"
            with open(fig_path, "wb") as f:
                f.write(fig_data["data"])
            
            self.all_images.append({
                "id": idx,
                "path": str(fig_path),
                "page": fig_data["page"],
                "size": len(fig_data["data"])  # 文件大小，用于过滤小图标
            })
        
        yield {"type": "status", "content": f"✅ 提取了 {len(self.all_images)} 张原始图片"}
        
        # 3. **关键：通过文本引用匹配图片**
        yield {"type": "status", "content": "🔗 正在智能匹配图片..."}
        
        self.figure_map = self._match_figures_intelligently()
        
        matched_count = len([v for v in self.figure_map.values() if v is not None])
        yield {"type": "status", "content": f"✅ 成功匹配 {matched_count} 个Figure"}
        
        # 完成
        yield {
            "type": "complete",
            "stats": {
                "pages": pdf_data["pages"],
                "raw_images": len(self.all_images),
                "matched_figures": matched_count
            }
        }
    
    def _match_figures_intelligently(self) -> Dict[int, Optional[Dict]]:
        """
        智能匹配：通过文本引用找到对应的图片
        
        改进策略：
        1. 扩大搜索范围（前后2页）
        2. 降低大小阈值（5KB）
        3. 避免重复匹配同一张图
        4. 对未匹配的大图使用备用策略
        """
        figure_map = {}
        used_image_ids = set()  # 跟踪已使用的图片ID
        
        # 收集所有Figure引用及其所在页
        figure_pages = {}  # {1: [3, 5, 7], 2: [8, 9], ...}
        
        for text_data in self.texts:
            page = text_data["page"]
            refs = self.ref_extractor.extract_references(text_data["content"])
            
            for ref in refs:
                fig_num = ref["figure"]
                if fig_num not in figure_pages:
                    figure_pages[fig_num] = []
                if page not in figure_pages[fig_num]:
                    figure_pages[fig_num].append(page)
        
        print(f"[图片匹配] 找到的Figure引用: {dict(sorted(figure_pages.items()))}")
        
        # === 策略1: 基于引用匹配 ===
        for fig_num in sorted(figure_pages.keys()):
            pages = figure_pages[fig_num]
            # 找到第一次提到这个Figure的页面
            first_mention_page = min(pages)
            
            # 扩大搜索范围：前后2页
            search_pages = []
            for offset in range(-2, 3):  # -2, -1, 0, 1, 2
                page = first_mention_page + offset
                if page > 0:
                    search_pages.append(page)
            
            print(f"[图片匹配] Figure {fig_num}: 首次提及页{first_mention_page}，搜索范围{search_pages}")
            
            # 找到这些页上的所有图片（排除已使用的）
            candidate_images = [
                img for img in self.all_images 
                if img["page"] in search_pages and img["id"] not in used_image_ids
            ]
            
            if not candidate_images:
                print(f"[图片匹配] Figure {fig_num}: 未找到可用的候选图片")
                figure_map[fig_num] = None
                continue
            
            # 选择最大的图片（排除小logo）
            # 提高阈值到50KB，避免提取小图标
            large_images = [img for img in candidate_images if img["size"] > 50000]
            
            if not large_images:
                # 如果都很小，降低要求到20KB
                large_images = [img for img in candidate_images if img["size"] > 20000]
            
            if not large_images:
                # 实在没有，就选最大的
                large_images = candidate_images
            
            # 按大小排序，选最大的
            best_image = max(large_images, key=lambda x: x["size"])
            
            # 标记为已使用
            used_image_ids.add(best_image["id"])
            
            # 保存主图信息
            figure_map[fig_num] = {
                "path": best_image["path"],
                "page": best_image["page"],
                "subfigures": {},
                "split_attempted": False
            }
            
            print(f"[图片匹配] Figure {fig_num}: ✓ 匹配到图片ID={best_image['id']}, 页{best_image['page']}, {best_image['size']/1024:.1f}KB")
        
        # === 策略2: 备用策略 - 处理未被引用但很大的图片 ===
        # 找出所有未使用的大图（>50KB，避免小图标但不要错过中等图）
        unmatched_large_images = [
            img for img in self.all_images 
            if img["id"] not in used_image_ids and img["size"] > 50000
        ]
        
        if unmatched_large_images:
            print(f"[图片匹配] 发现 {len(unmatched_large_images)} 张未匹配的大图(>50KB)，启用备用策略...")
            
            # 按页面顺序和大小排序
            unmatched_large_images.sort(key=lambda x: (x["page"], -x["size"]))
            
            # 分配新的Figure编号
            next_fig_num = max(figure_map.keys()) + 1 if figure_map else 1
            
            for img in unmatched_large_images:
                # 避免编号冲突
                while next_fig_num in figure_map:
                    next_fig_num += 1
                
                figure_map[next_fig_num] = {
                    "path": img["path"],
                    "page": img["page"],
                    "subfigures": {},
                    "split_attempted": False
                }
                
                used_image_ids.add(img["id"])
                print(f"[图片匹配] Figure {next_fig_num} (备用): 页{img['page']}, {img['size']/1024:.1f}KB")
                
                next_fig_num += 1
        
        # 最终统计
        total_matched = len([v for v in figure_map.values() if v is not None])
        print(f"[图片匹配] 完成: 共匹配 {total_matched} 个Figure (基于引用: {len(figure_pages)}, 备用策略: {len(unmatched_large_images)})")
        
        return figure_map
    
    def query(self, question: str) -> Generator[Dict, None, None]:
        """回答问题"""
        
        if not self.texts:
            yield {"type": "error", "content": "请先上传PDF文献"}
            return
        
        print(f"[DEBUG] 问题: {question}")
        yield {"type": "thinking", "content": "🔍 正在分析..."}
        
        # 1. 提取Figure编号（支持子图）
        fig_ref = self._extract_figure_number(question)
        
        if fig_ref:
            fig_num = fig_ref["number"]
            subfig = fig_ref.get("subfigure")  # 可能是 "a", "b" 等
            
            print(f"[DEBUG] 查询 Figure {fig_num}{subfig or ''}")
            
            # 检查是否匹配到这个Figure
            if fig_num in self.figure_map and self.figure_map[fig_num]:
                fig_data = self.figure_map[fig_num]
                
                # **延迟分割：只在需要子图时才分割**
                if subfig and not fig_data.get("split_attempted", False):
                    # 用户询问子图，但还没分割过
                    if self.splitter.is_available():
                        yield {"type": "status", "content": f"🔍 检测 Figure {fig_num} 是否包含子图..."}
                        
                        try:
                            subfigs = self.splitter.split(
                                fig_data["path"],
                                str(self.data_dir / "images"),
                                fig_num
                            )
                            
                            fig_data["subfigures"] = subfigs
                            fig_data["split_attempted"] = True
                            
                            if subfigs:
                                subfig_labels = ", ".join(subfigs.keys())
                                yield {"type": "status", "content": f"✅ 成功分割出 {len(subfigs)} 个子图: {subfig_labels}"}
                                
                                # 返回所有子图，添加到侧边栏
                                for label, path in subfigs.items():
                                    image_filename = Path(path).name
                                    yield {
                                        "type": "figure",
                                        "data": {
                                            "path": f"images/{image_filename}",
                                            "label": f"Figure {fig_num}{label}",
                                            "page": fig_data["page"],
                                            "type": "subfigure"
                                        }
                                    }
                            else:
                                yield {"type": "status", "content": f"ℹ️  Figure {fig_num} 未检测到子图，将作为整图分析"}
                        except Exception as e:
                            yield {"type": "status", "content": f"⚠️  子图分割失败: {str(e)}，将使用完整图片"}
                            fig_data["split_attempted"] = True
                    else:
                        yield {"type": "status", "content": f"ℹ️  子图分割功能未启用，将使用完整图片"}
                        fig_data["split_attempted"] = True
                
                # 如果询问的是整图但还没分割过，也尝试分割（可能有子图）
                elif not subfig and not fig_data.get("split_attempted", False):
                    if self.splitter.is_available():
                        yield {"type": "status", "content": f"🔍 正在检测 Figure {fig_num} 的子图..."}
                        
                        try:
                            subfigs = self.splitter.split(
                                fig_data["path"],
                                str(self.data_dir / "images"),
                                fig_num
                            )
                            
                            fig_data["subfigures"] = subfigs
                            fig_data["split_attempted"] = True
                            
                            if subfigs:
                                subfig_labels = ", ".join(subfigs.keys())
                                yield {"type": "status", "content": f"💡 检测到 {len(subfigs)} 个子图 ({subfig_labels})，如需单独分析可指定子图编号"}
                                
                                # 返回所有子图，添加到侧边栏
                                for label, path in subfigs.items():
                                    image_filename = Path(path).name
                                    yield {
                                        "type": "figure",
                                        "data": {
                                            "path": f"images/{image_filename}",
                                            "label": f"Figure {fig_num}{label}",
                                            "page": fig_data["page"],
                                            "type": "subfigure"
                                        }
                                    }
                        except Exception as e:
                            print(f"[DEBUG] 子图分割失败: {e}")
                            fig_data["split_attempted"] = True
                
                # **关键：选择正确的图片**
                if subfig and subfig in fig_data.get("subfigures", {}):
                    # 用户问子图 → 只给模型看子图！
                    image_path = fig_data["subfigures"][subfig]
                    label = f"Figure {fig_num}{subfig}"
                    print(f"[DEBUG] 使用子图: {image_path}")
                else:
                    # 用户问主图 → 给完整图
                    image_path = fig_data["path"]
                    label = f"Figure {fig_num}"
                    if subfig:
                        print(f"[DEBUG] 未找到子图{subfig}，使用完整图")
                    print(f"[DEBUG] 使用主图: {image_path}")
                
                # 返回图片（修复：使用相对路径）
                # 去掉路径前缀，只保留文件名
                image_filename = Path(image_path).name
                
                if subfig:
                    yield {"type": "thinking", "content": f"📍 找到 Figure {fig_num}{subfig}"}
                else:
                    yield {"type": "thinking", "content": f"📍 找到 Figure {fig_num}"}
                
                yield {
                    "type": "figure",
                    "data": {
                        "path": f"images/{image_filename}",  # 使用相对路径
                        "label": label,
                        "page": fig_data["page"]
                    }
                }
                
                # **立即分析图片（不需要用户再问）**
                yield {"type": "thinking", "content": "👀 正在分析图片内容..."}
                
                # 获取文中描述
                description = self._get_figure_description(fig_num, subfig)
                
                # 构建分析prompt
                analysis_prompt = f"""请分析这个{'子' if subfig else ''}图。

问题：{question}

文中描述：
{description}

请详细分析图片内容，包括：
1. 图片展示的内容
2. 关键信息和数据
3. 与研究的关系

用中文回答。"""
                
                # 使用LLM分析
                try:
                    messages = [
                        {"role": "system", "content": "你是一个专业的文献分析助手。"},
                        {"role": "user", "content": analysis_prompt}
                    ]
                    
                    full_answer = ""
                    for chunk in self.llm.stream_chat(messages):
                        full_answer += chunk
                        yield {"type": "answer_chunk", "content": chunk}
                    
                    if not full_answer:
                        # 流式失败，尝试普通调用
                        full_answer = self.llm.chat(messages)
                        yield {"type": "answer", "content": full_answer}
                    else:
                        yield {"type": "answer_done", "content": full_answer}
                except Exception as e:
                    print(f"[ERROR] 图片分析失败: {e}")
                    # 返回文本描述
                    answer = f"**{label}** (第{fig_data['page']}页)\n\n{description}"
                    yield {"type": "answer", "content": answer}
                
                return
            else:
                yield {"type": "error", "content": f"未找到 Figure {fig_num}（可能文中未提及或图片提取失败）"}
                return
        
        # ... 后续代码不变 ...
        
        # 2. 模糊图片搜索
        if self._is_figure_question(question):
            yield {"type": "thinking", "content": "🔍 正在搜索相关图片..."}
            
            best_fig = self._search_figure_by_description(question)
            
            if best_fig:
                fig_num, score = best_fig
                img_info = self.figure_map[fig_num]
                
                yield {"type": "thinking", "content": f"📍 找到 Figure {fig_num} (相关度 {score:.0%})"}
                
                yield {
                    "type": "figure",
                    "data": {
                        "path": img_info["path"],
                        "label": f"Figure {fig_num}",
                        "page": img_info["page"]
                    }
                }
                
                description = self._get_figure_description(fig_num)
                answer = f"根据文中描述，**Figure {fig_num}**最相关：\n\n{description}"
                
                yield {"type": "answer", "content": answer}
                return
        
        # 3. 文本问答
        yield {"type": "thinking", "content": "💭 正在生成回答..."}
        
        # 简单问候
        greetings = ["你好", "您好", "hi", "hello"]
        if any(g in question.lower() for g in greetings):
            answer = """你好！我是文献阅读助手。

我可以帮你：
- 📖 理解文献内容
- 🖼️ 查找图片（通过Figure编号或描述）
- 💬 回答问题

试试问：
• "Figure 1展示了什么？"
• "这篇文章的主要方法？"
• "哪张图展示了架构？"
"""
            yield {"type": "answer", "content": answer}
            return
        
        # 检索相关文本
        relevant = self._search_text(question, top_k=5)
        
        if relevant:
            context = "\n\n".join(relevant)
        else:
            context = self.full_text[:3000]
        
        prompt = f"""请根据文献内容回答问题。

问题：{question}

文献内容：
{context}

请用中文详细回答。"""
        
        # LLM回答
        try:
            messages = [
                {"role": "system", "content": "你是一个专业的文献阅读助手。"},
                {"role": "user", "content": prompt}
            ]
            
            full_answer = ""
            for chunk in self.llm.stream_chat(messages):
                full_answer += chunk
                yield {"type": "answer_chunk", "content": chunk}
            
            if not full_answer:
                # 如果流式失败，尝试普通调用
                full_answer = self.llm.chat(messages)
                yield {"type": "answer", "content": full_answer}
            else:
                yield {"type": "answer_done", "content": full_answer}
        except Exception as e:
            print(f"[ERROR] LLM调用失败: {e}")
            import traceback
            traceback.print_exc()
            yield {"type": "error", "content": f"LLM调用失败: {str(e)}"}
    
    def _extract_figure_number(self, text: str) -> Optional[Dict]:
        """提取Figure编号（支持子图，支持中文）"""
        patterns = [
            # Figure 1a, Figure 1.a, Figure 1(a), Figure 1-a
            (r'[Ff]igure?\s*(\d+)\s*[-\.\(]?\s*([a-zA-Z])\s*[\)]?', True),
            # Fig. 1a, Fig 1a
            (r'[Ff]ig\.?\s*(\d+)\s*[-\.\(]?\s*([a-zA-Z])\s*[\)]?', True),
            # 图1a, 图1-a, 图1.a, 图 1 a
            (r'图\s*(\d+)\s*[-\.\(]?\s*([a-zA-Z])\s*[\)]?', True),
            # 中文：图1子图a, 图1的子图a  
            (r'图\s*(\d+)\s*(?:的)?子图\s*([a-zA-Z])', True),
            # 中文：figure1子图c
            (r'[Ff]igure?\s*(\d+)\s*子图\s*([a-zA-Z])', True),
            # Figure 1 (without subfigure)
            (r'[Ff]igure?\s*(\d+)(?!\s*[a-zA-Z])', False),
            # Fig. 1
            (r'[Ff]ig\.?\s*(\d+)(?!\s*[a-zA-Z])', False),
            # 图1
            (r'图\s*(\d+)(?!\s*[a-zA-Z])', False),
        ]
        
        for pattern, has_subfig in patterns:
            match = re.search(pattern, text)
            if match:
                result = {"number": int(match.group(1))}
                if has_subfig and len(match.groups()) > 1:
                    result["subfigure"] = match.group(2).lower()  # 统一转小写
                return result
        
        return None
    
    def _is_figure_question(self, text: str) -> bool:
        """判断是否图片问题"""
        keywords = ["哪张图", "什么图", "图片", "figure", "展示", "显示", "架构", "流程"]
        return any(kw in text.lower() for kw in keywords)
    
    def _get_figure_description(self, fig_num: int, subfig: Optional[str] = None) -> str:
        """获取Figure的文中描述（支持子图）"""
        descriptions = []
        
        for text_data in self.texts:
            refs = self.ref_extractor.extract_references(text_data["content"])
            
            for ref in refs:
                # 如果指定了子图，只匹配该子图
                if ref["figure"] == fig_num:
                    if subfig:
                        # 查询子图，只返回提到该子图的描述
                        if ref.get("subfigure") == subfig:
                            context = self.ref_extractor.get_context(text_data["content"], ref, 250)
                            descriptions.append(context)
                    else:
                        # 查询主图，返回所有描述
                        context = self.ref_extractor.get_context(text_data["content"], ref, 250)
                        descriptions.append(context)
        
        if descriptions:
            # 去重并限制数量
            unique_desc = []
            seen = set()
            for desc in descriptions:
                if desc not in seen:
                    unique_desc.append(desc)
                    seen.add(desc)
                    if len(unique_desc) >= 3:
                        break
            
            return "\n\n".join(unique_desc)
        else:
            if subfig:
                return f"文中未找到关于Figure {fig_num}{subfig}的明确描述。"
            else:
                return f"文中未找到关于Figure {fig_num}的明确描述。"
    
    def _search_figure_by_description(self, query: str) -> Optional[tuple]:
        """根据描述搜索Figure"""
        best_fig = None
        best_score = 0
        
        for fig_num in self.figure_map.keys():
            desc = self._get_figure_description(fig_num)
            score = self._similarity(query, desc)
            
            if score > best_score:
                best_score = score
                best_fig = (fig_num, score)
        
        if best_score > 0.2:
            return best_fig
        return None
    
    def _search_text(self, query: str, top_k: int = 5) -> List[str]:
        """检索文本"""
        query_words = set(w for w in query.lower().split() if len(w) > 1)
        
        if not query_words:
            return [t["content"] for t in self.texts[:3]]
        
        scored = []
        for text_data in self.texts:
            content = text_data["content"]
            content_words = set(content.lower().split())
            
            score = len(query_words & content_words) * 2
            
            for word in query_words:
                if len(word) > 2 and word in content.lower():
                    score += 5
            
            if score > 0:
                scored.append((score, content))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        
        if not scored:
            return [t["content"] for t in self.texts[:3]]
        
        return [text for _, text in scored[:top_k]]
    
    def _similarity(self, text1: str, text2: str) -> float:
        """计算相似度"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1:
            return 0.0
        
        return len(words1 & words2) / len(words1)
    
    def _is_english(self, text: str) -> bool:
        """判断文本是否主要是英文"""
        # 简单判断：如果英文字符占比>60%，认为是英文
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in text if c.isalpha())
        
        if total_chars == 0:
            return False
        
        return english_chars / total_chars > 0.6
    
    def auto_split_all_figures(self):
        """自动分割所有Figure的子图"""
        if not self.splitter.is_available():
            print("⚠️  子图分割器不可用，跳过自动分割")
            return
        
        print("🔍 开始自动分割子图...")
        total_subfigures = 0
        
        for fig_num, fig_data in list(self.figure_map.items())[:5]:  # 限制前5个
            if not fig_data or fig_data.get("split_attempted"):
                continue
            
            try:
                print(f"  分割 Figure {fig_num}...")
                subfigs = self.splitter.split(
                    fig_data["path"],
                    str(self.data_dir / "images"),
                    fig_num,
                    use_numbers=True
                )
                
                if subfigs:
                    fig_data["subfigures"] = subfigs
                    fig_data["split_attempted"] = True
                    total_subfigures += len(subfigs)
                    print(f"  ✅ Figure {fig_num}: {len(subfigs)} 个子图")
                else:
                    fig_data["split_attempted"] = True
                    print(f"  ℹ️  Figure {fig_num}: 无子图")
                    
            except Exception as e:
                print(f"  ❌ Figure {fig_num} 分割失败: {e}")
                fig_data["split_attempted"] = True
                continue
        
        if total_subfigures > 0:
            print(f"✅ 自动分割完成，共 {total_subfigures} 个子图")
        else:
            print("ℹ️  未检测到复合图")

