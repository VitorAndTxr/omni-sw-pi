# Phase Execution Details (TDD flow)

Step-by-step orchestration for each phase. The orchestrator reads this file with `phase-matrix.md` at initialization.

Spawn contract (every phase): from the `waves` array returned by `phase prepare`, spawn each agent with
`subagent({ agent: <agent.agent>, task: <agent.prompt>, ...(agent.model ? { model: agent.model } : {}) })`,
in parallel within a wave, waiting for wave N before wave N+1. Adopt `<agent.name>` as the `todo` owner.
Only pass `model` when it is non-null (see `models.json`).

## Phase 1: Plan

**Goal:** `{DOCS_PATH}/PROJECT_BRIEF.md` + backlog with verifiable acceptance criteria.

| Name | Agent | Tier | Role |
| ------ | ------- | ------ | ------ |
| `pm-plan` | `omni-sw-pm` | opus | Lead: PROJECT_BRIEF.md |
| `po-plan` | `omni-sw-po` | sonnet | Lead: backlog from brief (after PM) |
| `tl-plan-assist` | `omni-sw-tl` | haiku | Assist: risk notes |
| `dev-plan-assist` | `omni-sw-dev` | haiku | Assist: implementability notes |
| `qa-plan-assist` | `omni-sw-qa` | haiku | Assist: testability notes |

1. Spawn `pm-plan` and the three assists in parallel (wave 1).
2. Handle `[QUESTIONS]` → `ask_user_question` → relay answers back.
3. Once PM completes, spawn `po-plan` (wave 2): read PROJECT_BRIEF.md, create the backlog.
4. **Quality bar:** every `Must` story must have acceptance criteria that QA can turn into a test without guessing.
5. Report: "Plan complete. Artifacts: PROJECT_BRIEF.md, backlog."

## Phase 2: Design & Contracts

**Goal:** `{DOCS_PATH}/ARCHITECTURE.md` + `{DOCS_PATH}/CONTRACTS.md`.

| Name | Agent | Tier | Role |
| ------ | ------- | ------ | ------ |
| `tl-design` | `omni-sw-tl` | opus | Lead: architecture + contracts |
| `dev-design-assist` | `omni-sw-dev` | haiku | Assist: implementability review (after TL) |
| `qa-design-assist` | `omni-sw-qa` | haiku | Assist: contract/testability review (after TL) |

1. Spawn `tl-design` (wave 1) with: "Produce ARCHITECTURE.md and CONTRACTS.md."
2. **`CONTRACTS.md` is mandatory.** It must define, with no ambiguity:
   - API endpoints: methods, paths, request/response schemas, status codes, errors
   - Interfaces/ports: signatures, invariants, pre/post-conditions
   - Data models: fields, types, validations
   - Event/message contracts between components
   - Error taxonomy: codes, messages, transport mapping
3. Once TL completes, spawn `dev-design-assist` and `qa-design-assist` in parallel (wave 2).
4. **qa-design-assist must explicitly answer:** can the entire test suite be authored from CONTRACTS.md alone? List any gap.
5. Report: "Design complete. Artifacts: ARCHITECTURE.md, CONTRACTS.md."

## Phase 3: Validate (GATE)

**Goal:** `{DOCS_PATH}/VALIDATION.md` with dual verdicts.

| Name | Agent | Tier | Role |
| ------ | ------- | ------ | ------ |
| `pm-validate` | `omni-sw-pm` | opus | Lead: business validation |
| `tl-validate` | `omni-sw-tl` | opus | Lead: technical + contract validation |
| `po-validate-assist` | `omni-sw-po` | haiku | Assist: backlog alignment |

1. Spawn `pm-validate` and `tl-validate` in parallel (wave 1); `po-validate-assist` alongside.
2. Append to both lead prompts: "End output with `[VERDICT:APPROVED]` or `[VERDICT:REPROVED]`."
3. Parse: `python {CLI} gate parse --file {DOCS_PATH}/VALIDATION.md --phase validate`.
4. `tl-validate` must confirm `CONTRACTS.md` completeness.
5. **Gate:** both APPROVED → Specify. PM REPROVED → Plan. TL REPROVED → Design. Escalate after 3 iterations.

## Phase 4: Specify — RED (GATE)

**Goal:** `{DOCS_PATH}/TEST_SPEC.md` + a failing suite in `tests/` + AC↔test traceability.

| Name | Agent | Tier | Role |
|------|-------|------|------|
| `qa-specify` | `omni-sw-qa` | sonnet | Lead: author failing business-rule suite |
| `tl-specify-assist` | `omni-sw-tl` | haiku | Assist: contract coverage review (after QA) |

1. Spawn `qa-specify` (wave 1). Append: "End output with `[GATE:RED_PASS]`, `[GATE:RED_FAIL_TESTS]`, or `[GATE:RED_FAIL_CONTRACT]`."
2. QA derives the suite mechanically:
   - one test per `Must` acceptance criterion
   - one contract test per element of `CONTRACTS.md`
   - boundary/edge cases from the ACs
   - writes `TEST_SPEC.md` with the traceability matrix (AC id → test name)
