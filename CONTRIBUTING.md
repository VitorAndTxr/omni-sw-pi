# Contributing to pi-omni-sw

Thanks for helping improve the agency. This document covers how the repository is laid out, how to make changes safely, and what a good pull request looks like.

## Development setup

```bash
git clone https://github.com/<your-user>/pi-omni-sw
cd pi-omni-sw
npm install
npm run typecheck
```

There is no build step — pi loads `extensions/*.ts` directly. `npm install` is only needed for local type-checking and tooling.

Requirements: Node.js 20+, Python 3.10+.

## Repository layout

```text
extensions/omni-sw.ts        # pi extension: /omni-sw command, omni_sw_cli tool, path manifest
skills/<name>/SKILL.md       # skills (discovered via package.json pi.skills)
skills/omni-sw-shared/       # shared agent setup, templates, models.json, CLI (Python)
agents/omni-sw-*.md          # custom subagents (via pi.subagents.agents)
```

## Adding or changing a skill

1. Create or edit `skills/<name>/SKILL.md` with valid frontmatter (`name`, `description`).
2. Keep the description specific — it is what triggers the skill.
3. Reference bundled files with paths relative to the skill directory.
4. For CLI access, use the three-step resolution documented in `skills/omni-sw-shared/agent-common.md` (`$OMNI_SW_CLI` → `~/.pi/agent/omni-sw.json` → Glob fallback). Never hardcode an absolute install path.

## Adding an agent

1. Add `agents/omni-sw-<role>.md` with frontmatter (`name`, `description`, `tools`, `skills`, `inheritSkills: false`, `systemPromptMode: replace`).
2. Follow the subagent protocol in the body: never spawn subagents, never call `ask_user_question`, return `[QUESTIONS]` instead.
3. If the agent owns a phase, register it in the CLI matrix (`skills/omni-sw-shared/scripts/commands/agent.py` → `AGENT_MATRIX`, `PHASE_ORDER`).

## Changing the phase flow

The phase sequence and gates are defined in several places that must stay consistent:

| File | What to update |
| ------ | ---------------- |
| `skills/omni-sw-shared/scripts/commands/phase.py` | `PHASES`, `PHASE_INFO`, `get_next_phase`, `prepare_phase` dependencies |
| `skills/omni-sw-shared/scripts/commands/state.py` | `PHASES`, `GATE_PHASES`, `can_proceed` dependencies |
| `skills/omni-sw-shared/scripts/commands/agent.py` | `VALID_PHASES`, `AGENT_MATRIX`, `PHASE_ORDER`, `GATE_SUFFIXES` |
| `skills/omni-sw-shared/scripts/commands/metrics.py`, `report.py`, `decision.py` | phase lists |
| `skills/omni-sw-shared/scripts/commands/gate.py` | verdict parsing for the phase |
| `skills/omni-sw-shared/scripts/commands/backlog_cmd.py` | `STATUSES`, `STATUS_TRANSITIONS`, `PHASE_STATUS_MAP` |
| `skills/omni-sw-backlog/scripts/backlog_manager.py` | `VALID_STATUSES` |
| `skills/omni-sw-orchestrator/references/*.md` | human-readable flow |

A consistency check you can reuse:

```bash
python - <<'PY'
import sys; sys.path.insert(0, "skills/omni-sw-shared/scripts/commands")
import phase, state, metrics, agent, decision
assert phase.PHASES == state.PHASES == metrics.PHASES == decision.VALID_PHASES
assert state.GATE_PHASES == metrics.GATE_PHASES
print("consistent:", phase.PHASES)
PY
```

## Testing checklist

Before opening a PR:

- [ ] `npm run typecheck` passes.
- [ ] `python skills/omni-sw-shared/scripts/agency_cli.py phase sequence` returns the expected phases.
- [ ] `python skills/omni-sw-shared/scripts/agency_cli.py phase prepare ...` returns ready waves for each phase in order.
- [ ] `python skills/omni-sw-shared/scripts/agency_cli.py gate parse --phase <p>` handles every verdict.
- [ ] Backlog transitions validate (`backlog validate-transition`).
- [ ] `pi -e .` loads the extension without errors and `/omni-sw status` prints paths.
- [ ] Documentation updated (`README.md`, `docs/`, and the relevant SKILL.md).

## Pull requests

- Keep changes focused; one concern per PR.
- Explain *why*, not just *what*.
- Update `CHANGELOG.md` under `## [Unreleased]`.
- Use conventional-ish commit subjects (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).

## Licensing of contributions

By contributing you agree your work is licensed under the repository's MIT license.
