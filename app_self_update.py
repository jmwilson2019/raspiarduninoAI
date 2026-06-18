"""Reusable in-place self-update capability for a git-backed app.

This is the "update app capable" primitive intended to be dropped, unmodified,
into any SynerGro repo whose deployed copy is a real git working tree (the
clone-and-pull deployment model). It is reality-only and self-contained:

* No third-party dependencies — it shells out to the real ``git`` binary.
* It operates on the actual repository the file lives in (auto-detected via
  ``git rev-parse``), so the same file works in every repo.
* ``check()`` performs a real ``git fetch`` and reports how many commits the
  local branch is behind / ahead of its upstream.
* ``apply()`` performs a **fast-forward-only** pull. It refuses to run when the
  working tree is dirty or the branch has diverged, so a self-update can never
  silently discard local work or create a merge conflict. ``force=True`` does a
  hard reset to the upstream tip (explicit, opt-in).

Safety / consent
----------------
When ``seraphina_capabilities`` is importable, ``apply()`` is gated behind
``Capability.UPDATE_INSTALLER`` (default-off). In a repo without that module,
the gate degrades to "allowed" so the primitive still works standalone — the
caller is expected to confirm intent.

Public API
----------
    repo_root()                 -> str | None
    current_commit()            -> str | None
    is_dirty()                  -> bool
    check(timeout=20)           -> dict
    apply(force=False, ...)     -> dict

CLI
---
    python -m app_self_update            # check only, JSON to stdout
    python -m app_self_update --apply    # fast-forward update if available
    python -m app_self_update --apply --force   # hard reset to upstream
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# git plumbing (real subprocess calls; never raises to the caller)
# ---------------------------------------------------------------------------
def _git(args: List[str], *, cwd: Optional[str] = None,
         timeout: int = 20) -> Dict[str, Any]:
    """Run a git command. Returns {ok, code, out, err}."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd or _HERE,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "out": (proc.stdout or "").strip(),
            "err": (proc.stderr or "").strip(),
        }
    except FileNotFoundError:
        return {"ok": False, "code": -1, "out": "", "err": "git not found on PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": -1, "out": "", "err": f"git {args[0]} timed out"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "code": -1, "out": "", "err": f"{type(exc).__name__}: {exc}"}


def repo_root(cwd: Optional[str] = None) -> Optional[str]:
    """Absolute path of the git repo the app lives in, or None."""
    res = _git(["rev-parse", "--show-toplevel"], cwd=cwd)
    return res["out"] if res["ok"] and res["out"] else None


def current_branch(cwd: Optional[str] = None) -> Optional[str]:
    res = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return res["out"] if res["ok"] and res["out"] else None


def current_commit(cwd: Optional[str] = None) -> Optional[str]:
    res = _git(["rev-parse", "HEAD"], cwd=cwd)
    return res["out"] if res["ok"] and res["out"] else None


def is_dirty(cwd: Optional[str] = None) -> bool:
    """True if the working tree has uncommitted changes."""
    res = _git(["status", "--porcelain"], cwd=cwd)
    return bool(res["ok"] and res["out"])


def _upstream(cwd: Optional[str] = None) -> Optional[str]:
    res = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=cwd)
    return res["out"] if res["ok"] and res["out"] else None


# ---------------------------------------------------------------------------
# capability gate (optional; degrades to allowed when module absent)
# ---------------------------------------------------------------------------
def _update_allowed() -> bool:
    try:
        from seraphina_capabilities import capabilities, Capability  # type: ignore
        return bool(capabilities.is_allowed(Capability.UPDATE_INSTALLER))
    except Exception:
        return True  # standalone repo without the capability registry


