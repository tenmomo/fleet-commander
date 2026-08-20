#!/usr/bin/env python3
"""return-channel v2 — typed durable task ledger for fleet-commander.

Backward-compatible superset of the four-verb v1 handback helper. The original
interface is untouched:

  register  a dispatched task's return contract (task_id, worker_pane, reply_to)
  return    a terminal result: durable envelope FIRST, then a one-line pane wake-up.
            The wake wire is fabric-detected from the pane token: herdr pane ids
            (`w6C:p7`, the $HERDR_PANE_ID shape) go over the herdr socket API;
            anything else takes the legacy tmux wire.
  pending   the returns awaiting a given parent pane (unacknowledged)
  ack       verify-then-close a return; idempotent by task_id

v2 adds a small file-backed control plane (GRAPH-ENG-AGENTS.md §4.4) on top of the
same mailbox, WITHOUT changing any v1 CLI syntax, output, or path semantics:

  transition    drive the typed state machine with an expected-prior + monotonic-seq
                guard (idempotent, rejects stale/out-of-order writeback). REFUSES
                `--to published` — that state is reachable ONLY via publish-task.
  heartbeat     refresh a task's lease (liveness); never changes state
  publish-task  verify all result_paths -> sha256 -> atomically commit `published`
                snapshot + event -> wake parent; ALL-OR-NOTHING (missing path =>
                zero side effects, even for a lease-expired task). Fuses "artifact
                landed + published event + wake". The atomic commit is the ledger.json
                SNAPSHOT (mkstemp+fsync+os.replace), NOT the artifact bytes — result
                artifacts stay under the worker's out/.staging->mv discipline, and a
                result_path may be a file OR a directory (tree-hashed).
  status/list   machine-readable (JSON) queries; join decisions read ledger state
                only, never "directory is non-empty".

All `--*-paths` flags (--owned-paths, --result-paths, --depends-on) take ONE
comma-separated argument, e.g. `--result-paths a.py,b.md` — NOT a repeated flag.

State machine (§4.4). The arrows below are EXACTLY the edges `transition` accepts
(kept in sync with the EDGES table); every other move is refused. `published` is the
one state `transition` will NOT enter — only `publish-task` writes it. `heartbeat`
is a dispatched/started/waiting self-loop that only refreshes the lease. retry/
reassign = `transition --to dispatched` from failed/lost/blocked/waiting (attempt+1);
abort = `transition --to aborted` (terminal, from ANY active state).

  registered ─▶ dispatched ─▶ started ══(publish-task)══▶ published ─▶ verified ─▶ acked
       │            │  ▲  └─ heartbeat (lease refresh; no state change)      │
       │            │  └──────────── retry / reassign (→ dispatched)         └─▶ aborted
       └─▶ waiting / blocked ─┘   failed / lost ─▶ dispatched | aborted
  (any active state) ─▶ aborted   ·   ══ = publish-task only, never `transition`

FOUR separate, never-conflated vocabularies:
  status  (transport/lifecycle) : done | blocked | needs_approval | failed
  outcome (domain review verdict): approved | changes_requested | informational
  decision (Mastermind, on ACK)  : continue_local_changes | merge | revise | abort
  state   (§4.4 state machine)   : registered | dispatched | started | waiting |
                                   blocked | published | verified | acked | failed |
                                   lost | aborted
The tokens `blocked`/`failed` deliberately appear in BOTH `status` and `state`
(the §4.4 diagram names states that way) — but they live in distinct fields and
are never written across. `status`/`outcome`/`decision` are v1 transport fields on
the return envelope; `state` is the v2 ledger field. They are not interchangeable.

Storage per task (mailbox/<task_id>/):
  contract.json   v1 return contract (unchanged)
  return.json     v1 terminal envelope (unchanged)
  ack.json        v1 acknowledgment (unchanged)
  ledger.json     v2 atomic typed snapshot (the read cache)
  events.jsonl    v2 append-only audit log, one line per transition (the truth trail)

Durable truth lives in the mailbox (default $FLEET_RETURN_MAILBOX, legacy
$TMUX_RETURN_MAILBOX, or
$TMPDIR/fleet-commander/mailbox, always OUTSIDE any repo). Notifications are only
hints: a failed wake-up is non-fatal; the durable record stays discoverable.
stdlib only; single file; invoked as `python3 .../return-channel.py <verb> ...`.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

# --- v1 transport vocabularies (unchanged) ---------------------------------
# Transport/lifecycle status — did the return arrive and terminate. NEVER carries a
# review verdict (a live case once emitted status=CHANGES_REQUESTED — that is an OUTCOME).
STATUSES = ("done", "blocked", "needs_approval", "failed")
# Domain review outcome — the verdict ON the work, separate from transport.
OUTCOMES = ("approved", "changes_requested", "informational")
# Mastermind decision the root commander may attach to a durable ACK.
DECISIONS = ("continue_local_changes", "merge", "revise", "abort")

# --- v2 state machine (§4.4) -----------------------------------------------
STATES = (
    "registered", "dispatched", "started", "waiting", "blocked",
    "published", "verified", "acked", "failed", "lost", "aborted",
)
# Terminal => task is no longer active; releases any owned_paths claim.
TERMINAL_STATES = frozenset({"acked", "aborted"})
# States where a live worker is expected to be heartbeating; ONLY these auto-flip to
# `lost` on lease expiry. waiting/blocked are deliberate pauses, never auto-lost.
RUNNING_STATES = frozenset({"dispatched", "started"})
# Allowed `transition` edges — this table is now the SINGLE source of truth for what
# the `transition` verb accepts, and `--help` renders the same graph (H4). `published`
# is DELIBERATELY absent from every source set: it is entered ONLY by `publish-task`
# (H3), which uses PUBLISH_SOURCES below — not EDGES — to decide legality. Still refuses
# nonsense (a lost task cannot jump anywhere but dispatched/aborted).
EDGES = {
    "registered": frozenset({"dispatched", "started", "waiting", "blocked", "failed", "lost", "aborted"}),
    "dispatched": frozenset({"started", "waiting", "blocked", "failed", "lost", "aborted"}),
    "started":    frozenset({"started", "waiting", "blocked", "failed", "lost", "aborted"}),
    "waiting":    frozenset({"dispatched", "started", "blocked", "failed", "lost", "aborted"}),
    "blocked":    frozenset({"dispatched", "started", "failed", "lost", "aborted"}),
    "published":  frozenset({"verified", "failed", "blocked", "aborted"}),
    "verified":   frozenset({"acked", "aborted"}),
    "acked":      frozenset(),
    "failed":     frozenset({"dispatched", "aborted"}),
    "lost":       frozenset({"dispatched", "aborted"}),
    "aborted":    frozenset(),
}
# The states publish-task may legally enter `published` FROM. Mirrors the old EDGES
# "-> published" reachability (incl. verified, i.e. re-publish after verify) so H3
# removes the `transition` bypass WITHOUT changing which states can actually publish.
PUBLISH_SOURCES = frozenset({"registered", "dispatched", "started", "waiting", "blocked", "verified"})
DEFAULT_LEASE_SECONDS = 900

# --- H1 mailbox-level mutex (concurrency) ----------------------------------
# One advisory flock on `<mailbox>/.lock` serializes every scan->read->modify->write
# critical section (register / transition / heartbeat / publish-task / lazy migration
# via status,list). fcntl.flock is released by the kernel when the fd is closed OR the
# holder dies, so a crash-while-holding never deadlocks. A live-but-stuck holder is
# bounded by a timeout (LOCK_EX|LOCK_NB poll loop against a real-clock deadline) that
# `_die`s instead of blocking forever. stdlib-only; the .lock file is invisible to all
# task scans (it is a file, not a <task_id>/ dir with contract/ledger).
_LOCK_FILE = ".lock"
DEFAULT_LOCK_TIMEOUT = 10.0
_LOCK_POLL_SECONDS = 0.05

TASK_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
# Pane whitelist: unicode word chars (CJK session names like 方法论/编排skill) + : . _ -
# A leading '-' (tmux flag) and all shell/whitespace metachars are rejected in valid_pane().
PANE_RE = re.compile(r"^[\w:._-]{1,128}$", re.UNICODE)


def _now():
    # Single time source so tests can freeze the clock (lease expiry, updated_at)
    # deterministically via FLEET_LEDGER_NOW; unset in production => wall clock.
    v = os.environ.get("FLEET_LEDGER_NOW")
    if v:
        try:
            return float(v)
        except ValueError:
            pass
    return time.time()


def _default_mailbox():
    env = os.environ.get("FLEET_RETURN_MAILBOX") or os.environ.get("TMUX_RETURN_MAILBOX")
    if env:
        return env
    tmp = os.environ.get("TMPDIR", "/tmp").rstrip("/")
    return os.path.join(tmp, "fleet-commander", "mailbox")


def _canon(p):
    """Canonical form of a stored path: expanduser + abspath (normalizes '.', '..',
    duplicate slashes, and makes it absolute). Deliberately NOT realpath — see H2 in
    DESIGN-HARDENING.md: realpath resolves symlinks against live filesystem state, so a
    result_path that does not yet exist at register time could resolve DIFFERENTLY at
    publish time and break the register==publish equality contract. abspath/expanduser
    is a pure, filesystem-state-independent canonical form, so both sides compare stably."""
    return os.path.abspath(os.path.expanduser(p))


def _lock_path(mailbox):
    return os.path.join(mailbox, _LOCK_FILE)


def _lock_timeout():
    v = os.environ.get("FLEET_LEDGER_LOCK_TIMEOUT")
    if v:
        try:
            return float(v)
        except ValueError:
            pass
    return DEFAULT_LOCK_TIMEOUT


@contextlib.contextmanager
def _mailbox_lock(mailbox):
    """Hold the mailbox-wide advisory lock for one critical section (H1). Blocks other
    writers; bounded by _lock_timeout() so a stuck holder never deadlocks callers (we
    poll LOCK_EX|LOCK_NB against a MONOTONIC deadline — the FLEET_LEDGER_NOW test clock
    must not warp the timeout). Callers acquire this ONCE at the cmd level; helpers
    assume it is already held and never re-acquire (flock is per-open-fd, so a nested
    acquire in the same process would self-deadlock)."""
    os.makedirs(mailbox, exist_ok=True)
    fd = os.open(_lock_path(mailbox), os.O_CREAT | os.O_RDWR, 0o600)
    timeout = _lock_timeout()
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    _die("mailbox lock timeout after %.2fs (held by another process): %s"
                         % (timeout, mailbox))
                time.sleep(_LOCK_POLL_SECONDS)
        yield
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)


def valid_task_id(s):
    # task_id becomes a directory name (mailbox/<task_id>), so reject the
    # filesystem-special all-dots names ('.', '..', '...') that would escape the
    # mailbox or hide a return from the pending scan. Slashes are already excluded
    # by TASK_RE, bounding any traversal — this closes the one-level dot escape.
    if not s or s.strip(".") == "" or not TASK_RE.match(s):
        return False
    return True


def valid_pane(s):
    if not s or s.startswith("-") or len(s) > 128:
        return False
    # tmux pane IDs are immortal within a server and therefore safer than
    # renumberable session:window.pane coordinates for stored contracts.
    if re.fullmatch(r"%[0-9]+", s):
        return True
    if any(c in s for c in " \t\n\r\f\v;|&$`'\"\\<>(){}[]*?!#~%"):
        return False
    return bool(PANE_RE.match(s))


def valid_result_path(s):
    # spaces allowed (stored path); newlines/nulls rejected (injection guard).
    return "\n" not in s and "\r" not in s and "\0" not in s


def _die(msg, code=2):
    sys.stderr.write("return-channel: " + msg + "\n")
    sys.exit(code)


def atomic_write_json(path, obj):
    """temp-write + fsync + rename: no partial envelope can ever look complete.
    This is the concrete realization of the §4.4 "staging -> 原子 mv" commit."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic within one filesystem
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _task_dir(mailbox, task_id):
    return os.path.join(mailbox, task_id)


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _emit(obj):
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))


