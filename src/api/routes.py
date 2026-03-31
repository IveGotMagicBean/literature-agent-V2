"""
API路由模块
定义所有API端点
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import json
import asyncio
import shutil
import tempfile

from src.core.app_state import AppState

router = APIRouter()


# === 数据模型 ===

class QueryRequest(BaseModel):
    question: str


class GenerateRequest(BaseModel):
    type: str  # "ppt" or "report"
    style: Optional[str] = "学术风格"
    language: Optional[str] = "中文"
    include_figures: Optional[bool] = True
    max_figures: Optional[int] = 5
    output_format: Optional[str] = "Word"


class SubfigureRequest(BaseModel):
    figure_num: int
    subfigure_label: Optional[str] = None


class SubfigureReportRequest(BaseModel):
    figure_num: int
    output_format: Optional[str] = "PDF"


# === 文件上传 ===

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """上传并解析PDF"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "只支持PDF文件")
    
    agent = AppState.get_agent()
    upload_path = Path("uploads") / file.filename
    upload_path.parent.mkdir(exist_ok=True)
    
    # 保存文件
    with open(upload_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 解析PDF
    events = []
    for event in agent.load_pdf(str(upload_path)):
        events.append(event)
    
    # 只在配置启用时才自动分割（默认关闭）
    if AppState.config["system"].get("auto_split_figures", False):
        try:
            agent.auto_split_all_figures()
        except Exception as e:
            print(f"自动分割子图失败: {e}")
    
    # 收集所有主图信息，用于侧边栏显示
    figures = []
    for fig_num, fig_data in agent.figure_map.items():
        if fig_data:
            image_path = Path(fig_data["path"])
            figures.append({
                "label": f"Figure {fig_num}",
                "path": f"images/{image_path.name}",
                "page": fig_data["page"],
                "type": "main"  # 标记为主图
            })
    
    return {
        "success": True,
        "filename": file.filename,
        "events": events,
        "stats": {
            "pages": len(agent.texts),
            "figures": len(agent.figure_map)
        },
        "figures": figures  # 返回所有主图
    }


@router.get("/load_example")
async def load_example():
    """加载示例文档"""
    example_path = Path("data/example/example.pdf")
    
    if not example_path.exists():
        raise HTTPException(404, "示例文档不存在")
    
    agent = AppState.get_agent()
    
    # 解析PDF
    events = []
    for event in agent.load_pdf(str(example_path)):
        events.append(event)
    
    # 收集所有主图信息
    figures = []
    for fig_num, fig_data in agent.figure_map.items():
        if fig_data:
            image_path = Path(fig_data["path"])
            figures.append({
                "label": f"Figure {fig_num}",
                "path": f"images/{image_path.name}",
                "page": fig_data["page"],
                "type": "main"
            })
    
    return {
        "success": True,
        "filename": "example.pdf",
        "events": events,
        "stats": {
            "pages": len(agent.texts),
            "figures": len(agent.figure_map)
        },
        "figures": figures
    }


# === 问答接口 ===

@router.post("/query")
async def query(req: QueryRequest):
    """智能问答（非流式）"""
    agent = AppState.get_agent()
    
    # 如果没有PDF，只允许简单对话
    if not agent.texts:
        # 简单的LLM对话
        try:
            llm = AppState.llm
            messages = [
                {"role": "system", "content": "你是一个友好的AI助手。"},
                {"role": "user", "content": req.question}
            ]
            answer = llm.chat(messages)
            return {"answer": answer, "figures": []}
        except Exception as e:
            return {"answer": f"你好！我是Literature Agent。\n\n当前未加载文献，我可以进行普通对话。你也可以上传PDF文献，我可以帮你分析文献内容、查找图表等。", "figures": []}
    
    router = AppState.get_router()
    
    response_text = ""
    figures = []
    downloads = []
    
    for event in router.route(req.question):
        if event["type"] == "figure":
            figures.append(event["data"])
        elif event["type"] in ["answer", "answer_chunk"]:
            response_text += event.get("content", "")
        elif event["type"] == "download":
            downloads.append(event["data"])
    
    result = {
        "answer": response_text or "未找到相关信息",
        "figures": figures
    }
    
    if downloads:
        result["downloads"] = downloads
    
    return result


@router.post("/query/stream")
async def query_stream(req: QueryRequest):
    """智能问答（流式）"""
    agent = AppState.get_agent()
    
    async def generate():
        # 如果没有PDF，简单对话
        if not agent.texts:
            yield f"data: {json.dumps({'type': 'status', 'content': '💬 普通对话模式'}, ensure_ascii=False)}\n\n"
            
            try:
                llm = AppState.llm
                messages = [
                    {"role": "system", "content": "你是一个友好的AI助手。"},
                    {"role": "user", "content": req.question}
                ]
                
                for chunk in llm.stream_chat(messages):
                    yield f"data: {json.dumps({'type': 'answer_chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'answer', 'content': '你好！我是Literature Agent。上传PDF文献后，我可以帮你分析文献内容。'}, ensure_ascii=False)}\n\n"
        else:
            # 有PDF，使用router
            router = AppState.get_router()
            for event in router.route(req.question):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# === 文档生成 ===

@router.post("/generate")
async def generate_document(req: GenerateRequest):
    """生成PPT或报告（流式，带进度）"""
    agent = AppState.get_agent()
    if not agent.texts:
        raise HTTPException(400, "请先上传PDF")
    
    async def generate_with_progress():
        try:
            doc_type = "PPT" if req.type == "ppt" else "报告"
            
            # 进度1: 开始生成
            yield f"data: {json.dumps({'type': 'progress', 'content': f'📝 开始生成{doc_type}...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            
            # 进度2: 收集内容
            yield f"data: {json.dumps({'type': 'progress', 'content': f'📚 正在收集文献内容...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            
            if req.type == "ppt":
                # 进度3: 分析图表
                yield f"data: {json.dumps({'type': 'progress', 'content': '🖼️ 正在处理图表...'}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
                
                # 生成PPT
                ppt_agent = AppState.ppt_agent
                file_path = ppt_agent.generate(
                    template=req.style,
                    language=req.language,
                    include_figures=req.include_figures,
                    max_figures=req.max_figures
                )
                
                yield f"data: {json.dumps({'type': 'progress', 'content': '✨ 正在美化PPT样式...'}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
            
            elif req.type == "report":
                # 进度3: 生成分析
                yield f"data: {json.dumps({'type': 'progress', 'content': '🔍 正在生成分析内容...'}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
                
                # 生成报告
                report_agent = AppState.report_agent
                file_path = report_agent.generate(
                    report_type="详细报告",
                    output_format=req.output_format,
                    include_figures=req.include_figures,
                    max_figures=req.max_figures
                )
                
                yield f"data: {json.dumps({'type': 'progress', 'content': '📄 正在格式化文档...'}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
            
            else:
                raise HTTPException(400, "未知的生成类型")
            
            # 完成
            yield f"data: {json.dumps({'type': 'progress', 'content': f'✅ {doc_type}生成完成！'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            
            # 返回下载链接
            result = {
                "type": "complete",
                "file_path": file_path,
                "download_url": f"/api/download?path={file_path}"
            }
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'content': f'生成失败: {str(e)}'}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_with_progress(),
        media_type="text/event-stream"
    )


