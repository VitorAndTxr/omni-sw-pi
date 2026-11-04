"""
agency_cli worktree -- Instance isolation and parallel lane merge management.

Supports two isolation levels of the SDLC workflow:

1. Instance isolation (one branch + worktree per orchestrator run):
   - `worktree init` creates a dedicated branch (`agency/<slug>-<timestamp>`) and a
     linked git worktree so a run can execute in parallel with other runs (or other
     work) on the same repository without colliding in the working tree.
   - `worktree pr` pushes the instance branch and opens a PR back to the base branch.
   - `worktree remove` cleans up the instance worktree (and optionally its branch).

2. Parallel lane merge (feature lanes created by pi-subagents managed worktrees):
   - Lane agents commit to their own branches (e.g. `pi-subagents/<lane>`).
   - `worktree merge` sequentially merges an approved lane branch into the current
     instance branch, reporting conflicts without leaving the repo in a conflicted
     state.

Git operations here are deterministic helpers ONLY. The orchestrator skill owns the
human-approval protocol: it must present the change set and receive explicit user
approval before invoking `worktree merge` and `worktree pr`.

Untracked agency scratch (agent_docs/, .pi/) is TOLERATED by the clean-tree checks:
untracked files under those prefixes never block init/merge/remove. Tracked changes
anywhere, and untracked files elsewhere, still block — commit or stash them first.

Usage:
    agency_cli worktree init --project-root <path> --short-description <slug> [--base-branch <ref>] [--worktree-root <dir>]
    agency_cli worktree status --project-root <path>
    agency_cli worktree merge --project-root <path> --branch <branch> [--message <msg>] [--no-ff]
    agency_cli worktree pr --project-root <path> --title <title> --base <branch> [--body <text>] [--draft]
    agency_cli worktree remove --project-root <path> --path <worktree-path> [--delete-branch <branch>] [--force]
"""

import argparse
import os
import re
import stat
import subprocess
import sys
import time
from datetime import datetime


AGENCY_BRANCH_PREFIX = "agency/"
LANE_BRANCH_PREFIX = "pi-subagents/"
# Untracked scratch that never blocks clean-tree gates (only `??` entries whose
# repo-relative posix path starts with one of these).
TOLERATED_UNTRACKED_PREFIXES = ("agent_docs/", ".pi/", ".pi-subagents/")


def _git(project_root: str, args: list[str], accepted=(0,)) -> subprocess.CompletedProcess:
    """Run a git command in project_root."""
    result = subprocess.run(
        ["git", "-C", project_root] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode not in accepted:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{(result.stderr or result.stdout).strip()[:2000]}"
        )
    return result


def _resolve_repo_root(project_root: str) -> str:
    """Resolve the repository root (handles running from a subdirectory or worktree)."""
    return _git(project_root, ["rev-parse", "--show-toplevel"]).stdout.strip()


def _resolve_main_root(repo_root: str) -> str:
    """Resolve the MAIN worktree root (the checkout that owns .git).

    `git rev-parse --git-common-dir` returns the primary .git directory even when
    run from a linked worktree; its parent is the main checkout. Branch management
    must run there because a removed worktree path is no longer a valid -C target.
    """
    common_dir = _git(repo_root, ["rev-parse", "--git-common-dir"]).stdout.strip()
    common_path = os.path.abspath(os.path.join(repo_root, common_dir))
    # Linked worktrees keep a .git file; the common dir still points at the main .git.
    if os.path.basename(common_path) == ".git" and os.path.isdir(common_path):
        return os.path.dirname(common_path)
    # Bare or unusual layouts: fall back to the worktree root itself.
    return repo_root


