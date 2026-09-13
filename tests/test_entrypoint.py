import runpy
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI


ENTRYPOINT = Path(__file__).resolve().parents[1] / "main.py"


def test_root_entrypoint_exports_app_without_starting_server():
    with patch("uvicorn.run") as run:
        namespace = runpy.run_path(str(ENTRYPOINT))
    assert isinstance(namespace["app"], FastAPI)
    run.assert_not_called()


def test_running_main_uses_explicit_application():
    with patch("uvicorn.run") as run:
        runpy.run_path(str(ENTRYPOINT), run_name="__main__")
    run.assert_called_once_with(
        "cognitive_os.main:app", host="127.0.0.1", port=8000
    )
