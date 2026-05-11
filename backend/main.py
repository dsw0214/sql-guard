
import os

from app.server import app

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("SQLGUARD_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.getenv("SQLGUARD_PORT", "8000").strip() or "8000")
    except ValueError:
        port = 8000

    uvicorn.run(app, host=host, port=port)
