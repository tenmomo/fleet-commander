# herdr worker adapter

Read this file completely whenever the target pane runs under herdr. The generic commander stages remain authoritative; this file owns only the herdr-specific mechanics.

## Prerequisites and topology

Install state integration once for each harness that will run under herdr:

```bash
herdr integration install claude
herdr integration install pi
herdr integration install codex
```

Integration hooks report `idle`, `working`, `blocked`, `done`, or `unknown`. Sessions already running when integration is installed do not report state; launch a new session after installation. Hook state replaces harness-spinner matching, subject to the trust-dialog exception under Launch.

herdr is the workspace manager around the worker, not a tmux pane: hierarchy workspace → tab → pane, pane ids such as `w4:p1`. Do not nest tmux inside herdr — the prefix is configurable (`[keys] prefix` in `~/.config/herdr/config.toml`, hot-applied by `herdr server reload-config`; a field-tested host has used `ctrl+g` since 2026-07-22, avoiding the stock `ctrl+b`-vs-tmux collision), but nesting stays unrecommended. Generic job-contract, worktree, and outward-action discipline lives in `SKILL.md`; do not duplicate it here.

## Launch

One fleet gets ONE workspace; every additional seat is a TAB inside it — never a sibling workspace (owner ruling 2026-07-22: sibling workspaces scatter the fleet and the human loses the one-glance war room; measured same day — a commander given only the workspace-create recipe spawned three sibling spaces). Create the fleet workspace once, add seats as tabs, retain each returned pane id, then start the worker with bare harness arguments after `--`. `workspace create --label` names the WORKSPACE — its root tab still gets a default numeric label, inconsistent with `tab create --label` siblings (owner-spotted 2026-07-23); follow up with `herdr tab rename <ws>:t1 <seat-label>` so every seat reads descriptively:

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

To pin per-seat environment, pass `--env KEY=VALUE` on `workspace create` and verify from inside — have the pane shell echo the variable to a file (`ps eww` cannot read another process's environment on macOS). Since 2026-07-31 the default `~/.pi/agent/` carries the subscription identity directly — bare `pi` is that identity, with no `PI_CODING_AGENT_DIR` env var needed (the earlier two-profile split is retired). The identity-marker extension shows `★ <plan> 7d·N%·↻Nd·passN` on openai-codex seats; ⚠ it is **hidden entirely on API-key providers** (openrouter etc.) — cash billing has no subscription quota, so the env echo stays the fallback identity proof there. The same footer line verifies model and thinking level (`(openai-codex) gpt-5.6-sol • high`). When hand-launching a worker in a bare-shell pane (`pane send-text`), do NOT `exec` the harness — `exec pi` makes worker exit close the pane, the tab, and (if last tab) the whole workspace (2026-07-23: a double-Ctrl-C seat reset vaporized both seats and their workspace); launch bare (`pi …`) so exit returns to the shell and the seat survives for relaunch. **Done** = exact pane id held, the requested worker process running, any hook-trust dialog resolved, and no launch error on the pane.

**Resetting a Pi seat: REPLACE the tab, do not try to exit the TUI.** `PI-WORKERS.md`'s double Ctrl+C is a tmux mechanic and does not reach a herdr-hosted Pi — measured 2026-07-26, four sends (`pane send-keys` ×2, then `agent send-keys` ×2, spaced) every one returning `{"type":"ok"}` while the footer stayed live and the agent kept running. Retrying the key is the trap; tabs are cheap and Stage 2's context-economy rule only asks for a *fresh context*, not this particular process:

```bash
herdr tab create --workspace <ws> --cwd <dir> --label <new-seat> --env KEY=VALUE   # new seat
# … identity gate, agent start, dispatch, CONFIRM consumption …
herdr tab close <old_tab_id>                                                       # only then
```

Close the old tab **after** the replacement is confirmed working, never before — a failed relaunch would otherwise leave the fleet a seat short. The workspace must hold ≥2 tabs at the moment you close (same constraint as the last-tab rule under § Close and worktrees). Nothing is lost: deliverables live on disk per `SKILL.md` §2.

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

## Steer

Use `SKILL.md` Stage 5 to decide when a same-task correction is safe.

**Same-task re-prompt of an IDLE seat is measured and works** — 3/3 on 2026-07-26 across two commanders: with the seat at `agent_status` `idle`/`done`, `herdr agent prompt <pane_id> '<correction>' --wait --until working` was consumed every time and each seat produced a revised deliverable. Independent confirmation came from the footer's turn counters advancing, not from the `--wait` return alone. Ordering hazard: a correction aimed at a seat that has *already finished* arrives as a fresh turn and **restarts it**, overwriting the delivered artifact — archive the first version before steering a `done` seat.

**Mid-turn interruption is still untested.** It is a different mechanism (the prompt has to cross a tool boundary rather than land on an idle prompt); do not let the idle-seat result above be read as covering it. If you must correct a `working` seat, mark the path untested and independently observe pane and hook state. **Done** = the correction's consumption is independently observed; no untested steering behavior is presented as established.

## Wait and heartbeat

Use hook waits instead of spinner-regex polling: `herdr agent wait <pane_id> --until <state> --timeout <ms>`. `--until` may be repeated; with no `--until`, the command matches `idle`, `done`, or `blocked`.

**A blocking `wait` in a detached watcher misses transitions — make the artifact scan the outer loop.** Measured 2026-07-22, three for three: long-timeout `agent wait` calls from detached/background watchers never fired on a real working→idle transition (artifacts landed, worker idled, the wait stayed blocked), while waits whose target state was already current returned instantly. A hung wait is silent in exactly the direction that reads as "worker still busy". Unattended sentinels therefore loop on a short cycle — check on-disk artifacts first, then `herdr agent list` for state and liveness — and cap any inner `wait` at the poll interval; never hang one long-timeout `wait` as the sole wake signal. Short foreground waits (`--until working` after dispatch) remain reliable as consumption probes.

**Bare `idle` is never completion.** Count and inspect the required on-disk outputs per `SKILL.md` Stage 4. Hook state is a necessary scheduling signal, not proof of handback — in particular, the Codex hook-trust dialog can be falsely reported as `idle`.

herdr's three harness-observation surfaces: transcript → `herdr pane read <pane_id>`; foreground process → `herdr pane process-info --pane <pane_id>`; integrated hook state → `herdr agent list`. The deliverable surface remains an independent disk check under `SKILL.md` Stage 4.

## Return channel

A herdr seat is not a tmux pane, so the standard tmux pane-notification line in `SKILL.md` cannot reach it — do not promise that wire path. This costs nothing: completion is anchored to the **artifact** (contracted path + atomic staging→`mv` publish, SKILL.md §2), which is fabric-independent — the same on-disk check closes a herdr task, a tmux task, and an ssh task. What remains unsolved is only cross-harness *notification* (the early-wake bell), so keep stating that boundary in the job contract and never present the bell as solved. Supporting surfaces stay `agent wait` + hook state. **A herdr-hosted intermediate commander must still register its workers with its OWN reply_to token** (the notify will fail non-fatally; envelopes stay pending and its watch loop scans `pending --reply-to <self>`) — never borrow the parent commander's tmux sink to "make the bell work": that floods the parent with worker-level receipts and breaks the one-hop chain (live 2026-07-23: six media-worker returns landed in the mastermind's chat before the owner caught it).

