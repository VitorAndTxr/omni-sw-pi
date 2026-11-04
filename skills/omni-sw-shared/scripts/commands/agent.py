"""
agency_cli agent -- Agent configuration: model lookup, naming, prompt generation, ordering.

Usage:
    agency_cli agent model --role <role> --phase <phase>
    agency_cli agent name --role <role> --phase <phase> --type <lead|assist>
    agency_cli agent list --phase <phase>
    agency_cli agent prompt --role <role> --phase <phase> --project-root <path> ...
    agency_cli agent order --phase <phase>
"""

import argparse
import json
import os

VALID_ROLES = {"pm", "po", "tl", "dev", "qa"}
VALID_PHASES = {
    "plan",
    "design",
    "validate",
    "specify",
    "implement",
    "review",
    "test",
    "document",
}


def validate_role(role: str) -> str:
    """Validate and normalize role name."""
    role = role.strip().lower()
    if role not in VALID_ROLES:
        raise ValueError(
            f"Invalid role: '{role}'. Valid roles: {', '.join(sorted(VALID_ROLES))}"
        )
    return role


def validate_phase(phase: str) -> str:
    """Validate and normalize phase name."""
    phase = phase.strip().lower()
    if phase not in VALID_PHASES:
        raise ValueError(
            f"Invalid phase: '{phase}'. Valid phases: {', '.join(VALID_PHASES)}"
        )
    return phase


# Full agent matrix: (phase, role) -> {type, description}.
# Per-agent models come from models.json, keyed by "<phase>:<role>".
AGENT_MATRIX = {
    # Plan
    ("plan", "pm"): {
        "type": "lead",
        "desc": "Lead: produce PROJECT_BRIEF.md",
        "skill": "/pm plan",
    },
    ("plan", "po"): {
        "type": "lead",
        "desc": "Lead: create backlog from brief",
        "skill": "/po plan",
    },
    ("plan", "tl"): {
        "type": "assist",
        "desc": "Assist: risk notes",
        "skill": "/tl plan",
    },
    ("plan", "dev"): {
        "type": "assist",
        "desc": "Assist: implementability notes",
        "skill": "/dev plan",
    },
    ("plan", "qa"): {
        "type": "assist",
        "desc": "Assist: testability notes",
        "skill": "/qa plan",
    },
    # Design
    ("design", "tl"): {
        "type": "lead",
        "desc": "Lead: produce ARCHITECTURE.md",
        "skill": "/tl design",
    },
    ("design", "dev"): {
        "type": "assist",
        "desc": "Assist: implementability review",
        "skill": "/dev design",
    },
    ("design", "qa"): {
        "type": "assist",
        "desc": "Assist: testability review",
        "skill": "/qa design",
    },
    # Validate
    ("validate", "pm"): {
        "type": "lead",
        "desc": "Lead: business validation",
        "skill": "/pm validate",
    },
    ("validate", "tl"): {
        "type": "lead",
        "desc": "Lead: technical validation",
        "skill": "/tl validate",
    },
    ("validate", "po"): {
        "type": "assist",
        "desc": "Assist: backlog alignment check",
        "skill": "/po validate",
    },
    # Specify (RED) -- QA authors the business-rule test suite from contracts
    ("specify", "qa"): {
        "type": "lead",
        "desc": "Lead: author failing business-rule tests (RED)",
        "skill": "/qa specify",
    },
    ("specify", "tl"): {
        "type": "assist",
        "desc": "Assist: contract coverage review",
        "skill": "/tl specify",
    },
    # Implement (GREEN)
    ("implement", "dev"): {
        "type": "lead",
        "desc": "Lead: write production code",
        "skill": "/dev implement",
    },
    ("implement", "tl"): {
        "type": "assist",
        "desc": "Assist: on-demand tech guidance",
        "skill": "/tl implement",
    },
    # Review
    ("review", "tl"): {
        "type": "lead",
        "desc": "Lead: code review, produce REVIEW.md",
        "skill": "/tl review",
    },
    ("review", "qa"): {
        "type": "assist",
        "desc": "Assist: correctness review",
        "skill": "/qa review",
    },
    # Test
    ("test", "qa"): {
        "type": "lead",
        "desc": "Lead: verify frozen suite, TEST_REPORT.md",
        "skill": "/qa test",
    },
    ("test", "tl"): {
        "type": "assist",
        "desc": "Assist: coverage review",
        "skill": "/tl test",
    },
    # Document
    ("document", "pm"): {
        "type": "lead",
        "desc": "Lead: README.md, CHANGELOG.md",
        "skill": "/pm document",
    },
    ("document", "tl"): {
        "type": "lead",
        "desc": "Lead: API_REFERENCE.md, ARCHITECTURE.md",
        "skill": "/tl document",
    },
    ("document", "po"): {
        "type": "assist",
        "desc": "Assist: documentation verification",
        "skill": "/po document",
    },
    ("document", "dev"): {
        "type": "assist",
        "desc": "Assist: developer documentation",
        "skill": "/dev document",
    },
    ("document", "qa"): {
        "type": "assist",
        "desc": "Assist: test documentation",
        "skill": "/qa document",
    },
}


