# Codex worker adapter

Read this file completely whenever the target pane runs `codex`. The generic commander stages remain authoritative; this file owns only Codex-specific mechanics.

## Commissioning gate

**Pin a ChatGPT-supported model explicitly.** On 2026-07-31 a herdr Codex seat launched with `codex-2025-07-15`; the ChatGPT-authenticated Codex route returned HTTP 400 immediately, produced no artifact, and left the task merely `registered` while the commander still described it as working. That provider id is not a valid fleet default. For the current ChatGPT-authenticated route use one of:

```text
gpt-5.6-sol
gpt-5.6-terra
gpt-5.6-luna
```

Do not infer subscription support from a model id appearing in another provider or an old job file. Smoke-check an unfamiliar route before dispatch, and treat any startup 400 as a failed launch requiring a supported-model relaunch—not as an idle worker.

Pin reasoning effort too. On the current model manifest, `gpt-5.6-sol` and `terra` describe `ultra` as automatic task delegation. That creates harness-native subagents with no fleet seat, heartbeat, or return contract, so fleet workers use `high`, `xhigh`, or `max`, never `ultra`; the generic real-seat rule remains authoritative.

The minimum Codex fleet equipment is:

1. `fleet-commander` resolvable on the Codex skills path — `~/.agents/skills/fleet-commander/SKILL.md`, which may be a symlink to the canonical `~/.claude/skills/fleet-commander/`;
2. every MCP server the fleet's jobs depend on (for example a browser-automation MCP) configured and enabled (`codex mcp list`).

Configuration presence is not readiness: inside the new seat, confirm the skill is discoverable and the MCP tools can be discovered before assigning work that depends on them. Existing Codex sessions do not hot-reload changed skill text; start a new chat/session or explicitly reread the companion after a skill update.

Before launch, record `codex --version`, `codex login status`, and `herdr integration status` when herdr is the fabric. The field-tested baseline on 2026-07-31 is Codex CLI 0.146.0, `Logged in using ChatGPT`, and herdr's Codex integration current.

## Launch

Probe the exact pane before typing anything. A shell prompt accepts a launch command; a live Codex composer consumes that command as a user prompt. Reuse a live seat only when its task identity and model match the contract.

For a tmux worker, pin model, effort, and permission posture at launch:

```bash
tmux new-session -d -s <concern> -c <worktree> \
  "exec codex -m gpt-5.6-sol -c 'model_reasoning_effort=\"high\"' \
  --dangerously-bypass-approvals-and-sandbox \
  --dangerously-bypass-hook-trust"
```

For a herdr worker, install the integration once, create the pane under the user-chosen workspace, then pass the real Codex flags after `--`:

```bash
herdr integration install codex
herdr agent start <lowercase-name> --kind codex --pane <pane_id> --timeout 60000 -- \
  -m gpt-5.6-sol -c 'model_reasoning_effort="high"' \
  --dangerously-bypass-approvals-and-sandbox \
  --dangerously-bypass-hook-trust
```

`herdr agent start --kind codex` launches the canonical `codex` executable directly; shell aliases such as `yolo-codex` do not expand because arguments after `--` do not pass through a shell. Expand the alias into its full flags. `--full-auto` is not valid in Codex 0.145/0.146.

The bypass posture is for unattended, user-designated fleet seats. If the user chooses the constrained posture instead, use `-s workspace-write -a never` and add every required external writable root with `--add-dir`—especially the durable `~/fleet/<concern>/` output directory. `-a never` suppresses approval prompts; it does not grant filesystem access, so missing roots fail rather than ask.

### Hook-trust false idle

The first enabled-hook launch can stop at a trust dialog while herdr reports `idle`. Prefer `--dangerously-bypass-hook-trust` only when the hook sources were already vetted. Otherwise inspect the pane, send literal `t` to trust all, and wait for the real composer:

```bash
herdr pane read <pane_id> --lines 40 --source visible --format text
herdr agent send-keys <pane_id> t
# tmux fabric: tmux send-keys -t <pane> t
```

Trust persists for the hook hash, but a changed hook can ask again. The dialog may consume the queued job, so after clearing it always deliver the pointer again. Launch is complete only when the composer is visible and the footer confirms the requested model + reasoning, permission mode, Codex version, context window, cwd, and branch.

## Deliver and prove consumption

Keep the self-contained contract in `~/fleet/<concern>/jobs/<job>.md` and send Codex one literal pointer, not the whole long job body:

