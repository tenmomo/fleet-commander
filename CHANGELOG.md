# Changelog

All notable changes to this project are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

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
