import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import base64
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.db import get_db

client = TestClient(app)
fresh_dir = Path(r"C:\Users\varti\Downloads\ReconAI_Fresh_5CSV_Test_Dataset")

# 1. Profile files
inv_bytes = (fresh_dir / "01_reconai_invoices.csv").read_bytes()
set_bytes = (fresh_dir / "02_reconai_settlements.csv").read_bytes()
bnk_bytes = (fresh_dir / "03_reconai_bank_transactions.csv").read_bytes()
rfd_bytes = (fresh_dir / "04_reconai_refunds.csv").read_bytes()

prof_resp = client.post("/api/upload/profile-json", json={
    "files": [
        {"filename": "01_reconai_invoices.csv", "content_b64": base64.b64encode(inv_bytes).decode("ascii")},
        {"filename": "02_reconai_settlements.csv", "content_b64": base64.b64encode(set_bytes).decode("ascii")},
        {"filename": "03_reconai_bank_transactions.csv", "content_b64": base64.b64encode(bnk_bytes).decode("ascii")},
        {"filename": "04_reconai_refunds.csv", "content_b64": base64.b64encode(rfd_bytes).decode("ascii")},
    ]
})
assert prof_resp.status_code == 200, f"Profiling failed: {prof_resp.text}"
profiles = prof_resp.json()["profiles"]

# 2. Confirm and Import Data
payload_files = []
for p in profiles:
    mapping = {m["source_column"]: m["target_field"] for m in p["column_mappings"] if m.get("target_field")}
    payload_files.append({
        "filename": p["filename"],
        "file_type": p["detected_file_type"],
        "column_mapping": mapping,
        "file_content_b64": p["file_content_b64"],
    })

import_resp = client.post("/api/upload/confirm", json={"files": payload_files})
assert import_resp.status_code == 200, f"Import failed: {import_resp.text}"
import_data = import_resp.json()
print("Import Status:", import_data["status"])
print("Counts from import confirmation:", import_data["dataset_counts"]["result"])

# 3. Header / data status counts
st0 = client.get("/api/data/status").json()
print(f"Header Status counts: INV {st0['invoices']} SET {st0['settlements']} BNK {st0['bank_transactions']} RFD {st0['refunds']}")

# Check DB records
with get_db() as c:
    active_invoices = [r[0] for r in c.execute("SELECT invoice_id FROM invoices").fetchall()]
    uploaded_invoices = [r[0] for r in c.execute("SELECT invoice_id FROM uploaded_invoices").fetchall()]
    bill_count = c.execute("SELECT count(*) FROM invoices WHERE invoice_id LIKE 'BILL-%'").fetchone()[0]

print("Total active invoices:", len(active_invoices))
print("Sample active IDs:", active_invoices[:3])
print("Old BILL-* records in active workspace:", bill_count)
all_sep = all(iid.startswith("INV-SEP26-") for iid in active_invoices)
print("All active records use INV-SEP26-* IDs:", all_sep)

# 4. Run reconciliation
rec_resp = client.post("/api/reconcile", json={})
assert rec_resp.status_code == 200
rec_data = rec_resp.json()
run_id = rec_data["run_id"]
print("Reconciliation Run ID:", run_id)
print("Run Records Processed:", rec_data["summary"]["records_processed"])

# Latest run check
latest = client.get("/api/reconcile/latest").json()
print("Latest run API invoices_count:", latest["invoices_count"])

# Results and exceptions
results = client.get(f"/api/reconcile/runs/{run_id}/results").json()
exceptions = client.get(f"/api/reconcile/runs/{run_id}/exceptions").json()
print("Results count:", len(results), "Sample result ID:", results[0]["invoice_id"] if results else None)
print("Exceptions count:", len(exceptions), "Sample exception ID:", exceptions[0]["invoice_id"] if exceptions else None)

# 5. Refresh 1
st1 = client.get("/api/data/status").json()
print(f"Refresh 1 counts: INV {st1['invoices']} SET {st1['settlements']} BNK {st1['bank_transactions']} RFD {st1['refunds']}")

# 6. Refresh 2
st2 = client.get("/api/data/status").json()
print(f"Refresh 2 counts: INV {st2['invoices']} SET {st2['settlements']} BNK {st2['bank_transactions']} RFD {st2['refunds']}")

# 7. Copilot bound to new run
cop_resp = client.post("/api/copilot/chat", json={"message": "Summarize this reconciliation run.", "run_id": run_id})
print("Copilot response status:", cop_resp.status_code)
cop_data = cop_resp.json()
print("Copilot mentioned new run ID:", run_id in cop_data["message"])
print("Copilot referenced IDs:", cop_data["referenced_ids"])
