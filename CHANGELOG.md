# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-03

### Added

- **Git worktree isolation** (two levels):
  - Instance isolation — one `agency/<slug>-<timestamp>` branch + linked git worktree per orchestrator run; agency artifacts live inside the instance so concurrent runs never collide; ends with a PR (`worktree init/status/pr/remove`).
  - Parallel lane worktrees — `pipeline group` now reports `worktree_mode` (auto for ≥ 2 independent features); each feature lane spawns in a pi-subagents managed worktree (`pi-subagents/*` branch) with `GIT_GRANT: COMMIT_LANE`; TL review and QA verify run inside the lane worktree; sequential approved `worktree merge` with clean conflict abort; `worktree.cleanup` fallback.
- Per-project **hygiene policy** (`agent_docs/agency/hygiene.json`): restrictive defaults injected into agent prompts (no narrative comments, no XML summaries, no agent-doc references in tests, forbidden tokens).
- **Gate loop-backs** continue the same child session: activation journal in `STATE.json` (`state agent-session/agent-sessions`), `phase prepare` emits `activation: resume` with continuation prompts and `--fresh` escape hatch.
- Lite mode (4-phase flow) for small objectives; `pipeline agents` per-lane artifact paths (`pipelines/<feature>/REVIEW.md`, `TEST_REPORT.md`) and `--cli-path/--state-path/--docs-path` flags.

### Changed

- Model routing migrated from abstract tiers (`opus`/`sonnet`/`haiku`) to per-agent `<phase>:<role>` keys in `models.json` (provider-agnostic ids + `:thinking` suffixes).
- Git Policy hardened: grants (`COMMIT_LANE`/`COMMIT_INSTANCE`) scoped per isolation protocol, one isolation block per spawn prompt, reviewers get no grant; clean-tree checks tolerate agency scratch (`agent_docs/`, `.pi/`); branch deletion runs against the main checkout root; PRs require an explicit `--base`.
- Claude Code hooks opt-in removed (always installed for compatibility); `agency_cli worktree` command added.

## [0.1.0] - 2026-09-14

### Added

- pi package manifest bundling skills, subagents and a TypeScript extension.
- `extensions/omni-sw.ts`:
  - `/omni-sw <objective>` command to start the TDD SDLC.
  - `omni_sw_cli` tool for deterministic agency CLI operations.
  - path manifest at `~/.pi/agent/omni-sw.json` and Python detection.
- Five role subagents: `omni-sw-pm`, `omni-sw-po`, `omni-sw-tl`, `omni-sw-dev`, `omni-sw-qa`.
- TDD workflow across eight phases: Plan, Design & Contracts, Validate, Specify (RED), Implement (GREEN), Review, Verify, Document.
- Contracts-first design: `CONTRACTS.md` anchors the test suite.
- Strict RED gate (`RED_PASS` / `RED_FAIL_TESTS` / `RED_FAIL_CONTRACT`).
- Test ownership protocol with the `[TEST-REVIEW]` Dev ⇄ QA handshake.
- Configurable model routing via `skills/omni-sw-shared/models.json` (tier → pi model id).
- `Specified` backlog status and updated phase/status mappings.
- Documentation: README, CONTRIBUTING, `docs/tdd-flow.md`, `docs/architecture.md`, `docs/cli-reference.md`.
