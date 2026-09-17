"""
settler.py — BUGGY version
Problem: No idempotency check. Running settlement twice doubles payouts.
"""

from datetime import datetime, timezone
from typing import List, Dict

# In-memory DB
accounts: Dict[str, int] = {}       # user_id -> credit balance
settled_tasks: List[str] = []        # list of task_ids that were paid out
payout_log: List[dict] = []          # audit log
notification_log: List[dict] = []    # notification log


def get_settlement_window(run_at: datetime):
    """Returns (start, end) UTC for the week prior to the given Tuesday 09:00 UTC."""
    # Find the most recent Monday 00:00 UTC before run_at
    days_since_monday = run_at.weekday()  # Monday=0
    end = run_at.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    end = end - timedelta(days=days_since_monday)
    start = end - timedelta(days=7)
    return start, end


def settle(tasks: List[dict], run_at: datetime = None):
    """
    BUG: No idempotency. If called twice for same window, credits are doubled.
    """
    if run_at is None:
        run_at = datetime.now(timezone.utc)

    start, end = get_settlement_window(run_at)

    # Filter tasks in window
    qualifying = [
        t for t in tasks
        if start <= t["completed_at"] < end   # end is excluded
    ]

    credits_by_user: Dict[str, int] = {}
    for task in qualifying:
        uid = task["user_id"]
        tid = task["task_id"]
        # BUG: no check if task_id already settled
        credits_by_user[uid] = credits_by_user.get(uid, 0) + 10
        settled_tasks.append(tid)

    # Payout
    for user_id, credits in credits_by_user.items():
        accounts[user_id] = accounts.get(user_id, 0) + credits
        payout_log.append({
            "user_id": user_id,
            "credits": credits,
            "run_at": run_at.isoformat(),
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
        })
        # Notify
        _send_notification(user_id, credits)

    return credits_by_user


def _send_notification(user_id: str, credits: int, fail: bool = False):
    if fail:
        notification_log.append({"user_id": user_id, "status": "FAILED"})
        raise RuntimeError(f"Notification failed for {user_id}")
    notification_log.append({"user_id": user_id, "credits": credits, "status": "SENT"})


def reset():
    global accounts, settled_tasks, payout_log, notification_log
    accounts = {}
    settled_tasks = []
    payout_log = []
    notification_log = []
