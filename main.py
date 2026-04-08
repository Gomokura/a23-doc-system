"""
A23 项目主入口 - 基于大语言模型的文档理解与多源数据融合系统
负责人: 成员1（队长）
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from config import settings
from db.database import init_db, check_db_health
from api.upload import router as upload_router
from api.query import router as query_router
from api.fill import router as fill_router
from api.files import router as files_router
from api.document_ops import router as document_ops_router
from errors import AppError
# ── 启动/关闭生命周期 ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()
    print("[OK] Database initialized")
    print(f"[OK] Server running: http://{settings.host}:{settings.port}")
    print(f"[OK] API docs:        http://{settings.host}:{settings.port}/docs")
    yield
    print("[STOP] Server shutting down")


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

# ── 根路径（浏览器打开 localhost:8000 时不再 404）────────────────
@app.get("/", include_in_schema=False)
async def root():
    """本端口为 API 服务；带界面的前端默认在 Vite 开发服务器上运行。"""
    return {
        "service": "A23 文档理解与多源数据融合系统",
        "api_docs": "/docs",
        "health": "/health",
        "frontend_hint": "页面请在项目目录执行: cd modules/frontend && pnpm dev，然后打开 http://localhost:5173",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# ── 注册路由 ──────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(fill_router)
app.include_router(files_router)
app.include_router(document_ops_router)


# ── 健康检查 ──────────────────────────────────────────────────
@app.get("/health", tags=["系统"])
async def health():
    db_status = check_db_health()
    now = datetime.now(timezone.utc).isoformat()

    if not db_status["ok"]:
        # 依赖挂掉返回 503
        return JSONResponse(
            status_code=503,
            content={
                "status":    "degraded",
                "version":   "1.0.0",
                "timestamp": now,
                "database":  db_status,
            },
        )

    return {
        "status":    "ok",
        "version":   "1.0.0",
        "timestamp": now,
        "database":  db_status,
    }


# ── 启动入口 ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