def _split_csv(s):
    if s is None:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


# herdr pane ids look like `w6C:p7` — the exact shape of $HERDR_PANE_ID inside any
# herdr pane. Detection is by shape: a token matching this is routed over the herdr
# socket API; everything else takes the legacy tmux wire (archived fabric, kept so
# old contracts and rare tmux seats still work).
HERDR_PANE_RE = re.compile(r"^w[0-9A-Za-z]+:p[0-9A-Za-z]+$")


def _herdr_detail(r):
    # herdr CLI errors arrive as JSON on stdout ({"error":{"code":…,"message":…}});
    # fall back to stderr for exec-level failures.
    return (r.stdout.strip() or r.stderr.strip())


def notify_pane(pane, line, socket=None):
    """One trusted line, then a SEPARATE Enter — never worker prose. Fabric is
    detected from the pane token: `wX:pY` ($HERDR_PANE_ID shape) goes over the herdr
    socket API; anything else takes the archived tmux wire. Returns (ok, detail).
    Any failure — including the fabric binary being absent — is non-fatal."""
    if HERDR_PANE_RE.match(pane):
        cmds = (["herdr", "pane", "send-text", pane, line],
                ["herdr", "pane", "send-keys", pane, "enter"])
        detail_of = _herdr_detail
    else:
        base = ["tmux"] + (["-S", socket] if socket else [])
        cmds = (base + ["send-keys", "-t", pane, "-l", line],
                base + ["send-keys", "-t", pane, "C-m"])
        detail_of = lambda r: r.stderr.strip()
    try:
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                return False, detail_of(r)
    except OSError as e:  # fabric binary missing / not executable — stay non-fatal
        return False, str(e)
    return True, ""


