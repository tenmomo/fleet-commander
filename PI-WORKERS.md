# Pi worker adapter

Read this file completely whenever the target pane runs `pi`. The generic commander stages remain authoritative; this file owns only the Pi-specific mechanics.

## Launch

**Probe pane state BEFORE injecting any launch command.** `capture-pane` the target and classify: a shell prompt (`user@host dir %`) accepts a launch command; a **live TUI editor consumes it as a prompt** (observed 2026-07-21: a `pi --model … --approve` line landed in a running Pi session, which loaded the commander skill and nearly launched its own child worker — commander-inside-worker recursion). The owner may have relaunched or exited the pane since you last looked; never assume the state you left. If a live TUI holds the pane, either deliver the job to that session (if model/name fit the contract) or exit it cleanly first — for Pi that is double Ctrl+C, **never `/exit`** (consumed as a billable prompt).

Start Pi in the assigned cwd and pin the user-approved model and thinking level at launch — **both flags explicit**; `--model provider/id` alone is legal but rides fuzzy matching plus the machine-local `defaultProvider`. The battle-tested form is the double flag:

```bash
tmux new-session -d -s <concern> -c <worktree> \
  "exec pi --provider openrouter --model <pattern> --thinking <level> --name '<task>' --approve"
```

Commissioning a seat on a model never used before? Smoke-test the route first, one shot: `pi --provider openrouter --model <pattern> -p --no-session --no-tools "ping"`.

⚠ **Pi silently clamps unsupported thinking levels** (measured 2026-07-21: `--thinking low` and `:low` on deepseek-v4-pro both came up `• high` in the footer — that model supports only {off, high} — while `--thinking off` and kimi-k3 `low` applied as asked). No error, no notice; you'd be paying the higher tier believing you picked the cheap one. **The footer is the only truth for what was actually applied** — footer verification is mandatory, not ceremonial.

For a read-only critic, narrow tools and pin its only writable artifact outside the repo in the job contract. Wait for the real editor, then verify the footer shows the intended model, thinking level, cwd, branch, and context percentage.

## Context economy — new task_id → kill + fresh

Reusing an idle Pi seat for a **new task_id** means **kill the session and relaunch fresh** — unconditionally. Do not read ctx% to decide, and do not `/compact` as pre-job hygiene: compact costs a summarization pass and its residue is re-billed every turn, while kill+fresh is truly zero (the self-contained job file makes rebuild cost ≈ 0; recreate the session under the same name if the roster should look unchanged). The skip exceptions differ by harness and must not be conflated: Claude Code may skip `/clear` when the new job explicitly builds on live context; Pi never skips for a new task_id — only a same-task steer/revise continuation (the normal return-channel revise loop) avoids the kill.

Before the kill, the Stage 5b checklist applies: capture the last screen, confirm no un-landed artifacts, no pending un-acked return. `/compact` retains exactly one legitimate use: **mid-task** (in-flight, so killing is forbidden) with context near the ceiling — persist state to disk first, then compact at a safe checkpoint.

## Deliver a job

Keep the self-contained job in `/tmp/commander/<job>.md`, but send Pi only one literal line that tells it to read that file:

```bash
MSG='Read /tmp/commander/<job>.md completely using the read tool, then execute the entire job. The file is the authoritative contract; do not stop after planning.'
tmux send-keys -t <pane> -l "$MSG"
tmux send-keys -t <pane> C-m
```

A multiline `tmux paste-buffer` into Pi is not a large editor paste (observed 2026-07-18: Pi submitted the first line and queued the rest as hundreds of `Steering:` messages, each fragment becoming a turn). The reliable proof is a `read /tmp/commander/<job>.md` tool call followed by the contract's first required action.

If fragmentation occurs, first verify the assigned worktree has no new writes. For a commander-created session with zero work: kill only that session, relaunch Pi, re-register the same `task_id` (register is an upsert), and use the one-line delivery above. Repeated Escape attempts lose time — queued steering messages can advance immediately after each abort.

## Steer

Send a short correction as one literal line plus a separate Enter; put a long correction in another `/tmp/commander/*.md` file and send one line telling Pi to read it. In Pi, Enter while working queues steering for the next tool boundary; reserve follow-up delivery for work that should wait until the current turn fully completes. **Done** = the transcript shows the correction consumed by this task and no fragmented queue appears.

## Heartbeat and context

The Pi footer exposes model, thinking level, context percentage, weekly-work percentage, cwd, and branch. Pair it with the pane transcript, process state, deliverable state, and durable return mailbox.

**Pi's busy/idle shapes are its own — SKILL.md Stage 4's Claude Code regex NEVER matches a Pi pane** (it keys on `… (2m 6s · ↓ 5.4k tokens)`; Pi renders nothing like it), so a mixed fleet watched with the CC shape reads every busy Pi seat as idle and nudges workers mid-turn. Measured 2026-07-21: **busy** = a braille spinner line just above the separator (`⠼ Working...`); **idle** = that line absent, footer showing the cost readout (`↑6.9k ↓335 $0.003 …` — a free per-turn expense receipt). Detection:

```bash
tmux capture-pane -p -t "$pane" -S -8 | grep -qE '⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏|⠉|⠈|⠐|⠠'
```

The Codex statusline extension shows weekly consumption as `(7d·N%)` — `usedPercent`, **spent, not remaining** (ignore the legacy `wk:N%`, which showed remaining). It self-refreshes; `/reload` is needed only after installing a new extension version. `/status` toggles the extension — it does not query Codex. Never use `/usage` unless the user authorizes a quota reset.

Pi has `/compact`, not Claude Code's `/clear` — an in-flight rescue only, never seat-reuse hygiene (Context economy above). If the task can restart from disk, kill + relaunch fresh instead; either way re-register the same task and send the one-line job/resume pointer.

Footer counters (`↑ ↓ $`) update only at TURN BOUNDARIES — a long single turn shows frozen counters while the spinner keeps spinning. Frozen counters + live spinner = a deep turn in flight, NOT a dead stream; the spinner is the liveness truth (2026-07-22: a commander Escape'd a deep-reasoning seat mid-write off a frozen-counter misread). Interrupt only when the spinner itself is gone or the harness prints a stream error.

A tmux `extended-keys is off` warning affects modified keys such as Shift+Enter; the commander's plain `C-m` submission still works. Configure tmux CSI-u support before relying on modified Enter bindings. Context rollovers resume from disk, never from chat memory.
