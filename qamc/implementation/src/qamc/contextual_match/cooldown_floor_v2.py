"""Conservative runtime pacing correction; never creates model requests."""
import sqlite3


def observe(records, seen, now):
    """New terminal faults wait from observation; old faults do not restart waits."""
    current = set(seen)
    deadlines, faults = [], []
    for key, record in records.items():
        if record['status'] in ('OK', 'PENDING_DELIVERY_UNKNOWN'):
            continue
        end = record['started_unix'] + record.get('elapsed_seconds', 0)
        if key not in current:
            deadlines.append(max(end + 300, now + 300))
            faults.append(key)
        current.add(key)
    return current, max(deadlines, default=None), sorted(faults)


def raise_floor(paths, deadline):
    """Raise both existing control rows; never lower pacing or clear hard stops."""
    receipts = []
    for path in paths:
        with sqlite3.connect('file:' + str(path.resolve()) + '?mode=rw', uri=True, timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT next_at,cooldown_until,hard_stop FROM dispatch WHERE id=1').fetchone()
            if old is None:
                raise ValueError('Missing existing dispatch control row')
            db.execute('UPDATE dispatch SET cooldown_until=MAX(cooldown_until,?) WHERE id=1', (deadline,))
            new = db.execute('SELECT next_at,cooldown_until,hard_stop FROM dispatch WHERE id=1').fetchone()
            if new[0] != old[0] or new[2] != old[2] or new[1] < max(old[1], deadline):
                raise ValueError('Control invariant violated')
            receipts.append({'path': str(path), 'previous_cooldown_until': old[1], 'new_cooldown_until': new[1]})
    return receipts