# ---- ledger helpers --------------------------------------------------------

def _ledger_path(td):
    return os.path.join(td, "ledger.json")


def _events_path(td):
    return os.path.join(td, "events.jsonl")


def append_event(td, event):
    """Append ONE JSON line to the per-task event log. Append-only, never rewritten:
    the log is the audit trail (why every edge was taken); the ledger snapshot is a
    derived read cache. fsync so a recorded transition survives a crash."""
    os.makedirs(td, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with open(_events_path(td), "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def _new_ledger(task_id, parent, worker, **kw):
    now = _now()
    return {
        "task_id": task_id,
        "parent": parent,                                  # reply_to pane (return edge endpoint)
        "worker": worker,                                  # worker pane
        "attempt": kw.get("attempt", 1),
        "state": kw.get("state", "registered"),
        "seq": kw.get("seq", 1),
        "created_at": kw.get("created_at", now),
        "updated_at": now,
        "lease_until": kw.get("lease_until"),
        "job_path": kw.get("job_path"),
        "result_paths": list(kw.get("result_paths") or []),
        "owned_paths": list(kw.get("owned_paths") or []),
        "base_sha": kw.get("base_sha"),
        "depends_on": list(kw.get("depends_on") or []),
        "retry_policy": kw.get("retry_policy"),
        "outcome": kw.get("outcome"),
        "artifact_hashes": dict(kw.get("artifact_hashes") or {}),
        "unverifiable": list(kw.get("unverifiable") or []),
    }


def _synthesize_state_from_legacy(td, env):
    """Map a v1-only task (contract/return/ack, no ledger) onto a §4.4 state."""
    if os.path.isfile(os.path.join(td, "ack.json")):
        return "acked"
    if env is not None:
        return {"done": "published", "failed": "failed",
                "blocked": "blocked", "needs_approval": "waiting"}.get(
                    env.get("status"), "published")
    return "registered"


def _load_or_migrate_ledger(mailbox, task_id, migrate=True):
    """Return (ledger_dict, task_dir) or (None, task_dir).

    A v2 task has ledger.json. A v1-only task (registered by the old binary) has
    just contract.json/return.json/ack.json — on first touch by a v2 verb we
    lazily synthesize a ledger from those envelopes and (if migrate) persist it,
    honoring "旧格式信封 ... 首次触碰时惰性迁移"."""
    td = _task_dir(mailbox, task_id)
    lp = _ledger_path(td)
    if os.path.isfile(lp):
        try:
            return _read_json(lp), td
        except (OSError, ValueError):
            pass  # corrupt snapshot -> fall through and rebuild from envelopes
    cpath = os.path.join(td, "contract.json")
    if not os.path.isfile(cpath):
        return None, td
    try:
        contract = _read_json(cpath)
    except (OSError, ValueError):
        return None, td
    env = None
    rpath = os.path.join(td, "return.json")
    if os.path.isfile(rpath):
        try:
            env = _read_json(rpath)
        except (OSError, ValueError):
            env = None
    state = _synthesize_state_from_legacy(td, env)
    result_paths, outcome = [], None
    if env is not None:
        outcome = env.get("outcome")
        if env.get("result_path"):
            result_paths = [env["result_path"]]
    L = _new_ledger(task_id, contract.get("reply_to"), contract.get("worker_pane"),
                    state=state, created_at=contract.get("created_at", _now()),
                    result_paths=result_paths, outcome=outcome)
    if migrate:
        atomic_write_json(lp, L)
        append_event(td, {"seq": L["seq"], "ts": _now(), "event": "migrated",
                          "from": None, "to": state, "attempt": L["attempt"],
                          "actor": "migration",
                          "note": "lazy migration from legacy envelope"})
    return L, td


def _apply_lease_expiry(td, L):
    """Query-side `lost` detection. An expired lease on a RUNNING task flips it to
    `lost` and records the fact — and NOTHING else. It NEVER retries a side effect
    or redispatches; recovery is a human decision (§4.4: "过期只标 lost")."""
    if (L["state"] in RUNNING_STATES and L.get("lease_until") is not None
            and L["lease_until"] < _now()):
        prev, new_seq = L["state"], L["seq"] + 1
        L["state"], L["seq"], L["updated_at"] = "lost", new_seq, _now()
        atomic_write_json(_ledger_path(td), L)
        append_event(td, {"seq": new_seq, "ts": _now(), "event": "lost",
                          "from": prev, "to": "lost", "attempt": L["attempt"],
                          "actor": "query", "note": "lease expired"})
    return L


def _norm(p):
    return os.path.normpath(p).rstrip("/") or "/"


def _paths_overlap(a, b):
    """True if two owned paths collide: equal, or one is an ancestor dir of the
    other. Compared component-wise so 'src' overlaps 'src/foo' but 's' does not."""
    a, b = _norm(a), _norm(b)
    if a == b:
        return True
    ap, bp = a.split(os.sep), b.split(os.sep)
    n = min(len(ap), len(bp))
    return ap[:n] == bp[:n]


def _find_owned_conflicts(mailbox, self_task, owned_paths):
    """List (other_task, their_path, requested_path) for every ACTIVE task whose
    owned_paths overlaps a requested path. Terminal (acked/aborted) tasks have
    released their claims; a `lost` task still holds them (its tree state is
    unknown — only a human abort/ack may release it)."""
    conflicts = []
    if not os.path.isdir(mailbox):
        return conflicts
    for name in sorted(os.listdir(mailbox)):
        if name == self_task:
            continue
        lp = _ledger_path(os.path.join(mailbox, name))
        if not os.path.isfile(lp):
            continue  # v1/bare tasks declare no owned_paths => cannot conflict
        try:
            L = _read_json(lp)
        except (OSError, ValueError):
            continue
        if L.get("state") in TERMINAL_STATES:
            continue
        for op in L.get("owned_paths") or []:
            for np in owned_paths:
                if _paths_overlap(op, np):
                    conflicts.append((L.get("task_id", name), op, np))
    return conflicts


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_path(path):
    """sha256 of a file, or a stable tree digest of a directory (sorted relpath +
    per-file hash) so a result_path may be a produced directory of artifacts."""
    if os.path.isdir(path):
        h = hashlib.sha256()
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for fn in sorted(files):
                fp = os.path.join(root, fn)
                h.update(os.path.relpath(fp, path).encode("utf-8") + b"\0")
                h.update(_sha256_file(fp).encode("ascii") + b"\n")
        return "tree:" + h.hexdigest()
    return _sha256_file(path)


def _iter_all_task_names(mailbox):
    if not os.path.isdir(mailbox):
        return
    for name in sorted(os.listdir(mailbox)):
        td = os.path.join(mailbox, name)
        if os.path.isfile(_ledger_path(td)) or os.path.isfile(os.path.join(td, "contract.json")):
            yield name


# ---- v1 verbs (behavior + output byte-compatible) --------------------------

def cmd_register(a):
    if not valid_task_id(a.task):
        _die("invalid task id %r (allowed: [A-Za-z0-9._-], <=128)" % a.task)
    for name, pane in (("worker-pane", a.worker_pane), ("reply-to", a.reply_to)):
        if not valid_pane(pane):
            _die("invalid %s pane %r (shell/newline/leading-dash rejected)" % (name, pane))
    # Validate raw (reject newline/null) BEFORE canonicalizing, then pin owned +
    # result paths to a stable canonical form (H2): expanduser+abspath, so owned
    # conflict detection and the publish-task register==publish equality check both
    # compare like-for-like regardless of ~ / relative / ./ spelling differences.
    owned_raw = _split_csv(a.owned_paths)
    for op in owned_raw:
        if not valid_result_path(op):
            _die("invalid owned path (newline/null rejected): %r" % op)
    owned = [_canon(op) for op in owned_raw]
    result_paths = [_canon(rp) for rp in _split_csv(a.result_paths)]
    depends_on = _split_csv(a.depends_on)
    td = _task_dir(a.mailbox, a.task)
    # H1: the entire scan->stale-wipe->contract->ledger critical section runs under one
    # mailbox lock, so two concurrent registers of the same owned path can never both
    # observe "no conflict" and both win (the TOCTOU double-register the un-locked scan
    # allowed). A bare v1 register (no owned_paths) still takes the lock, but its output
    # and on-disk result are byte-identical to v1 — the lock is invisible.
    with _mailbox_lock(a.mailbox):
        # --- owned_paths conflict GATE: reject BEFORE any side effect (no contract
        #     write, no stale wipe). Without --owned-paths this is skipped entirely,
        #     so a bare register is byte-identical to v1.
        if owned:
            conflicts = _find_owned_conflicts(a.mailbox, a.task, owned)
            if conflicts:
                sys.stderr.write("return-channel: register REJECTED — owned_paths conflict:\n")
                for other, op, np in conflicts:
                    sys.stderr.write("  task %s owns %s (overlaps requested %s)\n" % (other, op, np))
                _die("owned_paths conflict with active task(s): %s"
                     % ", ".join(sorted({c[0] for c in conflicts})))
        # Upsert = a NEW dispatch generation: any envelope from the previous generation
        # is void and must not survive to impersonate the new worker's return, or be
        # re-bound to the new reply_to by the pending scan. Warn on stderr so a
        # discarded stale return is seen. (v1 behavior, preserved verbatim.)
        for stale in ("return.json", "ack.json"):
            sp = os.path.join(td, stale)
            if os.path.exists(sp):
                sys.stderr.write("return-channel: register discarding stale %s for %r\n"
                                 % (stale, a.task))
                os.remove(sp)
        contract = {
            "task_id": a.task,
            "worker_pane": a.worker_pane,
            "reply_to": a.reply_to,
            "created_at": _now(),
        }
        atomic_write_json(os.path.join(td, "contract.json"), contract)
        # --- ledger: advance an existing one (new generation), else create it ONLY if
        #     new-flow fields were supplied. A bare v1 register leaves no ledger.json.
        lp = _ledger_path(td)
        existing = None
        if os.path.isfile(lp):
            try:
                existing = _read_json(lp)
            except (OSError, ValueError):
                existing = None
        new_flow = bool(owned or result_paths or depends_on or a.job_path
                        or a.base_sha or a.retry_policy)
        if existing is not None:
            attempt = int(existing.get("attempt", 1)) + 1
            seq = int(existing.get("seq", 0)) + 1
            L = _new_ledger(a.task, a.reply_to, a.worker_pane,
                            attempt=attempt, seq=seq, state="registered",
                            created_at=existing.get("created_at", _now()),
                            owned_paths=owned or existing.get("owned_paths"),
                            result_paths=result_paths or existing.get("result_paths"),
                            depends_on=depends_on or existing.get("depends_on"),
                            job_path=a.job_path or existing.get("job_path"),
                            base_sha=a.base_sha or existing.get("base_sha"),
                            retry_policy=a.retry_policy or existing.get("retry_policy"))
            atomic_write_json(lp, L)
            append_event(td, {"seq": seq, "ts": _now(), "event": "registered",
                              "from": existing.get("state"), "to": "registered",
                              "attempt": attempt, "actor": "commander",
                              "note": "re-register (new dispatch generation)"})
        elif new_flow:
            L = _new_ledger(a.task, a.reply_to, a.worker_pane,
                            owned_paths=owned, result_paths=result_paths,
                            depends_on=depends_on, job_path=a.job_path,
                            base_sha=a.base_sha, retry_policy=a.retry_policy)
            atomic_write_json(lp, L)
            append_event(td, {"seq": 1, "ts": _now(), "event": "registered",
                              "from": None, "to": "registered", "attempt": 1,
                              "actor": "commander", "note": "register"})
    print(td)  # UNCHANGED v1 output: the task dir path


def cmd_return(a):
    if not valid_task_id(a.task):
        _die("invalid task id %r" % a.task)
    if a.status not in STATUSES:
        _die("invalid status %r (allowed: %s)" % (a.status, "|".join(STATUSES)))
    td = _task_dir(a.mailbox, a.task)
    cpath = os.path.join(td, "contract.json")
    if not os.path.exists(cpath):
        _die("no registered contract for task %r (register first)" % a.task)
    contract = _read_json(cpath)
    reply_to = contract.get("reply_to")
    if not reply_to or not valid_pane(reply_to):
        _die("contract reply_to pane %r is invalid or missing" % reply_to)
    if a.outcome is not None and a.outcome not in OUTCOMES:
        _die("invalid outcome %r (allowed: %s)" % (a.outcome, "|".join(OUTCOMES)))
    result = a.result
    if result is not None and not valid_result_path(result):
        _die("invalid result path (newline rejected)")
    report = a.report
    if a.report_file:
        with open(a.report_file, encoding="utf-8") as f:
            report = f.read()
    envelope = {
        "task_id": a.task,
        "status": a.status,          # transport/lifecycle only
        "outcome": a.outcome,        # domain verdict, separate (may be None)
        "result_path": result,
        "reply_to": reply_to,
        "worker_pane": contract.get("worker_pane"),
        "report": report,            # full prose lives ONLY here, on disk
        "returned_at": _now(),
    }
    # 1) durable FIRST (idempotent: same task_id overwrites one envelope atomically)
    atomic_write_json(os.path.join(td, "return.json"), envelope)
    # A re-return supersedes any earlier acknowledgment. Without this, a task
    # acked `revise` comes back INVISIBLE to `pending` — the wire line is then the
    # only wake-up, and a missed notification sleeps forever.
    try:
        os.remove(os.path.join(td, "ack.json"))
    except FileNotFoundError:
        pass
    # 2) then the wake-up hint — trusted enumerated fields + a pointer only
    notified, detail = (False, "skipped")
    if not a.no_notify:
        outc = "" if a.outcome is None else " outcome=%s" % a.outcome
        line = "[RETURN task=%s status=%s%s result=%s]" % (
            a.task, a.status, outc, result if result else "-")
        notified, detail = notify_pane(reply_to, line, a.socket)
        if not notified:
            sys.stderr.write(
                "return-channel: notify %s failed (%s); envelope pending\n"
                % (reply_to, detail or "unknown"))
    print(json.dumps({"task_id": a.task, "status": a.status,
                      "outcome": a.outcome, "durable": True,
                      "notified": notified,
                      "envelope": os.path.join(td, "return.json")},
                     ensure_ascii=False))


def _iter_tasks(mailbox):
    if not os.path.isdir(mailbox):
        return
    for name in sorted(os.listdir(mailbox)):
        td = os.path.join(mailbox, name)
        cpath = os.path.join(td, "contract.json")
        if os.path.isfile(cpath):
            yield td, cpath


def cmd_pending(a):
    if not valid_pane(a.reply_to):
        _die("invalid reply-to pane %r" % a.reply_to)
    rows = []
    for td, cpath in _iter_tasks(a.mailbox):
        rpath = os.path.join(td, "return.json")
        if not os.path.isfile(rpath):
            continue                                  # returned? not yet
        if os.path.isfile(os.path.join(td, "ack.json")):
            continue                                  # already acknowledged/closed
        try:
            contract = _read_json(cpath)
            env = _read_json(rpath)
        except (OSError, ValueError):
            continue
        if contract.get("reply_to") != a.reply_to:
            continue                                  # scoped to THIS parent only
        rows.append(env)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False))
    else:
        for env in rows:
            print("task=%s status=%s outcome=%s result=%s" % (
                env["task_id"], env["status"],
                env.get("outcome") or "(no outcome)",
                env.get("result_path") or "(no result)"))
    return rows


