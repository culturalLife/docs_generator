# docs_gen — VM Deployment Guide

## What This Is
A production-grade FastAPI service that generates boardroom-grade `.docx` reports
using parallel Mistral API calls. Triggered via a single HTTP endpoint.

---

## Files on the VM

```
VMCompatible/
├── api.py                ← FastAPI app (start this)
├── config.py             ← All configuration knobs
├── logger.py             ← Logging setup (imported by all modules)
├── report_generator.py   ← Core Mistral pipeline
├── summarize_data.py     ← JSON → markdown summarizer
├── prompt.md             ← The report prompt (edit to customize)
├── data.json             ← The consulting questionnaire payload
├── requirements.txt      ← Python dependencies
├── .env                  ← API key (never commit this)
├── logs/                 ← Auto-created on first run
└── reports/              ← Auto-created on first run, .docx files saved here
```

---

## VM Setup (One-Time)

```bash
# 1. Copy the VMCompatible folder to the VM
scp -r ./VMCompatible user@your-vm-ip:/opt/docs-gen

# 2. SSH into the VM
ssh user@your-vm-ip

# 3. Navigate to the app directory
cd /opt/docs-gen

# 4. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Linux/Mac
# .venv\Scripts\activate        # Windows

# 5. Install dependencies
pip install -r requirements.txt

# 6. Set up the API key
cp .env.example .env
nano .env                       # Fill in MISTRAL_API_KEY=your_actual_key
```

---

## Starting the Server

```bash
# Development (auto-reload on file change)
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Production (no reload, adjust workers if needed)
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 1
```

---

## API Usage

### Check if the server is alive
```bash
curl http://your-vm-ip:8000/health
```
Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "model": "mistral-medium-latest",
  "prompt_file": "prompt.md",
  "payload_file": "data.json",
  "parallel_calls": 3
}
```

### Trigger report generation and download the .docx
```bash
curl -X POST http://your-vm-ip:8000/api/generate-docs \
     --output report.docx
```

The response is a binary `.docx` file download. The file is also saved to the
`reports/` directory on the VM.

---

## Configuration (config.py)

| Variable | Default | What It Controls |
|---|---|---|
| `GENERATION_MODEL` | `mistral-medium-latest` | Mistral model used |
| `TEMPERATURE` | `0.2` | LLM determinism (0=strict, 1=creative) |
| `MAX_PARALLEL_CALLS` | `3` | Parallel Mistral API threads |
| `PROMPT_FILE_PATH` | `prompt.md` | Path to the report prompt |
| `JSON_PAYLOAD_PATH` | `data.json` | Path to the consulting data |
| `REPORTS_OUTPUT_DIR` | `reports/` | Where .docx files are saved |
| `MAX_RETRIES` | `3` | Retry attempts per Mistral call |
| `RETRY_BACKOFF_SECONDS` | `2.0` | Base backoff (exponential) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Logs

Logs are written to `logs/pipeline.log` with rotation (5MB × 3 backups).
Every request has a short `request_id` (e.g. `[A3F2C1B8]`) in all log lines
so you can grep for a single run:

```bash
grep "A3F2C1B8" logs/pipeline.log
```

---

## Updating prompt.md or data.json

Just replace the files on the VM. No restart needed — files are read at request time.

```bash
scp ./new_prompt.md user@your-vm-ip:/opt/docs-gen/prompt.md
scp ./new_data.json user@your-vm-ip:/opt/docs-gen/data.json
```

---

## Running as a Background Service (Linux systemd)

Create `/etc/systemd/system/docs-gen.service`:
```ini
[Unit]
Description=Docs Gen API
After=network.target

[Service]
WorkingDirectory=/opt/docs-gen
ExecStart=/opt/docs-gen/.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000 --workers 1
Restart=on-failure
EnvironmentFile=/opt/docs-gen/.env

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable docs-gen
sudo systemctl start docs-gen
sudo systemctl status docs-gen
```
