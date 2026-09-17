# Settlement Simulator

> Quest: Prevent a Recurring Business-Flow Failure  
> Bug: **DEF-001** — Duplicate payout on settlement retry  
> Stack: Python · Pytest · Streamlit

---

## What this is

A minimal reproducible simulation of a weekly rewards settlement flow.

The bug: when a settlement job retries (due to network timeout, server crash, or manual re-trigger), the buggy implementation re-processes all tasks — issuing **double credits** to users.

The fix: an **idempotency set** that tracks settled `task_id`s and skips already-processed tasks on any subsequent run.

---

## Business rules

| Rule | Detail |
|------|--------|
| Settlement runs | Every Tuesday at 09:00 UTC |
| Window | Mon 00:00 UTC (inclusive) → next Mon 00:00 UTC (exclusive) |
| Credits per task | 10 |
| Deduplication | Task IDs counted once; retries must not create second payout |
| Notification | Sent after successful payout; failure must NOT reverse payout |

---

## Project structure

```
settlement-quest/
├── app.py               # Streamlit dashboard
├── settler.py           # Buggy implementation (no idempotency)
├── settler_fixed.py     # Fixed implementation (idempotent + notify decoupled)
├── test_settlement.py   # 9 regression test cases (pytest)
├── intent.md            # Problem selection & prioritization
├── directive.md         # Full spec, defect report & handoff
├── requirements.txt
└── README.md
```

---

## Run locally

```bash
# Clone
git clone https://github.com/onlyrituraj/settlement-quest.git
cd settlement-quest

# Install
pip install -r requirements.txt

# Run Streamlit dashboard
streamlit run app.py

# Run regression tests
pytest test_settlement.py -v
```

---

## Test results

```
test_settlement.py::TestBuggySettler::test_TC01_happy_path                  PASSED
test_settlement.py::TestBuggySettler::test_TC02_duplicate_payout_on_retry   FAILED  ← bug proven
test_settlement.py::TestFixedSettler::test_TC01_happy_path                  PASSED
test_settlement.py::TestFixedSettler::test_TC02_idempotent_retry            PASSED
test_settlement.py::TestFixedSettler::test_TC03_boundary_end_excluded       PASSED
test_settlement.py::TestFixedSettler::test_TC04_boundary_end_included       PASSED
test_settlement.py::TestFixedSettler::test_TC05_timezone_conversion         PASSED
test_settlement.py::TestFixedSettler::test_TC06_duplicate_task_id_in_batch  PASSED
test_settlement.py::TestFixedSettler::test_TC07_notification_failure_no_rollback PASSED
test_settlement.py::TestFixedSettler::test_TC08_task_outside_window_excluded PASSED
test_settlement.py::TestFixedSettler::test_TC09_multiple_users              PASSED

1 failed (TC02 on buggy — bug confirmed), 10 passed
```

---

## Defect summary

**DEF-001 · Critical · settler.py**

| | |
|---|---|
| Root cause | No idempotency store — every invocation re-processes all tasks in window |
| Expected | 10 credits after retry |
| Actual | 20 credits (doubled) |
| Fix | `settled_task_ids: Set[str]` — skip task_id if already in set |
| Bonus fix | Notification committed after payout; failure is best-effort, never rolls back |

---

## AI contribution

- Code scaffolding and test structure generated with Claude (Sonnet 4.6)
- All business rule assertions, boundary conditions, and defect reasoning verified manually
- TC05 timezone logic corrected after catching an off-by-one in the initial draft
- All test pass/fail outcomes verified by running `pytest` locally

---

## Limitations

- In-memory only — no persistence across runs
- No distributed lock testing (concurrent workers)
- Notification is a stub, not a real gateway
