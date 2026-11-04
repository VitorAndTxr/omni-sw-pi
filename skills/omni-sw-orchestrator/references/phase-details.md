# Phase Execution Details (TDD flow)

Step-by-step orchestration for each phase. The orchestrator reads this file with `phase-matrix.md` at initialization.

Spawn contract (every phase): from the `waves` array returned by `phase prepare`, activate each agent according to
`<agent.activation>`. When it is `spawn`, call
`subagent({ agent: <agent.agent>, task: <agent.prompt>, ...(agent.model ? { model: agent.model } : {}) })`.
When it is `resume` (gate loop-back), call
`subagent({ action: "resume", id: <agent.resume_from_run_id>, message: <agent.prompt> })` — same session, short
continuation prompt, no model override. After every activation, persist the run id with
`state agent-session --key {phase}:{role} --run-id <run_id> --iteration <agent.iteration>`.
Run agents in parallel within a wave, waiting for wave N before wave N+1. Adopt `<agent.name>` as the `todo` owner.
Only pass `model` when it is non-null (see `models.json`).

Gate loop-backs never re-instantiate a role: `phase prepare` for the failing phase returns `activation: resume`
with the run id to continue, and `prior_verdict` explains what the gate rejected. Pass `--fresh` only when you
deliberately want an unanchored verdict.

## Phase 1: Plan

**Goal:** `{DOCS_PATH}/PROJECT_BRIEF.md` + backlog with verifiable acceptance criteria.

| Name | Agent | Role |
| ------ | ------- | ------ |
| `pm-plan` | `omni-sw-pm` | Lead: PROJECT_BRIEF.md |
| `po-plan` | `omni-sw-po` | Lead: backlog from brief (after PM) |
| `tl-plan-assist` | `omni-sw-tl` | Assist: risk notes |
| `dev-plan-assist` | `omni-sw-dev` | Assist: implementability notes |
| `qa-plan-assist` | `omni-sw-qa` | Assist: testability notes |

1. Spawn `pm-plan` and the three assists in parallel (wave 1).
2. Handle `[QUESTIONS]` → `ask_user_question` → relay answers back.
3. Once PM completes, spawn `po-plan` (wave 2): read PROJECT_BRIEF.md, create the backlog.
4. **Quality bar:** every `Must` story must have acceptance criteria that QA can turn into a test without guessing.
5. Report: "Plan complete. Artifacts: PROJECT_BRIEF.md, backlog."

## Phase 2: Design & Contracts

**Goal:** `{DOCS_PATH}/ARCHITECTURE.md` + `{DOCS_PATH}/CONTRACTS.md`.

| Name | Agent | Role |
| ------ | ------- | ------ |
| `tl-design` | `omni-sw-tl` | Lead: architecture + contracts |
| `dev-design-assist` | `omni-sw-dev` | Assist: implementability review (after TL) |
| `qa-design-assist` | `omni-sw-qa` | Assist: contract/testability review (after TL) |

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

| Name | Agent | Role |
| ------ | ------- | ------ |
| `pm-validate` | `omni-sw-pm` | Lead: business validation |
| `tl-validate` | `omni-sw-tl` | Lead: technical + contract validation |
| `po-validate-assist` | `omni-sw-po` | Assist: backlog alignment |

1. Spawn `pm-validate` and `tl-validate` in parallel (wave 1); `po-validate-assist` alongside.
2. Append to both lead prompts: "End output with `[VERDICT:APPROVED]` or `[VERDICT:REPROVED]`."
3. Parse: `python {CLI} gate parse --file {DOCS_PATH}/VALIDATION.md --phase validate`.
4. `tl-validate` must confirm `CONTRACTS.md` completeness.
5. **Gate:** both APPROVED → Specify. PM REPROVED → Plan. TL REPROVED → Design. Escalate after 3 iterations. On a loop-back, re-enter the target phase with `phase prepare` and honor `activation` (`resume` continues the same session, `prior_verdict` carries the reproval reason).

## Phase 4: Specify — RED (GATE)

**Goal:** `{DOCS_PATH}/TEST_SPEC.md` + a failing suite in `tests/` + AC↔test traceability.

| Name | Agent | Role |
|------|-------|------|
| `qa-specify` | `omni-sw-qa` | Lead: author failing business-rule suite |
| `tl-specify-assist` | `omni-sw-tl` | Assist: contract coverage review (after QA) |

1. **Repo split check:** if the cycle's stories touch both back-end and front-end repos (check ARCHITECTURE.md / CONTRACTS.md scope), spawn **two QA authors in parallel** (single `subagent` call with `tasks:[...]`, PARALLEL mode): `qa-specify-api` authors the failing suite + TEST_SPEC traceability for the back-end repo/contracts only, and `qa-specify-front` for the front-end repo/contracts only. Split `TEST_SPEC.md` per repo (`TEST_SPEC.API.md`, `TEST_SPEC.Front.md`) or keep one file with clearly separated repo sections — the gate parser must still find the single `[GATE:*]` marker, so designate ONE of the two QAs (or the orchestrator) to emit the consolidated final marker after both finish. If single-repo, spawn one `qa-specify` as before.
2. Each QA derives its repo's suite mechanically:
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
7. **On `RED_FAIL_TESTS`:** this is the highest-cost loop of the SDLC, so it must continue the same session. Record the verdict, then re-enter with `phase prepare --phase specify`: it returns `activation: resume`, `resume_from_run_id` for `qa-specify` and `tl-specify-assist`, and `prior_verdict: RED_FAIL_TESTS`. Resume both — the QA agent still holds the suite it authored, so it fixes only the flagged items instead of re-deriving the whole traceability matrix. Do NOT shut the agents down between iterations.

