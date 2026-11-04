"""
agency_cli phase -- Phase state machine for SDLC orchestration.

Usage:
    agency_cli phase sequence                     # Returns ordered phase list
    agency_cli phase next --current <phase> --verdict <verdict>   # Next phase after gate
    agency_cli phase artifacts --phase <phase> --project-root <path>  # Artifact paths
    agency_cli phase info --phase <phase>         # Phase metadata
    agency_cli phase prepare --phase <phase> --project-root <path> --state-path <path> --script-path <path> --backlog-path <path> --objective <text> [--skip-assists]
        # Combined: updates state + returns agent order + prompts in ONE call (reduces orchestrator turns)
"""

import argparse
import os
import json
import sys

# Canonical phase sequence
PHASES = [
    "plan",
    "design",
    "validate",
    "specify",
    "implement",
    "review",
    "test",
    "document",
]

# Phase metadata
PHASE_INFO = {
    "plan": {
        "index": 0,
        "goal": "docs/PROJECT_BRIEF.md + backlog",
        "has_gate": False,
        "artifacts": ["docs/PROJECT_BRIEF.md"],
    },
    "design": {
        "index": 1,
        "goal": "docs/ARCHITECTURE.md + docs/CONTRACTS.md",
        "has_gate": False,
        "artifacts": ["docs/ARCHITECTURE.md", "docs/CONTRACTS.md"],
    },
    "validate": {
        "index": 2,
        "goal": "docs/VALIDATION.md with dual verdicts",
        "has_gate": True,
        "gate_type": "dual",
        "artifacts": ["docs/VALIDATION.md"],
    },
    "specify": {
        "index": 3,
        "goal": "docs/TEST_SPEC.md + failing tests (RED)",
        "has_gate": True,
        "gate_type": "red",
        "artifacts": ["docs/TEST_SPEC.md", "tests/"],
    },
    "implement": {
        "index": 4,
        "goal": "Source code in src/ (GREEN) + complementary tests",
        "has_gate": False,
        "artifacts": ["src/"],
    },
    "review": {
        "index": 5,
        "goal": "docs/REVIEW.md",
        "has_gate": True,
        "gate_type": "single",
        "artifacts": ["docs/REVIEW.md"],
    },
    "test": {
        "index": 6,
        "goal": "Verify frozen suite + docs/TEST_REPORT.md",
        "has_gate": True,
        "gate_type": "single_extended",
        "artifacts": ["tests/", "docs/TEST_REPORT.md"],
    },
    "document": {
        "index": 7,
        "goal": "README.md, CHANGELOG.md, docs/API_REFERENCE.md",
        "has_gate": False,
        "artifacts": ["README.md", "CHANGELOG.md", "docs/API_REFERENCE.md"],
    },
}


def resolve_artifact_path(artifact_template: str, docs_path: str) -> str:
    """Replace 'docs/' prefix with the dynamic docs_path if applicable."""
    if artifact_template.startswith("docs/"):
        return os.path.join(docs_path, artifact_template[5:])
    return artifact_template