# ---------------------------------------------------------------------------
# public: check + apply
# ---------------------------------------------------------------------------
def check(timeout: int = 20, *, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Fetch upstream and report update status. Never raises.

    Returns a dict::

        {
          "ok":        bool,         # the check ran successfully
          "available": bool,         # local branch is behind upstream
          "behind":    int,          # commits behind upstream
          "ahead":     int,          # local commits not yet pushed
          "branch":    "main",
          "upstream":  "origin/main",
          "current":   "<sha>",
          "dirty":     bool,
          "error":     str | None,
        }
    """
    out: Dict[str, Any] = {
        "ok": False, "available": False, "behind": 0, "ahead": 0,
        "branch": None, "upstream": None, "current": None,
        "dirty": False, "error": None,
    }
    root = repo_root(cwd)
    if root is None:
        out["error"] = "not a git repository"
        return out
    out["branch"] = current_branch(cwd)
    out["current"] = current_commit(cwd)
    out["dirty"] = is_dirty(cwd)

    fetched = _git(["fetch", "--quiet"], cwd=cwd, timeout=timeout)
    if not fetched["ok"]:
        out["error"] = f"fetch failed: {fetched['err'] or fetched['code']}"
        return out

    upstream = _upstream(cwd)
    if upstream is None:
        out["error"] = "no upstream tracking branch configured"
        out["ok"] = True  # the check itself succeeded; just nothing to compare
        return out
    out["upstream"] = upstream

    counts = _git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], cwd=cwd)
    if counts["ok"] and counts["out"]:
        parts = counts["out"].split()
        if len(parts) == 2:
            out["ahead"] = int(parts[0])
            out["behind"] = int(parts[1])
    out["available"] = out["behind"] > 0
    out["ok"] = True
    return out


def apply(*, force: bool = False, timeout: int = 60,
          cwd: Optional[str] = None) -> Dict[str, Any]:
    """Apply an available update. Fast-forward-only unless ``force=True``.

    Never raises. Returns a dict with ``ok``, ``updated``, ``from``, ``to``,
    and ``error``. Refuses (``ok=False``) when:

    * the update capability is disabled,
    * the working tree is dirty (would lose local edits),
    * the branch has diverged and ``force`` is not set.
    """
    out: Dict[str, Any] = {
        "ok": False, "updated": False, "from": None, "to": None,
        "method": None, "error": None,
    }
    if not _update_allowed():
        out["error"] = ("update blocked: enable Capability.UPDATE_INSTALLER "
                        "in the Capabilities tab")
        return out

    status = check(timeout=timeout, cwd=cwd)
    if status["error"] and not status["ok"]:
        out["error"] = status["error"]
        return out
    out["from"] = status["current"]
    upstream = status["upstream"]
    if upstream is None:
        out["error"] = "no upstream tracking branch configured"
        return out

    if not status["available"] and not force:
        out["ok"] = True
        out["updated"] = False
        out["to"] = status["current"]
        return out

    if status["dirty"] and not force:
        out["error"] = ("working tree has uncommitted changes; commit/stash "
                        "first or pass force=True")
        return out

    if status["ahead"] > 0 and not force:
        out["error"] = (f"local branch is {status['ahead']} commit(s) ahead "
                        "of upstream (diverged); pass force=True to hard reset")
        return out

    if force:
        reset = _git(["reset", "--hard", upstream], cwd=cwd, timeout=timeout)
        if not reset["ok"]:
            out["error"] = f"reset failed: {reset['err'] or reset['code']}"
            return out
        out["method"] = "reset --hard"
    else:
        pull = _git(["merge", "--ff-only", upstream], cwd=cwd, timeout=timeout)
        if not pull["ok"]:
            out["error"] = f"fast-forward failed: {pull['err'] or pull['code']}"
            return out
        out["method"] = "merge --ff-only"

    new_commit = current_commit(cwd)
    out["to"] = new_commit
    out["updated"] = new_commit != out["from"]
    out["ok"] = True
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="app_self_update",
        description="Check for and apply in-place git updates for this app.",
    )
    parser.add_argument("--apply", action="store_true",
                        help="apply an available update (fast-forward only)")
    parser.add_argument("--force", action="store_true",
                        help="with --apply: hard reset to upstream tip")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)

    if args.apply:
        result = apply(force=args.force, timeout=args.timeout)
    else:
        result = check(timeout=args.timeout)
    print(json.dumps(result, indent=2))
    return 0 if result.get("error") is None else 1


if __name__ == "__main__":
    raise SystemExit(_main())