# Canonical skill command for every role/phase (pi syntax).
def skill_command(role: str, phase: str) -> str:
    return f"/skill:omni-sw-{role} {phase}"


# Per-agent model config, shared by all agency skills: "<phase>:<role>" ->
# concrete pi model id (any provider) or null/absent to inherit the session model.
_MODELS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models.json")
)


def resolve_model(phase: str, role: str) -> str | None:
    """Resolve the configured model for a (phase, role) pair from models.json.

    Keyed by "<phase>:<role>" (e.g. "design:tl"). Values are concrete pi model
    ids of ANY provider, optionally with a `:thinking` suffix (off..max), e.g.
    "openai/gpt-5.2:high", "zai/glm-5.3:medium". Provider-agnostic: no vendor
    or tier naming is assumed anywhere in the extension.
    Returns None when the key is absent or null: the spawn omits the model
    override and inherits the session/default model.
    """
    try:
        with open(_MODELS_PATH, encoding="utf-8") as f:
            mapping = json.load(f)
    except (OSError, ValueError):
        return None
    value = mapping.get(f"{phase}:{role}")
    return value.strip() if isinstance(value, str) and value.strip() else None


# Normalize the legacy `skill` fields so no caller can read a stale command.
for (_p, _r), _info in AGENT_MATRIX.items():
    _info["skill"] = skill_command(_r, _p)


# Sequential dependencies within phases
PHASE_ORDER = {
    "plan": [["pm", "tl", "dev", "qa"], ["po"]],  # PM + assists parallel, PO after PM
    "design": [["tl"], ["dev", "qa"]],  # TL first, Dev/QA after
    "validate": [["pm", "tl"], ["po"]],  # PM+TL parallel, PO after
    "specify": [["qa"], ["tl"]],  # QA authors RED tests, TL reviews contract coverage
    "implement": [["dev"], ["tl"]],  # Dev makes tests green, TL on-demand guidance
    "review": [["tl"], ["qa"]],  # TL first, QA after
    "test": [["qa"], ["tl"]],  # QA verifies, TL coverage review after
    "document": [["pm", "tl"], ["po", "dev", "qa"]],  # PM+TL parallel, rest after
}

# Gate verdict suffixes for lead prompts
GATE_SUFFIXES = {
    "validate": "End output with [VERDICT:APPROVED] or [VERDICT:REPROVED].",
    "specify": "End output with [GATE:RED_PASS], [GATE:RED_FAIL_TESTS], or [GATE:RED_FAIL_CONTRACT].",
    "review": "End output with [GATE:PASS] or [GATE:FAIL].",
    "test": "End output with [GATE:PASS], [GATE:FAIL_BUG], or [GATE:FAIL_TEST].",
}

# Guidance injected when resuming a child session after a gate loop-back. The child
# already has its role skill, CLAUDE.md and the phase artifacts in context, so the
# continuation prompt only carries what changed: the verdict and the focus.
LOOP_BACK_HINTS = {
    "validate": (
        "Address only the reproved items recorded in VALIDATION.md. Do not rewrite "
        "sections that were already approved."
    ),
    "specify": (
        "Re-open TEST_SPEC.md and the frozen suite and fix ONLY the flagged items: "
        "missing tests for Must ACs or contracts, tests that pass, infrastructure "
        "errors, or contract gaps. Do not rewrite the whole suite and never touch src/."
    ),
    "review": "Address only the blocking issues listed in REVIEW.md.",
    "test": "Address only the failing checks recorded in TEST_REPORT.md.",
}