def get_next_phase(current: str, verdict: str) -> dict:
    """Determine next phase based on current phase and gate verdict."""
    current = current.lower()
    verdict = verdict.upper().strip()

    if current == "validate":
        # Dual gate: expects "APPROVED,APPROVED" or "REPROVED,APPROVED" etc.
        parts = [v.strip() for v in verdict.split(",")]
        if len(parts) != 2:
            raise ValueError(
                f"Validate gate requires two verdicts (PM,TL). Got: {verdict}"
            )
        pm_verdict, tl_verdict = parts

        if pm_verdict == "APPROVED" and tl_verdict == "APPROVED":
            return {
                "next_phase": "specify",
                "action": "proceed",
                "reason": "Both approved -- proceed to Specify (RED)",
            }
        elif pm_verdict == "REPROVED":
            return {
                "next_phase": "plan",
                "action": "loop_back",
                "reason": "PM reproved -- return to Plan",
            }
        elif tl_verdict == "REPROVED":
            return {
                "next_phase": "design",
                "action": "loop_back",
                "reason": "TL reproved -- return to Design",
            }

    elif current == "specify":
        # RED gate: verdict is RED_PASS, RED_FAIL_TESTS, or RED_FAIL_CONTRACT
        if verdict == "RED_PASS":
            return {
                "next_phase": "implement",
                "action": "proceed",
                "reason": "RED baseline valid -- proceed to Implement (GREEN)",
            }
        elif verdict == "RED_FAIL_TESTS":
            return {
                "next_phase": "specify",
                "action": "loop_back",
                "reason": "Test spec incomplete or not failing correctly -- revise tests",
            }
        elif verdict == "RED_FAIL_CONTRACT":
            return {
                "next_phase": "design",
                "action": "loop_back",
                "reason": "Contracts missing/ambiguous -- return to Design & Contracts",
            }

    elif current == "review":
        if verdict == "PASS":
            return {
                "next_phase": "test",
                "action": "proceed",
                "reason": "Review passed",
            }
        elif verdict == "FAIL":
            return {
                "next_phase": "implement",
                "action": "loop_back",
                "reason": "Blocking issues found",
            }

    elif current == "test":
        if verdict == "PASS":
            return {
                "next_phase": "document",
                "action": "proceed",
                "reason": "All tests pass",
            }
        elif verdict == "FAIL_BUG":
            return {
                "next_phase": "implement",
                "action": "loop_back",
                "reason": "Bug found -- return to Implement",
            }
        elif verdict == "FAIL_TEST":
            return {
                "next_phase": "specify",
                "action": "loop_back",
                "reason": "Test issue -- QA owns the suite, return to Specify to revise tests, then re-verify",
            }

    raise ValueError(f"Invalid phase/verdict combination: {current}/{verdict}")


def get_artifacts(phase: str, project_root: str, docs_path: str | None = None) -> dict:
    """Resolve artifact absolute paths for a phase.

    If docs_path is provided, artifacts with 'docs/' prefix are resolved
    to the dynamic docs directory instead.
    """
    phase = phase.lower()
    if phase not in PHASE_INFO:
        raise ValueError(f"Unknown phase: {phase}. Valid: {', '.join(PHASES)}")

    info = PHASE_INFO[phase]
    resolved = []
    for artifact in info["artifacts"]:
        if docs_path:
            artifact_resolved = resolve_artifact_path(artifact, docs_path)
        else:
            artifact_resolved = artifact
        abs_path = (
            os.path.join(project_root, artifact_resolved)
            if not os.path.isabs(artifact_resolved)
            else artifact_resolved
        )
        resolved.append(
            {
                "relative": artifact_resolved,
                "absolute": abs_path,
                "exists": os.path.exists(abs_path),
            }
        )

    return {"phase": phase, "artifacts": resolved}


def validate_artifacts(phase: str, project_root: str, docs_path: str | None = None) -> dict:
    """Check if required artifacts from a phase exist before proceeding."""
    phase = phase.lower()
    if phase not in PHASE_INFO:
        raise ValueError(f"Unknown phase: {phase}. Valid: {', '.join(PHASES)}")

    info = PHASE_INFO[phase]
    results = []
    all_exist = True

    for artifact in info["artifacts"]:
        if docs_path:
            artifact = resolve_artifact_path(artifact, docs_path)
        abs_path = (
            os.path.join(project_root, artifact)
            if not os.path.isabs(artifact)
            else artifact
        )
        exists = os.path.exists(abs_path)
        is_dir = os.path.isdir(abs_path)
        is_empty = False

        if exists:
            if is_dir:
                # Check directory is not empty
                is_empty = len(os.listdir(abs_path)) == 0
            else:
                is_empty = os.path.getsize(abs_path) == 0

        valid = exists and not is_empty
        if not valid:
            all_exist = False

        results.append(
            {
                "artifact": artifact,
                "absolute": abs_path,
                "exists": exists,
                "is_empty": is_empty,
                "valid": valid,
            }
        )

    # Determine which phase this blocks
    idx = PHASES.index(phase)
    next_phase = PHASES[idx + 1] if idx < len(PHASES) - 1 else None

    return {
        "phase": phase,
        "all_valid": all_exist,
        "can_proceed": all_exist,
        "next_phase": next_phase,
        "artifacts": results,
        "message": (
            f"All artifacts for {phase} are present. Ready to proceed to {next_phase}."
            if all_exist
            else f"Missing artifacts for {phase}: {', '.join(a['artifact'] for a in results if not a['valid'])}"
        ),
    }


