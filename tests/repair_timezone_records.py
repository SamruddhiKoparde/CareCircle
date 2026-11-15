
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "carecircle.db"
BACKUP = ROOT / "data" / "carecircle_before_timezone_repair.db"

if not DATABASE.exists() or not BACKUP.exists():
    raise SystemExit("STOP: Database or verified backup is missing.")

db = sqlite3.connect(DATABASE)
db.row_factory = sqlite3.Row

try:
    # Verify the backup still matches the live dose records.
    backup_db = sqlite3.connect(BACKUP)

    live_rows = db.execute(
        "SELECT * FROM dose_records ORDER BY id"
    ).fetchall()

    backup_rows = backup_db.execute(
        "SELECT * FROM dose_records ORDER BY id"
    ).fetchall()

    if [tuple(r) for r in live_rows] != [tuple(r) for r in backup_rows]:
        raise RuntimeError("STOP: Backup does not match live dose records.")

    backup_db.close()

    # Verify the exact records before changing anything.
    expected = {
        1: (1, "2026-11-15 18:00:00.000000", "taken", "Test Patient"),
        2: (2, "2026-11-15 18:00:00.000000", "taken", "Test Patient"),
        3: (3, "2026-11-15 18:00:00.000000", "upcoming", None),
        4: (1, "2026-11-16 12:30:00.000000", "upcoming", None),
        5: (2, "2026-11-16 12:30:00.000000", "upcoming", None),
        6: (3, "2026-11-16 12:30:00.000000", "upcoming", None),
        7: (1, "2026-11-15 12:30:00.000000", "upcoming", None),
        8: (2, "2026-11-15 12:30:00.000000", "upcoming", None),
        9: (3, "2026-11-15 12:30:00.000000", "upcoming", None),
    }

    for dose_id, expected_values in expected.items():
        row = db.execute(
            """
            SELECT medication_id, scheduled_for, status,
                   confirmed_by_name
            FROM dose_records
            WHERE id = ?
            """,
            (dose_id,),
        ).fetchone()

        if row is None or tuple(row) != expected_values:
            raise RuntimeError(
                f"STOP: Dose {dose_id} does not match expected data."
            )

    # Preserve confirmation details for the two patient-confirmed doses.
    confirmations_before = db.execute(
        """
        SELECT id, status, confirmation_type,
               confirmed_by_user_id, confirmed_by_name,
               confirmed_by_role, confirmed_at, notes
        FROM dose_records
        WHERE id IN (1, 2)
        ORDER BY id
        """
    ).fetchall()

    # Duplicate records must not have audit references.
    audit_count = db.execute(
        """
        SELECT COUNT(*) FROM audit_logs
        WHERE entity_id IN (7, 8, 9)
        """
    ).fetchone()[0]

    if audit_count:
        raise RuntimeError("STOP: Duplicate records have audit references.")

    # All changes happen in one transaction.
    db.execute("BEGIN IMMEDIATE")

    deleted = db.execute(
        "DELETE FROM dose_records WHERE id IN (7, 8, 9)"
    ).rowcount

    if deleted != 3:
        raise RuntimeError("STOP: Expected exactly three duplicate records.")

    for dose_id in (1, 2, 3):
        db.execute(
            """
            UPDATE dose_records
            SET scheduled_for = ?
            WHERE id = ?
            """,
            ("2026-11-15 12:30:00.000000", dose_id),
        )

    # Confirm the original patient confirmations remain unchanged.
    confirmations_after = db.execute(
        """
        SELECT id, status, confirmation_type,
               confirmed_by_user_id, confirmed_by_name,
               confirmed_by_role, confirmed_at, notes
        FROM dose_records
        WHERE id IN (1, 2)
        ORDER BY id
        """
    ).fetchall()

    if [tuple(r) for r in confirmations_before] != [
        tuple(r) for r in confirmations_after
    ]:
        raise RuntimeError("STOP: Confirmation history changed.")

    db.commit()

    print("TIMEZONE REPAIR: SUCCESS")
    print("Duplicate records removed:", deleted)
    print("Original records retained: 1, 2, 3, 4, 5, 6")
    print("Patient confirmations preserved: 1, 2")
    print("Final dose count:", db.execute(
        "SELECT COUNT(*) FROM dose_records"
    ).fetchone()[0])

except Exception:
    db.rollback()
    raise

finally:
    db.close()
