# CLI reference

The agency CLI is `skills/omni-sw-shared/scripts/agency_cli.py`. Prefer the `omni_sw_cli` tool (or `$OMNI_SW_CLI`) so paths do not need to be reconstructed.

```bash
python "$OMNI_SW_CLI" <group> <subcommand> [options]
```

## Groups

| Group | Subcommands | Purpose |
| ------- | ------------- | --------- |
| `init` | — | Resolve project paths (`--scan-root`, `--create-dirs`). |
| `setup` | — | Full project setup: `CLAUDE.md`, dirs, optional hooks, `--verify`. |
| `phase` | `sequence`, `next`, `artifacts`, `info`, `validate-artifacts`, `prepare` | Phase state machine. `prepare` returns ready waves + prompts. |
| `gate` | `parse`, `check`, `extract-questions` | Parse `[VERDICT:*]` / `[GATE:*]` markers; iteration limits. |
| `agent` | `model`, `name`, `list`, `prompt`, `order` | Agent matrix, model tier resolution, prompt generation. |
| `backlog` | `validate-transition`, `phase-transition`, `batch-create`, `expected-status` | Batch backlog operations with permission checks. |
| `state` | `init`, `update`, `gate-record`, `query`, `can-proceed`, `summary`, `checkpoint` | Persistent state machine. |
| `decision` | `add`, `list`, `get`, `summary` | Append-only decision log. |
| `pipeline` | `group`, `agents`, `status`, `ready-for` | Feature-parallel execution. |
| `metrics` | `dashboard`, `stories`, `phase`, `export` | Workflow observability. |
| `report` | `phase-summary`, … | Markdown summaries. |
| `notify` | `send`, `phase-complete`, `sdlc-complete`, `input-needed` | OS toast notifications (Windows; no-op elsewhere). |
| `scan` | `discover`, `repo` | Repository/project discovery for repo-map. |
| `diagram` | `er`, `endpoints`, `service-map`, `workflow` | Mermaid diagram scaffolding. |
| `tokens` | analysis | Token/fragmentation analysis. |

## Common recipes

### Inspect the flow

```bash
python "$OMNI_SW_CLI" phase sequence
python "$OMNI_SW_CLI" phase info --phase specify
python "$OMNI_SW_CLI" agent list --phase validate
```

### Prepare a phase (state + agents + prompts in one call)

```bash
python "$OMNI_SW_CLI" phase prepare \
  --phase specify \
  --project-root /path/to/project \
  --state-path /path/to/project/agent_docs/agency/STATE.json \
  --script-path /path/to/pi-omni-sw/skills/omni-sw-backlog/scripts/backlog_manager.py \
  --backlog-path /path/to/project/agent_docs/backlog/backlog.json \
  --objective "Build a user authentication API"
```

Returns `{ ready, waves, artifacts, goal, has_gate }`. Each wave agent carries `agent` (registered pi-subagents id), `name` (todo label), `model` (resolved or `null`) and the full `prompt`.

### Parse a gate

```bash
python "$OMNI_SW_CLI" gate parse --file DOCS/VALIDATION.md --phase validate
python "$OMNI_SW_CLI" gate parse --file DOCS/TEST_SPEC.md --phase specify
python "$OMNI_SW_CLI" gate parse --file DOCS/REVIEW.md   --phase review
python "$OMNI_SW_CLI" gate parse --file DOCS/TEST_REPORT.md --phase test
```

### Record a gate and decide the next phase

```bash
python "$OMNI_SW_CLI" state gate-record --state-path STATE.json --phase specify --verdict RED_PASS
python "$OMNI_SW_CLI" phase next --current specify --verdict RED_PASS
```

### Backlog transitions

```bash
python "$OMNI_SW_CLI" backlog validate-transition --from Validated --to Specified
python "$OMNI_SW_CLI" backlog expected-status --phase specify
python "$OMNI_SW_CLI" backlog phase-transition --phase specify --caller qa \
  --backlog-path BACKLOG.json --script-path backlog_manager.py
```

## Exit codes

`0` on success; non-zero on validation errors (unknown phase/subcommand, missing state, invalid verdict, unauthorized caller). The `omni_sw_cli` tool surfaces the exit code in `details.exitCode` and marks the result as an error when non-zero.
