
from pathlib import Path
import sqlite3

database = Path("data/carecircle.db")
backup = Path("data/carecircle_before_timezone_repair.db")

if not database.exists() or not backup.exists():
    raise SystemExit("ERROR: Database or backup file is missing.")

def inspect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row

    rows = connection.execute("""
        SELECT
            d.id,
            d.medication_id,
            d.scheduled_for,
            d.status,
            d.confirmed_by_name,
            d.confirmed_at,
            d.confirmation_type
        FROM dose_records AS d
        ORDER BY d.id
    """).fetchall()

    connection.close()
    return [dict(row) for row in rows]


original = inspect(database)
saved = inspect(backup)

print("LIVE RECORDS:", len(original))
print("BACKUP RECORDS:", len(saved))
print("BACKUP MATCHES LIVE:", original == saved)

print("\nDOSE RECORDS:")
for row in original:
    print(row)

print("\nNo records were modified.")
