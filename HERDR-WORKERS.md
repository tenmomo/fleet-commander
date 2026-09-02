# herdr fabric — seats for any harness (commander AND worker)

Read this file completely before the session's first seat is created. herdr is the fleet's standing seat fabric (owner ruling 2026-08-20, SKILL.md §Seat fabric); the generic commander stages remain authoritative — this file owns the fabric mechanics.

## Prerequisites and topology

Install state integration once for each harness that will run under herdr:

```bash
herdr integration install omp        # omp is a SEPARATE integration from pi (~/.omp/agent/extensions/herdr-omp-agent-state.ts)
herdr integration install claude
herdr integration install pi
herdr integration install codex
herdr integration status             # audit: every harness the fleet runs must read `current`, never `not installed`
```

Integration hooks report `idle`, `working`, `blocked`, `done`, or `unknown`. Sessions already running when integration is installed do not report state; launch a new session after installation. Hook state replaces harness-spinner matching, subject to the trust-dialog exception under Launch.

**A missing integration is NOT visible as an error — it is a permanent false `idle`.** With no hook, herdr still labels a known agent `idle` forever, spinner and all; the tell is only in `herdr agent explain <pane>`: `fallback_reason: default_known_agent_idle_fallback` (no hook) versus `screen_detection_skip_reason: full_lifecycle_hook_authority` (hook live). Measured 2026-08-13: three omp seats sat at `agent_status: idle` with animating spinners for a whole session because `herdr integration install omp` had never been run — a commander heartbeating on `agent list` alone would have read every one as finished. Run `agent explain` once per new seat class, not per seat. omp's extension root follows the active agent dir, so a seat launched with `--profile <name>` or `PI_CODING_AGENT_DIR` reads `~/.omp/profiles/<name>/agent/extensions` instead and silently has no hook.

herdr is the workspace manager around the worker, not a tmux pane: hierarchy workspace → tab → pane, pane ids such as `w4:p1`. Do not nest tmux inside herdr — the prefix is configurable (`[keys] prefix` in `~/.config/herdr/config.toml`, hot-applied by `herdr server reload-config`; this machine runs `ctrl+g` since 2026-07-22, so the stock `ctrl+b`-vs-tmux collision no longer applies locally), but nesting stays unrecommended. Generic job-contract, worktree, and outward-action discipline lives in `SKILL.md`; do not duplicate it here.

## Launch

One fleet gets ONE workspace; every additional seat is a TAB inside it — never a sibling workspace (owner ruling 2026-07-22: sibling workspaces scatter the fleet and the human loses the one-glance war room; measured same day — a commander given only the workspace-create recipe spawned three sibling spaces).

**Sub-fleet refinement (owner ruling 2026-08-14): a 子fleet is one DEDICATED workspace × n panes that collaborate toward ONE PR, closed on ack.** This does not contradict 07-22 — that ruling forbids scattering the *same* fleet's standing seats across sibling workspaces; a sub-fleet is a bounded mission with its own workspace precisely so the owner can glance one workspace = one deliverable. Standing commander seats stay tabs in the fleet workspace; PR-sized missions get their own workspace with however many collaborating panes the job needs (writer/verifier/judge …), and `workspace close` on ack remains part of the ack (07-31 ruling). Create the fleet workspace once, add seats as tabs, retain each returned pane id, then start the worker with bare harness arguments after `--`. `workspace create --label` names the WORKSPACE — its root tab still gets a default numeric label, inconsistent with `tab create --label` siblings (owner-spotted 2026-07-23); follow up with `herdr tab rename <ws>:t1 <seat-label>` so every seat reads descriptively:

```bash
herdr workspace create --cwd <workdir> --label <fleet> --no-focus                             # fleet's first seat only
herdr tab create --workspace <workspace_id> --cwd <workdir> --label <seat> [--env KEY=VALUE]  # every further seat
herdr agent start <name> --kind <pi|claude|codex|…> --pane <pane_id> --timeout 60000 -- <bare-flag-args>
```

`agent start` 的 `<name>` **必须全小写**:`ctx-A` 被拒为 `invalid_agent_name`(规则=小写字母开头,只含小写字母、数字、`-`、`_`,1–32 字符),而 `tab create --label` **不受此限**——于是「tab 叫 ctx-A、agent 却起不来」很容易被误读成启动失败或权限问题(2026-07-26 连续两席被拦)。席位标签与 agent 名不必相同,生成时就统一小写最省事。

Both create verbs return the exact pane id and accept `--env` (per-seat identity pinning — below). Arguments after `--` do not pass through a shell, so aliases do not expand — expand an alias such as `yolo-codex` into its real flags before launch.

