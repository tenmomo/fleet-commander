#!/usr/bin/env python3
"""return-channel — hierarchical Worker→commander handback for fleet-commander.

Deep module, four-verb interface. Callers never touch mailbox layout, atomic
writes, quoting, pane validation, or tmux — the helper owns all of it.

  register  a dispatched task's return contract (task_id, worker_pane, reply_to)
  return    a terminal result: durable envelope FIRST, then a one-line pane wake-up
  pending   the returns awaiting a given parent pane (unacknowledged)
  ack       verify-then-close a return; idempotent by task_id

Durable truth lives in the mailbox (default $TMUX_RETURN_MAILBOX or
$TMPDIR/fleet-commander/mailbox, always OUTSIDE any repo). The notification
is only a hint: if it fails, the envelope stays discoverable via `pending`.

Three separate enums, never overloaded onto one another:
  status  (transport/lifecycle) : done | blocked | needs_approval | failed
  outcome (domain review verdict): approved | changes_requested | informational
  decision (Mastermind, on ACK)  : continue_local_changes | merge | revise | abort
A review that requests changes is `status=done outcome=changes_requested` — never
`status=CHANGES_REQUESTED`. All three are trusted enumerated fields, so the one-line
pane pointer can carry status+outcome without ever leaking worker prose.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

# Transport/lifecycle status — did the return arrive and terminate. NEVER carries a
# review verdict (a live case once emitted status=CHANGES_REQUESTED — that is an OUTCOME).
STATUSES = ("done", "blocked", "needs_approval", "failed")
# Domain review outcome — the verdict ON the work, separate from transport. Small,
# trusted, enumerated (so it can ride the one-line pointer without leaking prose).
OUTCOMES = ("approved", "changes_requested", "informational")
# Mastermind decision the root commander may attach to a durable ACK.
DECISIONS = ("continue_local_changes", "merge", "revise", "abort")
TASK_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
# Pane whitelist: Unicode word chars (pane names may use any UTF-8 script) + : . _ -
# A leading '-' (tmux flag) and all shell/whitespace metachars are rejected in valid_pane().
PANE_RE = re.compile(r"^[\w:._-]{1,128}$", re.UNICODE)


def _default_mailbox():
    env = os.environ.get("TMUX_RETURN_MAILBOX")
    if env:
        return env
    tmp = os.environ.get("TMPDIR", "/tmp").rstrip("/")
    return os.path.join(tmp, "fleet-commander", "mailbox")


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
    if any(c in s for c in " \t\n\r\f\v;|&$`'\"\\<>(){}[]*?!#~"):
        return False
    return bool(PANE_RE.match(s))


def valid_result_path(s):
    # spaces allowed (stored path); newlines/nulls rejected (injection guard).
    return "\n" not in s and "\r" not in s and "\0" not in s


def _die(msg, code=2):
    sys.stderr.write("return-channel: " + msg + "\n")
    sys.exit(code)


def atomic_write_json(path, obj):
    """temp-write + fsync + rename: no partial envelope can ever look complete."""
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


def notify_pane(pane, line, socket=None):
    """One trusted line via literal send-keys, then a SEPARATE Enter. Never the
    unnamed buffer, never worker prose. Returns (ok, detail)."""
    base = ["tmux"] + (["-S", socket] if socket else [])
    r1 = subprocess.run(base + ["send-keys", "-t", pane, "-l", line],
                        capture_output=True, text=True)
    if r1.returncode != 0:
        return False, r1.stderr.strip()
    r2 = subprocess.run(base + ["send-keys", "-t", pane, "C-m"],
                        capture_output=True, text=True)
    if r2.returncode != 0:
        return False, r2.stderr.strip()
    return True, ""


# ---- verbs -----------------------------------------------------------------

def cmd_register(a):
    if not valid_task_id(a.task):
        _die("invalid task id %r (allowed: [A-Za-z0-9._-], <=128)" % a.task)
    for name, pane in (("worker-pane", a.worker_pane), ("reply-to", a.reply_to)):
        if not valid_pane(pane):
            _die("invalid %s pane %r (shell/newline/leading-dash rejected)" % (name, pane))
    td = _task_dir(a.mailbox, a.task)
    # Upsert = a NEW dispatch generation: any envelope from the previous generation
    # is void and must not survive to impersonate the new worker's return, or be
    # re-bound to the new reply_to by the pending scan (10-model audit 2026-07-22:
    # four auditors independently hit this — "no new envelope" had documented the
    # bug as a feature). Warn on stderr so a discarded stale return is seen.
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
        "created_at": time.time(),
    }
    atomic_write_json(os.path.join(td, "contract.json"), contract)
    print(td)


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
        "returned_at": time.time(),
    }
    # 1) durable FIRST (idempotent: same task_id overwrites one envelope atomically)
    atomic_write_json(os.path.join(td, "return.json"), envelope)
    # A re-return supersedes any earlier acknowledgment. Without this, a task
    # acked `revise` comes back INVISIBLE to `pending` — the wire line is then
    # the only wake-up, and a missed notification sleeps forever (2026-07-18:
    # the S2 rebase re-return never woke the mailbox sentry).
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
            # notify failure is non-fatal: envelope stays pending & discoverable
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
                       "acked_at": time.time()})   # idempotent: overwrites in place
    print("acked %s%s" % (a.task, "" if a.decision is None else " decision=%s" % a.decision))


def build_parser():
    p = argparse.ArgumentParser(prog="return-channel", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mailbox", default=_default_mailbox(),
                   help="mailbox root (default: $TMUX_RETURN_MAILBOX or $TMPDIR/fleet-commander/mailbox)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="register a dispatched task's return contract")
    r.add_argument("--task", required=True)
    r.add_argument("--worker-pane", required=True)
    r.add_argument("--reply-to", required=True)
    r.set_defaults(func=cmd_register)

    rt = sub.add_parser("return", help="return a terminal result (durable, then notify)")
    rt.add_argument("--task", required=True)
    rt.add_argument("--status", required=True, help="transport: " + "|".join(STATUSES))
    rt.add_argument("--outcome", help="domain verdict (separate from status): " + "|".join(OUTCOMES))
    rt.add_argument("--result", help="path to the result/report artifact")
    g = rt.add_mutually_exclusive_group()
    g.add_argument("--report", help="short report text (stored in envelope only)")
    g.add_argument("--report-file", help="read report text from a file")
    rt.add_argument("--socket", help="tmux -S socket for notification (tests/isolation)")
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
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
