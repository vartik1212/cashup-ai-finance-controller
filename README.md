# CashUP — AI Finance Controller
## Razorpay Buildathon 2026

Multi-source financial reconciliation agent that closes the finance-ops loop across 120+ synthetic records.

---

## Quick Start

### 1. Generate Data
```bash
python scripts/generate_data.py
```

### 2. Start Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

### 3. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173

---

## Architecture

```
DATA INGESTION → NORMALIZATION → DETERMINISTIC MATCHING
→ CONFIDENCE SCORING → ROUTE (Auto/Review/Human)
→ EXCEPTION CLASSIFICATION → REPORT GENERATION
```

**Core principle: AI proposes. Deterministic logic verifies.**

---

## Dataset (120 Invoices)

| Scenario | Count |
|---|---|
| Exact matches | 35 |
| Fee-adjusted | 20 |
| Delayed settlements | 12 |
| Missing settlements | 12 |
| Partial payments | 10 |
| Refunds | 8 |
| Incorrect references | 7 |
| Duplicate payments | 6 |
| Amount mismatches | 6 |
| Ambiguous matches | 4 |

Ground-truth labels embedded for accuracy measurement.

---

## Metrics (all computed from real data)

- **Match Rate** = reconciled / eligible invoices
- **Verified Accuracy** = correct predictions / total predictions (vs ground truth)
- **Auto-Resolution Rate** = auto-resolved / total

---

## AI Copilot

Works without a Gemini API key (data-driven mode).
Set `GEMINI_API_KEY` in `backend/.env` to enable full Gemini analysis.