def prepare_phase(args: list[str]) -> dict:
    """Combined operation: update state + return agent order + all prompts in ONE call.

    This replaces 3+ separate CLI calls per phase transition, reducing orchestrator turns
    and context growth in the main session.
    """
    parser = argparse.ArgumentParser(prog="agency_cli phase prepare")
    parser.add_argument("--phase", required=True, help="Phase to prepare")
    parser.add_argument("--project-root", required=True, help="Project root path")
    parser.add_argument("--state-path", required=True, help="Path to STATE.json")
    parser.add_argument(
        "--script-path", required=True, help="Path to backlog_manager.py"
    )
    parser.add_argument(
        "--backlog-path", required=True, help="Path to backlog directory"
    )
    parser.add_argument(
        "--objective", required=False, default=None, help="Project objective"
    )
    parser.add_argument(
        "--objective-stdin", action="store_true", help="Read objective from stdin"
    )
    parser.add_argument(
        "--skip-assists",
        action="store_true",
        help="Exclude assist agents (only spawn leads)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Force activation=spawn even when a resumable session was recorded",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=None,
        help="Override the derived iteration number (default: recorded gate iterations + 1)",
    )
    opts = parser.parse_args(args)

    if opts.objective_stdin:
        objective = sys.stdin.read().strip()
    elif opts.objective:
        objective = opts.objective
    else:
        raise ValueError("Either --objective or --objective-stdin is required")

    phase = opts.phase.lower().strip()
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}. Valid: {', '.join(PHASES)}")

    # --- 1. Check prerequisites via state ---
    from state import _get_now_iso, _load_state, _save_state

    state_path = os.path.abspath(opts.state_path)
    state = _load_state(state_path)

    # Check can-proceed logic inline (avoid circular import overhead)
    dependencies = {
        "plan": [],
        "design": ["plan"],
        "validate": ["design"],
        "specify": ["validate"],
        "implement": ["specify"],
        "review": ["implement"],
        "test": ["review"],
        "document": ["test"],
    }
    for required in dependencies.get(phase, []):
        req_status = state["phases"][required]["status"]
        if req_status != "completed":
            return {
                "ready": False,
                "blocked_by": required,
                "reason": f"Phase {required} has status: {req_status}",
            }

    # --- 2. Mark phase in_progress ---
    phase_obj = state["phases"][phase]
    old_status = phase_obj["status"]
    now = _get_now_iso()
    if old_status != "in_progress":
        phase_obj["status"] = "in_progress"
        phase_obj["started_at"] = now
        state["current_phase"] = phase
    _save_state(state_path, state)

    # --- 2.1 Derive loop-back state (iteration + why the gate failed) ---
    # The activation journal (`agent_sessions`) is authoritative: the orchestrator
    # records one entry per spawn/resume, so the iteration number is stable across
    # context compaction and idempotent when the same phase is prepared twice.
    # Gate verdict counts are deliberately NOT used here: both the agent and the
    # orchestrator may record the same verdict, which would inflate the number.
    gate = phase_obj.get("gate") or {}
    gate_iterations = int(gate.get("iterations", 0) or 0)
    prior_verdict = None
    for verdict_record in reversed(gate.get("verdicts") or []):
        if verdict_record.get("verdict"):
            prior_verdict = verdict_record["verdict"]
            break
        if verdict_record.get("combined"):
            prior_verdict = verdict_record["combined"]
            break
    agent_sessions = state.get("agent_sessions") or {}
    phase_prefix = f"{phase}:"
    # One activation event is recorded per (round, role), so the highest activation
    # count among the roles of this phase IS the number of completed rounds. Correct
    # whether or not the orchestrator passes --iteration to `state agent-session`.
    completed_rounds = 0
    for key, entry in agent_sessions.items():
        if not key.startswith(phase_prefix):
            continue
        completed_rounds = max(completed_rounds, int(entry.get("activations") or 1))
    loop_back = completed_rounds > 0
    iteration = (
        opts.iteration if opts.iteration is not None else completed_rounds + 1
    )

    # --- 3. Read docs_path from state ---
    docs_path = state.get("docs_path")
    if not docs_path:
        docs_path = os.path.join(opts.project_root, "docs").replace("\\", "/")

    # --- 3.1 Per-project hygiene policy (agent_docs/agency/hygiene.json) ---
    # Appended to every prompt of the phases in HYGIENE_PHASES when the project
    # opts in by having the config file. Absent file = no injection (pre-config
    # behavior preserved). Malformed file = warning in the output, prepare
    # continues without policy (never fails the phase transition).
    from hygiene import HYGIENE_PHASES, hygiene_policy_section, load_hygiene_config

    hygiene = load_hygiene_config(opts.project_root)
    if hygiene["status"] == "invalid":
        print(f"Warning: {hygiene['warning']}", file=sys.stderr)
    hygiene_section = (
        hygiene_policy_section(hygiene["config"])
        if hygiene["status"] == "loaded"
        else ""
    )
    inject_hygiene = phase in HYGIENE_PHASES and bool(hygiene_section)

    # --- 4. Get agent order + prompts ---
    from agent import (
        AGENT_MATRIX,
        PHASE_ORDER,
        generate_prompt,
        get_agent_name,
        resolve_model,
    )

    # Derive CLI path from this script's own location
    cli_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "agency_cli.py")
    )

    waves = []
    for i, wave_roles in enumerate(PHASE_ORDER.get(phase, [])):
        wave_agents = []
        for role in wave_roles:
            key = (phase, role)
            if key not in AGENT_MATRIX:
                continue
            info = AGENT_MATRIX[key]

            # Skip assists if --skip-assists
            if opts.skip_assists and info["type"] == "assist":
                continue

            agent_name = get_agent_name(role, phase, info["type"])
            session_key = f"{phase}:{role}"
            recorded = agent_sessions.get(session_key) or {}
            recorded_run_id = recorded.get("run_id")
            can_resume = bool(
                loop_back
                and not opts.fresh
                and recorded_run_id
                and recorded.get("status") not in ("stopped", "failed")
            )
            prompt = generate_prompt(
                role,
                phase,
                opts.project_root,
                opts.script_path,
                opts.backlog_path,
                objective,
                info["type"],
                cli_path=cli_path,
                state_path=opts.state_path,
                docs_path=docs_path,
                iteration=iteration,
                prior_verdict=prior_verdict,
                resumed=can_resume,
            )
            if inject_hygiene:
                prompt = f"{prompt}\n\n{hygiene_section}"

            wave_agents.append(
                {
                    "role": role,
                    "name": agent_name,
                    "agent": f"omni-sw-{role}",
                    "model": resolve_model(phase, role),
                    "type": info["type"],
                    "prompt": prompt,
                    "skill_command": info["skill"],
                    "iteration": iteration,
                    "activation": "resume" if can_resume else "spawn",
                    "resume_key": session_key,
                    "resume_from_run_id": recorded_run_id,
                    "prompt_kind": "continuation" if can_resume else "full",
                }
            )
            if loop_back and not can_resume:
                reason = (
                    "--fresh was passed"
                    if opts.fresh
                    else (
                        "no run id recorded for this session key"
                        if not recorded_run_id
                        else f"recorded session status is '{recorded.get('status')}'"
                    )
                )
                wave_agents[-1]["fresh_fallback_reason"] = reason

        if wave_agents:
            waves.append(
                {
                    "wave": i + 1,
                    "parallel": len(wave_agents) > 1,
                    "agents": wave_agents,
                }
            )

    # --- 5. Get phase artifacts (resolved through docs_path) ---
    info = PHASE_INFO[phase]
    artifacts = []
    for artifact in info["artifacts"]:
        resolved = resolve_artifact_path(artifact, docs_path)
        abs_path = (
            os.path.join(opts.project_root, resolved).replace("\\", "/")
            if not os.path.isabs(resolved)
            else resolved.replace("\\", "/")
        )
        artifacts.append(
            {
                "relative": resolved,
                "absolute": abs_path,
                "exists": os.path.exists(abs_path),
            }
        )

    return {
        "ready": True,
        "phase": phase,
        "goal": info["goal"],
        "has_gate": info.get("has_gate", False),
        "docs_path": docs_path,
        "state_updated": True,
        "skip_assists": opts.skip_assists,
        "iteration": iteration,
        "loop_back": loop_back,
        "gate_iterations": gate_iterations,
        "prior_verdict": prior_verdict,
        "hygiene_policy": {
            "status": hygiene["status"],
            "path": hygiene["path"],
            "injected": inject_hygiene,
            **(
                {"warning": hygiene["warning"]}
                if "warning" in hygiene
                else {}
            ),
        },
        "waves": waves,
        "total_agents": sum(len(w["agents"]) for w in waves),
        "artifacts": artifacts,
    }