def _current_branch(project_root: str) -> str:
    return _git(project_root, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def _dirty_paths(project_root: str, tolerated: bool = False) -> list[str]:
    """List changed paths from git status --porcelain.

    With tolerated=True, untracked (`??`) paths under agency scratch prefixes
    (agent_docs/, .pi/) are filtered out; every tracked change still counts.
    """
    result = _git(project_root, ["status", "--porcelain"])
    paths = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if tolerated and line.startswith("??"):
            normalized = path.replace("\\", "/").rstrip("/")
            # Compare as a directory: porcelain lists untracked dirs without a
            # trailing slash (e.g. `?? .pi/`), so append one before prefix check.
            check = normalized + "/"
            if any(check.startswith(prefix) for prefix in TOLERATED_UNTRACKED_PREFIXES):
                continue
        paths.append(path)
    return paths


def _registered_worktrees(repo_root: str) -> list[str]:
    """Return the paths currently registered via `git worktree list --porcelain`."""
    out = _git(repo_root, ["worktree", "list", "--porcelain"]).stdout
    paths = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            paths.append(line[len("worktree "):].strip())
    return paths


def _slugify(text: str, max_len: int = 30) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_len].rstrip("-") or "run"


def _branch_exists(project_root: str, branch: str) -> bool:
    result = _git(project_root, ["rev-parse", "--verify", "--quiet", branch], accepted=(0, 1))
    return result.returncode == 0


def _rmtree_resilient(directory: str, attempts: int = 4) -> tuple[bool, str | None]:
    """Delete a directory tree, tolerating Windows file locks.

    Clears read-only attributes on failure (AV/indexers routinely hold `.git` and
    `obj/` handles) and retries with growing backoff. Returns (removed, last_error).
    """
    import shutil

    def _onerror(func, path, _exc):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            raise

    delays = [1.5, 3.0, 6.0]
    last_error = None
    for attempt in range(attempts):
        if not os.path.isdir(directory):
            return True, None
        try:
            shutil.rmtree(directory, onerror=_onerror)
            return True, None
        except OSError as exc:
            last_error = str(exc)
            if attempt < attempts - 1:
                time.sleep(delays[min(attempt, len(delays) - 1)])
    return os.path.isdir(directory) is False, last_error


def worktree_init(project_root: str, short_description: str,
                  base_branch: str | None = None, worktree_root: str | None = None) -> dict:
    """Create an instance branch + linked worktree for an isolated orchestrator run.

    Requires a clean working tree (untracked agency scratch is tolerated). The
    worktree is created OUTSIDE the repository checkout by default, mirroring the
    pi-subagents convention: <repo-parent>/worktrees/<repo>-<slug>-<timestamp>.

    `base_branch` anchors the instance branch to a named ref instead of HEAD; an
    unresolvable `--base-branch` is an error, not a silent fallback. In detached
    HEAD state `base_branch` comes back as None and the orchestrator must ask the
    user for the PR base.
    """
    project_root = _resolve_repo_root(project_root)

    dirty = _dirty_paths(project_root, tolerated=True)
    if dirty:
        return {
            "ready": False,
            "error": "clean_working_tree_required",
            "message": (
                "Instance isolation requires a clean working tree (untracked "
                "agent_docs/ and .pi/ scratch is tolerated). Ask the user to commit "
                "or stash the pending changes, then re-run worktree init."
            ),
            "dirty_paths": dirty[:20],
            "dirty_count": len(dirty),
        }

    detached = _current_branch(project_root) in ("HEAD", "")
    if base_branch:
        if not _branch_exists(project_root, base_branch):
            return {
                "ready": False,
                "error": "base_branch_not_found",
                "message": f"--base-branch '{base_branch}' does not resolve to a ref.",
            }
        base = base_branch
        base_commit = _git(project_root, ["rev-parse", "--verify", base]).stdout.strip()
    elif detached:
        base = "HEAD"
        base_commit = _git(project_root, ["rev-parse", "HEAD"]).stdout.strip()
    else:
        base = _current_branch(project_root)
        base_commit = _git(project_root, ["rev-parse", "HEAD"]).stdout.strip()

    repo_name = os.path.basename(project_root)
    slug = _slugify(short_description)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"{AGENCY_BRANCH_PREFIX}{slug}-{timestamp}"

    if worktree_root is None:
        worktree_root = os.path.join(os.path.dirname(project_root), "worktrees")
    worktree_name = f"{repo_name}-{slug}-{timestamp}"
    worktree_path = os.path.abspath(os.path.join(worktree_root, worktree_name))

    os.makedirs(worktree_root, exist_ok=True)
    # Create the branch at the base commit, then attach a worktree to it.
    _git(project_root, ["branch", branch, base_commit])
    created = _git(project_root, ["worktree", "add", worktree_path, branch], accepted=(0, 128))
    if created.returncode != 0:
        try:
            _git(project_root, ["branch", "-D", branch])
        except RuntimeError:
            pass  # rollback failure must not mask the original error
        return {
            "ready": False,
            "error": "worktree_add_failed",
            "message": (created.stderr or created.stdout).strip()[:1000],
            "branch": branch,
        }

    detached_note = (
        " Detached HEAD: ask the user which branch the PR must target (--base) "
        "before running worktree pr." if detached else ""
    )
    return {
        "ready": True,
        "branch": branch,
        "base_branch": None if detached else base,
        "detached": detached,
        "base_commit": base_commit,
        "worktree_path": worktree_path.replace("\\", "/"),
        "project_root": project_root.replace("\\", "/"),
        "instance_root": worktree_path.replace("\\", "/"),
        "message": (
            "Instance isolation active. Re-run `init --scan-root <instance_root>` and "
            "`state init --project-root <instance_root>` so all agency artifacts live "
            "inside the instance worktree, and pass cwd=<instance_root> on every "
            "subagent spawn. Store `branch` as {BRANCH} and `base_branch` as "
            "{BASE_BRANCH} for later steps." + detached_note
        ),
    }


