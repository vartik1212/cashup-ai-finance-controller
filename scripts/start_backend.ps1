# Start ReconAI Backend
# Run from project root: .\scripts\start_backend.ps1

$env:PYTHONPATH = "."
python -m uvicorn backend.main:app --reload --port 8000 --log-level info
