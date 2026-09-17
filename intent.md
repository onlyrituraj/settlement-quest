# intent.md — Why this problem?

## Problem selected

**Duplicate payout on retry (TC02): Settlement runs twice for the same task window, crediting users double.**

---

## Alternatives considered

| # | Problem | User Impact | Likelihood | Effort | Score |
|---|---------|------------|------------|--------|-------|
| **1** | **Duplicate payout on retry** | **High — double credits issued** | **High — retries are routine** | **Low** | **🥇 First** |
| 2 | Off-by-one boundary (task at window end counted twice) | Medium — affects users with tasks at exact boundary | Medium | Medium | Second |
| 3 | Notification failure rolls back committed payout | High — user loses earned credits | Low — rare gateway failure | Medium | Third |

### Scoring criteria
- **User impact**: How many users are affected? Do they lose or gain money/credits?
- **Likelihood**: How often does this code path execute in real systems? (retries = very common)
- **Effort**: How much code and test infrastructure is needed to prove the fix?

---

## Why problem #1 ranked first

In any distributed system, the settlement job can be retried due to:
- Network timeout on the job scheduler
- Server crash mid-run
- Ops team manually re-triggering after a perceived failure
- Cloud function timeout causing a second invocation

Without an idempotency check, each retry issues a fresh payout for every task in the window. Users get double (or triple) credits. This is a **financial correctness bug** that is both high-frequency (retries happen in every real system) and high-impact (users gain unearned value, company loses money).

Problem #3 (notification rollback) is also high impact but lower likelihood — most notification gateways are reliable. I treat it as a secondary fix in the same implementation.

---

## Affected users

In the fictional scenario: **any user who has qualifying tasks in the settlement window** when the job retries. In a real rewards platform this could be 100% of active users during any Tuesday 09:00 UTC run that experiences a transient failure.

---

## Evidence and uncertainty

This is a synthetic scenario — I have no access to live incident history. The failure mode is well-documented in distributed systems literature (idempotency is a standard requirement for financial job processors). I am not fabricating incidents; I am reproducing a structurally realistic bug using in-memory code.

---

## Intended value

- Prevents credit double-spend on any settlement retry
- Proves the regression automatically — no manual verification needed
- Decouples notification from payout commit (bonus fix for problem #3)

---

## Non-goals

- Not testing a live financial system
- Not covering all possible edge cases (e.g., database corruption, race conditions in distributed locks)
- Not implementing a full scheduler or job queue