def cmd_ack(a):
    if not valid_task_id(a.task):
        _die("invalid task id %r" % a.task)
    if a.decision is not None and a.decision not in DECISIONS:
        _die("invalid decision %r (allowed: %s)" % (a.decision, "|".join(DECISIONS)))
    td = _task_dir(a.mailbox, a.task)
    rpath = os.path.join(td, "return.json")
    if not os.path.isfile(rpath):
        _die("no return to acknowledge for task %r" % a.task)
    atomic_write_json(os.path.join(td, "ack.json"),
                      {"task_id": a.task, "acknowledged": True,
                       "decision": a.decision,     # trusted Mastermind decision (may be None)
                       "acked_at": _now()})        # idempotent: overwrites in place
    print("acked %s%s" % (a.task, "" if a.decision is None else " decision=%s" % a.decision))


# ---- v2 verbs --------------------------------------------------------------

def cmd_transition(a):
    if not valid_task_id(a.task):
        _die("invalid task id %r" % a.task)
    if a.to not in STATES:
        _die("invalid state %r (allowed: %s)" % (a.to, "|".join(STATES)))
    if a.from_state is not None and a.from_state not in STATES:
        _die("invalid --from state %r" % a.from_state)
    if a.outcome is not None and a.outcome not in OUTCOMES:
        _die("invalid outcome %r (allowed: %s)" % (a.outcome, "|".join(OUTCOMES)))
    if a.decision is not None and a.decision not in DECISIONS:
        _die("invalid decision %r (allowed: %s)" % (a.decision, "|".join(DECISIONS)))
    if a.worker is not None and not valid_pane(a.worker):
        _die("invalid worker pane %r" % a.worker)
    with _mailbox_lock(a.mailbox):  # H1: load->decide->write is one atomic section
        L, td = _load_or_migrate_ledger(a.mailbox, a.task)
        if L is None:
            _die("no ledger/contract for task %r (register first)" % a.task)
        L = _apply_lease_expiry(td, L)  # reflect reality before deciding the edge
        cur, cur_seq, to = L["state"], L["seq"], a.to
        # Idempotent replay: already in the target state -> no-op success, no new event.
        if cur == to:
            _emit(L)
            return
        if a.from_state is not None and cur != a.from_state:
            _die("wrong prior state: expected %s, current %s (task %s)"
                 % (a.from_state, cur, a.task))
        if to not in EDGES.get(cur, frozenset()):
            # H3: `published` is not an edge in EDGES at all; refuse it with a targeted
            # message (placed inside the illegal-edge branch, AFTER the wrong-prior
            # check, so callers that assert a prior still get the prior-mismatch error).
            if to == "published":
                _die("transition --to published is refused (H3): `published` is entered "
                     "ONLY via publish-task, which verifies+hashes all result_paths "
                     "(task %s, current %s)" % (a.task, cur))
            _die("illegal transition %s -> %s (task %s)" % (cur, to, a.task))
        if a.seq is not None:
            if a.seq <= cur_seq:
                _die("stale seq %d (current %d) for task %s" % (a.seq, cur_seq, a.task))
            new_seq = a.seq
        else:
            new_seq = cur_seq + 1
        # optional field updates carried by this transition
        if a.worker is not None:
            L["worker"] = a.worker
        if a.outcome is not None:
            L["outcome"] = a.outcome
        if a.base_sha is not None:
            L["base_sha"] = a.base_sha
        if a.result_paths is not None:
            L["result_paths"] = _split_csv(a.result_paths)
        if a.unverifiable is not None:
            L["unverifiable"] = _split_csv(a.unverifiable)
        if a.lease_seconds is not None:
            L["lease_until"] = _now() + a.lease_seconds
        # retry/reassign back into dispatched bumps the attempt counter
        if to == "dispatched" and cur in ("failed", "lost", "blocked", "waiting"):
            L["attempt"] = L["attempt"] + 1
        if a.attempt is not None:
            L["attempt"] = a.attempt
        L["state"], L["seq"], L["updated_at"] = to, new_seq, _now()
        atomic_write_json(_ledger_path(td), L)
        append_event(td, {"seq": new_seq, "ts": _now(), "event": to,
                          "from": cur, "to": to, "attempt": L["attempt"],
                          "actor": a.actor, "note": a.note,
                          "outcome": a.outcome, "decision": a.decision})
        _emit(L)


