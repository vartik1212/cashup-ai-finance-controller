import csv
from datetime import datetime, timedelta

with open(r'C:\Users\varti\Downloads\reconai_processor_settlements.csv', 'r', encoding='utf-8-sig') as f:
    sets = list(csv.DictReader(f))

indices_58 = list(range(50)) + [50, 52, 54, 56, 57, 58, 59, 61]
assert len(indices_58) == 58, f"Expected 58, got {len(indices_58)}"

bank_rows = []
for idx in indices_58:
    s = sets[idx]
    s_date = s['paid_on']
    try:
        dt = datetime.strptime(s_date, '%Y-%m-%d')
        b_date = (dt + timedelta(days=1)).strftime('%d/%m/%Y')
    except Exception:
        b_date = s_date

    bank_rows.append({
        'utr': f"UTR-HDFC-{s['payment_ref']}",
        'txn_date': b_date,
        'credit': s['received'],
        'description': f"CMS/SETTLEMENT/{s['payment_ref']}/{s['bill_reference']}",
    })

for target in [
    r'C:\Users\varti\Downloads\reconai_bank_statement.csv',
    r'tests\fixtures\alternate_schemas\reconai_bank_statement.csv',
]:
    with open(target, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['utr', 'txn_date', 'credit', 'description'])
        w.writeheader()
        w.writerows(bank_rows)
    print(f"Wrote {len(bank_rows)} rows to {target}")
