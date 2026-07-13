"""The verification loop, with its discipline (copy-pasteable skeleton).

The four rules, in code shape:
  1. objective tests run BEFORE the judge (never spend a judging call on
     something that does not validate)
  2. the loop is bounded TWICE, by turns and by spend (max_turns and
     max_budget_usd exist natively in the Claude Agent SDK; use them)
  3. feedback is always the concrete failure, not "try again"
  4. the last turn never returns an untested draft

generate/run_objective_tests/judge/spent/escalate are yours to implement.
A registry-backed, runnable version of the gate side lives in agent_gate_demo.py.
"""


def solve(task, max_turns=4, max_budget_usd=2.0):
    draft = generate(task)
    for _ in range(max_turns):
        if spent() >= max_budget_usd:        # spend bounds BOTH paths, checked first
            break
        tests = run_objective_tests(draft)   # hard correctness first: tests, schema
        if not tests.all_pass:
            draft = generate(task, feedback=tests.failures)
            continue
        review = judge(task, draft)          # LLM judge only for quality, never correctness
        if review.accept:
            break
        draft = generate(task, feedback=review.feedback)
    # last turn: never return an untested draft
    return draft if run_objective_tests(draft).all_pass else escalate(draft)
