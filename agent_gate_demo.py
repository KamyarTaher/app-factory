#!/usr/bin/env python3
"""Minimal agent verification gate. Runnable companion to
"Building agents you can trust: Skills and loop engineering".

One dependency-free file that implements all seven lessons as working code:
  1. semantic checks on top of shape checks (a fabricated PASS is rejected)
  2. negative fixtures: every check is proven able to fail
  3. multi-lens consensus with a DEFINED convergence rule (no open P0/P1)
  4. stall detection on issue identity in a review loop, bounded by a turn cap
  5. evidence-required reports (no success from intent)
  6. verify-the-verifier: self-tests, a read-only assertion, a runtime-regression guard
  7. token budget as a validation: oversized work packets are deferred, with a fixture

Run:  python3 agent_gate_demo.py
Exit code 0 = gate demo healthy (checks pass, fixtures fail as required, self-tests pass).
"""

import copy
import time

# --- 1. The artifact an agent hands us, and the gate over it ----------------

REQUIRED_FIELDS = {"task", "status", "evidence"}


def shape_check(report) -> list[str]:
    """Schema-level: right fields, right types. Necessary, nowhere near sufficient."""
    # A verifier flags malformed input; it never crashes on it (Lesson 6),
    # including input that isn't even the right TYPE.
    if not isinstance(report, dict):
        return [f"report must be a dict, got {type(report).__name__}"]
    issues = []
    missing = REQUIRED_FIELDS - report.keys()
    if missing:
        issues.append(f"missing fields: {sorted(missing)}")
    if not isinstance(report.get("evidence", []), list):
        issues.append("evidence must be a list")
    return issues


def semantic_check(report: dict) -> list[str]:
    """Truth-level: a PASS must be backed by verifiable artifacts (Lesson 1)."""
    issues = []
    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        evidence = []   # missing, None, int, bool: treat as no evidence, never iterate a non-list
    if report.get("status") == "PASS" and not evidence:
        issues.append("PASS without evidence artifacts (fabricated success?)")
    for ev in evidence:
        if not isinstance(ev, dict) or not ev.get("artifact") or ev.get("result") not in {"ok", "fail"}:
            issues.append(f"evidence entry not grounded in a tool result: {ev}")
    return issues


CHECKS = [("shape", shape_check), ("semantic", semantic_check)]


def run_gate(report) -> list[str]:
    """Read-only: returns issues, never mutates the report (asserted in self-test)."""
    if not isinstance(report, dict):
        return [f"shape: report must be a dict, got {type(report).__name__}"]
    return [f"{name}: {issue}" for name, check in CHECKS for issue in check(report)]


# --- 2. Negative fixtures: prove every check can fail (Lesson 2) -------------
# A check without a failing fixture is a check you have never seen work.

NEGATIVE_FIXTURES = [
    {"id": "rejects-fabricated-pass",
     "input": {"task": "t1", "status": "PASS", "evidence": []},
     "must_flag": "PASS without evidence"},
    {"id": "rejects-missing-fields",
     "input": {"status": "PASS"},
     "must_flag": "missing fields"},
    {"id": "rejects-ungrounded-evidence",
     "input": {"task": "t1", "status": "PASS", "evidence": [{"artifact": "", "result": "trust me"}]},
     "must_flag": "not grounded"},
    {"id": "flags-malformed-evidence-without-crashing",
     "input": {"task": "t1", "status": "PASS", "evidence": ["pytest passed"]},
     "must_flag": "not grounded"},   # a bare string, not a dict: flag, never AttributeError
    {"id": "flags-non-dict-report-without-crashing",
     "input": "not a report at all",
     "must_flag": "must be a dict"},
    {"id": "flags-null-evidence-without-crashing",
     "input": {"task": "t1", "status": "PASS", "evidence": None},
     "must_flag": "PASS without evidence"},
    {"id": "flags-non-iterable-evidence-without-crashing",
     "input": {"task": "t1", "status": "PASS", "evidence": 123},
     "must_flag": "PASS without evidence"},   # a bare int: treat as empty, never TypeError
]


def run_negative_fixtures() -> list[str]:
    failures = []
    for fx in NEGATIVE_FIXTURES:
        issues = run_gate(fx["input"])
        if not any(fx["must_flag"] in i for i in issues):
            failures.append(f"fixture {fx['id']}: gate ACCEPTED a broken input")
    return failures


# --- 3. Multi-lens consensus with a DEFINED convergence rule (Lesson 3) ------
# Distinct lenses, not clones. Convergence is explicit: no open P0 or P1
# across ANY reviewer. Merging is the union of issue sets, not a vote.

def consensus(report: dict, reviewers) -> tuple[bool, list[dict]]:
    open_issues = [iss for review in reviewers for iss in review(report)]
    blocking = [i for i in open_issues if i["severity"] in {"P0", "P1"}]
    return (not blocking), open_issues


# --- 4. A review loop bounded by a turn cap, with stall detection (Lesson 4) -

def review_loop(candidate: dict, revise, reviewers, max_turns: int = 4) -> tuple[dict, str]:
    previous_open: frozenset = frozenset()
    stall_rounds = 0
    for turn in range(1, max_turns + 1):
        green, issues = consensus(candidate, reviewers)
        if green:
            return candidate, f"green after {turn} turn(s)"
        open_now = frozenset(i["id"] for i in issues)
        if open_now == previous_open:
            stall_rounds += 1                    # same issues survived; not progress
            if stall_rounds >= 2:
                return candidate, f"stalled on {sorted(open_now)}; needs a human"
        else:
            stall_rounds = 0                     # progress resets the counter
        previous_open = open_now
        candidate = revise(candidate, sorted(open_now))
    # The turn cap was hit right after the last revise() call, so that
    # candidate has never been checked. Verify it before reporting anything:
    # a status message must describe the candidate it is returned with
    # (Lesson 5), not the issue set from one revision ago.
    green, issues = consensus(candidate, reviewers)
    if green:
        return candidate, f"green after {max_turns} turn(s), verified post-cap"
    return candidate, f"turn cap reached, open: {sorted(i['id'] for i in issues)}"


