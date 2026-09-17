"""
settler_fixed.py — FIXED version
Fix: Idempotency key per (task_id). Already-settled tasks are skipped.
Fix: Notification failure does NOT reverse a committed payout.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set

# In-memory DB
accounts: Dict[str, int] = {}
settled_task_ids: Set[str] = set()   # FIX: idempotency store
payout_log: List[dict] = []
notification_log: List[dict] = []


def get_settlement_window(run_at: datetime):
    days_since_monday = run_at.weekday()
    end = run_at.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end - timedelta(days=days_since_monday)
    start = end - timedelta(days=7)
    return start, end


def settle(tasks: List[dict], run_at: datetime = None, notify_fail_for: str = None):
    """
    FIX 1: Skip task_ids already in settled_task_ids (idempotent).
    FIX 2: Commit payout first, then notify. Notification failure is logged
           but does NOT roll back the payout.
    """
    if run_at is None:
        run_at = datetime.now(timezone.utc)

    start, end = get_settlement_window(run_at)

    qualifying = [
        t for t in tasks
        if start <= t["completed_at"] < end
    ]

    credits_by_user: Dict[str, int] = {}
    for task in qualifying:
        uid = task["user_id"]
        tid = task["task_id"]
        # FIX 1: idempotency check
        if tid in settled_task_ids:
            continue
        credits_by_user[uid] = credits_by_user.get(uid, 0) + 10
        settled_task_ids.add(tid)

    # Commit payout FIRST
    for user_id, credits in credits_by_user.items():
        accounts[user_id] = accounts.get(user_id, 0) + credits
        payout_log.append({
            "user_id": user_id,
            "credits": credits,
            "run_at": run_at.isoformat(),
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "status": "PAID",
        })

    # FIX 2: Notify separately — failure is best-effort, never rolls back
    for user_id, credits in credits_by_user.items():
        try:
            fail = (notify_fail_for == user_id)
            _send_notification(user_id, credits, fail=fail)
        except RuntimeError:
            notification_log.append({
                "user_id": user_id,
                "status": "FAILED",
                "note": "Payout already committed — not reversed"
            })

    return credits_by_user


def _send_notification(user_id: str, credits: int, fail: bool = False):
    if fail:
        raise RuntimeError(f"Notification gateway timeout for {user_id}")
    notification_log.append({"user_id": user_id, "credits": credits, "status": "SENT"})


def reset():
    global accounts, settled_task_ids, payout_log, notification_log
    accounts = {}
    settled_task_ids = set()
    payout_log = []
    notification_log = []