# Same idea for assist agents: they must not redo the whole review, only the delta.
LOOP_BACK_ASSIST_HINTS = {
    "validate": "Re-check only the items the PM reproved and update your [NOTES].",
    "specify": "Re-check only what changed in TEST_SPEC.md and the suite against CONTRACTS.md. Do not re-review unchanged contracts.",
    "review": "Re-check only the blocking issues and the areas the previous review touched.",
    "test": "Re-check only the failing checks and the areas changed since your previous review.",
}
LOOP_BACK_ASSIST_DEFAULT = (
    "Re-check only what changed since your previous review and report the delta as [NOTES]. "
    "Do not repeat findings you already reported."
)


def get_agent_name(role: str, phase: str, agent_type: str) -> str:
    """Generate deterministic agent name."""
    role = validate_role(role)
    phase = validate_phase(phase)
    if agent_type == "assist":
        return f"{role}-{phase}-assist"
    return f"{role}-{phase}"


def get_model(role: str, phase: str) -> str | None:
    """Resolve the configured model for role/phase (None = inherit session model)."""
    role = validate_role(role)
    phase = validate_phase(phase)
    key = (phase, role)
    if key not in AGENT_MATRIX:
        raise ValueError(f"No agent defined for role={role}, phase={phase}")
    return resolve_model(phase, role)


def list_agents(phase: str, skip_assists: bool = False) -> list[dict]:
    """List all agents for a phase with full config.

    Args:
        phase: Phase name.
        skip_assists: If True, exclude assist agents (only return leads).
    """
    phase = validate_phase(phase)
    agents = []
    for (p, role), info in AGENT_MATRIX.items():
        if p == phase:
            if skip_assists and info["type"] == "assist":
                continue
            agents.append(
                {
                    "role": role,
                    "name": get_agent_name(role, phase, info["type"]),
                    "agent": f"omni-sw-{role}",
                    "model": resolve_model(phase, role),
                    "type": info["type"],
                    "description": info["desc"],
                    "skill_command": skill_command(role, phase),
                }
            )
    if not agents:
        raise ValueError(f"No agents defined for phase: {phase}")
    return agents


def _bash_path(path: str) -> str:
    """Normalize a path for bash on Windows: forward slashes, no trailing slash."""
    if not path:
        return path
    return path.replace("\\", "/").rstrip("/")


