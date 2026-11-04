# Lite Flow — Simple Implementations

Reduced SDLC for small, well-understood objectives (e.g. 1–2 endpoints, a single
bug fix with tests, a contained UI change). **4 phases, 1 essential actor per
gate.** All other roles are skipped; their output is folded into the leads'
prompts instead of separate artifacts.

## When to Use (decision at Step 0)

Choose lite when ALL of the following hold:

- Objective is implementable as **≤ 3 stories** (you judge this in one turn — no PM needed)
- **Single feature area**, single repo touched (no cross-repo coordination beyond a 1:1 proxy)
- No new external contracts, no schema migrations with data backfill, no security-sensitive surface changes
- Requirements are unambiguous enough that the TL can write a 1-page contract without business input

If any of these fail → full flow (`phase-matrix.md`). When in doubt, ask the user.

## Phase Map (lite vs full)

| # | Lite phase | Actor (gate owner) | Gate | Skipped from full flow |
|---|-----------|--------------------|------|------------------------|
| 0 | Triage | Orchestrator | — | Plan (PM/PO/brief/multi-story backlog) |
| 1 | Design-lite | TL | TL `[VERDICT:APPROVED]` self-check | Design wave 2 (Dev+QA contract review), Validate phase (PM+PO double gate) |
| 2 | Specify (RED) | QA | `[GATE:RED_PASS]` | — (kept: test ownership is non-negotiable) |
| 3 | Implement (GREEN) | Dev | build + suite green | TL on-demand guidance (only if Dev escalates) |
| 4 | Review + Verify | TL | `[GATE:PASS]` incl. full suite run | Separate Verify phase, QA assist, TL coverage assist |
| 5 | Document-lite | PM (single pass) | — | Document wave 2 assists, LIMITATIONS.md (fold into CHANGELOG) |

## Procedure

### Step 0 — Triage (orchestrator, 1 turn)

Write the objective as **1–3 stories directly** into `backlog.json` via
`agency_cli backlog add` (role: you act as PO; keep ACs terse, ≤ 5 per story).
Record the lite-mode choice in STATE.json phase notes: `mode: lite`.

### Step 1 — Design-lite (TL, 1 spawn)

Prompt TL with: objective, stories, and a hard budget:

- `ARCHITECTURE.md`: **optional** — only if something non-obvious is needed; else skip
- `CONTRACTS.md`: **≤ 1 page** (per endpoint: route, request/response, error codes; ≤ 10 DEC entries)
- End with `[VERDICT:APPROVED]` or `[VERDICT:REPROVED]` after a self-check
  against the ACs. REPROVED → fix in the same session (max 1 iteration, then escalate).

### Step 2 — Specify (QA, 1 spawn, unchanged mechanics)

Same as full flow: QA authors the RED suite from the lite contract; scaffold via
Dev only if the contract requires new types (single Dev pre-pass, no review wave).
Gate `[GATE:RED_PASS]` — identical rules to the full flow (failing-for-the-right-
reason, exemptions need a DEC entry).

### Step 3 — Implement (Dev, 1 spawn)

Same as full flow GREEN. Dev `[TEST-REVIEW]` handshakes route to the same QA
session (resume it). TL guidance only on explicit escalation.

### Step 4 — Review + Verify (TL, 1 spawn, resumed allowed)

TL reviews diff AND runs the verification in one pass:

- Suite green + build 0 errors/warnings (source of truth: `dotnet build` / `dotnet test`)
- Test integrity: no frozen test edited by Dev (diff nominal)
- Ends with `[GATE:PASS]` / `[GATE:FAIL]`. FAIL → loop back to Step 3
  (resume Dev session), max 3 iterations, then escalate to the user.

### Step 5 — Document-lite (PM, 1 spawn)

Single pass: CHANGELOG entry, README touch only if user-facing behavior changed,
backlog statuses → Done. No LIMITATIONS.md; fold notes into the CHANGELOG entry.

## Model Configuration

Lite spawns use the same `models.json` lookup as the full flow. The per-agent
override keys apply directly (`design:tl`, `specify:qa`, `implement:dev`,
`review:tl`). Recommended for lite: leads on a mid-capability model with `:medium` thinking —
the reduced artifact budget compensates for the smaller model.

## Teardown

Identical to full flow: checkpoint, `stop spawned subagents`, final summary
(report phases as lite map above so the user sees what was skipped).
