# CashUP

### AI Finance Controller for Multi-Source Financial Reconciliation

CashUP is an AI-assisted finance operations system that reconciles **invoices, payment settlements, bank transactions, and refunds** across batch financial data.

Instead of asking an LLM to decide whether money matches, CashUP separates intelligence from financial truth:

> **AI investigates. Deterministic financial logic verifies.**

CashUP processes financial records through a deterministic reconciliation engine, surfaces uncertain records for human review, reports measurable performance, and uses AI to investigate and explain exceptions.

---

## The Problem

Finance teams frequently reconcile data spread across:

- ERP invoices
- Payment gateway settlements
- Bank statements
- Refund records

Differences in schemas, references, settlement timing, fees, partial payments, and missing records make reconciliation slow and difficult to verify reliably.

CashUP is designed to close this finance-operations loop rather than simply generate an AI answer.

---

## How CashUP Works

```text
Invoices ──────────┐
Settlements ───────┼────→ Schema Mapping
Bank Transactions ─┤              ↓
Refunds ───────────┘         Validation
                                  ↓
                             Normalization
                                  ↓
                         Candidate Matching
                                  ↓
                            Verification
                                  ↓
                           Classification
                                  ↓
                ┌─────────────────┼─────────────────┐
                ↓                 ↓                 ↓
          Auto Verified     Review Required      Unresolved
                │                 │                 │
                └─────────────────┼─────────────────┘
                                  ↓
                       Exceptions + Metrics
                                  ↓
                           Finance Copilot
```

The workflow is orchestrated using **LangGraph**, while the underlying financial verification remains deterministic.

---

## Core Features

### Multi-Source Reconciliation
Reconciles invoice records against settlements and bank transactions across 50+ record batches.

### Flexible CSV Ingestion
Supports varying source schemas through inspection, schema mapping, validation, and normalization.

### Deterministic Verification
Financial matching and arithmetic are performed by deterministic rules rather than an LLM.

### Exception Routing
Every record is routed into an operational outcome:

- **Auto Verified**
- **Review Required**
- **Unresolved**

### Exception Investigation
CashUP surfaces records involving missing evidence, timing differences, amount mismatches, partial payments, duplicates, refunds, and other reconciliation exceptions.

### AI Finance Copilot
Gemini investigates deterministic reconciliation results and helps answer questions about exceptions and financial activity.

The Copilot **cannot override financial verification results**.

### Run Reports
Provides reconciliation metrics, exception reports, execution information, and exportable results.

---

## Measured Evaluation

CashUP was tested not only on its controlled dataset, but also against an **unseen 72-record dataset with unfamiliar schemas**.

| Metric | Result |
|---|---:|
| Records evaluated | 72 |
| Classification accuracy | **77.8%** |
| Auto-verified precision | **89.5%** |
| Match precision | **100%** |
| Match recall | **79.7%** |

The objective was not to hide failures behind a perfect demo.

The unseen evaluation exposed categories where CashUP still struggled, while also showing which reconciliation decisions it could make reliably.

---

## What Broke During Testing?

The controlled dataset performed strongly, but testing against unfamiliar schemas exposed real weaknesses.

The ingestion system initially struggled with:

- distinguishing certain bank and refund sources
- unfamiliar column names
- fee-adjusted transactions
- refund-related reconciliation
- ambiguous mappings

It also exposed cases where displayed reconciliation counts and percentages could become inconsistent.

Instead of adding dataset-specific rules, the ingestion flow was moved toward **confidence-aware schema mapping with human confirmation for uncertain fields**, while financial verification remained deterministic.

This became an important design principle:

> **Uncertainty should be surfaced, not silently cleared.**

---

## AI Architecture

CashUP deliberately separates AI reasoning from financial verification.

### Deterministic Layer

Responsible for:

- normalization
- candidate matching
- amount comparison
- verification
- classification
- reconciliation status
- metrics

### AI Layer

Gemini is used for:

- exception investigation
- explanations
- reconciliation Q&A
- summaries
- controller assistance

AI consumes verified reconciliation state rather than becoming the source of financial truth.

---

## Tech Stack

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Recharts
- Lucide

### Backend

- Python
- FastAPI
- Pandas
- Pydantic
- SQLite

### AI & Orchestration

- LangGraph
- Google Gemini API

---

## Application

CashUP contains five primary operational views:

**Overview**  
Run health, reconciliation metrics, status distribution, and exceptions requiring attention.

**Reconciliation**  
Record-level reconciliation results and financial evidence.

**Exceptions**  
Review-required and unresolved transactions.

**AI Copilot**  
Gemini-powered investigation over deterministic reconciliation data.

**Run Reports**  
Metrics, execution details, and exportable reconciliation results.

---

## Running CashUP Locally

### 1. Clone

```bash
git clone https://github.com/vartik1212/cashup-ai-finance-controller.git
cd cashup-ai-finance-controller
```

### 2. Backend

```bash
cd backend
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your environment configuration using `.env.example` and add your Gemini API key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Start the backend:

```bash
uvicorn main:app --reload
```

### 3. Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL provided by Vite.

---

## Demo Flow

```text
Load / Upload Data
        ↓
Inspect & Map Schema
        ↓
Validate
        ↓
Run Reconciliation
        ↓
Review Metrics
        ↓
Investigate Exceptions
        ↓
Ask Finance Copilot
        ↓
Export Results
```

---

## Safety & Design Principle

CashUP does not try to eliminate human financial judgment.

It automates cases where sufficient evidence exists and directs human attention toward cases where that evidence remains uncertain.

> **Reconcile. Verify. Investigate. Report.**

---

## Built For

**Razorpay AI Buildathon 2026**  
**Track 04: AI Finance Controller**

Built by **Vartik Srivastav**
