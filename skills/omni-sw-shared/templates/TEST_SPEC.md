# Test Specification (RED)

> Phase 4 (Specify) output — QA Specialist leads, Tech Lead assists.
> Authored BEFORE implementation. The RED gate proves this suite compiles and fails for the right reason.

## Summary

**Date:** *YYYY-MM-DD*
**Framework:** *e.g., xUnit + FluentAssertions*
**Baseline verdict:** RED_PASS / RED_FAIL_TESTS / RED_FAIL_CONTRACT
**Implementation present for these contracts?** No / Yes (must be "No" for RED_PASS)

## Acceptance-Criteria Traceability Matrix

Every `Must` acceptance criterion must map to at least one test.

| Story | AC | Criterion (verifiable statement) | Test(s) | Level |
|-------|----|----------------------------------|---------|-------|
| US-001 | AC-1 | *...* | *`Create_WithValidInput_ReturnsCreated`* | *unit/integration* |

## Contract Coverage Matrix

Every element of `CONTRACTS.md` must map to a contract test.

| Contract element | Type (endpoint/interface/model/event/error) | Test(s) | Status |
|------------------|---------------------------------------------|---------|--------|
| *POST /resource* | endpoint | *`PostResource_Valid_Returns201`* | covered |
| *IResourceService.Get* | interface | *`Get_UnknownId_ThrowsNotFound`* | covered |

## RED Baseline Evidence

| Check | Result | Evidence |
| ------- | -------- | ---------- |
| Suite compiles | Yes/No | *command + output* |
| All tests fail (none pass) | Yes/No | *command + output* |
| Failures are for the right reason | Yes/No | *explanation per failure group* |
| No infrastructure errors | Yes/No | *command + output* |

## Test Inventory

| Test file | Tests | Covers |
|-----------|-------|--------|
| `tests/...` | *n* | *US-xxx, contracts* |

## Ownership

- These tests are QA-owned and frozen. Dev makes them pass and may add distinctly named complementary tests.
- Disputes go through `[TEST-REVIEW]`; only QA edits these tests.

## Open Questions / Contract Gaps

- *Any ambiguity found in CONTRACTS.md that blocks test authoring (→ RED_FAIL_CONTRACT).*