```bash
MSG='Skip any repo Session Init / health sweep / context ritual. Read ~/fleet/<concern>/jobs/<job>.md completely, then execute the entire job. The file is the authoritative contract; do not stop after planning.'
tmux send-keys -t <pane> -l "$MSG"
tmux send-keys -t <pane> C-m
```

On herdr, use `herdr agent prompt <pane_id> "$MSG" --wait --until working`; follow `HERDR-WORKERS.md` if Enter stalls. Submission proof is not text visible in the composer. Require Codex's busy marker (`• Working (... • esc to interrupt)`), hook state `working`, or the contract's first tool/action. If hook trust or another dialog intercepted it, resolve the dialog and re-deliver.

Short same-task corrections use one literal line plus a separate Enter. Put long corrections in a new durable job file and point Codex to it. Never paste a correction into an interactive dialog or mistake queued composer text for a consumed turn.

## Context economy and lifecycle

For a new `task_id`, `/clear` is the Codex-native reset: it clears the terminal and starts a new chat. First satisfy the generic pre-reset gate (idle, artifacts in the SoT, no unacked return), then send `/clear` and wait until a fresh composer with `Context 0%` appears before delivering the next job. Do not inject during the transition.

`/compact` is only an in-flight rescue after state has been written to disk. A compaction summary can drop seat identity, skill rules, or mutable ids; after compaction reread `~/fleet/<concern>/SEAT.md`, the job contract, and this adapter before continuing.

`/exit` is a valid Codex command and exits the TUI; this is intentionally different from Pi, where `/exit` is a billable prompt and forbidden. Use `/exit` when the process itself must be relaunched (for example to change launch flags). In a tmux seat started with `exec codex`, exit also ends that pane/session. Under herdr, inspect the pane after exit and require a real shell prompt before relaunch rather than assuming the seat survived. `Esc` interrupts the current turn—it is not the normal process-exit mechanism.

## Context numbers: trust the live denominator

Do not plan around a marketing/banner context number. A previous route/banner showed roughly 1.1M, but fleet observation hit compaction near ~400K; treat that as an observed failure boundary, not a guaranteed exact threshold because the route and counter semantics have since changed. On the current 0.146.0 + GPT-5.6 route, `~/.codex/models_cache.json` declares 272,000 tokens with `effective_context_window_percent=95`; the effective ceiling is 258,400 and the TUI rounds it to `258K window`.

The footer exposes two different counters:

- `Context N% used` is live occupancy against the current effective window;
- `NNNK used` is cumulative usage across turns/compactions and can exceed the window.

For example, this seat showed `Context 41% used · 258K window · 411K used`; that is internally consistent, not proof of a 411K live context. Use the percentage + window for rollover risk, cumulative `used` only for accounting, and the fleet `ctx-probe` for measured degradation. Persist to disk before the live context becomes unsafe; never wait for the advertised maximum.

## Weekly quota is shared with Pi

Codex CLI and Pi's `openai-codex` provider draw from the same ChatGPT rolling seven-day pool. Their labels point in opposite directions:

- Codex footer: `weekly N% left` = remaining;
- Pi identity extension: `★ <plan> 7d·N%` = spent.

A same-time reading of Codex `24% left` and Pi `7d·76%` is one pool expressed two ways, not two independent budgets. Fleet capacity planning must sum Codex and Pi work together. Read the live footers at dispatch and heartbeat; do not reserve the same remainder twice.

## Heartbeat and failure classification

For tmux Codex, **busy** includes the `• Working (... • esc to interrupt)` line; **idle** requires that marker absent and the `›` composer present. Debounce idle over several reads because tool transitions can briefly remove the marker. Under herdr, use integration state plus transcript/process inspection, but retain the hook-trust exception: bare `idle` is never launch or completion proof.

Always keep the generic four surfaces: transcript, process/hook state, contracted artifacts, and return ledger. Codex-specific status/footer evidence is useful but subordinate to the artifact. Classify these explicitly:

- unsupported model / HTTP 400 before first action → launch failed; no worker is running;
- composer still contains the pointer → not submitted;
- `idle` at hook-trust or another dialog → `waiting`, not idle;
- process exited to shell with no artifact → failed/stopped, not done;
- artifact landed atomically at the contracted path → eligible for commander verification regardless of whether a return envelope arrived.

At task end, `/exit` or `/clear` only after the artifact and return state are safe. Close only seats the commander created or the user explicitly named.