# --- 5. Token budget as a validation: defer oversized packets (Lesson 7) -----
# The budget is the model's input window minus headroom for its reply and
# system prompt. Size is measured, not guessed. Over budget -> split/defer,
# never dispatch, because the failure mode past the budget is silent quality loss.

INPUT_WINDOW = 200_000
REPLY_HEADROOM = 40_000
DISPATCH_BUDGET = INPUT_WINDOW - REPLY_HEADROOM


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)   # ~4 chars/token; swap for a real tokenizer in prod


def dispatch(packet: str, budget: int = DISPATCH_BUDGET):
    """Return 'DEFER' when a packet would blow the budget, else 'DISPATCH'."""
    return "DEFER" if approx_tokens(packet) > budget else "DISPATCH"


# --- 6. Verify the verifier (Lesson 6): self-tests + read-only + runtime guard

RUNTIME_BUDGET_S = 2.0
RUNTIME_REGRESSION_TOLERANCE = 0.5    # trip if this run is >1.5x baseline runtime


def check_runtime_regression(elapsed_s: float, baseline_s: float) -> str | None:
    """Trip if this run is more than RUNTIME_REGRESSION_TOLERANCE over baseline."""
    if baseline_s > 0 and elapsed_s > baseline_s * (1 + RUNTIME_REGRESSION_TOLERANCE):
        return f"runtime regression: {elapsed_s:.3f}s vs baseline {baseline_s:.3f}s"
    return None


def self_test() -> list[str]:
    fails = []
    # read-only guard: the gate must not mutate what it grades
    probe = {"task": "t1", "status": "PASS", "evidence": []}
    before = copy.deepcopy(probe)
    run_gate(probe)
    if probe != before:
        fails.append("read-only violated: run_gate mutated its input")
    # the token-deferral rule must actually fire on an oversized packet
    if dispatch("x" * (DISPATCH_BUDGET * 4 + 8)) != "DEFER":
        fails.append("token-budget deferral did not fire on an oversized packet")
    if dispatch("small task") != "DISPATCH":
        fails.append("token-budget deferral misfired on a small packet")
    # the regression gate must fire when a run blows past 1.5x baseline...
    if check_runtime_regression(elapsed_s=2.0, baseline_s=1.0) is None:
        fails.append("runtime regression gate did not fire on a 2x-baseline run")
    # ...and must stay quiet on a run within tolerance
    if check_runtime_regression(elapsed_s=1.2, baseline_s=1.0) is not None:
        fails.append("runtime regression gate misfired inside tolerance")
    # every negative fixture must still fail as required
    fails.extend(run_negative_fixtures())
    return fails


# --- Demo -------------------------------------------------------------------

def lens_correctness(report):   # shape only: fields present, right types
    return [{"id": f"corr:{i}", "severity": "P1", "msg": i} for i in shape_check(report)]


def lens_evidence(report):      # semantic only: is a PASS actually grounded
    return [{"id": f"ev:{i}", "severity": "P0", "msg": i} for i in semantic_check(report)]


def lens_style(report):   # a deliberately non-blocking lens (P2 only)
    return [] if report.get("task") else [{"id": "sty:untitled", "severity": "P2", "msg": "no task label"}]


REVIEWERS = [lens_correctness, lens_evidence, lens_style]


def main() -> int:
    start = time.perf_counter()

    fake_pass = {"task": "migrate-config", "status": "PASS", "evidence": []}
    print("fabricated PASS  ->", run_gate(fake_pass) or "ACCEPTED (this would be the bug)")
    assert run_gate(fake_pass), "gate accepted a fabricated PASS"

    honest = {"task": "migrate-config", "status": "PASS",
              "evidence": [{"artifact": "pytest.log", "result": "ok"}]}
    print("grounded PASS    ->", run_gate(honest) or "accepted")

    print("negative fixtures->", run_negative_fixtures() or f"all {len(NEGATIVE_FIXTURES)} fail as required")

    print("token dispatch   ->", "oversized=%s small=%s"
          % (dispatch("x" * (DISPATCH_BUDGET * 4 + 8)), dispatch("small task")))

    _, verdict = review_loop(fake_pass, revise=lambda c, _i: c, reviewers=REVIEWERS)
    print("stalling loop    ->", verdict)
    assert "human" in verdict, "stall detection failed"

    def fix(c, _issues):
        return {**c, "evidence": [{"artifact": "pytest.log", "result": "ok"}]}
    _, verdict = review_loop(fake_pass, revise=fix, reviewers=REVIEWERS)
    print("converging loop  ->", verdict)

    st = self_test()
    print("self-test        ->", st or "verifier verifies itself")
    assert not st, f"self-test failed: {st}"

    elapsed = time.perf_counter() - start
    over = elapsed > RUNTIME_BUDGET_S
    print(f"runtime          -> {elapsed*1000:.0f}ms (budget {RUNTIME_BUDGET_S*1000:.0f}ms{'; OVER' if over else ''})")

    print("gate demo healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
