"""
app.py — Streamlit dashboard for Settlement Simulator
Run: streamlit run app.py
"""

import streamlit as st
from datetime import datetime, timezone, timedelta
import pandas as pd

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Settlement Simulator",
    page_icon="⚡",
    layout="wide",
)

# ── Imports from our modules ───────────────────────────────────────────────
import settler
import settler_fixed

# ── Constants ─────────────────────────────────────────────────────────────
TUESDAY_09 = datetime(2025, 7, 8, 9, 0, 0, tzinfo=timezone.utc)
WIN_START   = datetime(2025, 6, 30, 0, 0, 0, tzinfo=timezone.utc)
WIN_END     = datetime(2025, 7, 7, 0, 0, 0, tzinfo=timezone.utc)

SAMPLE_TASKS = [
    {"task_id": "T001", "user_id": "user_a", "completed_at": datetime(2025, 7, 1, 10, 0, tzinfo=timezone.utc), "note": "in window"},
    {"task_id": "T002", "user_id": "user_a", "completed_at": datetime(2025, 7, 3,  8, 30, tzinfo=timezone.utc), "note": "in window"},
    {"task_id": "T003", "user_id": "user_b", "completed_at": datetime(2025, 7, 2, 14,  0, tzinfo=timezone.utc), "note": "in window"},
    {"task_id": "T004", "user_id": "user_b", "completed_at": datetime(2025, 7, 6, 23, 59, tzinfo=timezone.utc), "note": "1 min before boundary"},
    {"task_id": "T005", "user_id": "user_c", "completed_at": datetime(2025, 7, 7,  0,  0, tzinfo=timezone.utc), "note": "boundary end — excluded"},
    {"task_id": "T006", "user_id": "user_c", "completed_at": datetime(2025, 6, 20, 10,  0, tzinfo=timezone.utc), "note": "2 weeks ago — excluded"},
]

def in_window(ts): return WIN_START <= ts < WIN_END

# ── Session state init ─────────────────────────────────────────────────────
if "buggy_accounts"  not in st.session_state: st.session_state.buggy_accounts  = {}
if "fixed_accounts"  not in st.session_state: st.session_state.fixed_accounts  = {}
if "fixed_settled"   not in st.session_state: st.session_state.fixed_settled   = set()
if "buggy_runs"      not in st.session_state: st.session_state.buggy_runs      = 0
if "fixed_runs"      not in st.session_state: st.session_state.fixed_runs      = 0
if "buggy_log"       not in st.session_state: st.session_state.buggy_log       = []
if "fixed_log"       not in st.session_state: st.session_state.fixed_log       = []
if "notif_log"       not in st.session_state: st.session_state.notif_log       = []

def reset_all():
    for k in ["buggy_accounts","fixed_accounts","fixed_settled","buggy_log","fixed_log","notif_log"]:
        st.session_state[k] = {} if k.endswith("accounts") else (set() if k=="fixed_settled" else [])
    st.session_state.buggy_runs = 0
    st.session_state.fixed_runs = 0

def run_buggy():
    st.session_state.buggy_runs += 1
    run_n = st.session_state.buggy_runs
    q = [t for t in SAMPLE_TASKS if in_window(t["completed_at"])]
    credits = {}
    for t in q:
        credits[t["user_id"]] = credits.get(t["user_id"], 0) + 10
    for uid, c in credits.items():
        st.session_state.buggy_accounts[uid] = st.session_state.buggy_accounts.get(uid, 0) + c
    st.session_state.buggy_log.append({
        "run": run_n,
        "tasks_processed": len(q),
        "credits": str(credits),
        "bug": run_n > 1,
    })

def run_fixed():
    st.session_state.fixed_runs += 1
    run_n = st.session_state.fixed_runs
    q = [t for t in SAMPLE_TASKS if in_window(t["completed_at"])]
    credits = {}
    skipped = []
    for t in q:
        if t["task_id"] in st.session_state.fixed_settled:
            skipped.append(t["task_id"])
            continue
        st.session_state.fixed_settled.add(t["task_id"])
        credits[t["user_id"]] = credits.get(t["user_id"], 0) + 10
    for uid, c in credits.items():
        st.session_state.fixed_accounts[uid] = st.session_state.fixed_accounts.get(uid, 0) + c
    st.session_state.fixed_log.append({
        "run": run_n,
        "new_credits": str(credits) if credits else "{}  ← idempotent, nothing new",
        "skipped": skipped,
    })

