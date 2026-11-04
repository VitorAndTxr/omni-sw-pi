"""
Per-project hygiene policy -- agent_docs/agency/hygiene.json.

Makes the code/test hygiene policy configurable per project. The config file is
created by `agency_cli init --create-dirs` with the DEFAULT RESTRICTIVE content
(DEFAULT_HYGIENE_CONFIG below): narrative comments, XML doc summaries in
production code and agent-document references in test code are all forbidden by
default, matching the hygiene note of 2025-10-21. Projects that want a category
allowed flip the flag to true (e.g. "xmlSummaries": true for projects that want
XML documentation blocks).

Semantics:
  - false = forbidden (the rule is enforced and injected into agent prompts)
  - true  = allowed (the rule is not injected)
  - forbiddenTokens = extra list of forbidden substrings, applied to tests AND
    production code.
  - Absent file = NO injection at all (pre-config behavior preserved). The
    restrictive default lives in the FILE CONTENT written by init, not in a
    runtime fallback.

In `phase prepare`, when the file exists and parses, the rendered policy is
appended to every agent prompt of the design/specify/implement/review/test
phases. A malformed file never fails prepare: a warning is emitted in the
output and prepare continues without policy.
"""

import json
import os

# Config file path relative to the project root.
HYGIENE_RELATIVE_PATH = os.path.join("agent_docs", "agency", "hygiene.json")

# Default content written by `agency_cli init --create-dirs`. Deliberately
# RESTRICTIVE (safe default): projects opt OUT of a rule by flipping its flag
# to true, never the other way around.
DEFAULT_HYGIENE_CONFIG = {
    "production": {"narrativeComments": False, "xmlSummaries": False},
    "tests": {"agentDocReferences": False},
    "forbiddenTokens": [
        "US-",
        "AC-",
        "DEC-",
        "CONTRACTS",
        "TEST_SPEC",
        "agent_docs",
        "§",
    ],
}

# Phases whose agent prompts receive the policy section in `phase prepare`.
HYGIENE_PHASES = {"design", "specify", "implement", "review", "test"}


def _fwd(p: str) -> str:
    """Normalize path to forward slashes (matches CLI output convention)."""
    return p.replace("\\", "/") if p else p


def hygiene_config_path(project_root: str) -> str:
    """Absolute path of the project's hygiene.json."""
    return os.path.join(project_root, HYGIENE_RELATIVE_PATH)


def default_hygiene_json() -> str:
    """Serialize the default (restrictive) policy as file content."""
    return json.dumps(DEFAULT_HYGIENE_CONFIG, indent=2, ensure_ascii=False) + "\n"


def ensure_hygiene_config(project_root: str) -> dict:
    """Create hygiene.json with the default restrictive content if missing.

    Non-destructive: an existing file is never overwritten.

    Returns {"path": ..., "action": "created"|"already_exists"|"error"[, "error"]}.
    """
    path = hygiene_config_path(project_root)
    result = {"path": _fwd(path)}
    if os.path.isfile(path):
        result["action"] = "already_exists"
        return result
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(default_hygiene_json())
        result["action"] = "created"
    except OSError as e:
        result["action"] = "error"
        result["error"] = str(e)
    return result


def load_hygiene_config(project_root: str) -> dict:
    """Load the per-project hygiene policy.

    Returns one of:
      {"status": "not_configured", "path": ...}           -- file absent: no injection
      {"status": "invalid", "path": ..., "warning": ...}  -- malformed: warn, no injection
      {"status": "loaded", "path": ..., "config": {...}}  -- policy to render
    """
    path = hygiene_config_path(project_root)
    if not os.path.isfile(path):
        return {"status": "not_configured", "path": _fwd(path)}
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError) as e:
        # json.JSONDecodeError and UnicodeDecodeError are ValueError subclasses.
        return {
            "status": "invalid",
            "path": _fwd(path),
            "warning": (
                f"Hygiene policy file is malformed and was ignored "
                f"(continuing without policy): {_fwd(path)}: {e}"
            ),
        }
    if not isinstance(config, dict):
        return {
            "status": "invalid",
            "path": _fwd(path),
            "warning": (
                f"Hygiene policy file must contain a JSON object and was ignored "
                f"(continuing without policy): {_fwd(path)}"
            ),
        }
    return {"status": "loaded", "path": _fwd(path), "config": config}


def hygiene_policy_section(config: dict) -> str:
    """Render the HYGIENE POLICY prompt section for the enforced categories.

    A category is enforced when its flag is explicitly false. Returns "" when
    nothing is enforced (all flags true and no forbidden tokens): nothing is
    injected in that case.
    """
    lines = [
        "HYGIENE POLICY (project config agent_docs/agency/hygiene.json — obedeça rigorosamente):"
    ]
    production = config.get("production")
    if isinstance(production, dict):
        if production.get("narrativeComments") is False:
            lines.append(
                "- Do NOT add comments or doc summaries that narrate the "
                "change/modification; code explains itself."
            )
        if production.get("xmlSummaries") is False:
            lines.append(
                "- Do NOT add <summary>/<remarks> XML documentation blocks in production code."
            )
    tests = config.get("tests")
    if isinstance(tests, dict) and tests.get("agentDocReferences") is False:
        lines.append(
            "- Do NOT reference agent documents in test code (doc comments, identifiers, "
            "Anchor constants, assertion messages): no US-/AC-/DEC-/CONTRACTS/TEST_SPEC/"
            "agent_docs/§ references."
        )
    tokens = config.get("forbiddenTokens")
    if isinstance(tokens, list):
        rendered = ", ".join(str(t) for t in tokens)
        if rendered:
            lines.append(
                f"- Forbidden substrings in new code (tests AND production): [{rendered}]."
            )
    if len(lines) == 1:
        return ""
    return "\n".join(lines)
