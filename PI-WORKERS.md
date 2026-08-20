# Pi worker adapter

Read this file completely whenever the target pane runs `pi`. The generic commander stages remain authoritative; this file owns only the Pi-specific mechanics.

## Launch

**Probe pane state BEFORE injecting any launch command.** `herdr pane read` the target and classify: a bare shell prompt accepts a launch command; a **live TUI editor consumes it as a prompt** (observed 2026-07-21: a `pi --model … --approve` line landed in a running Pi session, which loaded the commander skill and nearly launched its own child worker — commander-inside-worker recursion). The owner may have relaunched or exited the pane since you last looked; never assume the state you left. If a live TUI holds the pane, either deliver the job to that session (if model/name fit the contract) or retire the seat by tab replacement (HERDR-WORKERS § Resetting a Pi seat) — **never `/exit`** (consumed as a billable prompt), and never the tmux-era double Ctrl+C (does not reach a herdr-hosted Pi; TMUX-ARCHIVE.md keeps the old mechanic).

Start Pi in the assigned cwd and pin the user-approved model and thinking level at launch — **both flags explicit**; `--model provider/id` alone is legal but rides fuzzy matching plus the machine-local `defaultProvider`. The battle-tested form is the double flag:

```bash
herdr agent start <name> --kind pi --pane <pane_id> --timeout 60000 -- \
  --provider openrouter --model <pattern> --thinking <level> --name '<task>' --approve
```

Commissioning a seat on a model never used before? Smoke-test the route first, one shot: `pi --provider openrouter --model <pattern> -p --no-session --no-tools "ping"`.

⚠ **Pi silently clamps unsupported thinking levels** (measured 2026-07-21: `--thinking low` and `:low` on deepseek-v4-pro both came up `• high` in the footer — that model supports only {off, high} — while `--thinking off` and kimi-k3 `low` applied as asked). No error, no notice; you'd be paying the higher tier believing you picked the cheap one. **The footer is the only truth for what was actually applied — but only once the seat has completed one turn**; reading it too early inverts the answer. A fresh seat echoes the level you *requested*, not the level in force: measured 2026-07-26 on `gpt-5.6-sol` (`thinkingLevelMap: {xhigh, max, minimal→low}`), the just-launched pane rendered `• minimal` and only after its first turn rendered `· low`, the value actually applied. When the level you asked for is absent from the provider's `models-store.json` map, cross-check there too.

⚠ **A Pi seat on a Claude model shows NO reasoning at all — build the heartbeat around that, and never read the clamp rule above as "worst case you overpay".** Measured 2026-08-13, same machine and account, model held at `claude-opus-5`: omp stored 12 non-empty thinking blocks up to 1,678 chars, while pi stored thinking blocks whose text length was **0** (signature only). Two stacked silent faults: ① `claude-opus-5` publishes `thinkingLevelMap: {xhigh, max}`, and pi's `defaultThinkingLevel: high` does not clamp UP into it — a one-shot probe returned `usage.reasoning = 0`, thinking simply **off**, not downgraded; `--thinking xhigh` returned `reasoning = 5`. ② Even then the text is empty: pi's catalog entry carries no `compat.forceAdaptiveThinking`, so `anthropic-messages.js` falls to budget mode `{type:"enabled", budget_tokens, display:"summarized"}` against an adaptive-thinking model, and Anthropic answers with signature-only blocks. The footer reports the level, never the display, so both faults are invisible there. Pi on OpenAI is unaffected — it requests `summary: "auto"` and does stream reasoning summaries. ⇒ A seat whose reasoning you need to read goes on an OpenAI model or runs under omp; a pi+Claude seat is judged by tool calls and artifacts only. Probe a new route in one shot before trusting anything:

```bash
pi --provider anthropic --model <id> --thinking <level> --mode json -p --no-session --no-tools \
  "A bat and ball cost \$1.10; the bat costs \$1.00 more than the ball. Price of the ball?" \
  | grep -o '"reasoning":[0-9]*'   # 0 = thinking never ran, whatever the footer says
```

For a read-only critic, narrow tools and pin its only writable artifact outside the repo in the job contract. Wait for the real editor, then verify the footer shows the intended model, thinking level, cwd, branch, and context percentage.

## Context economy — new task_id → replace the tab

Reusing an idle Pi seat for a **new task_id** means **replace the tab and relaunch fresh** (HERDR-WORKERS § Resetting a Pi seat) — unconditionally. Do not read ctx% to decide, and do not `/compact` as pre-job hygiene: compact costs a summarization pass and its residue is re-billed every turn, while a fresh tab is truly zero (the self-contained job file makes rebuild cost ≈ 0; reuse the seat label if the roster should look unchanged). The skip exceptions differ by harness and must not be conflated: Claude Code may skip `/clear` when the new job explicitly builds on live context; Pi never skips for a new task_id — only a same-task steer/revise continuation avoids the replacement.

