"""
test_settlement.py — 8 test cases covering the full quest requirements.
Run:  pytest test_settlement.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta

# ── Helpers ──────────────────────────────────────────────────────────────────

TUESDAY_09 = datetime(2025, 7, 8, 9, 0, 0, tzinfo=timezone.utc)   # Tuesday 2025-07-08 09:00 UTC
# Settlement window for that run: Mon 2025-06-30 00:00 UTC  →  Mon 2025-07-07 00:00 UTC

def make_task(task_id: str, user_id: str, completed_at: datetime) -> dict:
    return {"task_id": task_id, "user_id": user_id, "completed_at": completed_at}

# ── Buggy tests (should FAIL with settler.py) ─────────────────────────────

class TestBuggySettler:
    """These tests demonstrate the BUG. They are expected to fail on settler.py."""

    def setup_method(self):
        import settler
        settler.reset()
        self.settler = settler

    def test_TC01_happy_path(self):
        """TC01 — Happy path: single task earns 10 credits."""
        tasks = [
            make_task("T001", "user_a", datetime(2025, 7, 1, 10, 0, tzinfo=timezone.utc))
        ]
        result = self.settler.settle(tasks, run_at=TUESDAY_09)
        assert self.settler.accounts["user_a"] == 10
        assert result["user_a"] == 10

    def test_TC02_duplicate_payout_on_retry_BUG(self):
        """TC02 — BUG: retry doubles the payout. EXPECT FAILURE on buggy settler."""
        tasks = [
            make_task("T001", "user_a", datetime(2025, 7, 1, 10, 0, tzinfo=timezone.utc))
        ]
        self.settler.settle(tasks, run_at=TUESDAY_09)
        self.settler.settle(tasks, run_at=TUESDAY_09)  # retry
        # BUG: user_a now has 20 instead of 10
        assert self.settler.accounts["user_a"] == 10, (
            f"BUG CONFIRMED: got {self.settler.accounts['user_a']} credits (expected 10)"
        )


# ── Fixed tests (all should PASS with settler_fixed.py) ──────────────────

class TestFixedSettler:
    """Full regression suite against the fixed implementation."""

    def setup_method(self):
        import settler_fixed
        settler_fixed.reset()
        self.settler = settler_fixed

    # TC01 — Happy path
    def test_TC01_happy_path(self):
        """Single qualifying task → 10 credits, notification sent."""
        tasks = [
            make_task("T001", "user_a", datetime(2025, 7, 1, 10, 0, tzinfo=timezone.utc))
        ]
        self.settler.settle(tasks, run_at=TUESDAY_09)
        assert self.settler.accounts["user_a"] == 10
        assert any(n["status"] == "SENT" for n in self.settler.notification_log)

    # TC02 — Duplicate payout on retry (the main bug)
    def test_TC02_idempotent_retry(self):
        """Retry with same tasks must NOT double the payout."""
        tasks = [
            make_task("T001", "user_a", datetime(2025, 7, 1, 10, 0, tzinfo=timezone.utc))
        ]
        self.settler.settle(tasks, run_at=TUESDAY_09)
        self.settler.settle(tasks, run_at=TUESDAY_09)  # retry
        assert self.settler.accounts["user_a"] == 10, "Idempotency failed — credits doubled"

    # TC03 — Boundary: task at exactly window end is EXCLUDED
    def test_TC03_boundary_end_excluded(self):
        """Task at Mon 07-07 00:00:00 UTC (window end) must be excluded."""
        window_end = datetime(2025, 7, 7, 0, 0, 0, tzinfo=timezone.utc)
        tasks = [make_task("T002", "user_b", window_end)]
        self.settler.settle(tasks, run_at=TUESDAY_09)
        assert self.settler.accounts.get("user_b", 0) == 0, "Boundary end must be excluded"

    # TC04 — Boundary: task 1 second before window end is INCLUDED
    def test_TC04_boundary_end_included(self):
        """Task at 23:59:59 Sunday (1 sec before window end) must be included."""
        just_before_end = datetime(2025, 7, 6, 23, 59, 59, tzinfo=timezone.utc)
        tasks = [make_task("T003", "user_c", just_before_end)]
        self.settler.settle(tasks, run_at=TUESDAY_09)
        assert self.settler.accounts.get("user_c", 0) == 10

    # TC05 — Timezone: task stored in IST, compared in UTC
    def test_TC05_timezone_conversion(self):
        """Task at 05:30 IST Monday = 00:00 UTC Monday → must be included (boundary start)."""
        # IST is UTC+5:30. Mon 00:00 UTC = Mon 05:30 IST
        ist_offset = timezone(timedelta(hours=5, minutes=30))
        task_ist = datetime(2025, 6, 30, 5, 30, 0, tzinfo=ist_offset)
        task_utc = task_ist.astimezone(timezone.utc)
        tasks = [make_task("T004", "user_d", task_utc)]
        self.settler.settle(tasks, run_at=TUESDAY_09)
        assert self.settler.accounts.get("user_d", 0) == 10, "Boundary start must be included"

    # TC06 — Duplicate task_id in same input (not a retry, same batch)
    def test_TC06_duplicate_task_id_in_batch(self):
        """Same task_id appearing twice in one batch must count only once."""
        tasks = [
            make_task("T005", "user_e", datetime(2025, 7, 2, 8, 0, tzinfo=timezone.utc)),
            make_task("T005", "user_e", datetime(2025, 7, 2, 8, 0, tzinfo=timezone.utc)),  # dup
        ]
        self.settler.settle(tasks, run_at=TUESDAY_09)
        assert self.settler.accounts.get("user_e", 0) == 10, "Duplicate task_id must not earn double"

    # TC07 — Notification failure must NOT roll back payout
    def test_TC07_notification_failure_no_rollback(self):
        """Notification gateway failure must NOT reverse committed payout."""
        tasks = [
            make_task("T006", "user_f", datetime(2025, 7, 3, 12, 0, tzinfo=timezone.utc))
        ]
        # notify_fail_for triggers notification failure for user_f
        self.settler.settle(tasks, run_at=TUESDAY_09, notify_fail_for="user_f")
        assert self.settler.accounts.get("user_f", 0) == 10, (
            "Payout must survive notification failure"
        )
        failed = [n for n in self.settler.notification_log if n["status"] == "FAILED"]
        assert len(failed) == 1, "Notification failure should be logged"

    # TC08 — Task outside window is excluded
    def test_TC08_task_outside_window_excluded(self):
        """Task from 2 weeks ago must not appear in this week's settlement."""
        old_task = make_task("T007", "user_g",
                             datetime(2025, 6, 20, 10, 0, tzinfo=timezone.utc))  # 2 weeks prior
        self.settler.settle([old_task], run_at=TUESDAY_09)
        assert self.settler.accounts.get("user_g", 0) == 0

    # TC09 — Multiple users in one run
    def test_TC09_multiple_users(self):
        """Multiple users each earn correct credits independently."""
        tasks = [
            make_task("T008", "user_h", datetime(2025, 7, 1, 9, 0, tzinfo=timezone.utc)),
            make_task("T009", "user_h", datetime(2025, 7, 2, 9, 0, tzinfo=timezone.utc)),
            make_task("T010", "user_i", datetime(2025, 7, 3, 9, 0, tzinfo=timezone.utc)),
        ]
        self.settler.settle(tasks, run_at=TUESDAY_09)
        assert self.settler.accounts["user_h"] == 20
        assert self.settler.accounts["user_i"] == 10
