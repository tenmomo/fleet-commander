# Changelog

All notable changes to this project are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## [3.1.3] - 2026-09-02

### Fixed

- Generalized remaining host-specific details in teaching examples (a
  credential backup filename, internal table / process / session names, a
  concern path in a footer capture); filled the author field.

## [3.1.2] - 2026-09-02

### Fixed

- Removed two more leftover account labels from HERDR-WORKERS and
  CODEX-WORKERS footer examples (same family as 3.1.1).

## [3.1.1] - 2026-09-02

### Fixed

- Rewrote CODEX-WORKERS "Weekly quota": the local Codex CLI and Pi are two
  independent budgets, not one shared pool (owner correction 2026-08-24). The
  3.1.0 SKILL.md worker-harness default already pointed at this section but
  the section itself still carried the superseded one-pool claim.
- Removed a leftover account label from footer examples.

## [3.1.0] - 2026-09-02

Based on private field build 5.4.0.

### Added

- Added the provider-route gate: subscription-authenticated workers run only on
  their supported harness; a route that lists models and reports usage is not
  proof it can generate. Canary every unproven harness×provider×auth route with
  one no-tool generation before dispatch.
- Added the worker-harness default (herdr + Pi) and the rule that another
  harness is picked only when the owner explicitly wants that route's quota
  spent.
- Added "Pi as commander seat" (PI-WORKERS): Pi has no `/goal`, does not resume
  itself after auto-compact; a shell guard loop treats idle/blocked/done all as
  stalls, never pushes during `Compacting context`, and stops on a line-anchored
  `QUEUE-EMPTY` marker.
- Added the third face of the seat-commissioning gate (HERDR-WORKERS): the model
  name can be right while the context window is wrong — read the footer
  denominator, and rescue a working seat with a queued `/model …[1m]` switch.
- Added the fourth face: a herdr server started from inside a Claude Code
  session passes `CLAUDE_CODE_CHILD_SESSION` to every pane and worker
  transcripts silently stop saving; clear it with `--env` at tab creation.
- Added the stale-constraint rule for multi-round revision contracts: a red line
  that was correct in v1 can block the correct action in v2; re-read every
  constraint each round and acknowledge expiry explicitly.
- Added the producer-side interface-file rule: close (or fork) before reading
  what you wrote, and assert record counts against the source.
- Added the bash 3.2 sentinel trap on macOS (`declare -A` silently collapses
  keys) and the decoy-task known-positive that catches it.
- Added the PR-run anchoring rule: `gh run list --commit` sees only push runs;
  wait on PR CI with `--branch <head>` + `headSha` or `gh pr checks --watch`.
- Added the Remote Control dialog rule: re-read the pane before answering a
  `waiting` seat — the owner may already have answered from the worker session.

### Changed

- Rewrote the reasoning-visibility rule: no supported harness×provider route
  exposes a dependable reasoning channel; watch tool calls, deliverables, and
  ledger state instead.
- Clarified that a typed-lane `acked` state is terminal: hold at `verified`
  during revise loops, and a register upsert needs a same-batch `dispatched`.

## [3.0.0] - 2026-08-20

Based on private field build 5.0.0.

### Added

- Added `SLASH-COMMANDS.md`, a four-harness slash command table covering Claude
  Code (103 commands), Pi (22), Codex (45), and omp (61), plus a cross-harness
  comparison matrix and herdr CLI verb reference.
- Added `TMUX-ARCHIVE.md`, archiving the tmux fabric mechanics for legacy seats.
- Added `scripts/usage.sh`, a headless quota reader that pulls live usage from
  the Claude Code OAuth API without injecting `/usage` into a seat.
- Added judge-seat wave doctrine (§6b): eight rules for writer×N + judge×1 batch
  waves — advisory-first process claims, SHA-pinned baselines, proxy execution
  with attribution, instrument-chain provenance, and batch-remainder broadcast.
- Added mutation-proof pin tests for the return-channel ledger.

### Changed

- Made herdr the sole standing fabric; every seat — commander and worker, any
  harness — runs in a herdr workspace. tmux mechanics are archived to
  `TMUX-ARCHIVE.md` and supported only when the owner explicitly names a tmux
  seat.
- Made the return-channel notify wire fabric-detected: herdr pane ids (`wX:pY`)
  are woken over the herdr socket API; everything else takes the legacy tmux
  wire.
- Added verification hardening: self-run hard criteria (your standards are your
  blind spot), independent checker must be at least as strong as the checked
  item, pipeline exit-code laundering guard, "keep current state" anchored to
  observed pre-change snapshots, interface-file format checks before batch feed,
  and regex banned for structured-output counting.
- Grew the book to seven files plus two new scripts.

## [2.1.0] - 2026-08-05

### Added

- Added `CODEX-WORKERS.md`, a Codex seat adapter: model-id commissioning gate,
  hook-trust false idle, the two footer context counters and the true window
  size, the weekly pool shared with Pi, and the minimum seat kit.
- Added the concern-string naming convention and the tmux `.`-in-name trap.
- Added `ctx-probe`, a piggybacked method for measuring context degradation.

### Changed

- Made herdr workspace close part of the final ack, not optional cleanup.
- Kept the parent-wake leg on ordinary jobs; `--no-notify` now requires a
  commander-installed ledger joiner.
- Added the third hypothesis face: numeric claims computable but only inferred.
- Simplified Pi identity guidance to the current single-profile default.
- Grew the book to five files; the return-channel helper itself is unchanged.

## [2.0.0] - 2026-07-30

### Added

- Added a typed durable task ledger with `transition`, `heartbeat`,
  `publish-task`, `status`, and `list` verbs.
- Added leases, lost-task detection, append-only events, artifact hashing, and
  exact registered-result-set enforcement.
- Added active `owned_paths` overlap rejection and mailbox-wide `flock` locking.
- Added concurrency, lock-liveness, atomicity, migration, and compatibility tests.

### Changed

- Made artifact placement the completion signal; return notifications are hints.
- Made `publish-task` the only route to `published`, atomically coupling verified
  result presence, hashes, ledger state, and parent wake-up.
- Expanded tmux, herdr, Pi, context-handover, watcher, and verification guidance.
- Preserved the v1 four-verb CLI and lazy migration of legacy envelopes.

## [1.0.0] - 2026-07-23

### Added

- Published the first public edition under the MIT license.
- Included the commander loop, herdr and Pi adapters, harvest workflow, and
  return-channel helper.
