# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