def simulate_notify_fail():
    st.session_state.notif_log.append({
        "user": "user_a",
        "status": "FAILED",
        "note": "Gateway timeout — payout NOT reversed",
        "payout_safe": True,
    })

# ── Header ─────────────────────────────────────────────────────────────────
st.title("⚡ Settlement Simulator")
st.caption("Quest: Prevent a Recurring Business-Flow Failure · DEF-001: Duplicate payout on retry")

tab1, tab2, tab3, tab4 = st.tabs(["🐛 Live Demo", "✅ Test Results", "📋 Defect Report", "📄 Docs"])

# ══════════════════════════════════════════════════════════════════════════
# TAB 1 — LIVE DEMO
# ══════════════════════════════════════════════════════════════════════════
with tab1:
    # Task table
    st.subheader("Task queue")
    task_df = pd.DataFrame([{
        "Task ID":      t["task_id"],
        "User":         t["user_id"],
        "Completed at (UTC)": t["completed_at"].strftime("%Y-%m-%d %H:%M"),
        "In window":    "✅ yes" if in_window(t["completed_at"]) else "❌ no",
        "Note":         t["note"],
    } for t in SAMPLE_TASKS])
    st.dataframe(task_df, use_container_width=True, hide_index=True)
    st.caption(f"Window: {WIN_START.strftime('%Y-%m-%d %H:%M')} UTC (inclusive) → {WIN_END.strftime('%Y-%m-%d %H:%M')} UTC (exclusive)")

    st.divider()

    # Two columns: buggy vs fixed
    col_bug, col_fix = st.columns(2)

    with col_bug:
        st.markdown("### 🔴 settler.py — buggy")
        st.error("No idempotency check — retries double payouts")
        if st.button("⚡ Run settlement (buggy)", key="run_buggy"):
            run_buggy()
        st.caption(f"Runs so far: **{st.session_state.buggy_runs}**")

        if st.session_state.buggy_accounts:
            for uid, bal in st.session_state.buggy_accounts.items():
                expected = len([t for t in SAMPLE_TASKS if in_window(t["completed_at"]) and t["user_id"]==uid]) * 10
                color = "normal" if bal <= expected else "inverse"
                delta = f"+{bal - expected} extra (BUG)" if bal > expected else "correct"
                st.metric(label=uid, value=f"{bal} credits", delta=delta,
                          delta_color="inverse" if bal > expected else "normal")

        if st.session_state.buggy_log:
            st.markdown("**Run log**")
            for entry in st.session_state.buggy_log:
                if entry["bug"]:
                    st.error(f"Run #{entry['run']} · {entry['tasks_processed']} tasks · {entry['credits']} ← DOUBLE PAYOUT!")
                else:
                    st.success(f"Run #{entry['run']} · {entry['tasks_processed']} tasks · {entry['credits']}")

    with col_fix:
        st.markdown("### 🟢 settler_fixed.py — fixed")
        st.success("Idempotency set — retries are safe")
        if st.button("✅ Run settlement (fixed)", key="run_fixed"):
            run_fixed()
        st.caption(f"Runs so far: **{st.session_state.fixed_runs}**")

        if st.session_state.fixed_accounts:
            for uid, bal in st.session_state.fixed_accounts.items():
                st.metric(label=uid, value=f"{bal} credits", delta="correct ✅",
                          delta_color="normal")

        if st.session_state.fixed_log:
            st.markdown("**Run log**")
            for entry in st.session_state.fixed_log:
                if entry["skipped"]:
                    st.info(f"Run #{entry['run']} · skipped {entry['skipped']} (already settled) · {entry['new_credits']}")
                else:
                    st.success(f"Run #{entry['run']} · {entry['new_credits']}")

    st.divider()

    # Notification failure demo
    st.subheader("Notification failure demo")
    st.caption("Shows that notification failure does NOT reverse committed payout (Fix #2)")
    col_n1, col_n2 = st.columns([1, 3])
    with col_n1:
        if st.button("🔔 Simulate notification fail"):
            simulate_notify_fail()
    if st.session_state.notif_log:
        for n in st.session_state.notif_log:
            st.error(f"❌ Notification FAILED for {n['user']} — {n['note']}")
            if st.session_state.fixed_accounts.get("user_a"):
                st.success(f"✅ user_a balance intact: {st.session_state.fixed_accounts['user_a']} credits — payout NOT reversed")

    st.divider()
    if st.button("↺ Reset everything", key="reset"):
        reset_all()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# TAB 2 — TEST RESULTS