Before the replacement, the Stage 5b checklist applies: capture the last screen, confirm no un-landed artifacts, no pending un-acked return. `/compact` retains exactly one legitimate use: **mid-task** (in-flight, so a reset is forbidden) with context near the ceiling — persist state to disk first, then compact at a safe checkpoint.

## Deliver a job

Keep the self-contained job in `~/fleet/<concern>/jobs/<job>.md` (durable commander workspace, SKILL.md Stage 2), but send Pi only one literal line that tells it to read that file:

```bash
MSG='Skip any repo Session Init / health sweep / context ritual. Read ~/fleet/<concern>/jobs/<job>.md completely using the read tool, then execute the entire job. The file is the authoritative contract; do not stop after planning.'
herdr agent prompt <pane_id> "$MSG" --wait --until working
```

A Pi seat can auto-load repo instructions before it opens the external job file. Therefore the job file's own init-suppression first line is necessary but not sufficient: repeat the suppression in the literal launch pointer so it is available before Pi can obey a repo-level init ritual. Measured 2026-07-23: two fresh launches loaded root `CLAUDE.md` first; the second ran its log/status and prod health sweep before reading the external contract.

A multiline paste into Pi is not a large editor paste (tmux-era `paste-buffer`, observed 2026-07-18: Pi submitted the first line and queued the rest as hundreds of `Steering:` messages, each fragment becoming a billable turn); herdr's `agent prompt` is single-line by design — keep it that way. The reliable proof is a `read ~/fleet/<concern>/jobs/<job>.md` tool call followed by the contract's first required action.

If fragmentation occurs, first verify the assigned worktree has no new writes. For a commander-created seat with zero work: replace the tab (fresh Pi), re-register the same `task_id` (register is an upsert), and use the one-line delivery above. Repeated Escape attempts lose time — queued steering messages can advance immediately after each abort.

## Steer

Send a short correction via `herdr agent prompt`; put a long correction in another `~/fleet/<concern>/jobs/*.md` file (durable commander workspace, same as the job contract) and send one line telling Pi to read it. In Pi, a prompt while working queues steering for the next tool boundary; reserve follow-up delivery for work that should wait until the current turn fully completes. **Done** = the transcript shows the correction consumed by this task and no fragmented queue appears.

## Heartbeat and context

The Pi footer exposes model, thinking level, context percentage, weekly-work percentage, cwd, and branch. Pair it with the pane transcript, process state, deliverable state, and durable return mailbox.

**Pi's busy/idle shapes are its own — SKILL.md Stage 4's Claude Code regex NEVER matches a Pi pane** (it keys on `… (2m 6s · ↓ 5.4k tokens)`; Pi renders nothing like it), so a mixed fleet watched with the CC shape reads every busy Pi seat as idle and nudges workers mid-turn. Measured 2026-07-21: **busy** = a braille spinner line just above the separator (`⠼ Working...`); **idle** = that line absent, footer showing the cost readout (`↑6.9k ↓335 $0.003 …` — a free per-turn expense receipt). Detection:

```bash
herdr pane read "$pane" --lines 8 | grep -qE '⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏|⠉|⠈|⠐|⠠'
```

The Codex statusline extension shows weekly consumption as `(7d·N%)` — `usedPercent`, **spent, not remaining** (ignore the legacy `wk:N%`, which showed remaining). It self-refreshes; `/reload` is needed only after installing a new extension version. `/status` toggles the extension — it does not query Codex. Never use `/usage` unless the user authorizes a quota reset.

Pi has `/compact`, not Claude Code's `/clear` — an in-flight rescue only, never seat-reuse hygiene (Context economy above). If the task can restart from disk, kill + relaunch fresh instead; either way re-register the same task and send the one-line job/resume pointer.

Footer counters (`↑ ↓ $`) update only at TURN BOUNDARIES — a long single turn shows frozen counters while the spinner keeps spinning. Frozen counters + live spinner = a deep turn in flight, NOT a dead stream; the spinner is the liveness truth (2026-07-22: a commander Escape'd a deep-reasoning seat mid-write off a frozen-counter misread). Interrupt only when the spinner itself is gone or the harness prints a stream error.

Context rollovers resume from disk, never from chat memory.

## 凭据卫生(2026-07-23 事故后新增,写进每张涉 prod/配置的 job)

- **worker 严禁把 .env / 配置文件的值打进输出**:不 `cat .env`、不 `source` prod 配置、不 echo 含 secret 的变量。transcript 即泄漏面——07-23 实锤:sample worker 一次误 source prod .env,一个 DB 密码值落入本地 transcript,触发全站 DB 密码轮换。
- **凭据侦察只走指纹**:要对比"两处密码是否相同",用 `grep PASSWORD <file> | sha256sum | cut -c1-16` 各算指纹对表,值本身永不出现在输出。
- **job 模板层面**:涉 prod .env / secrets 的单,硬约束区加一行「读配置只允许指纹/键名级操作,任何 secret 值出现在你的输出=事故,立即上报」。
