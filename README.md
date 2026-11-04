# pi-omni-sw

> A TDD-oriented, multi-agent software development agency for [pi](https://pi.dev).

`pi-omni-sw` packages a complete SDLC workflow — five role-based agents (PM, PO, TL, Dev, QA), 13 skills, and a deterministic Python CLI — into a single installable pi package. Tests are authored **before** implementation, anchored to explicit interface contracts.

```text
Plan → Design & Contracts → Validate → Specify (RED) → Implement (GREEN) → Review → Verify → Document
```

## Why it is different

- **Contracts first.** The Tech Lead defines structures, objects, endpoints and entities in `CONTRACTS.md`. QA derives the entire test suite from it.
- **TDD / ATDD, not test-after.** A dedicated **Specify (RED)** phase authors the failing suite; a strict RED gate proves it compiles and fails for the right reason *before* any code exists.
- **Clear test ownership.** QA owns the business-rule suite. Dev makes it green and may add complementary tests, but **never** edits, deletes or weakens a QA test. Disputes go through a `[TEST-REVIEW]` handshake where Dev waits for QA's ruling.
- **Deterministic core.** Phase sequencing, gates, backlog transitions, state and metrics run through a CLI instead of prompting the model — fewer tokens, fewer mistakes.
- **Bring your own models.** Per-agent model config in `skills/omni-sw-shared/models.json` keyed by `<phase>:<role>` — any pi model id of any provider, with a `:thinking` suffix for effort control; absent keys inherit the session model.
- **Git worktree isolation.** Parallel implementations never share a working tree: instance isolation gives each run a dedicated `agency/*` branch + worktree ending in a PR, and parallel feature lanes run in managed worktrees (`pi-subagents/*` branches) with lane-scoped commits, per-lane review/verify, and sequential approved merges via the `worktree` CLI.

## Requirements

- [pi](https://pi.dev) with the [`pi-subagents`](https://www.npmjs.com/package/pi-subagents) package (for agent spawning).
- **Python 3.10+** on `PATH` (the agency CLI is Python).
- Node.js 20+ (for the extension runtime and local development).

## Install

```bash
# From GitHub (recommended, pin a tag)
pi install git:github.com/<your-user>/pi-omni-sw@v0.1.0

# From a local clone
pi install /absolute/path/to/pi-omni-sw

# Try without installing
pi -e /absolute/path/to/pi-omni-sw
```

The extension writes a path manifest to `~/.pi/agent/omni-sw.json` so skills resolve the CLI reliably. `pi install` also registers the bundled agents and skills automatically.

> Migrating from a manual `~/.pi/agent/skills` install? Remove the old `omni-sw-*` skill directories and `omni-sw-*.md` agents first to avoid duplicate-name warnings.

## Quick start

1. Create or open a project and set up its `CLAUDE.md`:

   ```bash
   /skill:omni-sw-init-omni-sw /path/to/project
   ```

2. Start the full TDD SDLC:

   ```bash
   /omni-sw "Build a user authentication API"
   # or
   /skill:omni-sw-orchestrator "Build a user authentication API"
   ```

The orchestrator drives all eight phases, evaluates gates, handles feedback loops, and surfaces questions to you.

## Entry points

| Entry point | What it does |
| ------------- | -------------- |
| `/omni-sw <objective>` | Extension command: starts the TDD SDLC. `/omni-sw status` prints resolved paths. |
| `/skill:omni-sw-orchestrator <objective>` | Same workflow, via the skill system. |
| `omni_sw_cli` tool | Lets the model run the agency CLI directly, with no path guessing. |
| `/skill:omni-sw-<role> <phase>` | Invoke a single role/phase manually (e.g. `/skill:omni-sw-qa specify`). |

## Agents

| Agent | Role | Leads | Assists |
| ------- | ------ | ------- | --------- |
| `omni-sw-pm` | Product Manager — brief, business validation, user-facing docs | Plan, Validate | Document |
| `omni-sw-po` | Product Owner — user stories, acceptance criteria, backlog | Plan | Validate, Document |
| `omni-sw-tl` | Tech Lead — architecture, **contracts**, technical validation, review | Design, Validate, Review, Document | Specify, Implement, Verify |
| `omni-sw-dev` | Developer — implements against the frozen suite | Implement | Plan, Design, Document |
| `omni-sw-qa` | QA — authors the RED suite, owns tests, verifies | Specify, Verify | Design, Review, Document |

Each phase runs in waves (leads first, then dependent assists), spawned in parallel by the orchestrator.

## Skills

| Skill | Purpose |
| ------- | --------- |
| `omni-sw-orchestrator` | Drives the full 8-phase workflow |
| `omni-sw-init-omni-sw` | One-shot project setup (`CLAUDE.md`, dirs, validation) |
| `omni-sw-pm` / `-po` / `-tl` / `-dev` / `-qa` | Role definitions and phase modes |
| `omni-sw-backlog` | JSON backlog management with role-based permissions |
| `omni-sw-repo-map` | Discovers and documents an existing codebase |
| `omni-sw-project-map` | Maps a multi-repo project in parallel |
| `omni-sw-apply-progressive-disclosure` | Optimizes `CLAUDE.md`/skills for token cost |
| `omni-sw-skill-creator` | Creates new skills |
| `omni-sw-api-doc-scraper` | Turns external API docs into a skill |
| `omni-sw-shared` | Shared agent setup, templates, CLI, model map (not user-invocable) |

## The TDD gates

| Phase | Gate | Verdicts |
| ------- | ------ | ---------- |
| Validate | Dual (PM + TL) | `APPROVED` / `REPROVED` |
| Specify (RED) | Strict | `RED_PASS`, `RED_FAIL_TESTS`, `RED_FAIL_CONTRACT` |
| Review | Single | `PASS` / `FAIL` |
| Verify | Single | `PASS`, `FAIL_BUG`, `FAIL_TEST` |

Each gate allows up to **3 iterations** before escalating to the user. See [`docs/tdd-flow.md`](docs/tdd-flow.md) for the full flow and loop-backs.

## Model routing

Edit [`skills/omni-sw-shared/models.json`](skills/omni-sw-shared/models.json):

```json
{
  "opus": "anthropic/claude-opus-4",
  "sonnet": "anthropic/claude-sonnet-4",
  "haiku": "anthropic/claude-haiku-4"
}
```

A `null` tier means "omit the per-spawn override and inherit the session/default model" — the package works out of the box on whatever model you use. Any pi model id (`provider/model[:thinking]`) is accepted.

## Project artifacts

```text
your-project/
├── CLAUDE.md
├── agent_docs/
│   ├── backlog/
│   │   ├── backlog.json          # source of truth
│   │   └── BACKLOG.md            # generated summary
│   ├── agency/
│   │   ├── STATE.json            # phase/gate state machine
│   │   └── CHECKPOINT.md         # compaction recovery
│   └── <run>-<timestamp>/        # DOCS_PATH for this SDLC run
│       ├── PROJECT_BRIEF.md
│       ├── ARCHITECTURE.md
│       ├── CONTRACTS.md
│       ├── VALIDATION.md
│       ├── TEST_SPEC.md
│       ├── DECISIONS.md
│       ├── REVIEW.md
│       └── TEST_REPORT.md
├── src/
└── tests/
```

Backlog statuses: `Draft → Ready → In Design → Validated → Specified → In Progress → In Review → In Testing → Done` (plus `Blocked`, `Cancelled`).

## CLI

The bundled CLI does all deterministic work. Run it directly if you want:

```bash
python skills/omni-sw-shared/scripts/agency_cli.py --help

# examples
python skills/omni-sw-shared/scripts/agency_cli.py phase sequence
python skills/omni-sw-shared/scripts/agency_cli.py phase prepare --phase specify --project-root . \
  --state-path agent_docs/agency/STATE.json \
  --script-path skills/omni-sw-backlog/scripts/backlog_manager.py \
  --backlog-path agent_docs/backlog/backlog.json --objective "…"
```

Or let the model use the `omni_sw_cli` tool. See [`docs/cli-reference.md`](docs/cli-reference.md).

## Environment variables

| Variable | Effect |
|----------|--------|
| `OMNI_SW_CLI` | Absolute path to `agency_cli.py` (set by the extension, useful in scripts). |
| `OMNI_SW_CLAUDE_HOOKS=1` | Opt in to writing Claude Code notification hooks during `init`/`setup`. Off by default — pi does not use them. |

## Development

```bash
npm install          # installs dev tooling + peer types
npm run typecheck    # tsc --noEmit
npm run cli:help     # sanity-check the CLI
```

There is no build step: pi loads `extensions/*.ts` directly and discovers `skills/`, `agents/` from the manifest.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes are tracked in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE). The bundled `omni-sw-skill-creator` retains its own [license](skills/omni-sw-skill-creator/LICENSE.txt).
