# directive.md — Settlement Quest

## Objective

Reproduce and fix the duplicate-payout bug in a weekly rewards settlement flow.
Prove the regression catches the bug before the fix, and passes after.

---

## Scope

- **In scope**: Idempotency on retry, boundary exclusion, timezone handling, notification decoupling
- **Out of scope**: Live databases, real payment systems, distributed locks, multi-node race conditions

---

## Business rules

1. Settlement runs every **Tuesday at 09:00 UTC**
2. Window: `Mon 00:00 UTC (inclusive)` → `Mon 00:00 UTC next week (exclusive)`
3. Each qualifying task earns **10 credits**
4. Task IDs must be counted **once** — retries must not create a second payout
5. Notification is sent **only after** a successful payout
6. Notification failure must **not** reverse the payout

---

## Requirements

| ID | Requirement |
|----|-------------|
| R1 | `settler_fixed.py` must be idempotent: same task_id settled twice → credits issued once |
| R2 | Window boundary: task at `end` datetime is excluded |
| R3 | All timestamps must be compared in UTC |
| R4 | Payout commits before notification is attempted |
| R5 | Notification failure is logged, not propagated as a rollback |
| R6 | Regression test `TC02` must FAIL on `settler.py` and PASS on `settler_fixed.py` |

---

## Completion criteria

- [ ] `pytest test_settlement.py -v` shows **10 passed, 1 failed** (TC02 on buggy settler)
- [ ] All 9 cases in `TestFixedSettler` pass
- [ ] `TC02` in `TestBuggySettler` fails with message `BUG CONFIRMED: got 20 credits`
- [ ] Loom video recorded (≤5 min)
- [ ] `intent.md` and `directive.md` submitted

---

## Defect report

### DEF-001: Duplicate payout on settlement retry

| Field | Detail |
|-------|--------|
| **Title** | Settlement job issues double credits on retry |
| **Severity** | Critical — financial correctness |
| **Component** | `settler.py` → `settle()` function |
| **Affected users** | All users with qualifying tasks in the settlement window |

**Reproduction steps**
1. Create one task for `user_a` with `completed_at` inside the settlement window
2. Call `settler.settle(tasks, run_at=TUESDAY_09)` — user_a receives 10 credits ✅
3. Call `settler.settle(tasks, run_at=TUESDAY_09)` again (simulating retry)
4. Check `settler.accounts["user_a"]` — it is **20** ❌

**Expected**: 10 credits (idempotent)
**Actual**: 20 credits (doubled)

**Root cause**: `settler.py` has no idempotency store. It re-processes every task in the window on each invocation without checking whether a task_id has already been settled.

**Proposed fix**: Maintain a `settled_task_ids: Set[str]` and skip any `task_id` already in the set before issuing credits. See `settler_fixed.py`.

**Release check that would block this**: `TestFixedSettler::test_TC02_idempotent_retry` — this test fails on the buggy code path and passes only on the fixed implementation. It must be in CI.

---

## Test cases summary

| TC | Description | Input | Expected | Covers |
|----|-------------|-------|----------|--------|
| TC01 | Happy path | 1 task in window | 10 credits, notification SENT | Happy path |
| TC02 | Retry idempotency | Same task, settle twice | 10 credits (not 20) | **Main bug** |
| TC03 | Boundary end excluded | Task at window end (00:00 Mon) | 0 credits | Boundary |
| TC04 | Boundary end-1s included | Task at 23:59:59 Sun | 10 credits | Boundary |
| TC05 | Timezone IST→UTC | Task stored in IST, boundary in UTC | 10 credits | Timezone |
| TC06 | Duplicate task_id in batch | Same task_id twice in one run | 10 credits | Dedup |
| TC07 | Notification failure | Notification gateway fails | Credits kept, failure logged | Partial failure |
| TC08 | Out-of-window task | Task from 2 weeks ago | 0 credits | Out-of-scope |
| TC09 | Multiple users | 3 tasks, 2 users | Correct per-user totals | Multi-user |

---

## Release readiness

### Decision: ✅ READY TO RELEASE (fixed version)

Evidence:
- All 9 `TestFixedSettler` cases pass
- Buggy behavior is proven in `TestBuggySettler::TC02` (fails as expected)
- Boundary, timezone, dedup, partial failure all covered

### Remaining gaps
- No test for distributed race condition (two workers settling same window simultaneously)
- No test for database rollback mid-payout (requires real DB or mock)
- No load/performance test

### Handoff instructions

```bash
# Clone or download the project
cd settlement-quest

# Install dependencies
pip install pytest

# Run regression suite
pytest test_settlement.py -v

# Expected result:
# 1 FAILED  (TestBuggySettler::test_TC02 — proves the bug exists)
# 10 PASSED (all fixed settler cases)
```

### Artifact links

| Artifact | Description |
|----------|-------------|
| `settler.py` | Buggy implementation (no idempotency) |
| `settler_fixed.py` | Fixed implementation (idempotent, notification decoupled) |
| `test_settlement.py` | 9 test cases + 1 bug-proof case |
| `intent.md` | Problem selection and prioritization |
| `directive.md` | This document |

---

## AI contribution and corrections

- AI generated initial structure of `settler.py`, `settler_fixed.py`, and test scaffolding
- I verified all 9 test assertions manually against the business rules
- I confirmed TC05 (timezone) uses `astimezone(utc)` correctly — initial draft had a raw offset error that I caught and corrected
- I wrote the prioritization scoring and defect report reasoning myself

---

## Limitations

- In-memory simulation only — no persistence across runs
- Settlement window assumes the caller passes a valid Tuesday 09:00 UTC `run_at`; no scheduler validation
- Notification is a stub — not integrated with any real gateway
