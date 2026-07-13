# Roadmap: the bricks

The factory is opened up piece by piece. Each brick is a self-contained, runnable part of the machinery, released when it is untangled enough to stand alone. Releases land here and get announced on [@makray1](https://x.com/makray1).

| # | Brick | What you learn | Status |
|---|-------|----------------|--------|
| 1 | **Verification gate** (`agent_gate_demo.py` + tests + fixtures) | How to reject fabricated agent success: shape vs semantic checks, negative fixtures, registry-backed evidence, stall detection, bounded loops, verify-the-verifier | **Shipped** |
| 2 | **Image-generation system** (App Store screenshots + marketing art) | The input contract, retry logic, and verification checks behind fleet-scale asset generation (hundreds of panels across dozens of locales, vision-judged before they count) | Next |
| 3 | **More of the pipeline** (orchestration patterns, checklist-engine concepts) | How a deterministic orchestrator walks a phase graph, hands agents bounded task packets, and never lets a worker mark its own work complete | Planned |
| 4 | **Product-judgment gates + the deep-quality loop** (rulebook rows as executable standards) | How "good" gets written down as rules agents build against: over-caution gates, copy-voice gates, adaptivity batteries, and the multi-axis convergence loop that drives a built app from working to excellent | Planned |

A brick counts as shipped when it runs standalone from a fresh clone, has its own README section, and its checks pass in CI.

Why not the whole system at once: a copy of my exact setup would not help you. It is too tangled and too specialised to how I work. The bricks are the reusable parts, extracted and made runnable.