For Codex 0.145 interactive mode, `--full-auto` is not a valid flag. Field-tested choices:

```text
-s workspace-write -a never
--dangerously-bypass-approvals-and-sandbox
```

On the first Codex launch, its hook-trust dialog is a `waiting` condition that herdr reports as `idle`. Either launch with `--dangerously-bypass-hook-trust` when the trusted hook is herdr's own, or send `t` to trust all (persists; needed once per machine): `herdr agent send-keys <pane_id> t`. After clearing that dialog, re-deliver the job — the dialog can consume the queued prompt. Never accept the reported `idle` at this dialog as launch completion (2026-07-22: the first Codex wait crossed a false idle and found an empty output directory).

If `agent start` times out and no agent starts, `agent read` fails with `agent_not_found`. Read the terminal through the pane instead — the only field-tested screen channel in that state:

```bash
herdr pane read <pane_id> [--lines N] [--source visible|recent|recent-unwrapped|detection] [--format text|ansi]
herdr pane process-info --pane <pane_id>
```

CLI inconsistency: `pane read` takes `pane_id` positionally, while `pane process-info` uses `--pane`. The raw write channel is `herdr pane send-text <pane_id> '<text>'` plus `herdr pane send-keys <pane_id> <key>…` — both work on a pane with no detected agent (measured 2026-07-22), so a commander can drive a bare shell or answer a pre-detection dialog without waiting for agent state.

