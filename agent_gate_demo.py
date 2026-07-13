#!/usr/bin/env python3
"""Runnable companion to "I built 20+ iOS apps with an agent factory. The hard
part was proving the agents weren't lying."

https://github.com/KamyarTaher/app-factory
First brick of the app-factory machinery being opened up piece by piece.

One dependency-free file demonstrates the seven tricks: semantic checks,
negative fixtures, consensus, bounded review loops, evidence, verifier tests,
and work-packet budgets.

Run: python3 agent_gate_demo.py
Exit code 0 means every demo check passed.
"""

import copy
import hashlib
import time
from dataclasses import dataclass

# --- 1. The artifact an agent hands us, and the gate over it ----------------
# Tricks 1 and 5: check meaning, then require evidence from the current run.

REQUIRED_FIELDS = {"task", "status", "evidence"}
VALID_STATUSES = {"PASS", "FAIL"}

def sha256_text(content: str) -> str:
    """Return the demo digest used by tool steps and evidence reports."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

class RunRegistry:
    """Small in-memory record of artifacts produced by each verification run."""
    def __init__(self):
        self._runs = {}
        self._run_counter = 0

    def start_run(self) -> int:
        self._run_counter += 1
        self._runs[self._run_counter] = {}
        return self._run_counter

    def register(self, run_id: int, artifact: str, digest: str, status: str) -> None:
        if run_id not in self._runs:
            raise ValueError(f"unknown run_id: {run_id}")
        if not isinstance(artifact, str) or not artifact:
            raise ValueError("artifact must be a non-empty string")
        if status not in {"ok", "fail"}:
            raise ValueError("status must be 'ok' or 'fail'")
        self._runs[run_id][artifact] = {"digest": digest, "status": status}

    def result_for(self, run_id: int, artifact: str):
        return self._runs.get(run_id, {}).get(artifact)

    def prior_run_for(self, run_id: int, artifact: str):
        matches = [rid for rid, entries in self._runs.items()
                   if rid < run_id and artifact in entries]
        return max(matches, default=None)

    def snapshot(self):
        """Expose a safe copy for the read-only verifier test."""
        return copy.deepcopy((self._run_counter, self._runs))

def shape_check(report) -> list[str]:
    """Check required fields and types without crashing on malformed input."""
    if not isinstance(report, dict):
        return [f"report must be a dict, got {type(report).__name__}"]
    issues = []
    missing = REQUIRED_FIELDS - report.keys()
    if missing:
        issues.append(f"missing fields: {sorted(missing)}")
    if "task" in report and (not isinstance(report["task"], str) or not report["task"].strip()):
        issues.append("task must be a non-empty string")
    if "status" in report and report["status"] not in VALID_STATUSES:
        issues.append(f"unknown status: {report['status']!r}")
    evidence = report.get("evidence", [])
    if not isinstance(evidence, list):
        issues.append("evidence must be a list")
        return issues
    for index, entry in enumerate(evidence):
        if not isinstance(entry, dict):
            issues.append(f"evidence[{index}] must be a dict")
            continue
        missing_keys = {"artifact", "result"} - entry.keys()
        if missing_keys:
            issues.append(f"evidence[{index}] missing keys: {sorted(missing_keys)}")
        if "artifact" in entry and (
                not isinstance(entry["artifact"], str) or not entry["artifact"].strip()):
            issues.append(f"evidence[{index}] artifact must be a non-empty string")
    return issues

def semantic_check(report: dict, registry: RunRegistry, run_id: int) -> list[str]:
    """Reject PASS claims not backed by successful artifacts from this run."""
    issues = []
    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    is_pass = report.get("status") == "PASS"
    if is_pass and not evidence:
        issues.append("PASS without evidence artifacts (fabricated success?)")
    for entry in evidence:
        grounded = (isinstance(entry, dict)
                    and isinstance(entry.get("artifact"), str)
                    and bool(entry.get("artifact", "").strip())
                    and entry.get("result") in {"ok", "fail"})
        if not grounded:
            issues.append(f"evidence entry not grounded in a tool result: {entry}")
            continue
        if not is_pass:
            continue
        artifact = entry["artifact"]
        registered = registry.result_for(run_id, artifact)
        if registered is None:
            prior_run = registry.prior_run_for(run_id, artifact)
            if prior_run is None:
                issues.append(f"unregistered evidence artifact: {artifact}")
            else:
                issues.append(f"stale evidence: artifact from run {prior_run}: {artifact}")
            continue
        if entry.get("digest") != registered["digest"]:
            issues.append(f"evidence digest does not match registry: {artifact}")
        if registered["status"] == "fail":
            issues.append(f"evidence cites a failing tool result: {artifact}")
    return issues

def run_gate(report, registry: RunRegistry, run_id: int) -> list[str]:
    """Return issues without mutating either the report or registry (Trick 6)."""
    if not isinstance(report, dict):
        return [f"shape: report must be a dict, got {type(report).__name__}"]
    return ([f"shape: {issue}" for issue in shape_check(report)]
            + [f"semantic: {issue}" for issue in semantic_check(report, registry, run_id)])

# --- 2. Negative fixtures: prove every check can fail (Trick 2) -------------
# Every new rule gets a broken case that must be rejected.

NEGATIVE_FIXTURES = [
    {"id": "rejects-fabricated-pass", "must_flag": "PASS without evidence",
     "input": {"task": "t1", "status": "PASS", "evidence": []}},
    {"id": "rejects-missing-fields", "must_flag": "missing fields",
     "input": {"status": "PASS"}},
    {"id": "rejects-ungrounded-evidence",
     "must_flag": "not grounded", "input": {"task": "t1", "status": "PASS",
     "evidence": [{"artifact": "", "result": "trust me"}]}},
    {"id": "flags-malformed-evidence-without-crashing", "must_flag": "not grounded",
     "input": {"task": "t1", "status": "PASS", "evidence": ["pytest passed"]}},
    {"id": "flags-non-dict-report-without-crashing", "must_flag": "must be a dict",
     "input": "not a report at all"},
    {"id": "flags-null-evidence-without-crashing", "must_flag": "PASS without evidence",
     "input": {"task": "t1", "status": "PASS", "evidence": None}},
    {"id": "flags-non-iterable-evidence-without-crashing",
     "must_flag": "PASS without evidence",
     "input": {"task": "t1", "status": "PASS", "evidence": 123}},
    {"id": "rejects-unknown-status", "must_flag": "unknown status",
     "input": {"task": "t1", "status": "MAYBE", "evidence": []}},
    {"id": "rejects-empty-task", "must_flag": "task must be a non-empty string",
     "input": {"task": "  ", "status": "FAIL", "evidence": []}},
    {"id": "rejects-evidence-that-is-not-a-dict", "must_flag": "must be a dict",
     "input": {"task": "t1", "status": "FAIL", "evidence": [7]}},
    {"id": "rejects-missing-artifact-key", "must_flag": "missing keys",
     "input": {"task": "t1", "status": "FAIL", "evidence": [{"result": "fail"}]}},
    {"id": "rejects-non-string-artifact",
     "must_flag": "artifact must be a non-empty string",
     "input": {"task": "t1", "status": "FAIL", "evidence": [{"artifact": 7, "result": "fail"}]}},
    {"id": "rejects-missing-result-key", "must_flag": "missing keys",
     "input": {"task": "t1", "status": "FAIL", "evidence": [{"artifact": "test.log"}]}},
    {"id": "rejects-digest-mismatch",
     "input": {"task": "t1", "status": "PASS",
               "evidence": [{"artifact": "test.log", "result": "ok",
                             "digest": sha256_text("claimed content")}]},
     "setup": [{"scope": "current", "artifact": "test.log",
               "content": "actual content", "status": "ok"}],
     "must_flag": "digest does not match"},
    {"id": "rejects-unregistered-artifact",
     "input": {"task": "t1", "status": "PASS",
               "evidence": [{"artifact": "ghost.log", "result": "ok",
                             "digest": sha256_text("ghost")}]},
     "must_flag": "unregistered evidence artifact"},
    {"id": "rejects-stale-run-evidence",
     "input": {"task": "t1", "status": "PASS",
               "evidence": [{"artifact": "old.log", "result": "ok",
                             "digest": sha256_text("old result")}]},
     "setup": [{"scope": "previous", "artifact": "old.log",
               "content": "old result", "status": "ok"}],
     "must_flag": "stale evidence: artifact from run 1"},
    {"id": "rejects-failing-evidence",
     "input": {"task": "t1", "status": "PASS",
               "evidence": [{"artifact": "failed.log", "result": "fail",
                             "digest": sha256_text("tests failed")}]},
     "setup": [{"scope": "current", "artifact": "failed.log",
               "content": "tests failed", "status": "fail"}],
     "must_flag": "evidence cites a failing tool result"},
]

def fixture_context(fixture) -> tuple[RunRegistry, int]:
    registry = RunRegistry()
    setup = fixture.get("setup", [])
    previous = [item for item in setup if item["scope"] == "previous"]
    if previous:
        prior_run = registry.start_run()
        for item in previous:
            registry.register(prior_run, item["artifact"], sha256_text(item["content"]), item["status"])
    run_id = registry.start_run()
    for item in (item for item in setup if item["scope"] == "current"):
        registry.register(run_id, item["artifact"], sha256_text(item["content"]), item["status"])
    return registry, run_id

def run_negative_fixtures() -> list[str]:
    failures = []
    for fixture in NEGATIVE_FIXTURES:
        registry, run_id = fixture_context(fixture)
        issues = run_gate(fixture["input"], registry, run_id)
        if not any(fixture["must_flag"] in issue for issue in issues):
            failures.append(f"fixture {fixture['id']}: required flag was not raised")
    return failures

# --- 3. Multi-lens consensus with a defined convergence rule (Trick 3) -----
# Distinct lenses merge issue sets. No open P0 or P1 means green.

def consensus(report: dict, reviewers) -> tuple[bool, list[dict]]:
    open_issues = [issue for review in reviewers for issue in review(report)]
    blocking = [issue for issue in open_issues if issue["severity"] in {"P0", "P1"}]
    return not blocking, open_issues

# --- 4. Bounded review loop with stall detection (Trick 4) -----------------
# Turns and spend both cap revision and post-cap verification paths.

@dataclass(frozen=True)
class GateResult:
    can_ship: bool
    candidate: dict
    open_issues: list
    turns: int
    spend_usd: float
    verdict: str

def review_loop(candidate: dict, revise, reviewers, max_turns: int = 4,
                max_spend_usd: float = 1.0, cost_per_turn: float = 0.05) -> GateResult:
    previous_open = frozenset()
    stall_rounds = 0
    spend = 0.0
    turns = 0
    def can_afford() -> bool:
        return spend + cost_per_turn <= max_spend_usd + 1e-12
    for turn in range(1, max_turns + 1):
        if not can_afford():
            return GateResult(False, candidate, [], turns, spend,
                              f"spend cap reached before turn {turn}")
        spend += cost_per_turn
        turns += 1
        green, issues = consensus(candidate, reviewers)
        if green:
            return GateResult(True, candidate, issues, turns, spend,
                              f"green after {turn} turn(s)")
        open_now = frozenset(issue["id"] for issue in issues)
        if open_now == previous_open:
            stall_rounds += 1
            if stall_rounds >= 2:
                return GateResult(False, candidate, issues, turns, spend,
                                  f"stalled on {sorted(open_now)}; needs a human")
        else:
            stall_rounds = 0
        previous_open = open_now
        candidate = revise(candidate, sorted(open_now))
    if not can_afford():
        return GateResult(False, candidate, [], turns, spend,
                          "spend cap reached before post-cap verification")
    spend += cost_per_turn
    turns += 1
    green, issues = consensus(candidate, reviewers)
    if green:
        return GateResult(True, candidate, issues, turns, spend,
                          f"green after {max_turns} turn(s), verified post-cap")
    return GateResult(False, candidate, issues, turns, spend,
                      f"turn cap reached, open: {sorted(i['id'] for i in issues)}")

# --- 5. Token budget as a validation (Trick 7) ------------------------------
# Measure packets and defer oversized work before dispatch.

INPUT_WINDOW = 200_000
REPLY_HEADROOM = 40_000
DISPATCH_BUDGET = INPUT_WINDOW - REPLY_HEADROOM
def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def dispatch(packet: str, budget: int = DISPATCH_BUDGET):
    return "DEFER" if approx_tokens(packet) > budget else "DISPATCH"

# --- 6. Verify the verifier (Trick 6) ---------------------------------------
# Self-tests cover read-only behavior, runtime regression, and all fixtures.

RUNTIME_BUDGET_S = 2.0
RUNTIME_REGRESSION_TOLERANCE = 0.5
def check_runtime_regression(elapsed_s: float, baseline_s: float) -> str | None:
    if baseline_s > 0 and elapsed_s > baseline_s * (1 + RUNTIME_REGRESSION_TOLERANCE):
        return f"runtime regression: {elapsed_s:.3f}s vs baseline {baseline_s:.3f}s"
    return None

def self_test() -> list[str]:
    failures = []
    registry = RunRegistry()
    run_id = registry.start_run()
    probe = {"task": "t1", "status": "PASS", "evidence": []}
    before_report = copy.deepcopy(probe)
    before_registry = registry.snapshot()
    run_gate(probe, registry, run_id)
    if probe != before_report or registry.snapshot() != before_registry:
        failures.append("read-only violated: run_gate mutated its input")
    if dispatch("x" * (DISPATCH_BUDGET * 4 + 8)) != "DEFER":
        failures.append("token-budget deferral did not fire")
    if dispatch("small task") != "DISPATCH":
        failures.append("small packet was incorrectly deferred")
    if check_runtime_regression(2.0, 1.0) is None:
        failures.append("runtime regression gate did not fire")
    if check_runtime_regression(1.2, 1.0) is not None:
        failures.append("runtime regression gate misfired")
    failures.extend(run_negative_fixtures())
    return failures

# --- 7. Runnable demonstration of all seven tricks -------------------------
# The final process status is itself part of the gate contract.

def lens_correctness(report):
    return [{"id": f"corr:{issue}", "severity": "P1", "msg": issue}
            for issue in shape_check(report)]
def lens_evidence(registry, run_id):
    def review(report):
        return [{"id": f"ev:{issue}", "severity": "P0", "msg": issue}
                for issue in semantic_check(report, registry, run_id)]
    return review
def lens_style(report):
    return [] if report.get("task") else [
        {"id": "sty:untitled", "severity": "P2", "msg": "no task label"}]
def failed(reason: str) -> int:
    print(f"gate demo FAILED: {reason}")
    return 1

def main() -> int:
    start = time.perf_counter()
    registry = RunRegistry()
    run_id = registry.start_run()
    good_content = "21 tests passed"
    bad_content = "1 test failed"
    registry.register(run_id, "unittest.log", sha256_text(good_content), "ok")
    registry.register(run_id, "failed.log", sha256_text(bad_content), "fail")
    fake_pass = {"task": "migrate-config", "status": "PASS", "evidence": []}
    fake_issues = run_gate(fake_pass, registry, run_id)
    print("fabricated PASS  ->", fake_issues or "ACCEPTED (this would be the bug)")
    if not fake_issues:
        return failed("gate accepted a fabricated PASS")
    honest = {"task": "migrate-config", "status": "PASS", "evidence": [
        {"artifact": "unittest.log", "result": "ok", "digest": sha256_text(good_content)}]}
    honest_issues = run_gate(honest, registry, run_id)
    print("grounded PASS    ->", honest_issues or "accepted")
    if honest_issues:
        return failed(f"gate rejected grounded evidence: {honest_issues}")
    failing = {"task": "migrate-config", "status": "PASS", "evidence": [
        {"artifact": "failed.log", "result": "fail", "digest": sha256_text(bad_content)}]}
    failing_issues = run_gate(failing, registry, run_id)
    print("failing evidence ->", failing_issues or "ACCEPTED (this would be the bug)")
    if not any("failing tool result" in issue for issue in failing_issues):
        return failed("gate accepted evidence from a failing tool")
    fixture_failures = run_negative_fixtures()
    print("negative fixtures->", fixture_failures or
          f"all {len(NEGATIVE_FIXTURES)} fail as required")
    if fixture_failures:
        return failed(str(fixture_failures))
    large = dispatch("x" * (DISPATCH_BUDGET * 4 + 8))
    small = dispatch("small task")
    print("token dispatch   ->", f"oversized={large} small={small}")
    if (large, small) != ("DEFER", "DISPATCH"):
        return failed("token dispatch checks failed")
    reviewers = [lens_correctness, lens_evidence(registry, run_id), lens_style]
    stalled = review_loop(fake_pass, lambda candidate, _issues: candidate, reviewers)
    print("stalling loop    ->", stalled.verdict)
    if stalled.can_ship or "human" not in stalled.verdict:
        return failed("stall detection failed")
    def fix(candidate, _issues):
        return {**candidate, "evidence": honest["evidence"]}
    converged = review_loop(fake_pass, fix, reviewers)
    print("converging loop  ->", converged.verdict)
    if not converged.can_ship:
        return failed(f"converging candidate was blocked: {converged.verdict}")
    self_test_failures = self_test()
    print("self-test        ->", self_test_failures or "verifier verifies itself")
    if self_test_failures:
        return failed(str(self_test_failures))
    elapsed = time.perf_counter() - start
    over = elapsed > RUNTIME_BUDGET_S
    print(f"runtime          -> {elapsed * 1000:.0f}ms "
          f"(budget {RUNTIME_BUDGET_S * 1000:.0f}ms{'; OVER' if over else ''})")
    if over:
        return failed("runtime budget exceeded")
    print("gate demo healthy")
    return 0
if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as error:
        exit_code = failed(f"unexpected {type(error).__name__}: {error}")
    raise SystemExit(exit_code)
