# Agent Common Setup

Shared setup for all agency agents (PM, PO, TL, Dev, QA). Each agent's SKILL.md references this file.

## Git Policy (HARD RULE)

Agents NEVER run `git push`, `git merge`, `git rebase`, `git tag`, or create/delete/switch branches (`git checkout -b`, `git switch -c`, `git branch -d`), UNLESS the orchestrator's spawn prompt explicitly grants that exact operation for this run — and the orchestrator only grants it with the human operator's explicit approval.

Commits are allowed ONLY under the isolation protocols below, and only when your spawn prompt carries the corresponding grant:

- **Default (no isolation grant):** NEVER run `git commit`. Leave all created/modified/deleted files in the working tree (staged or unstaged is fine) and end your report with a `FILES CHANGED:` list (path + operation) so the orchestrator and the human can review and commit.
- **`GIT_GRANT: COMMIT_LANE`:** you own a pi-subagents managed lane worktree. You MAY run `git commit` on the CURRENT branch of your worktree (`pi-subagents/*`). Never switch branches, never push, never merge, never touch other branches. Commit messages must start with `[lane:<feature>]`.
- **`GIT_GRANT: COMMIT_INSTANCE`:** the run is instance-isolated. You MAY run `git commit` on the CURRENT branch of the instance worktree (`agency/*`). Never switch branches, never push, never merge, never touch other branches. Commit messages must start with `[agency]`.

In every mode:

- Never stage or commit files you did not author; never touch unrelated working-tree changes (e.g., pre-existing dirty files from earlier cycles).
- When you cannot commit, end your report with a `FILES CHANGED:` list (path + operation).
- Only the orchestrator merges lane branches, pushes, and opens PRs — always after presenting the change set to the human and receiving explicit approval. Commits carry clear attribution of which agent produced the content.

## Resolved Paths (from Orchestrator)

When spawned by the orchestrator, your prompt includes all resolved paths in a `Resolved paths:` block. Parse and use them directly:

- `PROJECT_ROOT` — project root directory (all artifact paths are relative to this)
- `SCRIPT_PATH` — absolute path to `backlog_manager.py`
- `BACKLOG_PATH` — absolute path to `backlog.json`
- `CLI_PATH` — absolute path to `agency_cli.py`
- `STATE_PATH` — absolute path to `STATE.json`
- `DOCS_PATH` — working documents directory for this SDLC run (timestamped subfolder under `agent_docs/`)

The orchestrator may also add isolation context to the same block:

- `CODE_ROOT` — directory where ALL code edits happen. In default runs it equals `PROJECT_ROOT`. In instance-isolated runs it is the instance worktree (branch `agency/*`), and in lane-isolated runs it is your lane worktree (branch `pi-subagents/*`). Your process cwd is already set to `CODE_ROOT`; treat every relative code path as resolved there. Agency artifacts (`DOCS_PATH`, `STATE_PATH`, `BACKLOG_PATH`) stay at their absolute paths — do NOT relocate or re-resolve them.
- `GIT_GRANT` — `COMMIT_LANE` or `COMMIT_INSTANCE`; see the Git Policy above. Absent means no commits.
- `LANE_ID` — feature area of your lane (lane-isolated runs only). Keep it in commit message prefixes.

**Do NOT re-resolve these via Glob.** The orchestrator already normalized them for bash.

### Fallback (standalone usage only)

If spawned without resolved paths (e.g., manual `/skill:omni-sw-pm plan` invocation), find the CLI once:

```
Glob pattern: "**/shared/scripts/agency_cli.py"
```

Store as `{CLI}`, then resolve all other paths:

```bash
python "{CLI}" init --scan-root {workspace}
# Returns JSON: project_root, script_path, backlog_path, team_name, claude_md
```

If `DOCS_PATH` is not provided in resolved paths (standalone invocation), fall back to `{PROJECT_ROOT}/docs/`.

## Backlog Integration

**NEVER read `backlog.json` or `BACKLOG.md` directly** — always use `backlog_manager.py` via Bash.

Pass `--caller <agent>` on every command. The script rejects unauthorized operations.

### Using the backlog script

```bash
# Always use the resolved SCRIPT_PATH and BACKLOG_PATH from your spawn prompt
python "{SCRIPT_PATH}" <command> "{BACKLOG_PATH}" [options] --caller {role}
```