3. Once QA completes, spawn `tl-specify-assist` (wave 2) to review contract coverage.
4. Parse: `python {CLI} gate parse --file {DOCS_PATH}/TEST_SPEC.md --phase specify`.
5. **RED gate criteria (all must hold for `RED_PASS`):**
   - 100% of `Must` ACs have ≥1 test; every contract has a test
   - the suite compiles
   - every test **fails** for the right reason (no passing tests, no infrastructure errors)
   - no matching `src/` implementation exists yet
6. **Gate:** `RED_PASS` → Implement. `RED_FAIL_TESTS` → Specify. `RED_FAIL_CONTRACT` → Design. Escalate after 3 iterations.

## Phase 5: Implement — GREEN

**Goal:** source code in `src/` making the frozen suite green, plus distinctly named complementary tests.

| Name | Agent | Tier | Role |
|------|-------|------|------|
| `dev-implement` | `omni-sw-dev` | sonnet | Lead: implement to green |
| `tl-implement-assist` | `omni-sw-tl` | sonnet | Assist: on-demand technical guidance |

1. Spawn `dev-implement` (wave 1) with: implement until `tests/` is green, following ARCHITECTURE.md and CONTRACTS.md.
2. Spawn `tl-implement-assist` alongside for on-demand guidance.
3. Dev **must not** edit QA-authored tests. Dev may add complementary tests named distinctly.
4. **Test-review handshake:** if Dev sends `[TEST-REVIEW]`:
   a. Relay it to a QA agent (spawn `qa-test-review` on demand if none is live).
   b. QA rules: fix the test itself, or reject with a precise explanation.
   c. Relay the ruling back to Dev and resume implementation.
5. If Dev reports an architecture deviation, STOP and escalate rather than improvising.
6. Report: "Implementation complete. Frozen suite green."

### Parallel Pipeline Mode

1. `python {CLI} pipeline group --backlog-path {BACKLOG_PATH} --script-path {SCRIPT_PATH} --status Specified`
2. If a single group or ≤3 stories, use standard mode.
3. For each wave-1 group: `python {CLI} pipeline agents --phase implement --feature {feature} ...` and spawn per feature.
4. Each feature runs its own Specify → Implement → Review → Verify with the handshake.
5. Wave 2 starts only after wave 1 dependencies clear.

## Phase 6: Review (GATE)

**Goal:** `{DOCS_PATH}/REVIEW.md`.

| Name | Agent | Tier | Role |
|------|-------|------|------|
| `tl-review` | `omni-sw-tl` | sonnet | Lead: code review |
| `qa-review-assist` | `omni-sw-qa` | haiku | Assist: correctness review (after TL) |

1. Spawn `tl-review` (wave 1). Append: "End output with `[GATE:PASS]` or `[GATE:FAIL]`."
2. Review for architecture compliance, quality, security, error handling, convention adherence, **and test integrity** (no empty assertions, no over-mocking that bypasses real behavior, no weakened tests).
3. Once TL completes, spawn `qa-review-assist` (wave 2).
4. Parse: `python {CLI} gate parse --file {DOCS_PATH}/REVIEW.md --phase review`.
5. **Gate:** PASS → Verify. FAIL → Implement. Escalate after 3 iterations.

## Phase 7: Verify (GATE)

**Goal:** `{DOCS_PATH}/TEST_REPORT.md` — independent verification of the frozen suite.

| Name | Agent | Tier | Role |
|------|-------|------|------|
| `qa-test` | `omni-sw-qa` | sonnet | Lead: verify suite + coverage + traceability |
| `tl-test-assist` | `omni-sw-tl` | haiku | Assist: coverage review (after QA) |

1. Spawn `qa-test` (wave 1). Append: "End output with `[GATE:PASS]`, `[GATE:FAIL_BUG]`, or `[GATE:FAIL_TEST]`."
2. QA runs the suite in a clean environment and checks:
   - all tests green; contract tests green
   - 100% of `Must` ACs traced to a passing test
   - integration/e2e coverage; regression run
   - the suite was not modified since the RED baseline except via QA rulings
3. Once QA completes, spawn `tl-test-assist` (wave 2).
4. Parse: `python {CLI} gate parse --file {DOCS_PATH}/TEST_REPORT.md --phase test`.
5. **Gate:** PASS → Document. `FAIL_BUG` → Implement. `FAIL_TEST` → Specify (only QA revises the suite). Escalate after 3 iterations.

## Phase 8: Document

**Goal:** final documentation.

| Name | Agent | Tier | Role |
| ------ | ------- | ------ | ------ |
| `pm-document` | `omni-sw-pm` | sonnet | Lead: README.md, CHANGELOG.md |
| `tl-document` | `omni-sw-tl` | sonnet | Lead: API_REFERENCE.md, ARCHITECTURE.md update |
| `po-document-assist` | `omni-sw-po` | haiku | Assist: documentation verification |
| `dev-document-assist` | `omni-sw-dev` | haiku | Assist: developer documentation |
| `qa-document-assist` | `omni-sw-qa` | haiku | Assist: test documentation |

1. Spawn `pm-document` and `tl-document` in parallel (wave 1).
2. Spawn the three assists in parallel (wave 2).
3. `tl-document` also maintains `docs/` technical documentation; QA documents the test strategy and AC coverage.
4. Report: "Documentation complete. SDLC cycle finished."
