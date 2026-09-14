"""FastAPI JSON API for Vercel. Streamlit in frontend/ is the UI."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from comet import __version__
from comet.exceptions import ConfigurationError
from comet.ui.pipeline import (
    PRODUCT_FULL_FORM,
    PRODUCT_NAME,
    SAMPLE_DOCUMENTS,
    build_settings,
    default_output_dir,
    default_tmp_root,
    run_batch,
    stage_uploads,
    summary_to_api,
)

logger = logging.getLogger(__name__)
app = FastAPI(title=PRODUCT_NAME)
_NO_STORE = {"Cache-Control": "no-store"}
_SAMPLE_FILES = {path.name: (path, mime) for _label, _title, path, mime in SAMPLE_DOCUMENTS}

_default_origins = "http://localhost:8501,http://127.0.0.1:8501"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get("COMET_CORS_ORIGINS", _default_origins).split(",")
        if origin.strip()
    ],
    allow_origin_regex=r"https://.*\.streamlit\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


def _json(payload: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers=_NO_STORE)


@app.get("/")
def home() -> JSONResponse:
    return _json(
        {
            "name": PRODUCT_NAME,
            "full_form": PRODUCT_FULL_FORM,
            "version": __version__,
            "process": "/api/process",
            "samples": "/api/samples",
        }
    )


@app.get("/api/samples")
def list_samples() -> JSONResponse:
    items = [
        {"filename": path.name, "title": title, "mime": mime}
        for _label, title, path, mime in SAMPLE_DOCUMENTS
        if path.is_file()
    ]
    return _json({"samples": items})


@app.get("/samples/{filename}")
def download_sample(filename: str) -> FileResponse:
    item = _SAMPLE_FILES.get(filename)
    if item is None or not item[0].is_file():
        raise HTTPException(status_code=404, detail="Sample not found")
    path, mime = item
    return FileResponse(path, media_type=mime, filename=path.name)


@app.post("/api/process")
async def process_files(files: list[UploadFile] = File(...)) -> JSONResponse:
    try:
        payloads = [(item.filename or "", await item.read()) for item in files]
        input_dir = stage_uploads(payloads, default_tmp_root())
        settings = build_settings(str(input_dir), str(default_output_dir()), True)
        summary = run_batch(settings)
    except ConfigurationError as exc:
        return _json({"detail": str(exc)}, status_code=400)
    except OSError as exc:
        logger.exception("api_process_os_error")
        return _json(
            {"detail": f"The run could not access its files: {exc}"},
            status_code=500,
        )
    except Exception as exc:
        logger.exception("api_process_failed")
        return _json(
            {
                "detail": (
                    "The workflow stopped unexpectedly. "
                    f"{type(exc).__name__}: {exc}"
                )
            },
            status_code=500,
        )
    return _json(summary_to_api(summary))
