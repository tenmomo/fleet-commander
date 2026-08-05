# Changelog

All notable changes to this project are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

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
