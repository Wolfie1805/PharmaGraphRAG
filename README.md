# PharmaGraph: Evidence-Grounded Pharmacogenomics Intelligence

PharmaGraph is a research prototype for evidence-grounded pharmacogenomics question answering, connecting structured clinical annotations (ClinPGx), clinical implementation guidelines (CPIC), and peer-reviewed literature (PubMed) without hallucinations or unverified inferred links.

## Answer Modes

PharmaGraph supports three answer generation modes:
1. **Extractive Mode (DEFAULT)**:
   - Free, deterministic, and 100% offline.
   - Requires zero model downloads, zero GPU/heavy CPU compute, zero API keys, and zero external network calls.
   - Builds structured claims strictly from fields stated in the retrieved evidence bundle (guidelines, annotations, drug labels, and publications).
2. **Ollama Mode (OPTIONAL)**:
   - Uses a local LLM running via Ollama (`http://localhost:11434`) using `httpx`.
   - Security-hardened: localhost-only network guard (refuses non-localhost URLs unless explicitly configured).
   - Fixed seed and temperature for reproducible grounded generation.
   - Automatic 1-attempt repair on invalid JSON with silent fallback to Extractive mode (`model_fallback` flag) if unparseable.
3. **Mock Mode (TESTS)**:
   - Used for offline test suites.

---

## Running in Extractive Mode (Default)

Extractive mode is enabled by default. To start the FastAPI server:

```powershell
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Start Uvicorn API server
.\.venv\Scripts\uvicorn.exe app.api.app:app --host 127.0.0.1 --port 8000
```

To run demo queries via the CLI:
```powershell
.\.venv\Scripts\python.exe scripts/demo_ask.py "What is the relationship between CYP2C19 and clopidogrel?"
```

---

## Enabling Optional Ollama Mode (Windows PowerShell)

To enable the optional local Ollama model mode:

1. **Install and Start Ollama**:
   Download and install Ollama for Windows from https://ollama.com.
   Ensure the Ollama service is running locally on port 11434:
   ```powershell
   ollama pull llama3
   ollama serve
   ```

2. **Configure Environment in PowerShell**:
   Set `LLM_MODE` to `ollama` in your `.env` file or export environment variables:
   ```powershell
   $env:LLM_MODE="ollama"
   $env:LLM_BASE_URL="http://localhost:11434"
   $env:LLM_MODEL="llama3"
   $env:LLM_TIMEOUT_SECONDS="180"
   ```

3. **Start the API Server**:
   ```powershell
   .\.venv\Scripts\uvicorn.exe app.api.app:app --host 127.0.0.1 --port 8000
   ```

---

## API Endpoints
- `GET /api/health`: Service health and active answer mode.
- `POST /api/ask`: Grounded answer synthesis with evidence bundle, claims, resolved entities, and safety flags.
  CORS is strictly locked to `http://localhost:5173`.

---

## Starting Backend and Frontend on Windows (PowerShell)

The Phase D3 React + TypeScript UI lives in `frontend/` and connects to `http://localhost:8000/api`. Open two PowerShell windows:

### Terminal 1 — Start FastAPI Backend
```powershell
cd d:\PharmaRAG
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.\.venv\Scripts\uvicorn.exe app.api.app:app --host 127.0.0.1 --port 8000
```

### Terminal 2 — Install & Start Vite Frontend
```powershell
cd d:\PharmaRAG\frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

### Frontend Checks (Typecheck, Lint, Tests, Build)
```powershell
cd d:\PharmaRAG\frontend
npm run typecheck
npm run lint
npm run test
npm run build
```


