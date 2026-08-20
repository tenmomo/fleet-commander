#!/usr/bin/env python3
"""Stdlib-unittest coverage for return-channel v2.

Every test runs against a throwaway temp mailbox (tearDown wipes it) — the real
$TMUX_RETURN_MAILBOX / $TMPDIR mailbox is NEVER touched. The module is loaded
straight from ../return-channel.py by path (its filename has a hyphen, so it is
not importable by name). Verbs are exercised in-process through main([...]) with
stdout/stderr captured and SystemExit (from _die/argparse) turned into an exit code.

Required coverage (job hard-constraint 7):
  (1) v1 four-verb compat, incl. reading a legacy envelope
  (2) owned_paths conflict rejection
  (3) stale seq / wrong prior-state rejection
  (4) publish-task atomicity — a missing path => zero side effects
  (5) lease expiry => lost, with NO auto-retry
  (6) event log is append-only
Plus: notify failure stays non-fatal (hard-constraint 8).

v2.1 hardening coverage (job fc-harden-20260730, hard-constraint 3):
  (H1) two REAL concurrent processes registering the same owned path => exactly one
       wins, one loses (mailbox flock closes the TOCTOU double-register); plus lock
       timeout does not deadlock, and crash-while-holding auto-releases.
  (H2) publish-task --result-paths must equal the REGISTERED set (override rejected,
       with the set diff in the message); register/publish path canonicalization.
  (H3) `transition --to published` is refused (published only via publish-task); a
       lazily-migrated `published` carries a `migrated` event, never a `published` one.
  (H6) a LEASE-EXPIRED task publishing with a missing path leaves zero side effects —
       specifically NO `lost` transition is written.
  (H5) one command (`unittest discover` over this dir) also runs the v1 interface test.
"""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODPATH = os.path.join(_HERE, os.pardir, "return-channel.py")
_V1_INTERFACE = os.path.join(_HERE, os.pardir, "test-return-channel.py")
_HAVE_TMUX = shutil.which("tmux") is not None


