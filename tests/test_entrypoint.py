import runpy
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTRYPOINT = Path(__file__).resolve().parents[1] / "main.py"


def test_root_entrypoint_exports_app_without_starting_server():
    with patch("uvicorn.run") as run:
        namespace = runpy.run_path(str(ENTRYPOINT))
    assert isinstance(namespace["app"], FastAPI)
    run.assert_not_called()


def test_main_registers_complete_api_without_launching_uvicorn():
    with patch("uvicorn.run") as run:
        namespace = runpy.run_path(str(ENTRYPOINT), run_name="__main__")
    run.assert_not_called()
    with TestClient(namespace["app"]) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/docs").status_code == 200
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/learning-sessions" in paths


def test_internal_factory_does_not_create_another_global_app():
    import cognitive_os.main as factory_module

    assert not hasattr(factory_module, "app")