def generate_prompt(
    role: str,
    phase: str,
    project_root: str,
    script_path: str,
    backlog_path: str,
    objective: str,
    agent_type: str | None = None,
    cli_path: str | None = None,
    state_path: str | None = None,
    docs_path: str | None = None,
    iteration: int = 1,
    prior_verdict: str | None = None,
    resumed: bool = False,
) -> str:
    """Generate the full agent spawn prompt.

    All paths are normalized to forward slashes for bash compatibility on Windows.

    When `resumed` is True the child session already holds its role skill, CLAUDE.md
    and the phase artifacts, so a short continuation prompt is emitted instead of the
    full onboarding prompt. This is what makes a gate loop-back continue the same
    session rather than re-instantiating the agent from zero.
    """
    role = validate_role(role)
    phase = validate_phase(phase)
    key = (phase, role)
    if key not in AGENT_MATRIX:
        raise ValueError(f"No agent defined for role={role}, phase={phase}")

    info = AGENT_MATRIX[key]
    atype = agent_type or info["type"]
    skill_cmd = skill_command(role, phase)
    skills_root = (
        os.path.dirname(os.path.dirname(os.path.dirname(cli_path)))
        if cli_path
        else None
    )
    skill_path = (
        _bash_path(os.path.join(skills_root, f"omni-sw-{role}", "SKILL.md"))
        if skills_root
        else None
    )

    # Normalize all paths for bash
    project_root = _bash_path(project_root)
    script_path = _bash_path(script_path)
    backlog_path = _bash_path(backlog_path)
    cli_path = _bash_path(cli_path) if cli_path else None
    state_path = _bash_path(state_path) if state_path else None
    docs_path = _bash_path(docs_path) if docs_path else None

    # Build environment block with all resolved paths
    env_lines = [
        f"PROJECT_ROOT={project_root}",
        f"SCRIPT_PATH={script_path}",
        f"BACKLOG_PATH={backlog_path}",
    ]
    if cli_path:
        env_lines.append(f"CLI_PATH={cli_path}")
    if state_path:
        env_lines.append(f"STATE_PATH={state_path}")
    if docs_path:
        env_lines.append(f"DOCS_PATH={docs_path}")
    agent_common = None
    if cli_path:
        agent_common = _bash_path(
            os.path.normpath(
                os.path.join(os.path.dirname(cli_path), "..", "agent-common.md")
            )
        )
        env_lines.append(f"AGENT_COMMON={agent_common}")
    if skill_path:
        env_lines.append(f"SKILL_PATH={skill_path}")
    env_block = " | ".join(env_lines)

    if resumed:
        verdict = (
            prior_verdict
            if prior_verdict
            else "unknown -- read the phase artifact for the flagged items"
        )
        parts = [
            f"CONTINUATION -- you are the same {role.upper()} session, iteration {iteration} of phase {phase}.",
            f"Do NOT re-read your role skill at {skill_path} or CLAUDE.md at {project_root}/CLAUDE.md; "
            f"you already have them in context.",
            f"Previous gate verdict: {verdict}.",
        ]
        if atype == "lead":
            focus = LOOP_BACK_HINTS.get(
                phase, "Address only the items flagged by the previous gate."
            )
            parts.append(f"Focus: {focus}")
            gate_suffix = GATE_SUFFIXES.get(phase.lower())
            if gate_suffix:
                parts.append(gate_suffix)
        else:
            focus = LOOP_BACK_ASSIST_HINTS.get(phase, LOOP_BACK_ASSIST_DEFAULT)
            parts.append(f"Focus: {focus}")
            parts.append("Provide your [NOTES] and review findings for the delta only.")
        parts.append(
            f"Resolved paths (unchanged, use directly, do NOT re-resolve via Glob): {env_block}."
        )
        parts.append(
            "If you need clarification, list all questions prefixed with [QUESTIONS]. "
            "Do NOT call the ask_user_question tool -- return questions to me prefixed with [QUESTIONS]."
        )
        parts.append("When done, mark your task as completed with the `todo` tool.")
        return " ".join(parts)

    if atype == "lead":
        prompt = (
            f"You are the {role.upper()}. Read and follow your role skill at {skill_path} (slash command: {skill_cmd}). "
            f"The project objective is: {objective}. "
            f"Resolved paths (use these directly, do NOT re-resolve via Glob): {env_block}. "
            f"Read CLAUDE.md at {project_root}/CLAUDE.md for context. "
            f"If you need clarification, list all questions prefixed with [QUESTIONS]. "
            f"Do NOT call the ask_user_question tool -- return questions to me prefixed with [QUESTIONS]. "
            f"When done, mark your task as completed with the `todo` tool."
        )
        # Add gate suffix if applicable
        gate_suffix = GATE_SUFFIXES.get(phase.lower())
        if gate_suffix:
            prompt += f" {gate_suffix}"
    else:
        prompt = (
            f"You are the {role.upper()} assist. Read and follow your role skill at {skill_path} (slash command: {skill_cmd}). "
            f"The project objective is: {objective}. "
            f"Resolved paths (use these directly, do NOT re-resolve via Glob): {env_block}. "
            f"Read CLAUDE.md at {project_root}/CLAUDE.md for context. "
            f"Provide your [NOTES] and review findings. "
            f"Do NOT call the ask_user_question tool -- return questions to me prefixed with [QUESTIONS]. "
            f"When done, mark your task as completed with the `todo` tool."
        )

    return prompt