def cmd_heartbeat(a):
    if not valid_task_id(a.task):
        _die("invalid task id %r" % a.task)
    with _mailbox_lock(a.mailbox):  # H1: load->refresh->write is one atomic section
        L, td = _load_or_migrate_ledger(a.mailbox, a.task)
        if L is None:
            _die("no ledger for task %r (register first)" % a.task)
        L = _apply_lease_expiry(td, L)
        if L["state"] not in ("dispatched", "started", "waiting"):
            _die("cannot heartbeat task %s in state %s (expected dispatched/started/waiting)"
                 % (a.task, L["state"]))
        if a.seq is not None:
            if a.seq <= L["seq"]:
                _die("stale seq %d (current %d) for task %s" % (a.seq, L["seq"], a.task))
            new_seq = a.seq
        else:
            new_seq = L["seq"] + 1
        lease = a.lease_seconds if a.lease_seconds is not None else DEFAULT_LEASE_SECONDS
        L["lease_until"], L["seq"], L["updated_at"] = _now() + lease, new_seq, _now()
        atomic_write_json(_ledger_path(td), L)
        append_event(td, {"seq": new_seq, "ts": _now(), "event": "heartbeat",
                          "from": L["state"], "to": L["state"], "attempt": L["attempt"],
                          "actor": a.actor, "note": a.note, "lease_until": L["lease_until"]})
        _emit(L)


