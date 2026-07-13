# Pairwise LLM-judge protocol (copy-pasteable)

The judge prompt, verbatim:

```text
You are comparing two candidate answers to the same task.
Task: {task}
Answer A: {a}   Answer B: {b}
1. State which answer is better and why, in two sentences.
2. Verdict: A, B, or TIE.
```

The protocol around it (the prompt alone is not the trick):

1. Run it **twice**, swapping which candidate is labelled A.
2. Only count a win if the same answer wins in **both orders**; otherwise record a tie. The extra ties expose order-sensitive judgments instead of turning them into false wins.
3. Verbosity bias: tell the judge to ignore length and prefer the shorter answer on a tie.
4. Self-favouring bias: never let a model cast the deciding vote on output produced by the same model or model family. Use a judge from a different family than the generator.
5. Scope: an LLM judge decides **preference and quality only**. Hard correctness belongs to deterministic checks and fixtures (see `agent_gate_demo.py`). Never let a preference score stand in for a passing test.

Basis: in Zheng et al.'s MT-Bench pairwise experiment (arxiv.org/abs/2306.05685), GPT-4 matched human preference picks about 85% of the time; two human annotators agreed 81%.
