"""
A23 项目主入口 - 基于大语言模型的文档理解与多源数据融合系统
负责人: 成员1（队长）
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from config import settings
from db.database import init_db
from api.upload import router as upload_router
from api.query import router as query_router
from api.fill import router as fill_router
from api.files import router as files_router


# ── 全局异常类 ────────────────────────────────────────────────
class AppError(Exception):
    def __init__(self, status_code: int, error_code: str, detail: str):
        self.status_code = status_code
        self.error_code  = error_code
        self.detail      = detail


# ── 启动/关闭生命周期 ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()
    print(f"✅ 数据库初始化完成")
    print(f"✅ 服务启动: http://{settings.host}:{settings.port}")
    print(f"✅ API文档:  http://{settings.host}:{settings.port}/docs")
    yield
    print("🛑 服务关闭")


# ── FastAPI 实例 ───────────────────────────────────────────────
app = FastAPI(
    title="A23 文档理解与多源数据融合系统",
    description="基于大语言模型的文档理解与多源数据融合系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS（允许Gradio前端跨域访问）────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局异常处理器 ─────────────────────────────────────────────
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "detail":     exc.detail,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "detail":     f"服务内部错误: {str(exc)}",
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }
    )

# ── 注册路由 ──────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(fill_router)
app.include_router(files_router)


# ── 健康检查 ──────────────────────────────────────────────────
@app.get("/health", tags=["系统"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ── 启动入口 ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
