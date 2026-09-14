# Phase-Agent Matrix & Gate Conditions (TDD flow)

Quick reference for the orchestrator's phase routing, model assignments, and gates.

## Flow Overview

```
Plan → Design & Contracts → Validate → Specify (RED) → Implement (GREEN) → Review → Verify → Document
                                          └──── Implement ⇄ QA test-review handshake ────┘
```

Tests are authored **before** implementation: QA derives the suite from the acceptance criteria and from `CONTRACTS.md`, the RED gate proves it fails for the right reasons, and Dev implements until it is green.

## Phase → Agent Mapping

| # | Phase | Lead Agent | Lead Tier | Registered Agent | Skill Command | Assists | Output Artifacts |
| --- | ------- | ----------- | ----------- | ------------------ | --------------- | --------- | ------------------ |
| 1 | Plan | PM → PO | opus / sonnet | `omni-sw-pm`, `omni-sw-po` | `/skill:omni-sw-pm plan`, `/skill:omni-sw-po plan` | TL/Dev/QA (haiku) | `{DOCS_PATH}/PROJECT_BRIEF.md`, backlog |
| 2 | Design & Contracts | TL | opus | `omni-sw-tl` | `/skill:omni-sw-tl design` | Dev/QA (haiku) | `{DOCS_PATH}/ARCHITECTURE.md`, `{DOCS_PATH}/CONTRACTS.md` |
| 3 | Validate | PM + TL | opus | `omni-sw-pm`, `omni-sw-tl` | `/skill:omni-sw-pm validate`, `/skill:omni-sw-tl validate` | PO (haiku) | `{DOCS_PATH}/VALIDATION.md` |
| 4 | Specify (RED) | QA | sonnet | `omni-sw-qa` | `/skill:omni-sw-qa specify` | TL (haiku) | `{DOCS_PATH}/TEST_SPEC.md`, failing tests in `tests/` |
| 5 | Implement (GREEN) | Dev | sonnet | `omni-sw-dev` | `/skill:omni-sw-dev implement` | TL (sonnet) | Source code in `src/` + complementary tests |
| 6 | Review | TL | sonnet | `omni-sw-tl` | `/skill:omni-sw-tl review` | QA (haiku) | `{DOCS_PATH}/REVIEW.md` |
| 7 | Verify | QA | sonnet | `omni-sw-qa` | `/skill:omni-sw-qa test` | TL (haiku) | `{DOCS_PATH}/TEST_REPORT.md`, coverage |
| 8 | Document | PM + TL | sonnet | `omni-sw-pm`, `omni-sw-tl` | `/skill:omni-sw-pm document`, `/skill:omni-sw-tl document` | PO/Dev/QA (haiku) | `README.md`, `CHANGELOG.md`, `{DOCS_PATH}/API_REFERENCE.md` |

## Model Routing

Each agent is spawned with a `model` override only when the abstract tier maps to a concrete pi model id in `omni-sw-shared/models.json`. When a tier is `null`/unmapped, **omit the `model` parameter** and the agent inherits the session/default model.

`models.json` (editable): maps `opus`, `sonnet`, `haiku` to `provider/model[:thinking]`. Default ships all three as `null` so the agency runs immediately on whatever default model is configured.

### Model Selection Principles

| Tier | Intended use |
| ------ | -------------- |
| opus | Judgment: architecture, contracts, requirement elicitation, gate verdicts |
| sonnet | Generation: code, stories, reviews, tests, documentation |
| haiku | Lightweight: optional assists, notes, alignment checks |

### Full Agent Matrix

`name` is the phase-scoped task label (used for `todo`); `agent` is the registered pi-subagents agent id passed to `subagent`.

| Phase | Name | Agent | Tier | Role |
| ------- | ------ | ------- | ------ | ------ |
| Plan | `pm-plan` | `omni-sw-pm` | opus | Lead: PROJECT_BRIEF.md |
| Plan | `po-plan` | `omni-sw-po` | sonnet | Lead: backlog from brief |
| Plan | `tl-plan-assist` | `omni-sw-tl` | haiku | Assist: risk notes |
| Plan | `dev-plan-assist` | `omni-sw-dev` | haiku | Assist: implementability notes |
| Plan | `qa-plan-assist` | `omni-sw-qa` | haiku | Assist: testability notes |
| Design | `tl-design` | `omni-sw-tl` | opus | Lead: ARCHITECTURE.md + CONTRACTS.md |
| Design | `dev-design-assist` | `omni-sw-dev` | haiku | Assist: implementability review |
| Design | `qa-design-assist` | `omni-sw-qa` | haiku | Assist: contract/testability review |
| Validate | `pm-validate` | `omni-sw-pm` | opus | Lead: business validation |
| Validate | `tl-validate` | `omni-sw-tl` | opus | Lead: technical + contract validation |
| Validate | `po-validate-assist` | `omni-sw-po` | haiku | Assist: backlog alignment |
| Specify | `qa-specify` | `omni-sw-qa` | sonnet | Lead: author failing business-rule suite (RED) |
| Specify | `tl-specify-assist` | `omni-sw-tl` | haiku | Assist: contract coverage review |
| Implement | `dev-implement` | `omni-sw-dev` | sonnet | Lead: make the frozen suite green |
| Implement | `tl-implement-assist` | `omni-sw-tl` | sonnet | Assist: on-demand technical guidance |
| Review | `tl-review` | `omni-sw-tl` | sonnet | Lead: code review, REVIEW.md |
| Review | `qa-review-assist` | `omni-sw-qa` | haiku | Assist: correctness review |
| Verify | `qa-test` | `omni-sw-qa` | sonnet | Lead: run frozen suite, coverage, TEST_REPORT.md |
| Verify | `tl-test-assist` | `omni-sw-tl` | haiku | Assist: coverage review |
| Document | `pm-document` | `omni-sw-pm` | sonnet | Lead: README.md, CHANGELOG.md |
| Document | `tl-document` | `omni-sw-tl` | sonnet | Lead: API_REFERENCE.md, ARCHITECTURE.md |
| Document | `po-document-assist` | `omni-sw-po` | haiku | Assist: documentation verification |
| Document | `dev-document-assist` | `omni-sw-dev` | haiku | Assist: developer documentation |
| Document | `qa-document-assist` | `omni-sw-qa` | haiku | Assist: test documentation |

