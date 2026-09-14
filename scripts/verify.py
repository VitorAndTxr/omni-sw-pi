#!/usr/bin/env python3
"""Repository smoke checks for pi-omni-sw. Standard library only.

Run with: python scripts/verify.py   (or: npm test)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "skills" / "omni-sw-shared" / "scripts" / "agency_cli.py"

EXPECTED_PHASES = [
    "plan", "design", "validate", "specify",
    "implement", "review", "test", "document",
]

failures: list[str] = []


def ok(message: str) -> None:
    print(f"[ok] {message}")


def fail(message: str) -> None:
    failures.append(message)
    print(f"[FAIL] {message}")


def run_cli(*args: str) -> dict | None:
    try:
        proc = subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        fail(f"agency_cli {' '.join(args)} could not run: {exc}")
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        fail(f"agency_cli {' '.join(args)} did not return JSON: {proc.stdout[:200]!r}")
        return None


def check_manifest() -> None:
    try:
        pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"cannot read package.json: {exc}")
        return
    pi = pkg.get("pi", {})
    missing = [key for key in ("extensions", "skills", "subagents") if not pi.get(key)]
    if missing:
        fail(f"pi manifest missing entries: {missing}")
    elif pkg.get("name") != "pi-omni-sw":
        fail("unexpected package name")
    elif "pi-package" not in pkg.get("keywords", []):
        fail('keywords missing "pi-package"')
    else:
        ok("package.json manifest valid")


def check_phase_sequence() -> None:
    data = run_cli("phase", "sequence")
    if data is None:
        return
    if data.get("phases") == EXPECTED_PHASES:
        ok(f"phase sequence OK ({len(EXPECTED_PHASES)} phases)")
    else:
        fail(f"unexpected phases: {data.get('phases')}")


def check_specify_wiring() -> None:
    agents = run_cli("agent", "list", "--phase", "specify")
    expected = run_cli("backlog", "expected-status", "--phase", "specify")
    if agents is None or expected is None:
        return
    has_qa_lead = any(a.get("agent") == "omni-sw-qa" for a in agents)
    if has_qa_lead and expected.get("to") == "Specified":
        ok("specify phase wired (QA lead -> Specified)")
    else:
        fail(f"specify wiring wrong: agents={agents}, expected={expected}")


def check_skills_and_agents() -> None:
    try:
        skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        agent_files = sorted((ROOT / "agents").glob("*.md"))
    except OSError as exc:
        fail(f"cannot scan skills/agents: {exc}")
        return

    bad: list[str] = []
    for skill_md in skill_files:
        try:
            head = skill_md.read_text(encoding="utf-8")[:200]
        except OSError:
            bad.append(str(skill_md))
            continue
        if not head.startswith("---"):
            bad.append(str(skill_md))

    if bad:
        fail(f"skills missing frontmatter: {bad}")
    elif len(agent_files) != 5:
        fail(f"expected 5 agent files, found {len(agent_files)}")
    else:
        ok(f"skills ({len(skill_files)}) and agents ({len(agent_files)}) OK")


def main() -> int:
    print(f"pi-omni-sw verify — {ROOT}\n")
    if not CLI.is_file():
        fail(f"agency_cli.py not found at {CLI}")
    check_manifest()
    check_phase_sequence()
    check_specify_wiring()
    check_skills_and_agents()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed.")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