## Phase 5: Implement — GREEN

**Goal:** source code in `src/` making the frozen suite green, plus distinctly named complementary tests.

| Name | Agent | Role |
|------|-------|------|
| `dev-implement` | `omni-sw-dev` | Lead: implement to green |
| `tl-implement-assist` | `omni-sw-tl` | Assist: on-demand technical guidance |

1. **Repo split check:** if the cycle's stories touch both back-end and front-end repos (check ARCHITECTURE.md / CONTRACTS.md scope), spawn **two dev leads in parallel** (single `subagent` call with `tasks:[...]`, PARALLEL mode): `dev-implement-api` scoped to the back-end repo and `dev-implement-front` scoped to the front-end repo. Each gets: implement until `tests/` is green **for its repo only**, following ARCHITECTURE.md and CONTRACTS.md. If scope is single-repo, spawn one `dev-implement` as before.
2. Spawn `tl-implement-assist` alongside for on-demand guidance (one assist agent is enough for both dev leads).
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

| Name | Agent | Role |
|------|-------|------|
| `tl-review` | `omni-sw-tl` | Lead: code review |
| `qa-review-assist` | `omni-sw-qa` | Assist: correctness review (after TL) |

1. Spawn `tl-review` (wave 1). The generated prompt already ends with the gate-marker instruction (`[GATE:PASS]` or `[GATE:FAIL]`).
2. Review for architecture compliance, quality, security, error handling, convention adherence, **and test integrity** (no empty assertions, no over-mocking that bypasses real behavior, no weakened tests).
3. Once TL completes, spawn `qa-review-assist` (wave 2).
4. Parse: `python {CLI} gate parse --file {DOCS_PATH}/REVIEW.md --phase review`.
5. **Gate:** PASS → Verify. FAIL → Implement. Escalate after 3 iterations. On FAIL, re-enter Implement with `phase prepare --phase implement`: it returns `activation: resume` for `dev-implement` and `tl-implement-assist` plus `prior_verdict: FAIL`, so the Dev session keeps the code it already wrote and addresses only the blocking issues.

## Phase 7: Verify (GATE)

**Goal:** `{DOCS_PATH}/TEST_REPORT.md` — independent verification of the frozen suite.

| Name | Agent | Role |
|------|-------|------|
| `qa-test` | `omni-sw-qa` | Lead: verify suite + coverage + traceability |
| `tl-test-assist` | `omni-sw-tl` | Assist: coverage review (after QA) |

1. **Repo split check:** if the cycle touched both back-end and front-end repos, spawn **two QA agents in parallel** (single `subagent` call with `tasks:[...]`, PARALLEL mode): `qa-test-api` runs the back-end suite and `qa-test-front` runs the front-end suite. Each applies the same checks to its repo. If single-repo, spawn one `qa-test` as before. IMPORTANT: only the LAST QA to finish writes the final gate verdict — the other reports its repo result as input; alternatively, wait for both and have the orchestrator consolidate before parsing the gate.
2. Each QA runs its repo's suite in a clean environment and checks:
   - all tests green; contract tests green
   - 100% of `Must` ACs traced to a passing test
   - integration/e2e coverage; regression run
   - the suite was not modified since the RED baseline except via QA rulings
3. Once QA completes, spawn `tl-test-assist` (wave 2).
4. Parse: `python {CLI} gate parse --file {DOCS_PATH}/TEST_REPORT.md --phase test`.
5. **Gate:** PASS → Document. `FAIL_BUG` → Implement. `FAIL_TEST` → Specify (only QA revises the suite). Escalate after 3 iterations. On a loop-back, re-enter the target phase with `phase prepare`; `activation: resume` continues the failing role's session while the QA/TL pair keeps ownership of the frozen suite across iterations.

## Phase 8: Document

**Goal:** final documentation.

| Name | Agent | Role |
| ------ | ------- | ------ |
| `pm-document` | `omni-sw-pm` | Lead: README.md, CHANGELOG.md |
| `tl-document` | `omni-sw-tl` | Lead: API_REFERENCE.md, ARCHITECTURE.md update |
| `po-document-assist` | `omni-sw-po` | Assist: documentation verification |
| `dev-document-assist` | `omni-sw-dev` | Assist: developer documentation |
| `qa-document-assist` | `omni-sw-qa` | Assist: test documentation |

1. Spawn `pm-document` and `tl-document` in parallel (wave 1).
2. Spawn the three assists in parallel (wave 2).
3. `tl-document` also maintains `docs/` technical documentation; QA documents the test strategy and AC coverage.
4. Report: "Documentation complete. SDLC cycle finished."
