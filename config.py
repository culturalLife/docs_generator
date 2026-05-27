"""
config.py — Central Configuration for docs_gen Pipeline
=========================================================
All tuneable knobs live here. Change values here only; never hardcode in logic files.

INPUT MODE:
  Currently FILE-DRIVEN: the API reads prompt.md and data.json from disk.
  To switch to API-DRIVEN (caller POSTs prompt + payload), set INPUT_MODE = "api"
  and update api.py accordingly.
"""

from pathlib import Path

# ─── Base Directory ────────────────────────────────────────────────────────────
# Absolute path to the VMCompatible folder — all relative paths resolve from here.
BASE_DIR = Path(__file__).parent

# ─── Input Mode ────────────────────────────────────────────────────────────────
# Set to "file" to read prompt.md and data.json from disk.
# Set to "api" to accept prompt and json_payload in the POST request body.
INPUT_MODE: str = "api"

# ─── Model Settings ────────────────────────────────────────────────────────────
# Which Mistral model to use for report generation.
# Options: "mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"
GENERATION_MODEL: str = "mistral-large-latest"

# LLM temperature. 0.0 = deterministic, 1.0 = creative.
TEMPERATURE: float = 0.2

# Number of parallel Mistral API calls to fan out during generation.
# Currently 3 maps 1:1 to the 3 section groups in the report.
# Changing this requires updating the `parts` list in report_generator.py too.
MAX_PARALLEL_CALLS: int = 3

# ─── Input Paths (File-Driven Mode) ────────────────────────────────────────────
# The pipeline reads these two files from disk at request time.
# Update these paths when deploying to the VM if directory layout differs.
PROMPT_FILE_PATH: Path = BASE_DIR / "prompt.md"
JSON_PAYLOAD_PATH: Path = BASE_DIR / "data.json"

# ─── Output Settings ───────────────────────────────────────────────────────────
# Directory where generated .docx reports are saved.
REPORTS_OUTPUT_DIR: Path = BASE_DIR / "reports"

# Prefix used in report filenames: <PREFIX>_YYYYMMDD_HHMMSS.docx
REPORT_FILENAME_PREFIX: str = "InvestSLM_Report"

# ─── API Server Settings ───────────────────────────────────────────────────────
# Host and port uvicorn will bind to on the VM.
# 0.0.0.0 makes it reachable from outside the VM (private network).
API_HOST: str = "0.0.0.0"
API_PORT: int = 8000

# ─── Retry Settings ────────────────────────────────────────────────────────────
# How many times to retry a failed Mistral API call before giving up.
MAX_RETRIES: int = 3

# Base backoff in seconds. Actual wait = RETRY_BACKOFF_SECONDS * 2^(attempt-1)
# e.g. attempt 1 → 2s, attempt 2 → 4s, attempt 3 → 8s
RETRY_BACKOFF_SECONDS: float = 2.0

# ─── Logging Settings ──────────────────────────────────────────────────────────
# Log level: "DEBUG", "INFO", "WARNING", "ERROR"
LOG_LEVEL: str = "INFO"

# Rotating log file path. Set to None to disable file logging (console only).
LOG_FILE: Path = BASE_DIR / "logs" / "pipeline.log"

# Max size per log file before rotation (bytes). 5MB default.
LOG_MAX_BYTES: int = 5 * 1024 * 1024

# Number of rotated log backups to keep alongside the current log file.
LOG_BACKUP_COUNT: int = 3

# ─── Prompts & Directives ──────────────────────────────────────────────────────
# The system prompt template for Mistral.
# Use '{data_summary_text}' placeholder where the dynamically summarized JSON data should be injected.
SYSTEM_PROMPT_TEMPLATE: str = (
    "You are a senior AI strategist with deep expertise in domain-specific language model fine-tuning. "
    "The following is a complete consulting-led assessment of a customer engagement named InvestSLM:\n\n"
    "--- DATA CONTEXT ---\n{data_summary_text}\n--- END DATA CONTEXT ---\n\n"
    "IMPORTANT DIRECTIVES:\n"
    "1. Your response must be highly professional, suitable for boardroom executives.\n"
    "2. DO NOT use conversational fillers like 'I think', 'Here is the report', or 'Sure, I can help'.\n"
    "3. DO NOT use markdown code blocks (```) or double ticks (``). Render data cleanly.\n"
    "4. Format tabular data using standard markdown tables (with | separators) where required.\n"
    "5. Be assertive, evidence-based, and directive in your language.\n"
    "6. You MUST begin each section with a standard markdown H2 heading (e.g. '## 5. Recommended Training Method Stack'). "
    "DO NOT use bold styling '**Heading**' for section titles; always use markdown '##' so they are recognized by the document formatting engine."
)

