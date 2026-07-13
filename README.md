# app-factory

The machinery behind an app factory: a system that turns a one-sentence idea
into a shipped iOS app (discovery, design, build, App Store screenshots,
submission), and the reliability engineering that keeps a ~30-step
nondeterministic pipeline honest at scale. More than 20 apps have gone through
it, several live on the App Store.

I am opening this up one brick at a time. This repo is where the bricks land.

## What is here now

- **`agent_gate_demo.py`** — the verification gate, ~250 lines, standard library
  only, runs in under a second. Seven reliability patterns as working code:
  schema-vs-semantic checks, negative fixtures (it rejects a fabricated `PASS`
  out of the box), stall detection on issue identity, evidence-grounded
  reporting, a token-budget guard, and a read-only self-test.

  ```bash
  python3 agent_gate_demo.py
  ```

  Fork it, replace `shape_check` / `semantic_check` with your artifact's real
  checks, and grow the fixture list as each check earns a way to fail.

## Coming over the next weeks

- the image-generation system (App Store screenshots + marketing art)
- more of the pipeline after that

## Why not a full clone?

A copy of my exact system would not help you: it is too tangled and too
specialised to how I work. This is the main bricks and the method, not a
turnkey product. Rebuild your own from these.

## Replicate it, then push back

If you build something with this, tell me, and tell me where I am wrong.
Issues and discussion welcome.

Full write-up: *Building agents you can trust* (on X).
Built by [Kamyar Taher](https://x.com/makray1) / Clashware.
