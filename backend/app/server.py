import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI()
    
    # CORS 配置 - 仅允许特定来源
    # 环境变量 ALLOWED_ORIGINS 示例: http://127.0.0.1:3000,http://localhost:3000
    allowed_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:8000"
    ).split(",")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],  # 仅需要的方法
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],  # 仅需要的请求头
    )
    app.include_router(router)
    return app


app = create_app()