# === 子图分析 ===

@router.post("/subfigure/analyze")
async def analyze_subfigure(req: SubfigureRequest):
    """分析子图"""
    agent = AppState.get_agent()
    if not agent.texts:
        raise HTTPException(400, "请先上传PDF")
    
    subfig_agent = AppState.subfigure_agent
    
    try:
        if req.subfigure_label:
            # 分析单个子图
            result = subfig_agent.analyze_subfigure(
                req.figure_num,
                req.subfigure_label
            )
        else:
            # 分析所有子图
            results = subfig_agent.analyze_all_subfigures(req.figure_num)
            result = {
                "figure": req.figure_num,
                "subfigures": results
            }
        
        return {"success": True, **result}
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"分析失败: {str(e)}")


@router.post("/subfigure/report")
async def generate_subfigure_report(req: SubfigureReportRequest):
    """生成子图分析报告"""
    agent = AppState.get_agent()
    if not agent.texts:
        raise HTTPException(400, "请先上传PDF")
    
    subfig_agent = AppState.subfigure_agent
    
    try:
        file_path = subfig_agent.generate_report(
            req.figure_num,
            req.output_format
        )
        
        return {
            "success": True,
            "file_path": file_path,
            "download_url": f"/api/download?path={file_path}"
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"生成失败: {str(e)}")


@router.post("/subfigure/ppt")
async def generate_subfigure_ppt(req: SubfigureRequest):
    """生成子图分析PPT"""
    agent = AppState.get_agent()
    if not agent.texts:
        raise HTTPException(400, "请先上传PDF")
    
    subfig_agent = AppState.subfigure_agent
    
    try:
        file_path = subfig_agent.generate_ppt(req.figure_num)
        
        return {
            "success": True,
            "file_path": file_path,
            "download_url": f"/api/download?path={file_path}"
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"生成失败: {str(e)}")


# === 文件下载 ===

@router.get("/download")
async def download_file(path: str):
    """下载文件或文件夹（打包为ZIP）"""
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    
    # 文件夹打包为ZIP
    if file_path.is_dir():
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            zip_path = tmp.name
        
        shutil.make_archive(
            zip_path.replace('.zip', ''),
            'zip',
            file_path.parent,
            file_path.name
        )
        
        return FileResponse(
            zip_path,
            filename=f"{file_path.name}.zip",
            media_type="application/zip"
        )
    
    # 单个文件直接返回
    return FileResponse(
        path,
        filename=file_path.name,
        media_type="application/octet-stream"
    )


# === 状态查询 ===

@router.get("/status")
async def get_status():
    """获取应用状态"""
    agent = AppState.get_agent()
    
    return {
        "loaded": len(agent.texts) > 0 if agent else False,
        "pages": len(agent.texts) if agent else 0,
        "figures": len(agent.figure_map) if agent else 0,
        "config": {
            "auto_analyze": AppState.config["system"]["auto_analyze"],
            "theme": AppState.config["ui"]["default_theme"]
        }
    }