To pin per-seat environment, pass `--env KEY=VALUE` on `workspace create` and verify from inside — have the pane shell echo the variable to a file (`ps eww` cannot read another process's environment on macOS). Since 2026-07-31 the default `~/.pi/agent/` carries the the shared Pro pool subscription — bare `pi` = the shared Pro pool, no `PI_CODING_AGENT_DIR` env var needed. The identity-marker extension shows `★ <account> 7d·N%·↻Nd·passN` on openai-codex seats; ⚠ **hidden entirely on API-key providers** (openrouter etc.) — cash billing has no subscription quota. The same footer line verifies model and thinking level (`(openai-codex) gpt-5.6-sol • high`). When hand-launching a worker in a bare-shell pane (`pane send-text`), do NOT `exec` the harness — `exec pi` makes worker exit close the pane, the tab, and (if last tab) the whole workspace (2026-07-23: a double-Ctrl-C seat reset vaporized both seats and their workspace); launch bare (`pi …`) so exit returns to the shell and the seat survives for relaunch. **Done** = exact pane id held, the requested worker process running, any hook-trust dialog resolved, and no launch error on the pane.

**Resetting a Pi seat: REPLACE the tab, do not try to exit the TUI.** The tmux-era double Ctrl+C exit (TMUX-ARCHIVE.md) does not reach a herdr-hosted Pi — measured 2026-07-26, four sends (`pane send-keys` ×2, then `agent send-keys` ×2, spaced) every one returning `{"type":"ok"}` while the footer stayed live and the agent kept running. Retrying the key is the trap; tabs are cheap and Stage 2's context-economy rule only asks for a *fresh context*, not this particular process:

```bash
herdr tab create --workspace <ws> --cwd <dir> --label <new-seat> --env KEY=VALUE   # new seat
# … identity gate, agent start, dispatch, CONFIRM consumption …
herdr tab close <old_tab_id>                                                       # only then
```

Close the old tab **after** the replacement is confirmed working, never before — a failed relaunch would otherwise leave the fleet a seat short. The workspace must hold ≥2 tabs at the moment you close (same constraint as the last-tab rule under § Close and worktrees). Nothing is lost: deliverables live on disk per `SKILL.md` §2.

**起 Claude Code worker 席,`--` 后面的两面旗缺一不可 —— 缺任何一面,席位起来了却是废的(2026-08-14 深夜一个 Claude Code 席实锤)。**

```bash
herdr agent start <name> --kind claude --pane <pane_id> --timeout 60000 -- \
  --model claude-opus-5 --dangerously-skip-permissions
```

- **缺 `--model claude-opus-5`** → 席位**静默继承 Fable**。footer 是唯一的观测面,起席后必读(`SKILL.md` 的起席验 footer 纪律)。
- **缺 `--dangerously-skip-permissions`** → 席位落进 **「don't ask」全拒模式**:Bash / Read **全部 denied**,
  worker 一句活都干不了,**而它看起来是活的**(agent 在跑、footer 正常、pane 有输出)。
  ⚠ **这个状态救不回来**:远程 `send-keys` 发 shift+tab **切不动**那个模式。
  **唯一解 = 退出重启并带上旗**;同一份派单在重启后**一次跑通**。

两面旗都属于「起席即验」而不是「出问题再查」:一个继承了 Fable 的席位会安静地把活干得不对,
一个全拒模式的席位会安静地什么都不干,**两种失败在 `agent list` 上都是绿的**。

**第三面同族:model 名对了,窗口还可能不对 —— 语料重的单必须点名 `[1m]` 变体,footer 闸要读分母不只读名字(2026-08-20 一个发版打包席实锤,owner 抓的,不是检查抓的)。** `--model claude-opus-4-6` 起的是 **200k** 窗口;1M 窗口是**另一个 model id** `claude-opus-4-6[1m]`,而两者的 footer 名字读起来几乎一样——分辨面是 ctx 字段的**分母**(`(48k/200k)` vs `(48k/1M)`)。一份「读全每个源文件 + 归档 + 克隆仓」的契约在 7 分钟内把 200k 席吃到 80%,compaction 一旦触发会静默丢掉在读的简报。**救法(实测有效):对 working 席队列 `/model claude-opus-4-6[1m]`**——在下一个 turn 边界落地,**上下文原样保留**、分母当场变 1M(161k/200k → 165k/1M);该席最终吃到 196k,不切换必爆。规矩:①派单前按契约的阅读面估窗口,语料重就直接 `[1m]` 起席;②footer 起席闸的检查项包含**窗口分母**;③中途发现窗口不够,先队列 `/model` 切换,别急着杀席重派。

**第四面:herdr server 的父进程环境会被每个 pane 继承——从 Claude Code 会话里拉起的 server,其所有 CC worker 席继承 `CLAUDE_CODE_CHILD_SESSION` 标记,transcript 静默不落盘(2026-08-21 实锤)。** 唯一观测面是 footer 警告行「⚠ Transcript saving is off — inherited CLAUDE_CODE_CHILD_SESSION marker」;`agent_status` 与 pane 输出全部正常,丢的是事后审计面(worker 的 jsonl transcript)。解法:起席的 tab 加 `--env CLAUDE_CODE_CHILD_SESSION=`(空串在 Node truthy 判定下等效未设,实测警告消失、transcript 正常落盘),或让 owner 从干净 shell 起 server。凡 server 是从某个 agent 会话内启动的,起首个 CC 席后必读 footer 查这行。

**Batch-launching seats in a shell for-loop silently fails (measured 2026-08-14, twice in one night).** Seven `agent start` calls inside `for spec in …; do set -- $spec; herdr agent start …` produced empty stdout and ZERO started agents; four `tab create` calls in the same shape also died. The identical commands issued one-per-invocation all succeeded. Until the mechanism is found, issue every `herdr agent start` / `tab create` as its own command — never in a loop — and verify with `agent list` + per-pane footer reads afterward.

**A shared batch output directory is contested space — a peer's tidy-up can swallow another seat's instruments (measured 2026-08-14, rw-b03).** Writer-1's `mv b03_*.py tools-w1/` carried away the judge's freshly written common module, and left a same-named copy whose path CONSTANT pointed at the writer's own worktree — a judge blindly reusing it would have graded an unmerged tree and gone all-green. Rules: each role's instruments live in a role-owned subdirectory; before `cp`-ing any instrument from a shared path, diff its constants block.

**A worker seat can make itself wake-able by holding its own polling shell.** The rewrite-wave judges (2026-08-14) started, prepared their harness, then kept a background shell polling for their writers' report files — footer shows `· 1 shell` and the seat re-activates itself when the files land. This beats commander-side polling for intra-sub-fleet handoffs; the commander still relays anything aimed at a seat WITHOUT such a shell (idle writers never self-wake — a judge's bounce file sat inert until the commander re-prompted the writer).

## Deliver a job

Follow `SKILL.md` Stage 2 for the self-contained contract. Under herdr, send only a one-line pointer to that job file and wait for hook state `working`:

```bash
herdr agent prompt <pane_id> '<one-line pointer to job file>' --wait --until working
```

Enter is intermittently swallowed — herdr exposes this as `agent_prompt_stalled` when no state change occurs within five seconds. Recover in this order:

```bash
herdr pane read <pane_id>                  # confirm the pointer remains in the input box
herdr agent send-keys <pane_id> enter
herdr agent wait <pane_id> --until working --timeout 20000
```

