"""Reality-only tests for the git-backed self-update primitive.

These build *real* git repositories on disk (a bare "remote" + a working
clone), make real commits, and drive app_self_update against them. No mocks,
no fake git: every assertion reflects actual git plumbing and real files.

If git is not on PATH the whole module is skipped (the primitive itself
degrades gracefully in that case, reporting an error dict).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import app_self_update as asu  # noqa: E402


def _have_git() -> bool:
    return shutil.which("git") is not None


def _run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True,
                   capture_output=True, text=True)


@unittest.skipUnless(_have_git(), "git not on PATH")
class TestSelfUpdateReality(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.remote = os.path.join(base, "remote.git")
        self.work = os.path.join(base, "work")
        # Real bare remote.
        _run(["git", "init", "--bare", "-b", "main", self.remote], base)
        # Real working clone with identity configured.
        _run(["git", "clone", self.remote, self.work], base)
        for kv in (("user.email", "test@example.com"),
                   ("user.name", "Reality Test"),
                   ("commit.gpgsign", "false")):
            _run(["git", "config", *kv], self.work)
        self._commit("app.py", "v1\n", "initial commit")
        _run(["git", "push", "-u", "origin", "main"], self.work)

    def tearDown(self):
        self._tmp.cleanup()

    def _commit(self, name, content, msg, cwd=None):
        cwd = cwd or self.work
        with open(os.path.join(cwd, name), "w", encoding="utf-8") as fh:
            fh.write(content)
        _run(["git", "add", name], cwd)
        _run(["git", "commit", "-m", msg], cwd)

    def _push_upstream_commit(self):
        """Make a second clone, commit, push — so `work` falls behind."""
        other = os.path.join(self._tmp.name, "other")
        _run(["git", "clone", self.remote, other], self._tmp.name)
        for kv in (("user.email", "u2@example.com"), ("user.name", "U2"),
                   ("commit.gpgsign", "false")):
            _run(["git", "config", *kv], other)
        self._commit("app.py", "v2\n", "upstream update", cwd=other)
        _run(["git", "push", "origin", "main"], other)

    # --- tests ---------------------------------------------------------
    def test_repo_root_and_commit_detected(self):
        self.assertIsNotNone(asu.repo_root(cwd=self.work))
        self.assertEqual(asu.current_branch(cwd=self.work), "main")
        self.assertEqual(len(asu.current_commit(cwd=self.work)), 40)

    def test_check_up_to_date(self):
        res = asu.check(cwd=self.work)
        self.assertTrue(res["ok"])
        self.assertFalse(res["available"])
        self.assertEqual(res["behind"], 0)

    def test_check_detects_available_update(self):
        self._push_upstream_commit()
        res = asu.check(cwd=self.work)
        self.assertTrue(res["ok"])
        self.assertTrue(res["available"])
        self.assertEqual(res["behind"], 1)

    def test_apply_fast_forward(self):
        self._push_upstream_commit()
        before = asu.current_commit(cwd=self.work)
        res = asu.apply(cwd=self.work)
        self.assertTrue(res["ok"], res.get("error"))
        self.assertTrue(res["updated"])
        self.assertEqual(res["method"], "merge --ff-only")
        after = asu.current_commit(cwd=self.work)
        self.assertNotEqual(before, after)
        # The real file on disk now holds the upstream content.
        with open(os.path.join(self.work, "app.py"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "v2\n")

    def test_apply_refuses_dirty_tree(self):
        self._push_upstream_commit()
        # Make the working tree dirty.
        with open(os.path.join(self.work, "app.py"), "a", encoding="utf-8") as fh:
            fh.write("local edit\n")
        res = asu.apply(cwd=self.work)
        self.assertFalse(res["ok"])
        self.assertIn("uncommitted", res["error"])

    def test_apply_refuses_diverged_without_force(self):
        self._push_upstream_commit()
        # Local commit that is NOT on upstream -> diverged.
        self._commit("local.py", "local\n", "local-only commit")
        res = asu.apply(cwd=self.work)
        self.assertFalse(res["ok"])
        self.assertIn("diverged", res["error"])

    def test_force_reset_recovers_diverged(self):
        self._push_upstream_commit()
        self._commit("local.py", "local\n", "local-only commit")
        res = asu.apply(force=True, cwd=self.work)
        self.assertTrue(res["ok"], res.get("error"))
        self.assertEqual(res["method"], "reset --hard")
        # Hard reset to upstream: the local-only file is gone.
        self.assertFalse(os.path.exists(os.path.join(self.work, "local.py")))

    def test_apply_noop_when_up_to_date(self):
        res = asu.apply(cwd=self.work)
        self.assertTrue(res["ok"])
        self.assertFalse(res["updated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
