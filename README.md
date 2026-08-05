# fleet-commander

`fleet-commander` is a field-tested operating manual for directing coding-agent
workers across tmux panes, herdr workspaces, and remote SSH seats. It turns
orchestration judgment into repeatable checks: exact targeting, self-contained
contracts, independent heartbeats, safe correction, verified handback, and
continuous harvesting.

## What v2.1 adds

- **A Codex seat adapter** — [`CODEX-WORKERS.md`](CODEX-WORKERS.md) covers the
  commissioning gate (an unsupported model id fails as an HTTP 400 launch that
  reads as an idle worker), hook-trust false idle, the two footer context
  counters and the real window size, the weekly pool Codex shares with Pi, why
  fleet seats never use automatic task delegation, and the minimum seat kit.
- **herdr lifecycle** — closing a workspace is part of the final ack, not
  optional cleanup; prompt-cache TTL is not a reason to keep a finished seat.
- **Naming convention** — one concern string keys the tmux session, the fleet
  directory, and `SEAT.md`; tmux session names must not contain `.`.
- **ctx-probe** — a piggybacked three-question control probe that measures at
  what context occupancy a seat starts forgetting its own identity.
- **Doctrine** — the third face of the hypothesis family (numeric claims that
  could have been computed and were not), and keeping the parent-wake leg on
  ordinary jobs rather than defaulting to `--no-notify`.
- Pi identity guidance simplified to the current single-profile default.

The skill is now a five-file book: [`SKILL.md`](SKILL.md) plus four companions
that must be read completely before their first matching command.

## Quickstart

Prerequisites: a POSIX host with tmux (macOS, Linux, or WSL2), plus at least one
supported agent harness.

1. Install this directory as a skill and read [`SKILL.md`](SKILL.md) completely.
2. Read the matching worker adapter before launching Pi, herdr, or Codex.
3. Put the self-contained job contract under `~/fleet/<concern>/jobs/`.
4. Register ownership and expected results:

   ```bash
   python3 <skill-dir>/scripts/return-channel.py register \
     --task example-001 --worker-pane publish:0.0 --reply-to mastermind:0.0 \
     --owned-paths src/example --result-paths out/REPORT.md
   ```

5. Deliver the contract once, prove it was consumed, and heartbeat from
   transcript, process/session state, artifacts, and ledger state.
6. Have the worker finish with `publish-task`; verify the artifact before moving
   the ledger through `verified` to `acked`.

Run `python3 scripts/return-channel.py --help` for the complete state machine,
enums, and CLI. The helper keeps the v1 `register`, `return`, `pending`, and
`ack` interface alongside the typed ledger verbs.

## File map

- [`SKILL.md`](SKILL.md) — commander loop, typed lifecycle, recovery, and guardrails.
- [`HERDR-WORKERS.md`](HERDR-WORKERS.md) — herdr launch, observation, and teardown.
- [`PI-WORKERS.md`](PI-WORKERS.md) — Pi launch, delivery, and heartbeat mechanics.
- [`CODEX-WORKERS.md`](CODEX-WORKERS.md) — Codex commissioning, launch, context, and quota.
- [`HARVEST.md`](HARVEST.md) — field-observation capture and promotion workflow.
- [`scripts/return-channel.py`](scripts/return-channel.py) — durable mailbox and ledger.
- [`scripts/tests/test_return_channel.py`](scripts/tests/test_return_channel.py) — tests.
- [`CHANGELOG.md`](CHANGELOG.md) — public release history.
- [`LICENSE`](LICENSE) — MIT license.

## License

MIT. See [`LICENSE`](LICENSE).
