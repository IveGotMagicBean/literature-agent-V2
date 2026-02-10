"""
Literature Agent - 主应用入口
智能文献阅读助手
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
import sys

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.api.routes import router
from src.core.app_state import AppState


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    await AppState.initialize()
    print("✅ Literature Agent 已启动")
    print(f"   访问地址: http://localhost:7860")
    
    yield
    
    # 关闭时清理
    await AppState.cleanup()


# 创建必要目录（在创建app之前）
Path("static").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)
Path("uploads").mkdir(exist_ok=True)

# 创建FastAPI应用
app = FastAPI(
    title="Literature Agent API",
    description="智能文献阅读助手",
    version="2.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 根路径返回主页
@app.get("/")
async def root():
    """返回主页"""
    return FileResponse("static/index.html")

# 注册API路由
app.include_router(router, prefix="/api")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/data", StaticFiles(directory="data"), name="data")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
