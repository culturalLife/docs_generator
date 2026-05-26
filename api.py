"""
api.py — Production FastAPI Application
========================================
Entry point for the VM-deployed docs_gen pipeline.

Endpoints:
  GET  /health             → Liveness check for VM/monitoring
  POST /api/generate-docs  → Triggers full pipeline, returns .docx as download

Design decisions:
  - FILE-DRIVEN: reads prompt.md and data.json from disk (configured in config.py)
  - No frontend served (VM-only, no UI required)
  - No auth (private network VM)
  - Each request gets a short UUID (request_id) threaded through all log lines
  - Errors are sanitized: caller sees clean HTTP messages, full detail in logs
  - Startup validation: fails fast if required files or API key are missing
"""

import json
import uuid
import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

import config # pyrefly: ignore [missing-import]
from logger import get_logger # pyrefly: ignore [missing-import]
from summarize_data import clean_data_summary # pyrefly: ignore [missing-import]
from report_generator import generate_report # pyrefly: ignore [missing-import]

logger = get_logger("api")

# ─── Request Schema ─────────────────────────────────────────────────────────────
class GenerateDocsRequest(BaseModel):
    prompt: Optional[str] = None
    json_payload: Optional[Dict[str, Any]] = None

# ─── App Initialization ─────────────────────────────────────────────────────────
app = FastAPI(
    title="Docs Gen API",
    version="1.0.0",
    description=(
        "Production pipeline: accepts a trigger call, reads prompt.md and data.json "
        "from disk, runs parallel Mistral generation, returns a boardroom-grade .docx."
    ),
    # Disable the interactive Swagger UI docs on production if desired
    # docs_url=None,
    # redoc_url=None,
)

# Enable CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins. For production, restrict this to specific domains.
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allows all headers
)

# ─── Startup Validation ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_checks():
    """
    Runs once when the server starts.
    Validates that all required files and directories are in place.
    Fails fast with a clear error rather than silently at request time.
    """
    errors = []

    # File checks are only relevant in file-driven mode
    if getattr(config, "INPUT_MODE", "file") == "file":
        if not config.PROMPT_FILE_PATH.exists():
            errors.append(f"Prompt file not found: {config.PROMPT_FILE_PATH}")
        if not config.JSON_PAYLOAD_PATH.exists():
            errors.append(f"JSON payload not found: {config.JSON_PAYLOAD_PATH}")

        if errors:
            for err in errors:
                logger.error(f"[STARTUP] {err}")
            raise RuntimeError(
                "Startup validation failed. Fix the above errors before starting the server."
            )
    else:
        logger.info("[STARTUP] Input mode is 'api'. Skipping prompt.md and data.json existence checks.")

    # Ensure output directories exist
    config.REPORTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"[STARTUP] Reports directory ready: {config.REPORTS_OUTPUT_DIR}")
    
    if getattr(config, "INPUT_MODE", "file") == "file":
        logger.info(
            f"[STARTUP] Server ready | model={config.GENERATION_MODEL} "
            f"| prompt={config.PROMPT_FILE_PATH.name} "
            f"| payload={config.JSON_PAYLOAD_PATH.name}"
        )
    else:
        logger.info(
            f"[STARTUP] Server ready in API mode | model={config.GENERATION_MODEL} "
            f"| parallel_calls={config.MAX_PARALLEL_CALLS}"
        )

# ─── Health Check ───────────────────────────────────────────────────────────────
@app.get("/health", summary="Liveness check")
async def health():
    """
    Returns server status and current configuration.
    Hit this endpoint to confirm the VM service is alive before making a generate call.
    """
    return {
        "status": "ok",
        "version": "1.0.0",
        "model": config.GENERATION_MODEL,
        "input_mode": getattr(config, "INPUT_MODE", "file"),
        "prompt_file": config.PROMPT_FILE_PATH.name if getattr(config, "INPUT_MODE", "file") == "file" else "N/A (API Mode)",
        "payload_file": config.JSON_PAYLOAD_PATH.name if getattr(config, "INPUT_MODE", "file") == "file" else "N/A (API Mode)",
        "parallel_calls": config.MAX_PARALLEL_CALLS,
    }