def cmd_publish_task(a):
    if not valid_task_id(a.task):
        _die("invalid task id %r" % a.task)
    with _mailbox_lock(a.mailbox):  # H1: verify->hash->commit is one atomic section
        L, td = _load_or_migrate_ledger(a.mailbox, a.task)
        if L is None:
            _die("no ledger for task %r (register first)" % a.task)
        # --- resolve + pin result paths (NO side effects yet) ------------------
        registered = list(L.get("result_paths") or [])
        if a.result_paths is not None:
            requested = [_canon(rp) for rp in _split_csv(a.result_paths)]
            # H2: a task that REGISTERED a result set may publish ONLY that exact set.
            # Overriding it (subset/superset/substitution) is refused with the set diff —
            # this closes the "register A,B then publish only A" escape. Tasks with NO
            # registered result set keep the old behavior (publish whatever is passed).
            if registered:
                reg_canon = [_canon(rp) for rp in registered]
                if set(requested) != set(reg_canon):
                    extra = sorted(set(requested) - set(reg_canon))
                    missing_reg = sorted(set(reg_canon) - set(requested))
                    _die("publish-task: --result-paths does not match the registered "
                         "result set (H2). extra (passed, not registered)=%s ; "
                         "missing (registered, not passed)=%s" % (extra, missing_reg))
            result_paths = requested
        else:
            result_paths = [_canon(rp) for rp in registered]
        if not result_paths:
            _die("publish-task: no result paths (pass --result-paths or set them at register)")
        for rp in result_paths:
            if not valid_result_path(rp):
                _die("invalid result path (newline/null rejected): %r" % rp)
        # === H6 ALL-OR-NOTHING GATE — BEFORE any side effect, incl. lease expiry ===
        # Verify EVERY path exists before we touch the ledger AT ALL. Placing this ahead
        # of _apply_lease_expiry is the H6 fix: a lease-EXPIRED task publishing with a
        # missing path must ALSO leave zero side effects. Previously the expiry flip to
        # `lost` (snapshot + event) fired first, so a "zero side effect" abort still
        # wrote a `lost` transition. (§4.4 / hard-constraint 5 + H6.)
        missing = [rp for rp in result_paths if not os.path.exists(rp)]
        if missing:
            _die("publish-task aborted: missing result paths (zero side effects): %s"
                 % ", ".join(missing))
        hashes = {rp: _sha256_path(rp) for rp in result_paths}  # still no side effect
        # Only NOW reflect lease reality (this MAY write `lost`) and decide the edge.
        L = _apply_lease_expiry(td, L)
        cur = L["state"]
        # Idempotent re-publish: already published with the identical artifact set ->
        # re-notify only, no duplicate event.
        already = (cur == "published"
                   and L.get("artifact_hashes") == hashes
                   and sorted(L.get("result_paths") or []) == sorted(result_paths))
        if not already:
            # H3: publish-task uses PUBLISH_SOURCES (not EDGES) — `published` is no longer
            # an EDGES target, but these states may still enter it via THIS verb.
            if cur != "published" and cur not in PUBLISH_SOURCES:
                _die("illegal transition %s -> published (task %s)" % (cur, a.task))
            if a.seq is not None:
                if a.seq <= L["seq"]:
                    _die("stale seq %d (current %d) for task %s" % (a.seq, L["seq"], a.task))
                new_seq = a.seq
            else:
                new_seq = L["seq"] + 1
            prev = cur
            L["result_paths"], L["artifact_hashes"] = result_paths, hashes
            L["state"], L["seq"], L["updated_at"] = "published", new_seq, _now()
            # Atomic snapshot commit (temp+fsync+rename) THEN append the audit event.
            atomic_write_json(_ledger_path(td), L)
            append_event(td, {"seq": new_seq, "ts": _now(), "event": "published",
                              "from": prev, "to": "published", "attempt": L["attempt"],
                              "actor": a.actor, "note": a.note,
                              "artifact_hashes": hashes, "result_paths": result_paths})
        out = dict(L)
        out["ledger"] = _ledger_path(td)
        parent = L.get("parent")
        n_results = len(result_paths)
    # Wake the parent AFTER the durable commit AND after releasing the mailbox lock (a
    # hung/slow tmux must never hold the mutex) — trusted enumerated fields + counts.
    notified, detail = (False, "skipped")
    if not a.no_notify:
        if parent and valid_pane(parent):
            line = "[PUBLISHED task=%s state=published results=%d]" % (a.task, n_results)
            notified, detail = notify_pane(parent, line, a.socket)
            if not notified:
                sys.stderr.write("return-channel: publish-task notify %s failed (%s); "
                                 "ledger is durable\n" % (parent, detail or "unknown"))
    out["notified"] = notified
    _emit(out)