def handle_phase(args: list[str]) -> dict | list:
    if not args:
        raise ValueError(
            "Subcommand required: sequence, next, artifacts, info, validate-artifacts, prepare"
        )

    subcmd = args[0]

    if subcmd == "sequence":
        return {"phases": PHASES, "total": len(PHASES)}

    elif subcmd == "next":
        parser = argparse.ArgumentParser(prog="agency_cli phase next")
        parser.add_argument("--current", required=True, help="Current phase name")
        parser.add_argument("--verdict", required=True, help="Gate verdict(s)")
        opts = parser.parse_args(args[1:])
        return get_next_phase(opts.current, opts.verdict)

    elif subcmd == "artifacts":
        parser = argparse.ArgumentParser(prog="agency_cli phase artifacts")
        parser.add_argument("--phase", required=True, help="Phase name")
        parser.add_argument("--project-root", required=True, help="Project root path")
        opts = parser.parse_args(args[1:])
        return get_artifacts(opts.phase, opts.project_root)

    elif subcmd == "info":
        parser = argparse.ArgumentParser(prog="agency_cli phase info")
        parser.add_argument("--phase", required=True, help="Phase name")
        opts = parser.parse_args(args[1:])
        phase = opts.phase.lower()
        if phase not in PHASE_INFO:
            raise ValueError(f"Unknown phase: {phase}")
        return {"phase": phase, **PHASE_INFO[phase]}

    elif subcmd == "validate-artifacts":
        parser = argparse.ArgumentParser(prog="agency_cli phase validate-artifacts")
        parser.add_argument("--phase", required=True, help="Phase to validate")
        parser.add_argument("--project-root", required=True, help="Project root path")
        opts = parser.parse_args(args[1:])
        return validate_artifacts(opts.phase, opts.project_root)

    elif subcmd == "prepare":
        return prepare_phase(args[1:])

    else:
        raise ValueError(
            f"Unknown subcommand: {subcmd}. Valid: sequence, next, artifacts, info, validate-artifacts, prepare"
        )
