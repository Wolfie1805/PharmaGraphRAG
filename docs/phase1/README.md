# Phase 1: Raw Data Acquisition

This module handles raw, immutable data acquisition from primary biomedical sources:
1. **ClinPGx / PharmGKB**: Pharmacogenomics catalog files, annotations, guidelines, variants, and relationships.
2. **PubMed / NCBI E-utilities**: Peer-reviewed biomedical abstracts and citation metadata retrieved using exact gene-drug query templates.

---

## Windows Virtual Environment & CLI Instructions

### 1. Activating Virtual Environment

On Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

If script execution policy restricts running scripts:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.venv\Scripts\Activate.ps1
```

On Windows Command Prompt (`cmd.exe`):
```cmd
.venv\Scripts\activate.bat
```

To deactivate:
```powershell
deactivate
```

---

## Running the Data Acquisition CLI

### ClinPGx Acquisition
Fetches official catalog metadata, records the release timestamp, and downloads all 10 selected raw archives sequentially with checksum verification and manifest creation:
```powershell
.venv\Scripts\python.exe app\ingestion\cli.py clinpgx --config configs/acquisition.yaml
```

### PubMed Acquisition (Pilot Mode: 50 PMIDs)
Executes deterministic pilot queries across all 4 gene-drug pairs, fetching raw PubMed XML batches with reconciliation:
```powershell
.venv\Scripts\python.exe app\ingestion\cli.py pubmed --pilot --pilot-cap 50 --config configs/acquisition.yaml
```

### Manifest Verification
Validates a generated manifest against files on disk, ensuring SHA-256 integrity, file sizes, and that no unexpected or tampered files exist:
```powershell
.venv\Scripts\python.exe app\ingestion\cli.py verify data/manifests/manifest_<run_id>.json
```

### Running Test Suite
```powershell
.venv\Scripts\pytest.exe -v
```

---

## Architectural & OS-Specific Guarantees
- **Atomic File Writes**: Raw files are written to `.tmp` files in binary mode (`mode="wb"`) and committed atomically using `os.replace`.
- **Immutability**: Overwriting existing raw files is prohibited (`FileExistsError`).
- **Path Portability**: All paths are managed using Python's `pathlib.Path`.
- **Encoding**: UTF-8 is explicitly declared for all text I/O and manifest serialization.
- **SSL Verification**: Uses `httpx` with `certifi` CA bundle (`certifi.where()`) to guarantee trusted TLS connections to NCBI and ClinPGx endpoints.