def _load_module():
    spec = importlib.util.spec_from_file_location("return_channel_v2", _MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rc = _load_module()


class Base(unittest.TestCase):
    def setUp(self):
        self.mbox = tempfile.mkdtemp(prefix="rc-test-")
        self._saved_env = {}
        # Make sure no ambient clock override leaks in from the outer shell.
        self._clear_now()

    def tearDown(self):
        shutil.rmtree(self.mbox, ignore_errors=True)
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # -- helpers --
    def _set_env(self, k, v):
        if k not in self._saved_env:
            self._saved_env[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = str(v)

    def _clear_now(self):
        self._set_env("FLEET_LEDGER_NOW", None)

    def run_cli(self, *args):
        """Invoke a verb in-process. Returns (exit_code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        code = 0
        argv = ["--mailbox", self.mbox] + list(args)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc.main(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        return code, out.getvalue(), err.getvalue()

    def _td(self, task):
        return os.path.join(self.mbox, task)

    def _ledger(self, task):
        return rc._read_json(os.path.join(self._td(task), "ledger.json"))

    def _events(self, task):
        p = os.path.join(self._td(task), "events.jsonl")
        if not os.path.isfile(p):
            return []
        with open(p, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


# (1) v1 four-verb compatibility, including legacy-envelope read -------------
class TestV1Compat(Base):
    def test_bare_register_is_v1_identical_no_ledger(self):
        code, out, err = self.run_cli("register", "--task", "t1",
                                      "--worker-pane", "%1", "--reply-to", "%0")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), self._td("t1"))          # prints the task dir
        self.assertTrue(os.path.isfile(os.path.join(self._td("t1"), "contract.json")))
        # A bare v1 register must leave NO v2 ledger behind.
        self.assertFalse(os.path.isfile(os.path.join(self._td("t1"), "ledger.json")))

    def test_register_return_pending_ack_flow(self):
        self.run_cli("register", "--task", "t2", "--worker-pane", "%1", "--reply-to", "%0")
        code, out, _ = self.run_cli("return", "--task", "t2", "--status", "done",
                                    "--outcome", "approved", "--result", "/tmp/r.md",
                                    "--no-notify")
        self.assertEqual(code, 0)
        env = json.loads(out)
        self.assertEqual(env["task_id"], "t2")
        self.assertEqual(env["status"], "done")
        self.assertEqual(env["outcome"], "approved")
        self.assertTrue(env["durable"])
        self.assertFalse(env["notified"])
        # v1 envelope schema on disk
        disk = rc._read_json(os.path.join(self._td("t2"), "return.json"))
        for k in ("task_id", "status", "outcome", "result_path", "reply_to",
                  "worker_pane", "report", "returned_at"):
            self.assertIn(k, disk)

        code, out, _ = self.run_cli("pending", "--reply-to", "%0", "--json")
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["task_id"], "t2")

        # pending is scoped to the parent pane
        _, out2, _ = self.run_cli("pending", "--reply-to", "%9", "--json")
        self.assertEqual(json.loads(out2), [])

        code, out, _ = self.run_cli("ack", "--task", "t2", "--decision", "merge")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "acked t2 decision=merge")
        # acked => no longer pending
        _, out3, _ = self.run_cli("pending", "--reply-to", "%0", "--json")
        self.assertEqual(json.loads(out3), [])

    def test_reads_legacy_envelope_and_lazily_migrates(self):
        # Simulate the OLD binary: contract.json + return.json written directly,
        # with NO ledger.json / events.jsonl present.
        td = self._td("legacy")
        os.makedirs(td)
        rc.atomic_write_json(os.path.join(td, "contract.json"),
                             {"task_id": "legacy", "worker_pane": "%2",
                              "reply_to": "%0", "created_at": 111.0})
        rc.atomic_write_json(os.path.join(td, "return.json"),
                             {"task_id": "legacy", "status": "done",
                              "outcome": "approved", "result_path": "/tmp/a.md",
                              "reply_to": "%0", "worker_pane": "%2",
                              "report": "hi", "returned_at": 222.0})
        # v1 pending still reads the legacy envelope
        _, out, _ = self.run_cli("pending", "--reply-to", "%0", "--json")
        self.assertEqual(json.loads(out)[0]["task_id"], "legacy")
        # first v2 touch lazily migrates: synthesizes a ledger + a `migrated` event
        code, out, _ = self.run_cli("status", "--task", "legacy")
        self.assertEqual(code, 0)
        L = json.loads(out)
        self.assertEqual(L["state"], "published")            # done -> published
        self.assertEqual(L["outcome"], "approved")
        self.assertEqual(L["result_paths"], ["/tmp/a.md"])
        self.assertTrue(os.path.isfile(os.path.join(td, "ledger.json")))
        self.assertEqual(self._events("legacy")[0]["event"], "migrated")


# (2) owned_paths conflict rejection -----------------------------------------
class TestOwnedPathsConflict(Base):
    def _reg(self, task, owned=None, worker="%1", reply="%0"):
        args = ["register", "--task", task, "--worker-pane", worker, "--reply-to", reply]
        if owned is not None:
            args += ["--owned-paths", owned]
        return self.run_cli(*args)

    def test_overlap_rejected_and_names_conflict(self):
        code, _, _ = self._reg("A", owned="src/foo,docs/x.md")
        self.assertEqual(code, 0)
        # exact overlap
        code, _, err = self._reg("B", owned="src/foo")
        self.assertNotEqual(code, 0)
        self.assertIn("A", err)
        self.assertIn("src/foo", err)
        self.assertFalse(os.path.isdir(self._td("B")))       # zero side effects on reject

    def test_ancestor_overlap_rejected(self):
        self._reg("A", owned="src")
        code, _, err = self._reg("B", owned="src/deep/thing.py")
        self.assertNotEqual(code, 0)
        self.assertIn("A", err)

    def test_disjoint_paths_ok(self):
        self.assertEqual(self._reg("A", owned="src/foo")[0], 0)
        self.assertEqual(self._reg("B", owned="src/bar")[0], 0)

    def test_no_owned_paths_never_conflicts_v1_behavior(self):
        # bare registers never conflict, regardless of overlap intent
        self.assertEqual(self._reg("A")[0], 0)
        self.assertEqual(self._reg("B")[0], 0)

    def test_terminal_task_releases_its_claim(self):
        self._reg("A", owned="src/foo")
        self.run_cli("transition", "--task", "A", "--to", "aborted")
        # A is aborted (terminal) => B may now claim the same path
        code, _, _ = self._reg("B", owned="src/foo")
        self.assertEqual(code, 0)


# (3) stale seq / wrong prior-state rejection --------------------------------
class TestTransitionGuards(Base):
    def _reg(self, task):
        self.run_cli("register", "--task", task, "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "p/" + task)

    def test_wrong_prior_state_rejected(self):
        self._reg("t")
        # from `registered`, claiming prior=started is a lie -> reject
        code, _, err = self.run_cli("transition", "--task", "t",
                                    "--to", "published", "--from", "started")
        self.assertNotEqual(code, 0)
        self.assertIn("wrong prior state", err)
        self.assertEqual(self._ledger("t")["state"], "registered")

    def test_illegal_edge_rejected(self):
        self._reg("t")
        # registered -> acked is not an allowed edge
        code, _, err = self.run_cli("transition", "--task", "t", "--to", "acked")
        self.assertNotEqual(code, 0)
        self.assertIn("illegal transition", err)

    def test_stale_seq_rejected_but_newer_accepted(self):
        self._reg("t")
        self.run_cli("transition", "--task", "t", "--to", "dispatched", "--seq", "5")
        self.assertEqual(self._ledger("t")["seq"], 5)
        # seq 5 again (<=current) is a stale/out-of-order writeback -> reject
        code, _, err = self.run_cli("transition", "--task", "t",
                                    "--to", "started", "--seq", "5")
        self.assertNotEqual(code, 0)
        self.assertIn("stale seq", err)
        self.assertEqual(self._ledger("t")["state"], "dispatched")   # unchanged
        # a strictly-newer seq advances
        code, _, _ = self.run_cli("transition", "--task", "t",
                                  "--to", "started", "--seq", "6")
        self.assertEqual(code, 0)
        self.assertEqual(self._ledger("t")["state"], "started")
        self.assertEqual(self._ledger("t")["seq"], 6)

    def test_idempotent_replay_is_noop(self):
        self._reg("t")
        self.run_cli("transition", "--task", "t", "--to", "dispatched")
        before = self._ledger("t")
        n_events = len(self._events("t"))
        # replaying the same target state -> success, no state churn, no new event
        code, out, _ = self.run_cli("transition", "--task", "t", "--to", "dispatched")
        self.assertEqual(code, 0)
        self.assertEqual(self._ledger("t")["seq"], before["seq"])
        self.assertEqual(len(self._events("t")), n_events)


# (4) publish-task atomicity: missing path => zero side effects --------------
class TestPublishAtomicity(Base):
    def _prep(self):
        self.run_cli("register", "--task", "pub", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "out/pub")
        self.run_cli("transition", "--task", "pub", "--to", "dispatched")
        self.run_cli("transition", "--task", "pub", "--to", "started")

    def test_missing_path_zero_side_effects(self):
        self._prep()
        good = os.path.join(self.mbox, "artifact_ok.txt")
        with open(good, "w") as f:
            f.write("ok")
        missing = os.path.join(self.mbox, "does_not_exist.txt")

        before_ledger = self._ledger("pub")
        before_events = self._events("pub")
        code, _, err = self.run_cli("publish-task", "--task", "pub",
                                    "--result-paths", "%s,%s" % (good, missing),
                                    "--no-notify")
        self.assertNotEqual(code, 0)
        self.assertIn("missing result paths", err)
        # ZERO side effects: ledger byte-identical, event log untouched, no hashes
        self.assertEqual(self._ledger("pub"), before_ledger)
        self.assertEqual(self._events("pub"), before_events)
        self.assertEqual(self._ledger("pub")["state"], "started")
        self.assertEqual(self._ledger("pub")["artifact_hashes"], {})

    def test_all_present_publishes_and_hashes(self):
        self._prep()
        a = os.path.join(self.mbox, "a.txt")
        b = os.path.join(self.mbox, "b.txt")
        for p in (a, b):
            with open(p, "w") as f:
                f.write(p)
        n_events = len(self._events("pub"))
        code, out, _ = self.run_cli("publish-task", "--task", "pub",
                                    "--result-paths", "%s,%s" % (a, b), "--no-notify")
        self.assertEqual(code, 0)
        L = json.loads(out)
        self.assertEqual(L["state"], "published")
        self.assertEqual(set(L["artifact_hashes"].keys()), {a, b})
        self.assertEqual(len(L["artifact_hashes"][a]), 64)   # hex sha256
        events = self._events("pub")
        self.assertEqual(len(events), n_events + 1)
        self.assertEqual(events[-1]["event"], "published")


# (5) lease expiry => lost, never auto-retried -------------------------------
class TestLeaseExpiry(Base):
    def test_expired_lease_marks_lost_no_retry(self):
        self.run_cli("register", "--task", "lz", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "out/lz")
        self.run_cli("transition", "--task", "lz", "--to", "dispatched")
        self.run_cli("transition", "--task", "lz", "--to", "started")
        # lease 60s into the (frozen) future
        self._set_env("FLEET_LEDGER_NOW", 1000)
        self.run_cli("heartbeat", "--task", "lz", "--lease-seconds", "60")
        self.assertEqual(self._ledger("lz")["state"], "started")
        # jump the clock past the lease and query
        self._set_env("FLEET_LEDGER_NOW", 5000)
        code, out, _ = self.run_cli("status", "--task", "lz")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["state"], "lost")
        events = self._events("lz")
        self.assertEqual(events[-1]["event"], "lost")
        self.assertEqual(events[-1]["note"], "lease expired")
        # NO auto-retry: no dispatched/started event was fabricated by the query
        self.assertNotIn("retry", [e["event"] for e in events])
        # idempotent: a second query does not append another `lost`
        n = len(self._events("lz"))
        self.run_cli("status", "--task", "lz")
        self.assertEqual(len(self._events("lz")), n)

    def test_lost_task_still_holds_owned_paths(self):
        self.run_cli("register", "--task", "lz", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "out/lz")
        self.run_cli("transition", "--task", "lz", "--to", "dispatched")
        self._set_env("FLEET_LEDGER_NOW", 1000)
        self.run_cli("heartbeat", "--task", "lz", "--lease-seconds", "10")
        self._set_env("FLEET_LEDGER_NOW", 5000)
        self.run_cli("status", "--task", "lz")               # flips to lost
        self._clear_now()
        # a lost worker's tree is unknown -> its claim is NOT auto-released
        code, _, err = self.run_cli("register", "--task", "other", "--worker-pane",
                                    "%3", "--reply-to", "%0", "--owned-paths", "out/lz")
        self.assertNotEqual(code, 0)
        self.assertIn("lz", err)


# (6) event log is append-only -----------------------------------------------
class TestEventLogAppendOnly(Base):
    def test_appends_never_rewrites(self):
        self.run_cli("register", "--task", "ev", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "out/ev")
        raw0 = self._raw("ev")
        self.assertEqual(len(raw0), 1)                       # registered

        self.run_cli("transition", "--task", "ev", "--to", "dispatched")
        raw1 = self._raw("ev")
        self.assertEqual(len(raw1), 2)
        self.assertEqual(raw1[0], raw0[0])                   # earlier line untouched

        self.run_cli("transition", "--task", "ev", "--to", "started")
        raw2 = self._raw("ev")
        self.assertEqual(len(raw2), 3)
        self.assertEqual(raw2[:2], raw1)                     # prefix preserved verbatim

        # seqs are strictly increasing, each line is valid JSON
        seqs = [json.loads(line)["seq"] for line in raw2]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(len(set(seqs)), len(seqs))

    def _raw(self, task):
        with open(os.path.join(self._td(task), "events.jsonl"), encoding="utf-8") as f:
            return [line for line in f if line.strip()]


# (+) notify failure is non-fatal (hard-constraint 8) ------------------------
class TestNotifyNonFatal(Base):
    def test_return_notify_failure_non_fatal(self):
        self.run_cli("register", "--task", "nf", "--worker-pane", "%1", "--reply-to", "%0")
        # Force the notification down a bogus tmux socket. Whether tmux is missing
        # (OSError, caught) or present-but-fails (nonzero rc), it must stay non-fatal.
        code, out, err = self.run_cli("return", "--task", "nf", "--status", "done",
                                      "--socket", os.path.join(self.mbox, "no.sock"))
        self.assertEqual(code, 0)                            # durable path succeeded
        env = json.loads(out)
        self.assertTrue(env["durable"])
        self.assertFalse(env["notified"])
        self.assertTrue(os.path.isfile(os.path.join(self._td("nf"), "return.json")))
        self.assertIn("notify", err)


# ============================================================================
# v2.1 HARDENING TESTS (job fc-harden-20260730)
# ============================================================================

# (H1) concurrency: mailbox flock closes the TOCTOU double-register -----------
class TestH1ConcurrentRegister(Base):
    def _popen_register(self, task, owned):
        return subprocess.Popen(
            [sys.executable, _MODPATH, "--mailbox", self.mbox, "register",
             "--task", task, "--worker-pane", "%1", "--reply-to", "%0",
             "--owned-paths", owned],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))

    def test_two_processes_same_owned_path_exactly_one_wins(self):
        # Two REAL processes (constraint 3.1) race to register DIFFERENT task_ids that
        # both claim the SAME owned path. The un-locked scan-then-write let both see
        # "no conflict" and both win; the mailbox flock serializes them => exactly one.
        shared = os.path.join(self.mbox, "contended", "tree")
        procs = [self._popen_register(t, shared) for t in ("procA", "procB")]
        results = []
        for p in procs:
            out, err = p.communicate()
            results.append((out, err, p.returncode))
        codes = [r[2] for r in results]
        self.assertEqual(codes.count(0), 1, "exactly one winner; codes=%r" % codes)
        self.assertEqual(sum(1 for c in codes if c != 0), 1,
                         "exactly one loser; codes=%r" % codes)
        loser_err = next(r[1] for r in results if r[2] != 0)
        self.assertIn("conflict", loser_err.lower())
        # the loser leaves ZERO side effects: exactly one of the two contracts exists
        contracts = [t for t in ("procA", "procB")
                     if os.path.isfile(os.path.join(self.mbox, t, "contract.json"))]
        self.assertEqual(len(contracts), 1, "loser must not write a contract")

    def test_many_way_race_still_one_winner(self):
        shared = os.path.join(self.mbox, "hot", "path")
        procs = [self._popen_register("r%d" % i, shared) for i in range(6)]
        codes = []
        for p in procs:
            p.communicate()
            codes.append(p.returncode)
        self.assertEqual(codes.count(0), 1, "exactly one of N winners; codes=%r" % codes)


# (H1) lock timeout + crash-while-holding never deadlock (constraint 3.5) -----
class TestH1LockLiveness(Base):
    def _lock_file(self):
        return rc._lock_path(self.mbox)

    def test_lock_timeout_does_not_deadlock(self):
        # Prime the mailbox, hold the lock from THIS process, and prove a locked verb
        # gives up after the (env-overridable) timeout instead of hanging forever.
        self.run_cli("register", "--task", "t", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "p/t")
        held = os.open(self._lock_file(), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(held, fcntl.LOCK_EX)
        try:
            self._set_env("FLEET_LEDGER_LOCK_TIMEOUT", "0.3")
            start = time.monotonic()
            code, _, err = self.run_cli("transition", "--task", "t", "--to", "started")
            elapsed = time.monotonic() - start
            self.assertNotEqual(code, 0)
            self.assertIn("lock timeout", err)
            self.assertLess(elapsed, 5.0, "must give up promptly, not hang")
            self.assertGreaterEqual(elapsed, 0.25, "must actually wait out the timeout")
        finally:
            fcntl.flock(held, fcntl.LOCK_UN)
            os.close(held)
        # lock released -> the same verb now succeeds
        self._set_env("FLEET_LEDGER_LOCK_TIMEOUT", None)
        code, _, err = self.run_cli("transition", "--task", "t", "--to", "started")
        self.assertEqual(code, 0, err)
        self.assertEqual(self._ledger("t")["state"], "started")

    def test_crash_while_holding_lock_auto_releases(self):
        # A process that DIES holding the flock must not wedge the mailbox: the kernel
        # drops the lock when the process goes away. Spawn a holder, SIGKILL it, then
        # prove a locked verb acquires immediately.
        self.run_cli("register", "--task", "t", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "p/t")
        ready = os.path.join(self.mbox, "holder-ready")
        holder_code = (
            "import fcntl, os, sys, time\n"
            "fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR, 0o600)\n"
            "fcntl.flock(fd, fcntl.LOCK_EX)\n"
            "open(sys.argv[2], 'w').close()\n"
            "time.sleep(60)\n"
        )
        holder = subprocess.Popen([sys.executable, "-c", holder_code,
                                   self._lock_file(), ready])
        try:
            deadline = time.monotonic() + 5.0
            while not os.path.exists(ready) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(os.path.exists(ready), "holder never acquired the lock")
            holder.kill()
            holder.wait()
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.wait()
        code, _, err = self.run_cli("transition", "--task", "t", "--to", "started")
        self.assertEqual(code, 0, err)
        self.assertEqual(self._ledger("t")["state"], "started")


# (H2) publish-task must publish exactly the REGISTERED result set ------------
class TestH2ResultPin(Base):
    def _files(self, *names):
        paths = []
        for n in names:
            p = os.path.join(self.mbox, n)
            with open(p, "w") as f:
                f.write(n)
            paths.append(p)
        return paths

    def _prep(self, result_paths):
        self.run_cli("register", "--task", "pin", "--worker-pane", "%1", "--reply-to", "%0",
                     "--owned-paths", "out/pin", "--result-paths", ",".join(result_paths))
        self.run_cli("transition", "--task", "pin", "--to", "started")

    def test_override_subset_rejected_with_diff(self):
        a, b = self._files("A.md", "B.md")
        self._prep([a, b])
        code, _, err = self.run_cli("publish-task", "--task", "pin",
                                    "--result-paths", a, "--no-notify")
        self.assertNotEqual(code, 0)
        self.assertIn("does not match the registered", err)
        self.assertIn("B.md", err)                       # B is the missing-from-passed diff
        self.assertEqual(self._ledger("pin")["state"], "started")   # zero side effects
        self.assertNotIn("published", [e["event"] for e in self._events("pin")])

    def test_override_superset_rejected_with_extra(self):
        a, b, c = self._files("A.md", "B.md", "C.md")
        self._prep([a, b])
        code, _, err = self.run_cli("publish-task", "--task", "pin",
                                    "--result-paths", ",".join([a, b, c]), "--no-notify")
        self.assertNotEqual(code, 0)
        self.assertIn("does not match the registered", err)
        self.assertIn("C.md", err)                       # C is the extra
        self.assertEqual(self._ledger("pin")["state"], "started")

    def test_exact_registered_set_publishes_order_independent(self):
        a, b = self._files("A.md", "B.md")
        self._prep([a, b])
        code, out, _ = self.run_cli("publish-task", "--task", "pin",
                                    "--result-paths", ",".join([b, a]), "--no-notify")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["state"], "published")

    def test_default_uses_registered_set(self):
        a, b = self._files("A.md", "B.md")
        self._prep([a, b])
        code, out, _ = self.run_cli("publish-task", "--task", "pin", "--no-notify")
        self.assertEqual(code, 0)
        L = json.loads(out)
        self.assertEqual(L["state"], "published")
        self.assertEqual(set(L["artifact_hashes"].keys()), {a, b})

    def test_unregistered_result_set_keeps_old_freedom(self):
        # H2 only pins tasks that REGISTERED a set; a bare task publishes freely.
        a = self._files("A.md")[0]
        self.run_cli("register", "--task", "free", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "out/free")
        self.run_cli("transition", "--task", "free", "--to", "started")
        code, out, _ = self.run_cli("publish-task", "--task", "free",
                                    "--result-paths", a, "--no-notify")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["state"], "published")


# (H2) canonicalization: owned + result paths compared like-for-like ---------
class TestH2Canonical(Base):
    def test_owned_conflict_detected_across_spellings(self):
        # './sub/x' and 'sub/x' canonicalize to the same abspath -> conflict.
        self.assertEqual(self.run_cli("register", "--task", "A", "--worker-pane", "%1",
                                      "--reply-to", "%0", "--owned-paths", "./sub/x")[0], 0)
        code, _, err = self.run_cli("register", "--task", "B", "--worker-pane", "%1",
                                    "--reply-to", "%0", "--owned-paths", "sub/x")
        self.assertNotEqual(code, 0)
        self.assertIn("A", err)

    def test_result_pin_matches_across_spellings(self):
        p = os.path.join(self.mbox, "art.txt")
        with open(p, "w") as f:
            f.write("x")
        noncanon = os.path.join(self.mbox, ".", "art.txt")   # canonicalizes to p
        self.run_cli("register", "--task", "cn", "--worker-pane", "%1", "--reply-to", "%0",
                     "--owned-paths", "out/cn", "--result-paths", noncanon)
        self.run_cli("transition", "--task", "cn", "--to", "started")
        # register already stored the canonical form
        self.assertEqual(self._ledger("cn")["result_paths"], [p])
        code, out, _ = self.run_cli("publish-task", "--task", "cn",
                                    "--result-paths", p, "--no-notify")
        self.assertEqual(code, 0, "canonical forms must compare equal")
        self.assertEqual(json.loads(out)["state"], "published")


# (H3) `published` is entered ONLY via publish-task --------------------------
class TestH3PublishOnlyViaPublishTask(Base):
    def _prep(self):
        self.run_cli("register", "--task", "t", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "out/t")
        self.run_cli("transition", "--task", "t", "--to", "started")

    def test_transition_to_published_refused(self):
        self._prep()
        code, _, err = self.run_cli("transition", "--task", "t", "--to", "published")
        self.assertNotEqual(code, 0)
        self.assertIn("publish-task", err)               # points at the right verb
        self.assertEqual(self._ledger("t")["state"], "started")   # zero side effects

    def test_transition_to_published_refused_even_with_correct_prior(self):
        self._prep()
        code, _, err = self.run_cli("transition", "--task", "t",
                                    "--to", "published", "--from", "started")
        self.assertNotEqual(code, 0)
        self.assertIn("publish-task", err)
        self.assertEqual(self._ledger("t")["state"], "started")

    def test_edges_table_has_no_published_target(self):
        # White-box: EDGES is now the honest truth for `transition` (H4) — no source
        # state lists `published`; publish-task uses PUBLISH_SOURCES instead.
        for src, targets in rc.EDGES.items():
            self.assertNotIn("published", targets, "EDGES[%s] reaches published" % src)
        self.assertTrue(rc.PUBLISH_SOURCES)

    def test_publish_task_still_reaches_published(self):
        self._prep()
        art = os.path.join(self.mbox, "art")
        with open(art, "w") as f:
            f.write("x")
        code, out, _ = self.run_cli("publish-task", "--task", "t",
                                    "--result-paths", art, "--no-notify")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["state"], "published")

    def test_migrated_published_carries_migrated_event_not_published(self):
        # A v1 `done` envelope lazily migrates to state=published, but the audit event
        # is `migrated`, NEVER a synthetic `published` (H3 verify-and-test).
        td = self._td("legacy")
        os.makedirs(td)
        rc.atomic_write_json(os.path.join(td, "contract.json"),
                             {"task_id": "legacy", "worker_pane": "%2",
                              "reply_to": "%0", "created_at": 1.0})
        rc.atomic_write_json(os.path.join(td, "return.json"),
                             {"task_id": "legacy", "status": "done", "outcome": "approved",
                              "result_path": "/tmp/a.md", "reply_to": "%0",
                              "worker_pane": "%2", "report": "", "returned_at": 2.0})
        code, out, _ = self.run_cli("status", "--task", "legacy")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["state"], "published")
        events = [e["event"] for e in self._events("legacy")]
        self.assertIn("migrated", events)
        self.assertNotIn("published", events)


# (H6) a lease-expired task publishing a missing path => zero side effects ----
class TestH6ExpiredPublishZeroSideEffects(Base):
    def test_expired_missing_path_writes_no_lost(self):
        self.run_cli("register", "--task", "ex", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "out/ex")
        self.run_cli("transition", "--task", "ex", "--to", "dispatched")
        self.run_cli("transition", "--task", "ex", "--to", "started")
        self._set_env("FLEET_LEDGER_NOW", 1000)
        self.run_cli("heartbeat", "--task", "ex", "--lease-seconds", "60")
        self._set_env("FLEET_LEDGER_NOW", 5000)          # lease now expired
        before_ledger = self._ledger("ex")
        before_events = self._events("ex")
        good = os.path.join(self.mbox, "good.txt")
        with open(good, "w") as f:
            f.write("ok")
        missing = os.path.join(self.mbox, "nope.txt")
        code, _, err = self.run_cli("publish-task", "--task", "ex",
                                    "--result-paths", "%s,%s" % (good, missing),
                                    "--no-notify")
        self.assertNotEqual(code, 0)
        self.assertIn("missing result paths", err)
        # H6: the missing-path gate ran BEFORE lease expiry -> NO `lost` was written.
        self.assertEqual(self._ledger("ex")["state"], "started")
        self.assertEqual(self._ledger("ex"), before_ledger)      # byte-identical
        self.assertEqual(self._events("ex"), before_events)
        self.assertNotIn("lost", [e["event"] for e in self._events("ex")])

    def test_expiry_still_detected_on_a_real_query(self):
        # Sanity: the lease genuinely WAS expired — a normal query DOES flip it to lost.
        # (Proves the previous test's `started` is the H6 fix, not a non-expired lease.)
        self.run_cli("register", "--task", "ex2", "--worker-pane", "%1",
                     "--reply-to", "%0", "--owned-paths", "out/ex2")
        self.run_cli("transition", "--task", "ex2", "--to", "started")
        self._set_env("FLEET_LEDGER_NOW", 1000)
        self.run_cli("heartbeat", "--task", "ex2", "--lease-seconds", "60")
        self._set_env("FLEET_LEDGER_NOW", 5000)
        _, out, _ = self.run_cli("status", "--task", "ex2")
        self.assertEqual(json.loads(out)["state"], "lost")


# (H5) one command (unittest discover) also runs the v1 interface test --------
class TestH5V1InterfaceScript(unittest.TestCase):
    def test_v1_interface_suite_passes(self):
        if not os.path.isfile(_V1_INTERFACE):
            self.skipTest("v1 interface script not present next to the suite")
        if not _HAVE_TMUX:
            self.skipTest("tmux unavailable; v1 interface notification checks need it")
        r = subprocess.run([sys.executable, _V1_INTERFACE],
                           capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 0,
                         "v1 interface test failed:\n" + (r.stdout[-2000:]) + (r.stderr[-2000:]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