def cmd_status(a):
    if a.task is not None and not valid_task_id(a.task):
        _die("invalid task id %r" % a.task)
    # A query on a non-existent mailbox has nothing to migrate/expire; never create the
    # mailbox (or its .lock) as a side effect of a pure read.
    if not os.path.isdir(a.mailbox):
        if a.task is not None:
            _die("no such task %r" % a.task)
        _emit([])
        return
    # H1: lazy migration + lease-expiry both WRITE, so status holds the lock too.
    with _mailbox_lock(a.mailbox):
        if a.task is not None:
            L, td = _load_or_migrate_ledger(a.mailbox, a.task)
            if L is None:
                _die("no such task %r" % a.task)
            _emit(_apply_lease_expiry(td, L))
            return
        rows = []
        for name in _iter_all_task_names(a.mailbox):
            L, td = _load_or_migrate_ledger(a.mailbox, name)
            if L is None:
                continue
            rows.append(_apply_lease_expiry(td, L))
        _emit(rows)


def cmd_list(a):
    if a.state is not None and a.state not in STATES:
        _die("invalid --state %r (allowed: %s)" % (a.state, "|".join(STATES)))
    if not os.path.isdir(a.mailbox):
        _emit([])
        return
    with _mailbox_lock(a.mailbox):  # H1: lazy migration + lease-expiry are writes
        rows = []
        for name in _iter_all_task_names(a.mailbox):
            L, td = _load_or_migrate_ledger(a.mailbox, name)
            if L is None:
                continue
            L = _apply_lease_expiry(td, L)
            if a.state is not None and L["state"] != a.state:
                continue
            if a.parent is not None and L.get("parent") != a.parent:
                continue
            rows.append({k: L.get(k) for k in (
                "task_id", "state", "seq", "attempt", "parent", "worker",
                "lease_until", "updated_at", "result_paths", "owned_paths", "outcome")})
        _emit(rows)


