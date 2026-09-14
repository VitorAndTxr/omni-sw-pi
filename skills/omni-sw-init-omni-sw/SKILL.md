---
name: omni-sw-init-omni-sw
description: >-
  Project Setup for Omni-SW Agency — Configures a project directory with all base files
  required by the SDLC Agency workflow before the orchestrator can run.
  Creates CLAUDE.md, agent_docs/ directories, and validates the
  environment. Use when: (1) setting up a new project for the agency (/skill:omni-sw-init-omni-sw),
  (2) user says "setup", "configure project", "init project", "prepare project for agency",
  "setup omni-sw", or
  (3) before running the orchestrator for the first time on a project. This skill should
  also trigger when the user wants to verify or fix the agency configuration in an
  existing project.
argument-hint: <path to project root directory>
---

# Omni-SW Project Setup

Configure a project directory for the SDLC Agency. This runs in the main session (not as a subagent) so that `ask_user_question` works correctly.

## Step 1: Resolve the CLI Path

Resolve `{CLI}` in this order (first match wins):

1. `$OMNI_SW_CLI` — set by the `pi-omni-sw` extension when installed as a pi package.
2. `~/.pi/agent/omni-sw.json` → `cli` — path manifest written by that extension.
3. Glob `**/omni-sw-shared/scripts/agency_cli.py` — standalone (non-package) install.

```bash
CLI="${OMNI_SW_CLI:-}"
if [ -z "$CLI" ] && [ -f "$HOME/.pi/agent/omni-sw.json" ]; then
  CLI=$(python -c "import json,os;print(json.load(open(os.path.expanduser('~/.pi/agent/omni-sw.json')))['cli'])" 2>/dev/null)
fi
ls "$CLI"
```

## Step 2: Determine What Exists

If the user provided a path as argument, use that as `{PROJECT_ROOT}`. Otherwise, use the current working directory.

Check the directory contents:

```bash
ls -la "{PROJECT_ROOT}" 2>&1
```

### Case A: Empty directory (no files, or only `.git`)

Use `ask_user_question` to collect project details. Ask all in a single call:

- **Project type** — Web API, Console App, Blazor, Library, other?
- **Project name** — What should the project be called?
- **Stack** — Technology stack (e.g., .NET 9, Node.js + TypeScript, Python + FastAPI)
- **Include tests?** — Yes or No

Then run the setup command with the answers:

```bash
MSBUILD_EXE_PATH="" python "{CLI}" setup --scan-root "{PROJECT_ROOT}" --name "{name}" --stack "{stack}" --type "{type}" [--no-tests]
```

### Case B: Non-empty directory without CLAUDE.md

The project has code but no CLAUDE.md. Use the `/skill:omni-sw-repo-map` skill to scan the codebase first:

```
/skill:omni-sw-repo-map {PROJECT_ROOT}
```

The repo-map will discover the stack, structure, and generate `CLAUDE.md`. After it completes, run setup to create the working directories:

```bash
MSBUILD_EXE_PATH="" python "{CLI}" setup --scan-root "{PROJECT_ROOT}"
```

### Case C: Non-empty directory WITH CLAUDE.md

The project already has a CLAUDE.md. Just run setup to ensure the directories are in place:

```bash
MSBUILD_EXE_PATH="" python "{CLI}" setup --scan-root "{PROJECT_ROOT}"
```

## Step 3: Verify and Report

After setup completes, run verify to confirm everything is ready:

```bash
MSBUILD_EXE_PATH="" python "{CLI}" setup --scan-root "{PROJECT_ROOT}" --verify
```

Report the results to the user.

Note: the `hooks` status is skipped by default. Claude Code notification hooks are opt-in for pi (`OMNI_SW_CLAUDE_HOOKS=1`); pi does not need them.

Then tell the user:
  > Everything is ready. Run `/skill:omni-sw-orchestrator "<objective>"` to start the SDLC.