Do not blindly send the fallback Enter before reading the pane. If an interactive dialog consumed the dispatch, resolve the dialog and issue `agent prompt` again — the original prompt is gone. **Complete** = hook state `working` for the dispatched pointer, no dialog or stalled input retained it.

**A lost dispatch can also masquerade as `done` (measured 2026-08-14):** `agent prompt --wait` timed out, the pane later read `done` with a BLANK transcript region — the prompt was never consumed and the seat had done nothing. `done`/`idle` after a dispatch proves nothing; the only consumption proof is transcript content (or the deliverable itself). Re-prompt on blank transcript.

## Steer

Use `SKILL.md` Stage 5 to decide when a same-task correction is safe.

**Same-task re-prompt of an IDLE seat is measured and works** — 3/3 on 2026-07-26 across two commanders: with the seat at `agent_status` `idle`/`done`, `herdr agent prompt <pane_id> '<correction>' --wait --until working` was consumed every time and each seat produced a revised deliverable. Independent confirmation came from the footer's turn counters advancing, not from the `--wait` return alone. Ordering hazard: a correction aimed at a seat that has *already finished* arrives as a fresh turn and **restarts it**, overwriting the delivered artifact — archive the first version before steering a `done` seat.

**Mid-turn interruption is still untested.** It is a different mechanism (the prompt has to cross a tool boundary rather than land on an idle prompt); do not let the idle-seat result above be read as covering it. If you must correct a `working` seat, mark the path untested and independently observe pane and hook state. **Done** = the correction's consumption is independently observed; no untested steering behavior is presented as established.

## Inject slash commands (`/goal`, `/loop`) — the harness itself is a commander tool

Measured 2026-08-06 (owner directive: "the harness itself becomes a tool for a commander"). A slash command is just prompt text, so the ordinary dispatch verb delivers it — **a commander can set a worker's `/goal`, arm a `/loop`, or `/clear` a seat without ever attaching**, and can do the same **to itself** (a herdr-hosted commander is a pane like any other):

```bash
herdr agent prompt <pane_id> '/goal <one-line objective>' --wait --until working
herdr agent prompt <pane_id> '/loop 15m <prompt-or-slash-command>'      # self-paced if interval omitted
herdr agent prompt <self_pane> '/goal …'                                # commander → itself; queues, fires after the current turn
```

**Consumption proof is the FOOTER, not the `--wait` return** — a consumed `/goal` renders `◎ /goal active (Ns)` on the status line, and that counter is the only positive signal (measured: footer showed `◎ /goal active (6s)` while the wait had already returned on an unrelated transition). The same footer read doubles as the identity gate this file's Launch section requires — one `pane read` confirms model, effort, ctx%, permission mode, **and** goal state: `Opus 5 high | ctx:3% (29k/1M) | (5h·7%) (7d·76%) | ~/fleet/<concern> | main ✱` / `⏵⏵ bypass permissions on`.

Two traps, both measured the same session:

- **Slash injection BYPASSES the job file, so it bypasses the init-suppression line with it.** Stage 2 opens every job file with "skip any repo Session Init"; a bare `/goal` carries no such clause, so the seat obeys its repo `CLAUDE.md` and burns a full Session Init before doing anything (measured: a seat sent only `/goal` read its whole 24k SEAT.md and climbed to 29k ctx before the real job arrived). Either fold the suppression into the injected text, or inject `/goal` **after** the job-file pointer has landed.
- **`--wait --until working` TIMES OUT against an already-`working` seat** — there is no state transition to observe, so herdr reports `{"error":{"code":"timeout"}}` for a prompt that was in fact queued and later consumed. **Never read that timeout as "not delivered."** Fall back to the SKILL.md §Return-channel delivery judgement: the seat's input line `❯` is **empty** and the text appears in the transcript region above it. Steering a busy seat remains the untested mid-turn path (§ Steer) — a queued slash command lands at the next turn boundary, which is also why self-injection is safe but never immediate.

Legacy tmux seats: the same two traps apply and the footer proof is identical; the raw send-keys form lives in [TMUX-ARCHIVE.md](TMUX-ARCHIVE.md).

**Done** = the footer shows `◎ /goal active`, or the transcript+empty-`❯` pair proves consumption; never a bare `--wait` return.

## Wait and heartbeat

Use hook waits instead of spinner-regex polling: `herdr agent wait <pane_id> --until <state> --timeout <ms>`. `--until` may be repeated; with no `--until`, the command matches `idle`, `done`, or `blocked`.