# ---- CLI -------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="return-channel", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mailbox", default=_default_mailbox(),
                   help="mailbox root (default: $FLEET_RETURN_MAILBOX / legacy "
                        "$TMUX_RETURN_MAILBOX / $TMPDIR/fleet-commander/mailbox)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="register a dispatched task's return contract")
    r.add_argument("--task", required=True)
    r.add_argument("--worker-pane", required=True)
    r.add_argument("--reply-to", required=True)
    # v2 optional fields (all default None -> a bare register stays v1-identical)
    r.add_argument("--owned-paths", help="ONE comma-separated arg: paths this task owns "
                   "(canonicalized, conflict-checked vs active tasks), e.g. a/b,c/d")
    r.add_argument("--result-paths", help="ONE comma-separated arg: expected result paths "
                   "(canonicalized; pins the set publish-task may later publish, H2)")
    r.add_argument("--depends-on", help="ONE comma-separated arg: task_ids this task depends on")
    r.add_argument("--job-path", help="path to the job file (node contract)")
    r.add_argument("--base-sha", help="git base SHA the worker branches from")
    r.add_argument("--retry-policy", help="opaque retry-policy tag")
    r.set_defaults(func=cmd_register)

    rt = sub.add_parser("return", help="return a terminal result (durable, then notify)")
    rt.add_argument("--task", required=True)
    rt.add_argument("--status", required=True, help="transport: " + "|".join(STATUSES))
    rt.add_argument("--outcome", help="domain verdict (separate from status): " + "|".join(OUTCOMES))
    rt.add_argument("--result", help="path to the result/report artifact")
    g = rt.add_mutually_exclusive_group()
    g.add_argument("--report", help="short report text (stored in envelope only)")
    g.add_argument("--report-file", help="read report text from a file")
    rt.add_argument("--socket", help="tmux -S socket for notification (tests/isolation; "
                                     "ignored for herdr wX:pY panes)")
    rt.add_argument("--no-notify", action="store_true",
                    help="write durable envelope only, skip the pane wake-up")
    rt.set_defaults(func=cmd_return)

    pd = sub.add_parser("pending", help="list unacknowledged returns for a parent pane")
    pd.add_argument("--reply-to", required=True)
    pd.add_argument("--json", action="store_true")
    pd.set_defaults(func=cmd_pending)

    ak = sub.add_parser("ack", help="acknowledge/close a verified return (idempotent)")
    ak.add_argument("--task", required=True)
    ak.add_argument("--decision", help="trusted Mastermind decision: " + "|".join(DECISIONS))
    ak.set_defaults(func=cmd_ack)

    tr = sub.add_parser("transition", help="drive the typed state machine (guarded)")
    tr.add_argument("--task", required=True)
    tr.add_argument("--to", required=True, help="target state: " + "|".join(STATES)
                    + " (NOTE: `published` is REFUSED here — it is entered only via publish-task)")
    tr.add_argument("--from", dest="from_state", help="expected prior state (rejected if mismatched)")
    tr.add_argument("--seq", type=int, help="monotonic seq token (stale/old rejected)")
    tr.add_argument("--outcome", help="domain verdict to record: " + "|".join(OUTCOMES))
    tr.add_argument("--decision", help="human decision to record: " + "|".join(DECISIONS))
    tr.add_argument("--worker", help="reassign to a new worker pane")
    tr.add_argument("--attempt", type=int, help="override attempt counter")
    tr.add_argument("--lease-seconds", type=int, help="set lease_until = now + N")
    tr.add_argument("--base-sha")
    tr.add_argument("--result-paths", help="ONE comma-separated arg: result paths to record")
    tr.add_argument("--unverifiable", help="comma-separated items the worker could not verify")
    tr.add_argument("--note", help="free-text reason (recorded in the event log)")
    tr.add_argument("--actor", default="commander", help="who drove this transition")
    tr.set_defaults(func=cmd_transition)

    hb = sub.add_parser("heartbeat", help="refresh a running task's lease (liveness)")
    hb.add_argument("--task", required=True)
    hb.add_argument("--seq", type=int, help="monotonic seq token (stale/old rejected)")
    hb.add_argument("--lease-seconds", type=int,
                    help="lease_until = now + N (default %d)" % DEFAULT_LEASE_SECONDS)
    hb.add_argument("--note")
    hb.add_argument("--actor", default="worker")
    hb.set_defaults(func=cmd_heartbeat)

    pt = sub.add_parser("publish-task",
                        help="verify+hash all result_paths, atomically commit the `published` "
                             "LEDGER SNAPSHOT (not artifact bytes), wake parent; the ONLY way "
                             "into `published`")
    pt.add_argument("--task", required=True)
    pt.add_argument("--result-paths", help="ONE comma-separated arg: result paths (else the "
                    "ledger's). If the task registered a result set, this must equal it (H2)")
    pt.add_argument("--seq", type=int, help="monotonic seq token (stale/old rejected)")
    pt.add_argument("--socket", help="tmux -S socket for notification (tests/isolation; "
                                     "ignored for herdr wX:pY panes)")
    pt.add_argument("--no-notify", action="store_true")
    pt.add_argument("--note")
    pt.add_argument("--actor", default="worker")
    pt.set_defaults(func=cmd_publish_task)

    st = sub.add_parser("status", help="JSON snapshot of one task (--task) or all")
    st.add_argument("--task")
    st.set_defaults(func=cmd_status)

    ls = sub.add_parser("list", help="JSON list of tasks (filter --state/--parent); join reads state only")
    ls.add_argument("--state", help="filter by state: " + "|".join(STATES))
    ls.add_argument("--parent", help="filter by parent pane")
    ls.set_defaults(func=cmd_list)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
