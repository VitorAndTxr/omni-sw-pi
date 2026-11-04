# Software Development Agency (Omni-SW)

Multi-agent, TDD-oriented SDLC workflow built on pi skills and subagents. Five role-based agents run across eight phases:

```
Plan → Design & Contracts → Validate → Specify (RED) → Implement (GREEN) → Review → Verify → Document
```

The orchestrator (`omni-sw-orchestrator`) drives the flow automatically; each agent can also be invoked standalone.

## Role-Phase Matrix

| Agent | Plan | Design | Validate | Specify | Implement | Review | Verify | Document |
|-------|------|--------|----------|---------|-----------|--------|--------|----------|
| PM    | L    | -      | L (biz)  | -       | -         | -      | -      | L (biz)  |
| PO    | A    | -      | A        | -       | -         | -      | -      | A        |
| TL    | A    | L      | L (tech) | A       | A         | L      | A      | L (tech) |
| Dev   | A    | A      | -        | -       | L         | -      | -      | A        |
| QA    | A    | A      | -        | L (RED) | -         | A      | L      | A        |

**L** = Leads. **A** = Assists. **-** = Does not participate.

## Key Design Principles

- Agents are role-constrained (PM never writes code, QA never modifies production code).
- **Tests before implementation:** QA authors the business-rule suite in Specify (RED) from the acceptance criteria and `CONTRACTS.md`; Dev implements until it is green.
- **Test ownership:** only QA edits QA-authored tests. Dev may add distinctly named complementary tests; disputes go through `[TEST-REVIEW]` and Dev waits for QA's ruling.
- Phases produce concrete artifacts (markdown documents, source code, tests).
- Gate phases (Validate, Specify, Review, Verify) enforce quality before progression.
- Feedback loops iterate without restarting the whole workflow.
- Stack-agnostic; project specifics come from `CLAUDE.md`.

## Shared Files

| File | Purpose |
| ------ | --------- |
| `agent-common.md` | Path resolution, backlog integration, permissions, state tracking, decision log |
| `models.json` | Per-agent model config, keyed by `"<phase>:<role>"` → concrete pi model id (any provider) or `null` to inherit the session model |
| `templates/` | Artifact templates (brief, architecture, contracts, test spec, review, test report, validation) |
| `scripts/agency_cli.py` | Deterministic CLI: phase state machine, gates, backlog batch ops, pipelines, metrics |