For batch transitions (e.g., transitioning all stories for a phase):

```bash
python "{CLI_PATH}" backlog phase-transition --phase {phase} --caller {role} --backlog-path "{BACKLOG_PATH}" --script-path "{SCRIPT_PATH}"
```

To validate a transition before executing:

```bash
python "{CLI_PATH}" backlog validate-transition --from "Ready" --to "In Design"
```

### Permission Matrix

| Operation  | po | pm | tl | dev | qa |
|------------|----|----|----|----|-----|
| Create US  | Y  | Y  | N  | N  | N  |
| Edit US    | Y  | Y  | Y  | N  | N  |
| Status     | Y  | Y  | Y  | Y  | Y  |
| Delete US  | Y  | Y  | N  | N  | N  |
| Question   | Y  | Y  | Y  | Y  | Y  |

## Phase Routing

Route to the phase matching the argument after `/{role}` (ask if none provided).

## TDD Phase Notes

- **Specify (RED):** QA authors the business-rule suite from the acceptance criteria and `CONTRACTS.md`. QA owns these tests.
- **Implement (GREEN):** Dev makes the frozen suite pass and may add distinctly named complementary tests, but must never edit, delete, or weaken QA-authored tests. A dispute goes through `[TEST-REVIEW]`; Dev stops and waits for QA's ruling.
- **Test / Verify:** QA re-runs the frozen suite in a clean environment and checks AC traceability and that the suite was not weakened since the RED baseline.

## Backlog Render Rule

When performing multiple mutations in sequence (creating stories, changing statuses), call `render` only once after all mutations are complete. Do NOT render after every individual mutation.

## State Tracking

All agents must update the project state when starting and completing phase work. This enables workflow enforcement, crash recovery, and metrics collection.

### On Phase Start

Before doing any phase work, update state:

```bash
python "{CLI_PATH}" state update --state-path "{STATE_PATH}" --phase {current_phase} --status in_progress --agent {agent_name} --agent-status in_progress
```

### On Phase Completion

After producing all artifacts for your phase:

```bash
python "{CLI_PATH}" state update --state-path "{STATE_PATH}" --phase {current_phase} --status completed --agent {agent_name} --agent-status completed
```

### On Gate Verdict (Gate phases only: validate, specify, review, test)

After writing your verdict, record it in state:

```bash
# Validate (PM or TL):
python "{CLI_PATH}" state gate-record --state-path "{STATE_PATH}" --phase validate --verdict "APPROVED" --pm APPROVED --tl APPROVED

# Specify (QA):
python "{CLI_PATH}" state gate-record --state-path "{STATE_PATH}" --phase specify --verdict RED_PASS

# Review (TL):
python "{CLI_PATH}" state gate-record --state-path "{STATE_PATH}" --phase review --verdict PASS

# Test (QA):
python "{CLI_PATH}" state gate-record --state-path "{STATE_PATH}" --phase test --verdict PASS --tests-passed 42 --tests-failed 0
```

### Important Rules

- State updates are **non-blocking** — if the state command fails, continue your work and report the failure.
- The orchestrator is responsible for `state init`. Individual agents only call `state update` and `state gate-record`.
- Assist agents do NOT update phase status (only their agent status).

## Decision Log

When making significant design decisions, trade-offs, or choosing between alternatives, record them:

```bash
python "{CLI_PATH}" decision add --decisions-path "{DOCS_PATH}/DECISIONS.md" --phase {phase} --agent {role} --title "Short decision title" --context "Why this decision was needed" --alternatives "Option A (rejected: reason), Option B (rejected: reason)" --decision "What was decided" --impact "Affected stories or components"
```

### When to Record Decisions

- **TL in Design:** Architecture choices, technology selections, pattern decisions
- **TL in Review:** Accepted deviations from architecture, new patterns adopted
- **Dev in Implement:** Implementation trade-offs, library choices within scope
- **PM in Validate:** Scope changes, requirement reinterpretations
- **QA in Test:** Test strategy decisions, coverage trade-offs

### Important Rules

- Only record decisions that affect the project direction — not routine implementation choices.
- The decision log is append-only. Never edit or delete existing entries.
- If unsure whether something qualifies as a "decision", err on the side of recording it.
