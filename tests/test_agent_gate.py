"""Focused tests for the dependency-free agent gate demo."""

import copy
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent_gate_demo as gate


class AgentGateTests(unittest.TestCase):
    def setUp(self):
        self.registry = gate.RunRegistry()
        self.run_id = self.registry.start_run()

    def report(self, artifact="tests.log", content="tests passed", result="ok"):
        return {"task": "verify-build", "status": "PASS", "evidence": [{
            "artifact": artifact, "result": result, "digest": gate.sha256_text(content)}]}

    def reviewers(self):
        return [gate.lens_correctness,
                gate.lens_evidence(self.registry, self.run_id), gate.lens_style]

    def test_fabricated_pass_is_rejected(self):
        report = {"task": "verify-build", "status": "PASS", "evidence": []}
        self.assertTrue(any("PASS without evidence" in issue
                            for issue in gate.run_gate(report, self.registry, self.run_id)))

    def test_grounded_pass_is_accepted(self):
        self.registry.register(self.run_id, "tests.log", gate.sha256_text("tests passed"), "ok")
        self.assertEqual([], gate.run_gate(self.report(), self.registry, self.run_id))

    def test_every_negative_fixture_raises_its_required_flag(self):
        for fixture in gate.NEGATIVE_FIXTURES:
            with self.subTest(fixture=fixture["id"]):
                registry, run_id = gate.fixture_context(fixture)
                issues = gate.run_gate(fixture["input"], registry, run_id)
                self.assertTrue(any(fixture["must_flag"] in issue for issue in issues), issues)

    def test_negative_fixture_runner_is_green(self):
        self.assertEqual([], gate.run_negative_fixtures())

    def test_unregistered_artifact_is_rejected(self):
        issues = gate.run_gate(self.report(), self.registry, self.run_id)
        self.assertTrue(any("unregistered evidence artifact" in issue for issue in issues))

    def test_stale_run_evidence_is_rejected(self):
        old_run = self.run_id
        self.registry.register(old_run, "tests.log", gate.sha256_text("tests passed"), "ok")
        current_run = self.registry.start_run()
        issues = gate.run_gate(self.report(), self.registry, current_run)
        self.assertTrue(any(f"stale evidence: artifact from run {old_run}" in issue
                            for issue in issues))

    def test_failing_evidence_is_rejected(self):
        self.registry.register(self.run_id, "tests.log", gate.sha256_text("tests failed"), "fail")
        issues = gate.run_gate(self.report(content="tests failed", result="fail"),
                               self.registry, self.run_id)
        self.assertTrue(any("evidence cites a failing tool result" in issue for issue in issues))

    def test_mismatched_digest_is_rejected(self):
        self.registry.register(self.run_id, "tests.log", gate.sha256_text("actual"), "ok")
        issues = gate.run_gate(self.report(content="claimed"), self.registry, self.run_id)
        self.assertTrue(any("digest does not match" in issue for issue in issues))

    def test_unknown_status_is_rejected(self):
        report = {"task": "verify", "status": "UNKNOWN", "evidence": []}
        self.assertTrue(any("unknown status" in issue for issue in gate.shape_check(report)))

    def test_empty_task_is_rejected(self):
        report = {"task": " ", "status": "FAIL", "evidence": []}
        self.assertTrue(any("non-empty string" in issue for issue in gate.shape_check(report)))

    def test_evidence_requires_artifact_and_result_keys(self):
        report = {"task": "verify", "status": "FAIL", "evidence": [{"artifact": "x"}]}
        self.assertTrue(any("missing keys" in issue for issue in gate.shape_check(report)))

    def test_evidence_entry_must_be_a_dict(self):
        report = {"task": "verify", "status": "FAIL", "evidence": ["passed"]}
        self.assertTrue(any("must be a dict" in issue for issue in gate.shape_check(report)))

    def test_review_loop_converges_on_current_candidate(self):
        self.registry.register(self.run_id, "tests.log", gate.sha256_text("tests passed"), "ok")
        initial = {"task": "verify-build", "status": "PASS", "evidence": []}
        result = gate.review_loop(initial, lambda _candidate, _issues: self.report(), self.reviewers())
        self.assertTrue(result.can_ship)
        self.assertEqual(self.report(), result.candidate)
        self.assertEqual(2, result.turns)

    def test_review_loop_stall_needs_a_human(self):
        initial = {"task": "verify-build", "status": "PASS", "evidence": []}
        result = gate.review_loop(initial, lambda candidate, _issues: candidate, self.reviewers())
        self.assertFalse(result.can_ship)
        self.assertIn("human", result.verdict)

    def test_review_loop_stops_before_overspend(self):
        self.registry.register(self.run_id, "tests.log", gate.sha256_text("tests passed"), "ok")
        initial = {"task": "verify-build", "status": "PASS", "evidence": []}
        result = gate.review_loop(initial, lambda _candidate, _issues: self.report(),
                                  self.reviewers(), max_spend_usd=0.05, cost_per_turn=0.05)
        self.assertFalse(result.can_ship)
        self.assertIn("spend cap", result.verdict)
        self.assertAlmostEqual(0.05, result.spend_usd)

    def test_post_cap_candidate_is_reverified(self):
        self.registry.register(self.run_id, "tests.log", gate.sha256_text("tests passed"), "ok")
        initial = {"task": "verify-build", "status": "PASS", "evidence": []}
        result = gate.review_loop(initial, lambda _candidate, _issues: self.report(),
                                  self.reviewers(), max_turns=1,
                                  max_spend_usd=0.10, cost_per_turn=0.05)
        self.assertTrue(result.can_ship)
        self.assertIn("verified post-cap", result.verdict)

    def test_turn_cap_preserves_non_shipping_verdict(self):
        initial = {"task": "verify-build", "status": "PASS", "evidence": []}
        result = gate.review_loop(initial, lambda candidate, _issues: candidate,
                                  self.reviewers(), max_turns=1)
        self.assertFalse(result.can_ship)
        self.assertIn("turn cap", result.verdict)

    def test_dispatch_defers_oversized_packet(self):
        self.assertEqual("DEFER", gate.dispatch("x" * 45, budget=10))

    def test_dispatch_accepts_small_packet(self):
        self.assertEqual("DISPATCH", gate.dispatch("small", budget=10))

    def test_runtime_regression_guard_fires(self):
        self.assertIn("runtime regression", gate.check_runtime_regression(2.0, 1.0))

    def test_runtime_regression_guard_stays_quiet(self):
        self.assertIsNone(gate.check_runtime_regression(1.5, 1.0))

    def test_gate_is_read_only(self):
        self.registry.register(self.run_id, "tests.log", gate.sha256_text("tests passed"), "ok")
        report = self.report()
        report_before = copy.deepcopy(report)
        registry_before = self.registry.snapshot()
        gate.run_gate(report, self.registry, self.run_id)
        self.assertEqual(report_before, report)
        self.assertEqual(registry_before, self.registry.snapshot())

    def test_script_exits_zero_and_prints_health_line(self):
        completed = subprocess.run([sys.executable, str(ROOT / "agent_gate_demo.py")],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertTrue(completed.stdout.rstrip().endswith("gate demo healthy"))


if __name__ == "__main__":
    unittest.main()