**Summary:** 11 lead spawns, 13 assist spawns.

### Agent Naming Convention

Task label (todo): `{role}-{phase}` (lead) / `{role}-{phase}-assist` (assist).
Registered agent (spawn): `omni-sw-{role}`.

### Phase Lifecycle

1. Loop over the `waves` array returned by `phase prepare`.
2. Spawn every agent in a wave in parallel: `subagent({ agent: <agent.agent>, task: <agent.prompt>, ...(agent.model ? { model: agent.model } : {}) })`.
3. Adopt `<agent.name>` as the `todo` owner for that task.
4. Monitor via `todo`; handle `[QUESTIONS]` via `ask_user_question`.
5. Wait for wave N before spawning wave N+1.
6. Proceed to the next phase.

## Gate Conditions

### Validate (Dual Gate)

| PM Verdict | TL Verdict | Action |
| ----------- | ----------- | -------- |
| APPROVED | APPROVED | Proceed to **Specify (RED)** |
| REPROVED | any | Return to **Plan** |
| any | REPROVED | Return to **Design & Contracts** |

The technical verdict must also confirm `CONTRACTS.md` is complete enough for QA to author the whole suite.

### Specify (RED Gate)

| Verdict | Condition | Action |
| --------- | ----------- | -------- |
| `RED_PASS` | Every `Must` AC and every contract has a test; suite compiles; all tests fail for the right reason; no implementation yet | Proceed to **Implement (GREEN)** |
| `RED_FAIL_TESTS` | Missing tests, tests that pass, or infrastructure errors | Return to **Specify** (QA revises the suite) |
| `RED_FAIL_CONTRACT` | Contracts missing/ambiguous/untestable | Return to **Design & Contracts** |

### Review

| Outcome | Action |
|---------|--------|
| Blocking issues | Return to **Implement** |
| No blocking issues | Proceed to **Verify** |

### Verify

| Outcome | Action |
| --------- | -------- |
| Bug (code issue) | Return to **Implement**, then re-verify |
| Test issue | Return to **Specify** — QA owns the suite, so only QA revises it |
| All pass | Proceed to **Document** |

## Implement ⇄ QA Test-Review Handshake

During Implement, Dev works only until the frozen suite is green. If Dev believes a QA-authored test is wrong:

1. Dev sends `[TEST-REVIEW]` with the test id, the reason, and a proposed correction, then **stops and waits**.
2. The orchestrator relays the request to a QA agent (spawn `qa-test-review` on demand if no QA agent is live) and waits for the ruling.
3. QA either fixes the test itself or rejects with an explanation.
4. The orchestrator relays the ruling back to Dev and resumes it.

Only QA may edit QA-authored tests. Dev may add distinctly named complementary tests but must never edit, delete, or weaken the frozen suite.

## Feedback Loop Limits

Maximum **3 iterations per gate** before escalating to the user with a full issue summary. On gate failure: increment the loop counter, shut down the current phase agents, and spawn fresh agents for the target phase.

## Sequential Dependencies Within Phases

- **Plan:** PM + TL/Dev/QA assists run in parallel; PO runs after PM completes.
- **Design:** TL produces ARCHITECTURE.md and CONTRACTS.md first; Dev/QA assists review after.
- **Validate:** PM and TL in parallel; PO after.
- **Specify:** QA authors the suite; TL reviews contract coverage after.
- **Implement:** Dev leads; TL is on-demand guidance.
- **Review:** TL first; QA after.
- **Verify:** QA first; TL coverage review after.
- **Document:** PM + TL in parallel; PO/Dev/QA after.

## Parallel Pipeline Mode

When the backlog has multiple independent feature areas, the orchestrator may parallelize Specify → Implement → Review → Verify per feature.

- Plan, Design & Contracts, and Validate always run **globally**.
- Document runs **globally** after all feature pipelines finish.
- Stories with cross-feature dependencies go to wave 2.

### Pipeline Agent Naming

| Phase | Feature | Task label | Registered agent |
| ------- | --------- | ----------- | ------------------ |
| Specify | auth | `qa-specify-auth` | `omni-sw-qa` |
| Implement | auth | `dev-implement-auth` | `omni-sw-dev` |
| Review | auth | `tl-review-auth` | `omni-sw-tl` |
| Verify | auth | `qa-test-auth` | `omni-sw-qa` |

Model tiers follow the full matrix. The Implement ⇄ QA handshake applies per feature.

### Incremental Flow

```mermaid
gantt
    title Parallel Feature Pipelines (TDD)
    dateFormat X
    axisFormat %s

    section Feature A
    Specify   :a0, 0, 1
    Implement :a1, after a0, 3
    Review    :a2, after a1, 2
    Verify    :a3, after a2, 2

    section Feature B
    Specify   :b0, 0, 1
    Implement :b1, after b0, 2
    Review    :b2, after b1, 1
    Verify    :b3, after b2, 1

    section Global
    Document  :milestone, after a3 b3, 0
```
