"""Explicit entry point for Uvicorn and Python run configurations."""

from cognitive_os.main import app

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("cognitive_os.main:app", host="127.0.0.1", port=8000)
