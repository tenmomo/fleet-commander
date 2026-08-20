# tmux fabric — ARCHIVED 2026-08-20 (owner ruling)

herdr is the fleet's standing seat fabric for both commander and worker seats since 5.0.0; tmux was archived wholesale because the owner's real fleets stopped using it (the tell: every herdr-hosted commander logged "return-channel notify failed" against a tmux wire that had no server to reach). **Read this file completely ONLY when the owner explicitly names a tmux seat for a task.** Nothing here is maintained against new harness versions; the dated lessons remain true for the mechanisms they describe. The return-channel helper keeps its tmux lane alive (any non-`wX:pY` pane token still routes over `tmux send-keys`), so an old contract or a deliberate tmux seat still works end to end.

## Address a pane

- Inventory: `tmux list-sessions`, `list-windows -a`, `list-panes -a`. Target `session:window.pane` exactly (`<session>:0.0`), never a bare session name — one mis-resolved to a sibling once. Numeric indices renumber when panes die/respawn: for **stored** targets (contracts, watch scripts) prefer the immortal pane id `%N` (`tmux list-panes -t <session> -F '#{pane_id}'`); `session:0.0` is fine for a single-pane session you own.
- Own address inside tmux: `tmux display-message -p '#{session_name}:#{window_index}.#{pane_index}'`. Return-sink from outside tmux: `tmux new-session -d -P -F '#{session_name}:#{window_index}.#{pane_index}' -s <name>`.
- One concern per session; a new concern gets a fresh named session (`tmux new -d -s <concern>`). Naming convention (owner ruling 2026-07-31): the concern string is the sole key across tmux session `cmdr-<concern>`, fleet directory `~/fleet/<concern>/`, and `~/fleet/<concern>/SEAT.md`. ⚠ tmux session names must NOT contain `.` (parsed as window.pane separator; no escaping works — live 2026-07-31: `cmdr-opus-4.6` was unreachable by any `attach -t` form, had to rename via session id).
- Prefer the user's normal **visible** tmux server; a private socket (`tmux -S <sock>`) only when isolation is explicitly wanted.

## Deliver a job

Claude Code seat launch: `tmux new-session -d -s <concern> -c <worktree> 'claude'` (with the same two-flag discipline as herdr seats: `--model`, `--dangerously-skip-permissions`). Wait for the real editor, then inject a large job via one **named** buffer, **serially**:

```bash
BUF="job-$$-$RANDOM"                               # never the unnamed shared buffer
tmux load-buffer  -b "$BUF" ~/fleet/<concern>/jobs/<job>.md
tmux paste-buffer -b "$BUF" -t <session>:0.0
tmux send-keys    -t <session>:0.0 C-m                  # one C-m; gap any retry behind proof
```

The unnamed global buffer races across panes — one unique named buffer per job; deliver to panes serially. Pi seats NEVER get the multiline paste (fragments into hundreds of queued `Steering:` turns, 2026-07-18) — one literal pointer line only:

```bash
tmux send-keys -t <pane> -l "$MSG"     # literal text
tmux send-keys -t <pane> C-m           # Enter as its own send
```

Small corrections: `tmux send-keys -t <pane> -l '<text>'` then `C-m` separately; control keys (`Escape`, `C-u`) each go as their own send. Slash injection: `tmux send-keys -t <pane> -l '/goal <objective>'` + separate `C-m` (same two traps as the herdr form — HERDR-WORKERS § Inject slash commands).

**Transition swallow (Claude Code):** `/clear` / `/effort` / `/model` have a transition window that **silently eats a paste** (bitten twice, 2026-07-21). After any such command, capture until a bare prompt — after `/clear`, until the status-bar ctx field is **gone** — only then paste. Consumption proof = status-bar **ctx% rises** after Enter; flat → one extra Enter; still flat → fresh named buffer, re-paste.

