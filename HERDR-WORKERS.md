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

To pin a worker identity or per-seat environment, pass `--env KEY=VALUE` on `workspace create` and verify from inside — have the pane shell echo the variable to a file (`ps eww` cannot read another process's environment on macOS). Measured 2026-07-22 with a harness-specific profile variable selecting a second subscription profile: the footer's profile tag could not distinguish the two profiles, so the environment echo was the only identity proof. When hand-launching a worker in a bare-shell pane (`pane send-text`), do NOT `exec` the harness — `exec pi` makes worker exit close the pane, the tab, and (if last tab) the whole workspace (2026-07-23: a double-Ctrl-C seat reset vaporized both seats and their workspace); launch bare (`pi …`) so exit returns to the shell and the seat survives for relaunch. **Done** = exact pane id held, the requested worker process running, any hook-trust dialog resolved, and no launch error on the pane.

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

Use `SKILL.md` Stage 5 to decide when a same-task correction is safe. No same-task or mid-turn herdr steering behavior was tested on 2026-07-22: the one-line `agent prompt` path and stalled-prompt recovery were validated only for initial dispatch — do not present their correction queueing or interruption semantics as known. If a correction is required, mark the herdr steering path untested and independently observe pane and hook state. **Done** = the correction's consumption is independently observed; no untested steering behavior is presented as established.

## Wait and heartbeat

Use hook waits instead of spinner-regex polling: `herdr agent wait <pane_id> --until <state> --timeout <ms>`. `--until` may be repeated for multiple states; with no `--until`, the command matches `idle`, `done`, or `blocked`.

**A blocking `wait` in a detached watcher misses transitions — make the artifact scan the outer loop.** Measured 2026-07-22, three for three: long-timeout `agent wait` calls from detached/background watchers never fired on a real working→idle transition (artifacts landed, worker idled, the wait stayed blocked), while waits whose target state was already current returned instantly. A hung wait is silent in exactly the direction that reads as "worker still busy". Unattended sentinels therefore loop on a short cycle — check on-disk artifacts first, then `herdr agent list` for state and liveness — and cap any inner `wait` at the poll interval; never hang one long-timeout `wait` as the sole wake signal. Short foreground waits (e.g. `--until working` after dispatch) remain reliable as consumption probes.

**Bare `idle` is never completion.** Count and inspect the required on-disk outputs per `SKILL.md` Stage 4. Hook state is a necessary scheduling signal, not proof of handback — in particular, the Codex hook-trust dialog can be falsely reported as `idle`.

herdr's three harness-observation surfaces: transcript → `herdr pane read <pane_id>`; foreground process → `herdr pane process-info --pane <pane_id>`; integrated hook state → `herdr agent list`. The deliverable surface remains an independent disk check under `SKILL.md` Stage 4. Report the heartbeat from these independent surfaces, not hook state alone.

## Return channel

A herdr seat is not a tmux pane, so the standard tmux pane-notification line in `SKILL.md` cannot reach it — do not promise that wire path. Use a durable mailbox plus `agent wait` and on-disk artifact counts as the available completion surfaces. A unified receipt mechanism for mixed herdr/tmux fleets is an **open question**: until designed and replayed, state this boundary in the job contract and do not present cross-harness notification as solved.

## Windows seat

herdr ships a Windows preview build. A GUI install lands under `%LOCALAPPDATA%\Programs\Herdr`, and its `bin\herdr.exe` is a **per-session virtual file** (MSIX-style projection): ssh sessions cannot see it — `dir /a` shows an empty directory and invoking the path fails with "The path cannot be traversed because it contains an untrusted mount point". This is not a broken install.

Fix (measured 2026-07-22): from the **desktop session**, copy the exe to a real path — `Copy-Item "$env:LOCALAPPDATA\Programs\Herdr\bin\herdr.exe" "$env:USERPROFILE\.local\bin\herdr.exe"` — the copy dereferences the projection. The copied CLI invoked over ssh reaches the desktop session's herdr server (named pipes cross sessions for the same user), so the full command surface works remotely: `ssh <user>@<host> 'C:\Users\<user>\.local\bin\herdr.exe workspace list'`. The server must already be running in the interactive desktop session — start the herdr app at the desktop, never over ssh. `agent start` on a freshly created workspace can race and time out once (observed on macOS too); one retry with identical args is normal recovery, not a failure signal. **Done** = the ssh-invoked CLI returns workspace JSON and a create → close round-trip succeeds from the remote side.

## Close and worktrees

`herdr workspace close <id>` deletes the workspace, kills all its processes, and removes its scrollback — not recoverable. The LAST tab in a workspace refuses `tab close` (`tab_close_failed`) — retiring a whole fleet ends with `workspace close`, not a final tab close (measured 2026-07-23). Before closing: capture the final screen, confirm required artifacts are in their source of truth, and resolve any unpushed worktree branch before allowing its directory to be deleted. The field test left no orphan process after close.

herdr supports native worktree workspaces through `herdr worktree create` (TUI: `prefix+shift+g`). Closing one may ask whether to delete the worktree directory — push an unpushed branch cleanly before closing, subject to the outward-action authority in `SKILL.md`; do not approve directory deletion while branch state remains only there. Non-destructive exit: `prefix q` detaches; `prefix+shift+x` closes a tab.
