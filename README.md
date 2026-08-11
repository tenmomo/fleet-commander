# fleet-commander

**Field-tested command discipline for coding-agent fleets.** fleet-commander is
an operational skillbook that turns a single human operator into a reliable fleet
commander running multiple AI coding agents across tmux panes, herdr workspaces,
and remote SSH seats. Every rule earned its place by surviving a real incident —
each carries the date it was forged.

Built for Claude Code, Pi, and Codex workers. Tested daily in production fleets
since July 2026.

## Why this exists

Running one coding agent is easy. Running five at once — each on its own branch,
in its own pane, on its own task — is where things break: a paste gets swallowed
by a mode transition, a worker silently edits the wrong checkout, a "done"
notification arrives but the artifact is empty. fleet-commander encodes the
judgment calls that prevent these failures into repeatable checks any mid-tier
model can execute.

**What makes it different:** this is not a theory document. Every guardrail
traces to a dated production incident. When a rule says "never do X (2026-07-18:
...)", that date is when someone did X and paid for it.

## How it works

```mermaid
flowchart LR
    subgraph Commander["Commander (you + this skill)"]
        A[Choose exact pane] --> B[Deliver job contract]
        B --> C[Prove consumption]
        C --> D[Heartbeat from<br/>independent state]
        D --> E[Correct / continue]
        E --> F[Verify handback]
        F --> G[Harvest lessons]
    end

    subgraph Workers["Worker seats"]
        W1[Claude Code<br/>tmux pane]
        W2[Pi<br/>herdr workspace]
        W3[Codex<br/>tmux pane]
    end

    B -.->|job file| W1 & W2 & W3
    W1 & W2 & W3 -.->|publish-task| F
```

The commander loop is one line:

> choose an exact pane → deliver a self-contained job → prove it started →
> heartbeat from independent state → correct/continue safely → verify handback
> and clean up

## Quickstart

### Prerequisites

- A POSIX host with **tmux** (macOS, Linux, or WSL2)
- At least one supported agent: [Claude Code](https://docs.anthropic.com/en/docs/claude-code),
  [Pi](https://pi.ai), or [Codex](https://openai.com/codex)

### Install as a Claude Code skill

```bash
# From the Claude Code CLI
npx skills use tenmomo/fleet-commander
```

Or clone directly:

```bash
git clone https://github.com/tenmomo/fleet-commander.git
# Point your agent's skill loader at this directory
```

### First fleet

1. Load [`SKILL.md`](SKILL.md) into your commander session.
2. Read the worker adapter for your agent before launching it:
   - [`HERDR-WORKERS.md`](HERDR-WORKERS.md) for herdr workspaces
   - [`PI-WORKERS.md`](PI-WORKERS.md) for Pi workers
   - [`CODEX-WORKERS.md`](CODEX-WORKERS.md) for Codex workers
3. Write a self-contained job contract under `~/fleet/<concern>/jobs/`.
4. Register the task with the durable ledger:

   ```bash
   python3 <skill-dir>/scripts/return-channel.py register \
     --task my-task-001 --worker-pane publish:0.0 --reply-to cmdr:0.0 \
     --owned-paths src/feature --result-paths out/REPORT.md
   ```

5. Deliver the contract to the worker pane, prove consumption, and heartbeat.
6. Worker finishes with `publish-task`; verify the artifact, then move the
   ledger through `verified` → `acked`.

## What's in the box

| File | Purpose |
|------|---------|
| [`SKILL.md`](SKILL.md) | Core commander loop — targeting, dispatch, heartbeat, verification, guardrails (249 rules) |
| [`HERDR-WORKERS.md`](HERDR-WORKERS.md) | herdr workspace launch, observation, and teardown |
| [`PI-WORKERS.md`](PI-WORKERS.md) | Pi agent launch, delivery, and heartbeat mechanics |
| [`CODEX-WORKERS.md`](CODEX-WORKERS.md) | Codex commissioning gate, context counters, quota management |
| [`HARVEST.md`](HARVEST.md) | Field-observation capture and promotion workflow |
| [`scripts/return-channel.py`](scripts/return-channel.py) | Durable mailbox and typed task ledger with flock locking |
| [`CHANGELOG.md`](CHANGELOG.md) | Public release history |

## Key concepts

- **Commander vs. Worker** — The commander steers; workers produce artifacts.
  The commander never does the worker's job in its pane.
- **Self-contained contracts** — Every job file carries its full context: cwd,
  owned paths, outputs, constraints, stop conditions, and return address.
- **Artifact-anchored completion** — A task is done when the artifact exists and
  verifies, not when the worker says "done."
- **Durable task ledger** — `return-channel.py` tracks task state with
  append-only events, lease expiry, artifact hashing, and owned-path conflict
  detection.
- **Harvest loop** — Every surprise becomes a dated rule so the next run starts
  better. The skillbook is its own cross-run memory.

## FAQ

**Q: Does this require a specific AI provider?**
No. The skill is provider-agnostic at the commander level. Worker adapters exist
for Claude Code, Pi, and Codex, but any agent that accepts text input in a
terminal pane can be commanded.

**Q: Can I use this without tmux?**
tmux is the primary seat fabric. herdr workspaces are the secondary option.
Remote SSH boxes work as worker targets inside a tmux pane. Native Windows
without WSL is not supported as a commander host.

**Q: How is this different from multi-agent frameworks like CrewAI or AutoGen?**
Those frameworks orchestrate agents programmatically via APIs. fleet-commander
operates at the terminal level — it commands real agent sessions the same way a
human operator would, using `tmux send-keys` and `capture-pane`. This means it
works with any agent that has a CLI, requires no API integration, and the human
operator can inspect and intervene at any point.

**Q: What does "field-tested" mean concretely?**
Every rule in the skillbook carries a date — that's the day the rule was forged
from a real incident. For example, the paste-swallow guard (2026-07-21) exists
because `/clear` silently ate a job contract twice. The naming convention rule
(2026-07-31) exists because a tmux session with a dot in its name became
unreachable.

**Q: Is the return-channel.py script required?**
It's strongly recommended. Without it you lose durable task tracking, artifact
verification, owned-path conflict detection, and the structured handback
protocol. But the commander loop principles work even with manual tracking.

## Release history

See [`CHANGELOG.md`](CHANGELOG.md) for the full history. Current: **v2.1.0**
(2026-08-05).

- **v2.1.0** — Codex seat adapter, herdr close-on-ack, naming convention,
  ctx-probe, five-file book structure.
- **v2.0.0** — Typed durable task ledger with 37 tests, publish-task atomic
  finish, owned-path conflict gate.
- **v1.0.0** — First public edition. Commander loop, herdr and Pi adapters,
  harvest workflow, return-channel helper.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE) — Copyright (c) 2026 TENMOMO LLC.