## Windows seat

herdr ships a Windows preview build. A GUI install lands under `%LOCALAPPDATA%\Programs\Herdr`, and its `bin\herdr.exe` is a **per-session virtual file** (MSIX-style projection): ssh sessions cannot see it — `dir /a` shows an empty directory and invoking the path fails with "The path cannot be traversed because it contains an untrusted mount point". This is not a broken install.

Fix (measured 2026-07-22): from the **desktop session**, copy the exe to a real path — `Copy-Item "$env:LOCALAPPDATA\Programs\Herdr\bin\herdr.exe" "$env:USERPROFILE\.local\bin\herdr.exe"` — the copy dereferences the projection. The copied CLI invoked over ssh reaches the desktop session's herdr server (named pipes cross sessions for the same user): `ssh <user>@<host> 'C:\Users\<user>\.local\bin\herdr.exe workspace list'`. The server must already be running in the interactive desktop session — start the herdr app at the desktop, never over ssh. `agent start` on a freshly created workspace can race and time out once (observed on macOS too); one retry with identical args is normal recovery. **Done** = the ssh-invoked CLI returns workspace JSON and a create → close round-trip succeeds from the remote side.

## Close and worktrees

**Mandatory close after ack (owner ruling 2026-07-31).** When the last task in a herdr workspace is `acked`, `workspace close` is part of the ack — not an optional cleanup. Prompt-cache TTL is ~5 min; a workspace left open "to reuse context" past that window is a phantom benefit consuming a visible slot. Cost of re-creating is near zero (fresh tab + one-line job pointer); cost of not closing is a growing graveyard the owner has to sweep by hand (live 2026-07-31: 30 idle tabs across three finished workspaces, caught by an owner screenshot). The one exception: a workspace with a DIFFERENT task still `working` in another tab — close only the finished tabs, leave the workspace alive for the running peer.

`herdr workspace close <id>` deletes the workspace, kills all its processes, and removes its scrollback — not recoverable. The LAST tab in a workspace refuses `tab close` (`tab_close_failed`) — retiring a whole fleet ends with `workspace close`, not a final tab close (measured 2026-07-23). Before closing: capture the final screen, confirm required artifacts are in their source of truth, and resolve any unpushed worktree branch before allowing its directory to be deleted.

herdr supports native worktree workspaces through `herdr worktree create` (TUI: `prefix+shift+g`). Closing one may ask whether to delete the worktree directory — push an unpushed branch cleanly before closing, subject to the outward-action authority in `SKILL.md`; do not approve directory deletion while branch state remains only there. Non-destructive exit: `prefix q` detaches; `prefix+shift+x` closes a tab.
