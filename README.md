# app-factory

This is where I open up the machinery behind my app factory, brick by brick.

The factory turns a one-sentence app idea into a shipped iOS app: discovery, pricing, design, build, App Store screenshots, submission. More than 20 apps have gone through it, a dozen live on the App Store ([Clashware developer page](https://apps.apple.com/us/developer/clashware-s%C3%A0rl/id1837470365)). The full story, and the reliability engineering that keeps a ~30-step nondeterministic pipeline honest, is in [the write-up on X](https://x.com/makray1/status/2076621937652998456).

The heart of the factory is a checklist that couples product judgment to proof: rules that define what a good app is, and gates that make sure no agent can claim them without evidence. Judgment without proof is optional prose; proof without judgment is a correctly verified mediocre app.

A copy of my exact system would not help you: it is too tangled and too specialised to how I work. The bricks are the reusable parts, extracted and made runnable. Roadmap: [ROADMAP.md](ROADMAP.md).

## Brick 1: the verification gate

A distilled, runnable version of the gate that decides whether agent output can be trusted. One file, standard library only, no dependencies, Python 3.10+.

```bash
python3 agent_gate_demo.py
```

Expected output (runtime line varies):

```text
fabricated PASS  -> ['semantic: PASS without evidence artifacts (fabricated success?)']
grounded PASS    -> accepted
failing evidence -> ['semantic: evidence cites a failing tool result: failed.log']
negative fixtures-> all 17 fail as required
token dispatch   -> oversized=DEFER small=DISPATCH
stalling loop    -> stalled on ['ev:PASS without evidence artifacts (fabricated success?)']; needs a human
converging loop  -> green after 2 turn(s)
self-test        -> verifier verifies itself
runtime          -> 1ms (budget 2000ms)
gate demo healthy
```

Exit code 0 only when everything above holds. Tests: `python3 -m unittest discover -s tests`.

## The seven tricks, mapped to code

| # | Trick | Where in the code |
|---|-------|-------------------|
| 1 | Schema validation is not verification | `shape_check` (shape) vs `semantic_check` (truth): a PASS needs registry-backed evidence |
| 2 | Prove the verifier can fail | `NEGATIVE_FIXTURES` (17 of them) + `run_negative_fixtures`; every check has an input it must reject |
| 3 | Consensus with a defined convergence rule | `consensus` + the `lens_*` reviewers: distinct lenses, pooled issues, any open P0/P1 keeps the gate red. Judge protocol: [snippets/judge_prompt.md](snippets/judge_prompt.md) |
| 4 | Stall detection + bounded loops | `review_loop` returns a `GateResult`; bounded by turns AND spend, stalls detected on issue identity, the last turn never returns an untested draft |
| 5 | Ground every claim in a tool result | `RunRegistry`: evidence must name an artifact registered THIS run, with a matching sha256 digest and status "ok". Fake, stale, and failing evidence are all rejected |
| 6 | Verify the verifier | `self_test` (read-only guard, fixture replay) + `check_runtime_regression` |
| 7 | Token budget as a correctness concern | `approx_tokens` + `dispatch`: oversized packets are deferred, never sent |

The loop skeleton from the article, copy-pasteable: [snippets/loop.py](snippets/loop.py).

## Start here: replicate a mini factory

Do not start with twenty apps. One chain, one gate:

1. **Chain three bounded steps end to end** (idea, spec, build): an ordinary script, one bounded agent call per step. State is files in a per-run directory. Each step ends by writing a report shaped like `{task, status, evidence: [{artifact, result}]}` (see [examples/](examples/)); the next step starts by reading it.
2. **Put the gate between every step.** Fork `agent_gate_demo.py`, swap `shape_check`/`semantic_check`'s placeholders for your artifact's real checks ("the project builds", "the diff touches only files named in the spec").
3. **Add one negative fixture per check.** Feed the gate one fabricated success; if it does not refuse, that is your first P0.
4. **Bound every loop** by turns and by spend (`review_loop` shows the shape). An unbounded loop does not error out; it quietly runs up a bill.
5. **Split judge from tests.** A model decides preference and quality; deterministic checks decide pass/fail. Protocol in [snippets/judge_prompt.md](snippets/judge_prompt.md).
6. **Write a ~20-case eval set** from real past inputs and run it on every prompt change: [evals/eval-set.template.json](evals/eval-set.template.json).

Wiring the gate to a real agent, producer side: end your step prompt with "write report.json as `{task, status, evidence: [{artifact, result}]}`; every artifact you name must exist on disk". Register each real tool result in the `RunRegistry` as it happens; the gate does the rest.

## Symptom to fix map

| Symptom you observe | Structural cause | Fix (trick) |
|---|---|---|
| Gate is green but the output is wrong | Validation checks shape, not truth | Adversarial fake-PASS cases (1) |
| You cannot say whether a check works | It has never been seen failing | One negative fixture per check (2) |
| Multi-agent review finds the same issue N times | Identical reviewers, redundant lens | Distinct lens per reviewer (3) |
| Loop keeps "working on it", nothing changes | Progress measured on model optimism | Stall detection on issue identity (4) |
| Agent reports done, artifact missing or stale | Success reported from intent | Registry-backed evidence, current run only (5) |
| Gate gets slower or flakier over months | Nobody verifies the verifier | Self-tests + runtime regression guard (6) |
| Quality drops after scaling inputs, no error | Prompt budget silently exceeded | Input-fits-budget as a validation (7) |

## Layout

```
agent_gate_demo.py     the gate, one file, stdlib only
tests/                 23 unit tests (unittest, run in CI)
examples/              report examples: valid, fake-pass, stale-evidence, failing-evidence
evals/                 eval-set template ({input, expected, pass_criterion})
snippets/              copy-pasteable code from the article (loop, judge protocol)
ROADMAP.md             the bricks: shipped, next, planned
```

## License and contributing

MIT ([LICENSE](LICENSE)). Issues and PRs welcome; the bar for a new check is that it comes with a negative fixture ([CONTRIBUTING.md](CONTRIBUTING.md)).

If you build something with this, tell me. And tell me where I am wrong: I would rather have the argument than the applause.

Built by [Kamyar Taher](https://x.com/makray1) / Clashware.
