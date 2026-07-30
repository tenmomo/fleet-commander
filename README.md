# fleet-commander

`fleet-commander` is a field-tested operating manual for directing coding-agent
workers across tmux panes, herdr workspaces, and remote SSH seats. It turns
orchestration judgment into repeatable checks: exact targeting, self-contained
contracts, independent heartbeats, safe correction, verified handback, and
continuous harvesting.

## What v2 adds

The typed durable task ledger extends the original four handback commands with
five control-plane verbs:

- `transition` — guarded typed state changes with monotonic sequence checks;
- `heartbeat` — renewable worker leases and query-side lost-task detection;
- `publish-task` — verify, hash, commit, and notify as one finish act;
- `status` — inspect one task or the complete ledger as JSON;
- `list` — filter task joins by state or parent.

A mailbox-wide `flock` serializes state mutations. `register --owned-paths`
rejects overlapping active writers, including ancestor/descendant overlaps.
Registered result sets are pinned, and `publish-task` has zero side effects when
any required path is missing. The helper remains compatible with the v1
`register`, `return`, `pending`, and `ack` interface.

## Quickstart

Prerequisites: a POSIX host with tmux (macOS, Linux, or WSL2), plus at least one
supported agent harness.

1. Install this directory as a skill and read [`SKILL.md`](SKILL.md) completely.
2. Read the matching worker adapter before launching Pi or herdr.
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
enums, and CLI.

## File map

- [`SKILL.md`](SKILL.md) — commander loop, typed lifecycle, recovery, and guardrails.
- [`HERDR-WORKERS.md`](HERDR-WORKERS.md) — herdr launch, observation, and teardown.
- [`PI-WORKERS.md`](PI-WORKERS.md) — Pi launch, delivery, and heartbeat mechanics.
- [`HARVEST.md`](HARVEST.md) — field-observation capture and promotion workflow.
- [`scripts/return-channel.py`](scripts/return-channel.py) — durable mailbox and ledger.
- [`scripts/tests/test_return_channel.py`](scripts/tests/test_return_channel.py) — tests.
- [`CHANGELOG.md`](CHANGELOG.md) — public release history.
- [`LICENSE`](LICENSE) — MIT license.

## License

MIT. See [`LICENSE`](LICENSE).