def get_order(phase: str, skip_assists: bool = False) -> list[dict]:
    """Get execution order (waves) for a phase.

    Args:
        phase: Phase name.
        skip_assists: If True, exclude assist agents from waves.
    """
    phase = validate_phase(phase)
    if phase not in PHASE_ORDER:
        raise ValueError(f"Unknown phase: {phase}")

    waves = []
    for i, wave_roles in enumerate(PHASE_ORDER[phase]):
        wave_agents = []
        for role in wave_roles:
            key = (phase, role)
            if key in AGENT_MATRIX:
                info = AGENT_MATRIX[key]
                if skip_assists and info["type"] == "assist":
                    continue
                wave_agents.append(
                    {
                        "role": role,
                        "name": get_agent_name(role, phase, info["type"]),
                        "model": resolve_model(phase, role),
                        "type": info["type"],
                    }
                )
        # Only include wave if it has agents after filtering
        if wave_agents:
            waves.append(
                {
                    "wave": i + 1,
                    "parallel": len(wave_agents) > 1,
                    "agents": wave_agents,
                    "blocked_by": f"wave_{i}" if i > 0 else None,
                }
            )

    return waves


def handle_agent(args: list[str]) -> dict | list | str:
    if not args:
        raise ValueError("Subcommand required: model, name, list, prompt, order")

    subcmd = args[0]

    if subcmd == "model":
        parser = argparse.ArgumentParser(prog="agency_cli agent model")
        parser.add_argument("--role", required=True)
        parser.add_argument("--phase", required=True)
        opts = parser.parse_args(args[1:])
        return {"model": get_model(opts.role, opts.phase)}

    elif subcmd == "name":
        parser = argparse.ArgumentParser(prog="agency_cli agent name")
        parser.add_argument("--role", required=True)
        parser.add_argument("--phase", required=True)
        parser.add_argument("--type", required=True, choices=["lead", "assist"])
        opts = parser.parse_args(args[1:])
        return {"name": get_agent_name(opts.role, opts.phase, opts.type)}

    elif subcmd == "list":
        parser = argparse.ArgumentParser(prog="agency_cli agent list")
        parser.add_argument("--phase", required=True)
        parser.add_argument(
            "--skip-assists",
            action="store_true",
            help="Exclude assist agents (only return leads)",
        )
        opts = parser.parse_args(args[1:])
        return list_agents(opts.phase, skip_assists=opts.skip_assists)

    elif subcmd == "prompt":
        parser = argparse.ArgumentParser(prog="agency_cli agent prompt")
        parser.add_argument("--role", required=True)
        parser.add_argument("--phase", required=True)
        parser.add_argument("--project-root", required=True)
        parser.add_argument("--script-path", required=True)
        parser.add_argument("--backlog-path", required=True)
        parser.add_argument("--objective", required=False, default=None)
        parser.add_argument(
            "--objective-stdin",
            action="store_true",
            help="Read objective from stdin (avoids shell escaping issues)",
        )
        parser.add_argument("--type", choices=["lead", "assist"], default=None)
        parser.add_argument(
            "--cli-path",
            required=False,
            default=None,
            help="Path to agency_cli.py (auto-derived if omitted)",
        )
        parser.add_argument(
            "--state-path", required=False, default=None, help="Path to STATE.json"
        )
        opts = parser.parse_args(args[1:])
        if opts.objective_stdin:
            import sys as _sys

            objective = _sys.stdin.read().strip()
        elif opts.objective:
            objective = opts.objective
        else:
            raise ValueError("Either --objective or --objective-stdin is required")
        # Auto-derive CLI path if not provided
        cli_path = opts.cli_path or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "agency_cli.py")
        )
        prompt = generate_prompt(
            opts.role,
            opts.phase,
            opts.project_root,
            opts.script_path,
            opts.backlog_path,
            objective,
            opts.type,
            cli_path=cli_path,
            state_path=opts.state_path,
        )
        return {
            "prompt": prompt,
            "model": get_model(opts.role, opts.phase),
            "name": get_agent_name(
                opts.role,
                opts.phase,
                opts.type
                or AGENT_MATRIX[(opts.phase.lower(), opts.role.lower())]["type"],
            ),
        }

    elif subcmd == "order":
        parser = argparse.ArgumentParser(prog="agency_cli agent order")
        parser.add_argument("--phase", required=True)
        parser.add_argument(
            "--skip-assists",
            action="store_true",
            help="Exclude assist agents from wave ordering",
        )
        opts = parser.parse_args(args[1:])
        return get_order(opts.phase, skip_assists=opts.skip_assists)

    else:
        raise ValueError(f"Unknown subcommand: {subcmd}")
