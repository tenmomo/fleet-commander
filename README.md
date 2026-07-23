# fleet-commander

`fleet-commander` is a field-tested operating manual for directing multiple coding-agent workers across tmux panes, herdr workspaces, and remote SSH seats. It exists to make delegation reliable: exact targeting, self-contained contracts, independent heartbeats, safe correction, verified handback, and continuous harvesting of operational lessons.

**The core value proposition: this skill encodes command judgment as discipline, so a mid-tier model can run a fleet reliably.** Most orchestration failures are not intelligence failures — they are skipped verifications, trusted self-reports, mis-anchored waits, and swallowed keystrokes. Every rule in this skillbook exists because one of those failures happened in live operation and was distilled into a check the commander runs mechanically instead of judging in the moment. In live side-by-side use, a mid-tier model running this skill matched a frontier model's command quality on identical fleet tasks — the discipline, not the model, carried the loop.

This matters because frontier capacity is the scarce resource on every plan: subscription tiers cap frontier-model usage per week, and API pricing makes it expensive to burn on orchestration overhead. When your frontier quota runs dry mid-week, a commander seat running this skill keeps fleet quality flat on the mid-tier model instead of degrading with it — you spend the frontier budget on the work that actually needs it, and the command loop stays cheap. That gap is structural, not temporary: running the strongest model will always cost more, so encoding command judgment into discipline is value that compounds rather than expires.

## Quickstart

Prerequisites: a POSIX host with tmux (macOS, Linux, or WSL2), plus at least one supported agent harness.

1. Install this directory as a skill and read `SKILL.md` completely.
2. Inventory the runtime topology and choose an exact `session:window.pane` or herdr pane id.
3. Put a self-contained job contract outside the worker's repository, for example `/tmp/commander/job.md`.
4. Register the return path:

   ```bash
   python3 <skill-dir>/scripts/return-channel.py register \
     --task example-001 --worker-pane publish:0.0 --reply-to mastermind:0.0
   ```

5. Launch the worker using the matching adapter, deliver the contract once, and prove it was consumed.
6. Heartbeat from transcript, process/session state, deliverables, and the durable return mailbox.
7. Verify the real artifact before acknowledging the return.

For Claude Code, use one unique named tmux buffer per large dispatch. For Pi and herdr, send a one-line pointer to the external job file. Read the relevant adapter before launching either harness.

## File map

- `SKILL.md` — the complete commander loop, return contract, recovery, remote-worker guidance, and guardrails.
- `HERDR-WORKERS.md` — herdr launch, delivery, observation, Windows, and teardown mechanics.
- `PI-WORKERS.md` — Pi launch, context, delivery, steering, and heartbeat mechanics.
- `HARVEST.md` — the field-observation capture and promotion workflow.
- `scripts/return-channel.py` — durable Worker → commander mailbox and tmux notification helper.
- `CHANGELOG.md` — public release history.
- `LICENSE` — MIT license.

## Origin and versioning

This project **originated as the 4th generation of a private battle-tested skillbook**. Public versioning starts independently at `v1.0.0`; the initial mapping is **v1.0.0 ← internal 4.0.0**. The public distribution is a single English-language version with no private repository history.

## License

MIT. See `LICENSE`.