# ─── Main Endpoint ──────────────────────────────────────────────────────────────
@app.post(
    "/api/generate-docs",
    summary="Trigger report generation",
    response_description="Returns a .docx report as a file download",
)
async def generate_docs(request: Request, payload: Optional[GenerateDocsRequest] = None):
    """
    Triggers the full pipeline:
      1. Reads prompt and JSON data (either from API request body or from disk depending on INPUT_MODE)
      2. Validates and converts JSON data to markdown summary
      3. Fans out parallel Mistral API calls (x3)
      4. Assembles a boardroom-grade .docx
      5. Returns it as a downloadable file
    """
    request_id = str(uuid.uuid4())[:8].upper()
    t_start = datetime.datetime.now()
    logger.info(f"[{request_id}] ── New request received from {request.client.host} ──")

    try:
        input_mode = getattr(config, "INPUT_MODE", "file")

        if input_mode == "api":
            # API-driven mode: accept prompt and json_payload from the request body
            if not payload or not payload.prompt or not payload.json_payload:
                missing_fields = []
                if not payload:
                    missing_fields = ["request body"]
                else:
                    if not payload.prompt:
                        missing_fields.append("prompt")
                    if not payload.json_payload:
                        missing_fields.append("json_payload")
                error_msg = f"Missing required parameter(s): {', '.join(missing_fields)}"
                logger.error(f"[{request_id}] API Validation error: {error_msg}")
                raise HTTPException(status_code=400, detail=error_msg)

            prompt_text = payload.prompt
            json_data = payload.json_payload
            logger.info(f"[{request_id}] Using prompt and JSON payload provided via API.")
        else:
            # File-driven mode: read from disk (previous implementation)
            logger.info(f"[{request_id}] Loading prompt from {config.PROMPT_FILE_PATH.name}")
            try:
                prompt_text = config.PROMPT_FILE_PATH.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.error(f"[{request_id}] prompt.md not found at {config.PROMPT_FILE_PATH}")
                raise HTTPException(status_code=500, detail="Server configuration error: prompt file missing.")

            logger.info(f"[{request_id}] Loading JSON payload from {config.JSON_PAYLOAD_PATH.name}")
            try:
                raw_json = config.JSON_PAYLOAD_PATH.read_text(encoding="utf-8")
                json_data = json.loads(raw_json)
            except FileNotFoundError:
                logger.error(f"[{request_id}] data.json not found at {config.JSON_PAYLOAD_PATH}")
                raise HTTPException(status_code=500, detail="Server configuration error: data file missing.")
            except json.JSONDecodeError as e:
                logger.error(f"[{request_id}] data.json is not valid JSON: {e}")
                raise HTTPException(status_code=500, detail="Server configuration error: data file is not valid JSON.")

        # ── Step 3: Summarize JSON → markdown ───────────────────────────────────
        logger.info(f"[{request_id}] Summarizing JSON payload...")
        try:
            data_summary_text = clean_data_summary(json_data)
        except ValueError as e:
            logger.error(f"[{request_id}] Payload validation failed: {e}")
            raise HTTPException(
                status_code=400 if input_mode == "api" else 500, 
                detail=f"Data payload error: {e}"
            )

        # ── Step 4: Generate report ──────────────────────────────────────────────
        timestamp = t_start.strftime("%Y%m%d_%H%M%S")
        filename = f"{config.REPORT_FILENAME_PREFIX}_{timestamp}.docx"
        output_path = config.REPORTS_OUTPUT_DIR / filename

        logger.info(f"[{request_id}] Starting pipeline → output: {filename}")
        try:
            generate_report(
                prompt_text=prompt_text,
                data_summary_text=data_summary_text,
                output_path=str(output_path),
                request_id=request_id,
            )
        except RuntimeError as e:
            # Raised by report_generator when a parallel part fails after all retries
            logger.error(f"[{request_id}] Pipeline failure: {e}")
            raise HTTPException(
                status_code=503,
                detail="Report generation failed — upstream API error. Check server logs.",
            )
        except Exception as e:
            logger.exception(f"[{request_id}] Unexpected pipeline error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error during report generation. Check server logs.",
            )

        # ── Step 5: Return as downloadable file ──────────────────────────────────
        elapsed = (datetime.datetime.now() - t_start).total_seconds()
        logger.info(f"[{request_id}] ── Request completed in {elapsed:.1f}s → {filename} ──")

        return FileResponse(
            path=str(output_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    except HTTPException:
        # Let FastAPI handle these normally (don't double-log)
        raise
    except Exception as e:
        # Catch-all: should never reach here, but log if it does
        elapsed = (datetime.datetime.now() - t_start).total_seconds()
        logger.exception(f"[{request_id}] Unhandled exception after {elapsed:.1f}s: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error. Check server logs.")


# ─── Custom Error Responses ─────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "available_endpoints": ["GET /health", "POST /api/generate-docs"]},
    )
