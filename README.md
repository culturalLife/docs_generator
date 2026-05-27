# docs_gen — VM Deployment Guide

## What This Is
A production-grade FastAPI service that generates boardroom-grade `.docx` reports
using parallel Mistral API calls. Triggered via a single HTTP endpoint.

---

## Files on the VM

```
VMCompatible/           ← backend service only, no frontend here
├── api.py                ← FastAPI app (entry point)
├── config.py             ← All configuration knobs
├── logger.py             ← Logging setup (imported by all modules)
├── report_generator.py   ← Core Mistral pipeline
├── summarize_data.py     ← JSON → markdown summarizer
├── prompt.md             ← The report prompt (edit to customise)
├── data.json             ← The consulting questionnaire payload
├── requirements.txt      ← Python dependencies
├── .env                  ← API key — created on the VM, never committed
├── logs/                 ← Auto-created on first run
└── reports/              ← Auto-created on first run, .docx files saved here
```

> The frontend lives in `docs_gen/frontend/` and is deployed separately (e.g. static hosting).
> The VM only runs the API.

---

## VM Setup (One-Time)

```bash
# 1. SSH into the VM
ssh azureuser@your-vm-ip

# 2. Clone your GitHub repo (only the VMCompatible folder is needed)
git clone https://github.com/<your-org>/<your-repo>.git /home/azureuser/himanshu/docs_generator_main
cd /home/azureuser/himanshu/docs_generator_main

# 3. Create a virtual environment
python3 -m venv /home/azureuser/himanshu/venv
source /home/azureuser/himanshu/venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set up the API key
#
# OPTION A — .env file (RECOMMENDED for a long-running VM service)
#   The app loads this automatically via python-dotenv on every start.
#   It survives reboots and service restarts without any extra steps.
cp .env.example .env
nano .env
# Set the values inside the file:
#   MISTRAL_API_KEY=your_actual_key_here
#   MISTRAL_READ_TIMEOUT=300          # optional, 300s is the default

# OPTION B — export (shell environment variable)
#   Works for the current SSH session only.
#   Disappears when you log out or restart the service.
#   Use this for a quick one-off test, not for production.
export MISTRAL_API_KEY="your_actual_key_here"
#
# For systemd (Option B alternative that survives restarts):
#   Add  Environment=MISTRAL_API_KEY=your_key  to the [Service] block
#   in /etc/systemd/system/docs-gen.service, then daemon-reload + restart.
#
# Bottom line: use the .env file (Option A) on the VM.
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
| `GENERATION_MODEL` | `mistral-large-latest` | Mistral model used |
| `TEMPERATURE` | `0.2` | LLM determinism (0=strict, 1=creative) |
| `MAX_PARALLEL_CALLS` | `3` | Parallel Mistral API threads |
| `PROMPT_FILE_PATH` | `prompt.md` | Path to the report prompt |
| `JSON_PAYLOAD_PATH` | `data.json` | Path to the consulting data |
| `REPORTS_OUTPUT_DIR` | `reports/` | Where .docx files are saved |
| `MAX_RETRIES` | `3` | Retry attempts per Mistral call |
| `RETRY_BACKOFF_SECONDS` | `2.0` | Base backoff (exponential) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### `.env` overrides (VM only, never committed)

| Variable | Default | What It Controls |
|---|---|---|
| `MISTRAL_API_KEY` | *(required)* | Your Mistral API key |
| `MISTRAL_READ_TIMEOUT` | `300` | HTTP read timeout in **seconds** for Mistral calls. Raise this if `mistral-large-latest` times out on large payloads. |

---

## Logs

Logs are written to `logs/pipeline.log` with rotation (5MB × 3 backups).
Every request has a short `request_id` (e.g. `[A3F2C1B8]`) in all log lines
so you can grep for a single run:

```bash
grep "A3F2C1B8" logs/pipeline.log
```

---

## Deploying a Code Update from GitHub

After you push changes to GitHub, SSH into the VM and run:

```bash
ssh azureuser@your-vm-ip
cd /home/azureuser/himanshu/docs_generator_main

# Pull the latest code
git pull origin main

# Activate the virtualenv
source /home/azureuser/himanshu/venv/bin/activate

# Install any new/changed dependencies (safe to re-run; skips already-installed)
pip install -r requirements.txt

# Restart the service so the new code is picked up
sudo systemctl restart docs-gen

# Confirm it came back up cleanly
sudo systemctl status docs-gen
```

> **Note:** The `.env` file lives only on the VM and is never overwritten by `git pull`.
> You only need to edit it if you're adding a new env variable (e.g. `MISTRAL_READ_TIMEOUT`).

---

## Updating prompt.md or data.json

Just replace the files on the VM (or commit them if they're in the repo).
No restart needed — files are read fresh on every request.

```bash
scp ./new_prompt.md azureuser@your-vm-ip:/home/azureuser/himanshu/docs_generator_main/prompt.md
scp ./new_data.json azureuser@your-vm-ip:/home/azureuser/himanshu/docs_generator_main/data.json
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