**Submission proof:** a large paste can sit unsubmitted; send a second `C-m` only after a real gap (an intervening tool call or several seconds) — back-to-back Enters can be swallowed together. Pi seat exit on tmux: double Ctrl+C (never `/exit`, a billable prompt); this does NOT reach a herdr-hosted Pi (HERDR-WORKERS § resetting a Pi seat).

Codex tmux launch:

```bash
tmux new-session -d -s <concern> -c <worktree> \
  "exec codex -m gpt-5.6-sol -c 'model_reasoning_effort=\"high\"' \
  --dangerously-bypass-approvals-and-sandbox \
  --dangerously-bypass-hook-trust"
```

Hook-trust dialog on tmux: `tmux send-keys -t <pane> t`. tmux Codex **busy** = the `• Working (... • esc to interrupt)` line; **idle** = marker absent + `›` composer present, debounced.

## Heartbeat

Pane transcript: `tmux capture-pane -p -J -t <pane> -S -200`. Idle (Claude Code) = no in-flight marker **and** worker jsonl mtime static ~3 min. The Claude Code busy SHAPE (matches a live turn's `✳ Verbing… (2m 6s · ↓ 5.4k tokens)` render):

```bash
tmux capture-pane -p -t "$pane" -S -25 | grep -qE '…\s*\([0-9]+[ms][^)]*↓[^)]*tokens\)'
```

Claude Code ONLY — busy Pi renders a braille spinner `⠼ Working...` (PI-WORKERS § Heartbeat), read as idle by this regex. A tmux `extended-keys is off` warning affects modified keys such as Shift+Enter; plain `C-m` submission still works.

**跨席消息的「已送达」判据是对方的输入行为空,不是「capture 里看得见我发的字」。** `capture-pane` 会把输入框内容一并抓出——未提交的长消息读起来与已进 transcript 的一模一样(2026-07-26 实锤:发完 `send-keys -l` + 单独 `C-m` 后 capture 到全文判「已消费」,实际那段话在对方输入框躺了十几分钟)。正判据两条同时成立:`❯` 那行**是空的**,且消息出现在输入框上方的 transcript 区;补 `C-m` 前先隔一个真实间隔——连发两个 Enter 会被一起吞掉。

## Session lifecycle

tmux session 是弹性资源,不是固定编制。concern 真正结束(交付已验收入 SoT、无后续单、无 pending return)的 session 就 kill(kill 前 capture 最后一屏留档);新 concern 就创造(`tmux new -d -s <name>` → yolo 启动 → 等真 prompt → cd 进驻 worktree)。空转 session 是负债(statusline 噪音 + 误投递面 + 幽灵 ctx)。边界:只 kill 自己创建或 owner 点名的 session;同 concern 还有后续单用 `/clear` 保 session,concern 终结才 kill。Monitor commands for the user: `tmux attach -t <concern>`, `capture-pane -p -J -t <pane> -S -200`.

## Fleet-loss (tmux server death)

The whole tmux topology lives in one server — a reboot, tmp cleaner, or tmux crash voids every contract's panes at once, and pane indices renumber even on routine kills. Census survivors per harness — `tmux ls` AND `herdr workspace list`; a herdr fleet does not live in the tmux server and survives its death intact (2026-07-23: tmux socket+server gone, all herdr seats + mailbox unaffected; the durable envelope carried the in-flight return). Relaunch seats, re-register every open task from its job file (register is an upsert), one line per open task: contract restored, re-run your return. After ANY pane kill/recreate or relayout, re-register open contracts against the re-inventoried topology.

## Return-channel tmux lane

`scripts/return-channel.py` routes any pane token that is NOT herdr-shaped (`wX:pY`) over `tmux send-keys -l` + separate `C-m`; `--socket` selects a private tmux server (tests/isolation). A tmux-hosted commander's reply_to is its `session:window.pane` or `%N`. All envelope/ledger semantics are fabric-independent and live in SKILL.md § Return channel.