**A blocking `wait` in a detached watcher misses transitions — make the artifact scan the outer loop.** Measured 2026-07-22, three for three: long-timeout `agent wait` calls from detached/background watchers never fired on a real working→idle transition (artifacts landed, worker idled, the wait stayed blocked), while waits whose target state was already current returned instantly. A hung wait is silent in exactly the direction that reads as "worker still busy". Unattended sentinels therefore loop on a short cycle — check on-disk artifacts first, then `herdr agent list` for state and liveness — and cap any inner `wait` at the poll interval; never hang one long-timeout `wait` as the sole wake signal. Short foreground waits (`--until working` after dispatch) remain reliable as consumption probes.

**Bare `idle` is never completion.** Count and inspect the required on-disk outputs per `SKILL.md` Stage 4. Hook state is a necessary scheduling signal, not proof of handback — in particular, the Codex hook-trust dialog can be falsely reported as `idle`.

herdr's three harness-observation surfaces: transcript → `herdr pane read <pane_id>`; foreground process → `herdr pane process-info --pane <pane_id>`; integrated hook state → `herdr agent list`. The deliverable surface remains an independent disk check under `SKILL.md` Stage 4.

## Return channel

Since 5.0.0 the return-channel bell reaches herdr seats natively: `scripts/return-channel.py` detects a herdr pane id (`wX:pY`, the `$HERDR_PANE_ID` shape) in `reply_to` and wakes it via `pane send-text` + a separate `enter` (live-verified 2026-08-20 into a busy omp commander — the line queued and landed at the next turn boundary). Register workers with the commander's own `$HERDR_PANE_ID` as `--reply-to`; an intermediate commander registers its workers with its OWN token, never its parent's. The bell stays best-effort and NEVER the gate: a bare-shell pane executes the wake line as a failed command, a worker may skip `return`/`publish-task` entirely, and completion remains anchored to the **artifact** (contracted path + atomic staging→`mv` publish, SKILL.md §2) — the same on-disk check closes a herdr task, an ssh task, and a legacy tmux task. Supporting surfaces stay `agent wait` + hook state.

## Windows seat

herdr ships a Windows preview build. A GUI install lands under `%LOCALAPPDATA%\Programs\Herdr`, and its `bin\herdr.exe` is a **per-session virtual file** (MSIX-style projection): ssh sessions cannot see it — `dir /a` shows an empty directory and invoking the path fails with "The path cannot be traversed because it contains an untrusted mount point". This is not a broken install.

Fix (measured 2026-07-22): from the **desktop session**, copy the exe to a real path — `Copy-Item "$env:LOCALAPPDATA\Programs\Herdr\bin\herdr.exe" "$env:USERPROFILE\.local\bin\herdr.exe"` — the copy dereferences the projection. The copied CLI invoked over ssh reaches the desktop session's herdr server (named pipes cross sessions for the same user): `ssh <user>@<host> 'C:\Users\<user>\.local\bin\herdr.exe workspace list'`. The server must already be running in the interactive desktop session — start the herdr app at the desktop, never over ssh. `agent start` on a freshly created workspace can race and time out once (observed on macOS too); one retry with identical args is normal recovery. **Done** = the ssh-invoked CLI returns workspace JSON and a create → close round-trip succeeds from the remote side.

## Close and worktrees

**Mandatory close after ack (owner ruling 2026-07-31).** When the last task in a herdr workspace is `acked`, `workspace close` is part of the ack — not an optional cleanup. Prompt-cache TTL is ~5 min; a workspace left open "to reuse context" past that window is a phantom benefit consuming a visible slot. Cost of re-creating is near zero (fresh tab + one-line job pointer); cost of not closing is a growing graveyard the owner has to manually sweep (live 2026-07-31: 30 idle tabs across three finished workspaces, caught by owner screenshot). The one exception: a workspace with a DIFFERENT task still `working` in another tab — close only the finished tabs, leave the workspace alive for the running peer.

`herdr workspace close <id>` deletes the workspace, kills all its processes, and removes its scrollback — not recoverable. The LAST tab in a workspace refuses `tab close` (`tab_close_failed`) — retiring a whole fleet ends with `workspace close`, not a final tab close (measured 2026-07-23). Before closing: capture the final screen, confirm required artifacts are in their source of truth, and resolve any unpushed worktree branch before allowing its directory to be deleted.

herdr supports native worktree workspaces through `herdr worktree create` (TUI: `prefix+shift+g`). Closing one may ask whether to delete the worktree directory — push an unpushed branch cleanly before closing, subject to the outward-action authority in `SKILL.md`; do not approve directory deletion while branch state remains only there. Non-destructive exit: `prefix q` detaches; `prefix+shift+x` closes a tab.