def worktree_status(project_root: str) -> dict:
    """Report instance branches, linked worktrees, and lane branches."""
    project_root = _resolve_repo_root(project_root)

    wt_out = _git(project_root, ["worktree", "list", "--porcelain"]).stdout
    worktrees = []
    entry: dict = {}
    for line in wt_out.splitlines():
        if not line.strip():
            if entry:
                worktrees.append(entry)
                entry = {}
            continue
        if line.startswith("worktree "):
            entry = {"path": line[len("worktree "):].strip()}
        elif line.startswith("HEAD "):
            entry["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            entry["branch"] = line[len("branch "):].strip()
        elif line.startswith("detached"):
            entry["detached"] = True
        elif line.startswith("bare"):
            entry["bare"] = True
        elif line.startswith("prunable "):
            entry["prunable"] = line[len("prunable "):].strip()
    if entry:
        worktrees.append(entry)

    for wt in worktrees:
        if wt.get("bare") or wt.get("detached"):
            continue
        # Stale/prunable entries may point at missing or locked paths; probe safely.
        try:
            wt["dirty_count"] = len(_dirty_paths(wt["path"], tolerated=True))
        except Exception as exc:
            wt["error"] = str(exc)[:300]
            wt.setdefault("prunable", "unknown (probe failed)")

    branches_out = _git(project_root, ["branch", "--list", "--format=%(refname:short)"]).stdout
    agency_branches = [b.strip() for b in branches_out.splitlines()
                       if b.strip().startswith(AGENCY_BRANCH_PREFIX)]
    lane_branches = [b.strip() for b in branches_out.splitlines()
                     if b.strip().startswith(LANE_BRANCH_PREFIX)]

    return {
        "current_branch": _current_branch(project_root),
        "worktrees": worktrees,
        "agency_branches": agency_branches,
        "lane_branches": lane_branches,
    }


def worktree_merge(project_root: str, branch: str, message: str | None = None,
                   no_ff: bool = True) -> dict:
    """Merge a lane branch into the CURRENT instance branch (no-ff by default).

    Untracked agency scratch (agent_docs/, .pi/) does not block the merge; real
    tracked changes do. On conflict, the merge is aborted and the conflicted files
    are reported so the orchestrator can surface them without a dirty merge state.
    """
    project_root = _resolve_repo_root(project_root)
    current = _current_branch(project_root)

    if current in ("HEAD", ""):
        return {"merged": False, "error": "detached_head",
                "message": "Cannot merge: instance worktree is in detached HEAD state."}
    if branch == current:
        return {"merged": False, "error": "same_branch",
                "message": f"Cannot merge {branch} into itself."}
    if not _branch_exists(project_root, branch):
        return {"merged": False, "error": "branch_not_found",
                "message": f"Branch '{branch}' does not exist."}

    dirty = _dirty_paths(project_root, tolerated=True)
    if dirty:
        return {
            "merged": False,
            "error": "clean_working_tree_required",
            "message": (
                "Merge requires a clean instance worktree (untracked agent_docs/ and "
                ".pi/ scratch is tolerated). With user approval, commit pending "
                "agency artifacts with the [agency] prefix (or stash them), then "
                "retry the merge."
            ),
            "dirty_paths": dirty[:20],
            "dirty_count": len(dirty),
        }

    args = ["merge", branch]
    if no_ff:
        args.append("--no-ff")
    if message:
        args += ["-m", message]

    # 0 = merged, 1 = conflicts, 128 = other merge refusal (e.g. unrelated histories).
    result = _git(project_root, args, accepted=(0, 1, 128))
    if result.returncode != 0:
        conflicts = []
        for line in result.stdout.splitlines():
            if line.startswith("CONFLICT"):
                if " in " in line:
                    conflicts.append(line.split(" in ", 1)[1].strip())
                elif ":" in line:
                    conflicts.append(line.split(":", 1)[1].strip())
        _git(project_root, ["merge", "--abort"], accepted=(0, 128))
        git_output = (result.stderr or result.stdout).strip()[:1000]
        if conflicts:
            return {
                "merged": False,
                "error": "merge_conflict",
                "aborted": True,
                "branch": branch,
                "into": current,
                "conflicts": conflicts,
                "git_output": git_output,
                "message": (
                    "Merge conflicts detected; the merge was aborted to keep the "
                    "instance clean. Surface the conflicting files to the user "
                    "(manual resolution, or re-open the lane to rebase its work)."
                ),
            }
        return {
            "merged": False,
            "error": "merge_failed",
            "aborted": True,
            "branch": branch,
            "into": current,
            "conflicts": [],
            "git_output": git_output,
            "message": "Merge failed without conflict markers; see git_output.",
        }

    merge_commit = _git(project_root, ["rev-parse", "HEAD"]).stdout.strip()
    return {
        "merged": True,
        "branch": branch,
        "into": current,
        "merge_commit": merge_commit,
        "message": message or f"Merge lane branch {branch} into {current}",
    }


def worktree_pr(project_root: str, title: str, base: str, body: str | None = None,
                draft: bool = False) -> dict:
    """Push the current instance branch and open a PR with the GitHub CLI (gh).

    `--base` is REQUIRED (many repos use master, develop, etc. — never guess).
    Without --body, `gh pr create --fill` derives title/body from the commits.
    The orchestrator MUST have explicit human approval for (1) pushing and
    (2) opening the PR before calling this command.
    """
    project_root = _resolve_repo_root(project_root)
    current = _current_branch(project_root)
    if current in ("HEAD", ""):
        return {"ready": False, "error": "detached_head",
                "message": "Cannot open PR: detached HEAD state."}
    if current.startswith(AGENCY_BRANCH_PREFIX) is False:
        return {
            "ready": False,
            "error": "not_an_agency_branch",
            "message": (
                f"Refusing to open a PR from '{current}': instance isolation expects "
                f"an '{AGENCY_BRANCH_PREFIX}*' branch."
            ),
        }
    if not base or base == "HEAD":
        return {
            "ready": False,
            "error": "base_required",
            "message": (
                "--base is required and must be a named branch (never 'HEAD'). "
                "Use the base_branch returned by worktree init, or ask the user."
            ),
        }

    try:
        gh = subprocess.run(["gh", "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        gh = None
    if gh is None or gh.returncode != 0:
        return {"ready": False, "error": "gh_unavailable",
                "message": "GitHub CLI (gh) is not installed or not on PATH."}

    try:
        _git(project_root, ["push", "-u", "origin", current])
    except RuntimeError as exc:
        return {
            "ready": False,
            "error": "push_failed",
            "branch": current,
            "message": str(exc)[:1000],
        }

    args = ["pr", "create", "--title", title, "--base", base, "--head", current]
    if body:
        args += ["--body", body]
    else:
        args.append("--fill")
    if draft:
        args.append("--draft")
    result = subprocess.run(["gh"] + args,
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            cwd=project_root)
    if result.returncode != 0:
        return {
            "ready": False,
            "error": "pr_create_failed",
            "pushed": True,
            "branch": current,
            "message": (result.stderr or result.stdout).strip()[:2000],
        }

    pr_url = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else None
    return {"ready": True, "pushed": True, "branch": current, "base": base, "pr_url": pr_url}


def worktree_remove(project_root: str, worktree_path: str,
                    delete_branch: str | None = None, force: bool = False) -> dict:
    """Remove an instance (or leftover) worktree; optionally delete its branch.

    Safety rules:
    - A REGISTERED worktree that git refuses to remove is only filesystem-deleted
      when it is clean (untracked agency scratch tolerated) OR --force was passed.
    - An UNREGISTERED path (never a worktree, or already deregistered) is only
      deleted with --force, so a wrong --path can never destroy data silently.
    - Branch deletion always runs against the MAIN checkout root (the worktree
      path is gone by then and is not a valid git target).
    """
    repo = _resolve_repo_root_fallback(project_root, worktree_path)
    if repo is None:
        return {
            "removed": False,
            "error": "repo_not_found",
            "message": (
                "Could not resolve a git repository from --project-root or the "
                "worktree path. Point --project-root at the main checkout."
            ),
        }
    main_root = _resolve_main_root(repo)

    registered = os.path.normpath(os.path.abspath(worktree_path)) in {
        os.path.normpath(p) for p in _registered_worktrees(repo)
    }
    removed = False
    note = None

    if registered:
        args = ["worktree", "remove", worktree_path]
        if force:
            args.append("--force")
        # 255: Windows file-lock failures while deleting; fallback handles them.
        result = _git(repo, args, accepted=(0, 128, 255))
        removed = result.returncode == 0

        if not removed:
            try:
                dirty = _dirty_paths(worktree_path, tolerated=True)
            except Exception:
                dirty = None  # probe failed (broken/stale worktree): treat as unknown
            if dirty and not force:
                return {
                    "removed": False,
                    "error": "dirty_worktree_requires_force",
                    "worktree_path": worktree_path.replace("\\", "/"),
                    "dirty_paths": dirty[:20],
                    "message": (
                        "The worktree has uncommitted (tracked) changes; deleting "
                        "them needs --force. Review and get user approval first."
                    ),
                }
            if dirty is None and not force:
                return {
                    "removed": False,
                    "error": "worktree_unprobeable_requires_force",
                    "worktree_path": worktree_path.replace("\\", "/"),
                    "message": (
                        "The worktree could not be probed for changes (broken or "
                        "stale entry); deleting it needs --force after user approval."
                    ),
                }
            # Deregistered by the failed remove; clean the leftovers on disk.
            removed, last_error = _rmtree_resilient(worktree_path)
            if not removed:
                note = (
                    f"Worktree deregistered, but the directory could not be deleted "
                    f"({last_error}); close programs holding files there and retry, "
                    f"or delete it manually."
                )
    else:
        if not force:
            return {
                "removed": False,
                "error": "not_registered",
                "worktree_path": worktree_path.replace("\\", "/"),
                "message": (
                    "Path is not a registered worktree. If it is an ORPHANED "
                    "directory from a failed removal, re-run with --force to delete "
                    "the folder (git worktree prune runs afterwards)."
                ),
            }
        removed, last_error = _rmtree_resilient(worktree_path)
        if not removed:
            note = f"Orphaned directory could not be deleted ({last_error})."

    # Prune stale registration entries after filesystem cleanup.
    _git(main_root, ["worktree", "prune"], accepted=(0, 128))

    branch_deleted = False
    branch_error = None
    if delete_branch:
        flag = "-D" if force else "-d"
        br = _git(main_root, ["branch", flag, delete_branch], accepted=(0, 1, 128))
        branch_deleted = br.returncode == 0
        if not branch_deleted:
            branch_error = (br.stderr or br.stdout).strip()[:300]

    return {
        "removed": removed,
        "worktree_path": worktree_path.replace("\\", "/"),
        "main_root": main_root.replace("\\", "/"),
        "branch_deleted": branch_deleted,
        "branch": delete_branch,
        "branch_error": branch_error,
        "message": note,
    }


def _resolve_repo_root_fallback(project_root: str, worktree_path: str | None = None) -> str | None:
    """Resolve the main repository root, tolerating a broken/removed worktree.

    Order: the given project_root, then the worktree path itself, then its parent
    directory (useful when the instance worktree was already deregistered).
    Returns None when nothing resolves to a git repository.
    """
    candidates = [project_root]
    if worktree_path:
        candidates += [worktree_path, os.path.dirname(os.path.abspath(worktree_path))]
    for candidate in candidates:
        try:
            return _resolve_repo_root(candidate)
        except Exception:
            continue
    return None


def handle_worktree(args: list[str]) -> dict:
    """Main entry point for the worktree command."""
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        sys.exit(0)

    subcmd = args[0]

    if subcmd == "init":
        parser = argparse.ArgumentParser(prog="agency_cli worktree init")
        parser.add_argument("--project-root", required=True)
        parser.add_argument("--short-description", required=True)
        parser.add_argument("--base-branch", default=None)
        parser.add_argument("--worktree-root", default=None)
        opts = parser.parse_args(args[1:])
        return worktree_init(opts.project_root, opts.short_description,
                             opts.base_branch, opts.worktree_root)

    elif subcmd == "status":
        parser = argparse.ArgumentParser(prog="agency_cli worktree status")
        parser.add_argument("--project-root", required=True)
        opts = parser.parse_args(args[1:])
        return worktree_status(opts.project_root)

    elif subcmd == "merge":
        parser = argparse.ArgumentParser(prog="agency_cli worktree merge")
        parser.add_argument("--project-root", required=True)
        parser.add_argument("--branch", required=True)
        parser.add_argument("--message", default=None)
        parser.add_argument("--no-ff", dest="no_ff", action="store_true", default=True)
        parser.add_argument("--ff", dest="no_ff", action="store_false")
        opts = parser.parse_args(args[1:])
        return worktree_merge(opts.project_root, opts.branch, opts.message, opts.no_ff)

    elif subcmd == "pr":
        parser = argparse.ArgumentParser(prog="agency_cli worktree pr")
        parser.add_argument("--project-root", required=True)
        parser.add_argument("--title", required=True)
        parser.add_argument("--base", required=True)
        parser.add_argument("--body", default=None)
        parser.add_argument("--draft", action="store_true")
        opts = parser.parse_args(args[1:])
        return worktree_pr(opts.project_root, opts.title, opts.base, opts.body, opts.draft)

    elif subcmd == "remove":
        parser = argparse.ArgumentParser(prog="agency_cli worktree remove")
        parser.add_argument("--project-root", required=True)
        parser.add_argument("--path", required=True)
        parser.add_argument("--delete-branch", default=None)
        parser.add_argument("--force", action="store_true")
        opts = parser.parse_args(args[1:])
        return worktree_remove(opts.project_root, opts.path, opts.delete_branch, opts.force)

    else:
        raise ValueError(f"Unknown subcommand: {subcmd}. Valid: init, status, merge, pr, remove")