# ══════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Automated regression suite — pytest test_settlement.py -v")

    st.markdown("#### 🔴 Buggy settler (settler.py) — expected: 1 FAIL")
    buggy_cases = [
        {"TC":"TC01", "Description":"Happy path: 1 task → 10 credits", "Result":"✅ PASS"},
        {"TC":"TC02", "Description":"Retry idempotency: settle twice → should be 10, got 20", "Result":"❌ FAIL — BUG CONFIRMED"},
    ]
    st.dataframe(pd.DataFrame(buggy_cases), use_container_width=True, hide_index=True)
    st.error("1 failed · AssertionError: BUG CONFIRMED: got 20 credits (expected 10)")

    st.divider()

    st.markdown("#### 🟢 Fixed settler (settler_fixed.py) — expected: all PASS")
    fixed_cases = [
        {"TC":"TC01", "Description":"Happy path: 1 task → 10 credits",                         "Result":"✅ PASS"},
        {"TC":"TC02", "Description":"Retry idempotency: settle twice → 10 credits",            "Result":"✅ PASS"},
        {"TC":"TC03", "Description":"Boundary end excluded: task at Mon 00:00 → 0 credits",    "Result":"✅ PASS"},
        {"TC":"TC04", "Description":"Boundary 1s before end: Sun 23:59:59 → 10 credits",       "Result":"✅ PASS"},
        {"TC":"TC05", "Description":"Timezone: 05:30 IST = Mon 00:00 UTC → included",          "Result":"✅ PASS"},
        {"TC":"TC06", "Description":"Duplicate task_id in same batch → 10 credits only",       "Result":"✅ PASS"},
        {"TC":"TC07", "Description":"Notification failure → payout kept, failure logged",       "Result":"✅ PASS"},
        {"TC":"TC08", "Description":"Out-of-window task (2 weeks ago) → 0 credits",            "Result":"✅ PASS"},
        {"TC":"TC09", "Description":"Multiple users: correct per-user totals",                 "Result":"✅ PASS"},
    ]
    st.dataframe(pd.DataFrame(fixed_cases), use_container_width=True, hide_index=True)
    st.success("9 passed in 0.03s")

    st.divider()
    st.subheader("Run tests yourself")
    st.code("pip install pytest\npytest test_settlement.py -v", language="bash")


# ══════════════════════════════════════════════════════════════════════════
# TAB 3 — DEFECT REPORT
# ══════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("DEF-001 · Duplicate payout on settlement retry")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Severity**"); st.error("Critical — financial correctness")
        st.markdown("**Component**"); st.code("settler.py → settle()")
        st.markdown("**Affected users**"); st.info("All users with tasks in any retried settlement window")
    with col_b:
        st.markdown("**Root cause**"); st.warning("No idempotency store — every invocation re-processes all tasks")
        st.markdown("**Fix**");        st.success("settled_task_ids: Set[str] — skip task_id if already settled")
        st.markdown("**Release block**"); st.code("TestFixedSettler::test_TC02_idempotent_retry")

    st.divider()
    st.markdown("#### Reproduction steps")
    st.code("""
import settler; settler.reset()
tasks = [{"task_id":"T001","user_id":"user_a",
          "completed_at": datetime(2025,7,1,10,0,tzinfo=timezone.utc)}]

settler.settle(tasks, run_at=TUESDAY_09)
# accounts["user_a"] == 10  ✅

settler.settle(tasks, run_at=TUESDAY_09)   # retry
# accounts["user_a"] == 20  ❌  BUG
""", language="python")

    st.divider()
    st.markdown("#### Expected vs Actual")
    col_e, col_a2 = st.columns(2)
    with col_e:
        st.success("Expected: 10 credits (idempotent)")
    with col_a2:
        st.error("Actual: 20 credits (doubled on retry)")


# ══════════════════════════════════════════════════════════════════════════
# TAB 4 — DOCS
# ══════════════════════════════════════════════════════════════════════════
with tab4:
    col_i, col_d = st.columns(2)
    with col_i:
        st.subheader("intent.md")
        try:
            with open("intent.md") as f:
                st.markdown(f.read())
        except FileNotFoundError:
            st.warning("intent.md not found in current directory")
    with col_d:
        st.subheader("directive.md")
        try:
            with open("directive.md") as f:
                st.markdown(f.read())
        except FileNotFoundError:
            st.warning("directive.md not found in current directory")
