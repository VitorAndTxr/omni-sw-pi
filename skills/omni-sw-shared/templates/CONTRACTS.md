# Contracts

> Phase 2 (Design & Contracts) output — Tech Lead leads, Dev/QA assist.
> This document is the anchor for the TDD test suite: every element here must become a test in the Specify (RED) phase.

## How to use this document

Each contract below is normative. QA derives one contract test per element; Dev implements exactly this. If something is missing or ambiguous, it is a **blocking gap** — return to this phase rather than guessing.

## API Contracts

For every endpoint:

| Method | Path | Auth | Request schema | Success response | Error responses |
|--------|------|------|----------------|------------------|-----------------|
| *GET* | */resource/{id}* | *bearer* | *none* | *200 `Resource`* | *404 `NotFound`* |

### Request / Response Schemas

```json
// Resource
{
  "id": "string (uuid)",
  "name": "string (1..200)",
  "createdAt": "string (ISO-8601)"
}
```

## Interfaces / Ports

For every internal boundary:

| Interface | Responsibility | Key methods (signature) | Invariants / pre-conditions / post-conditions |
|-----------|----------------|-------------------------|-----------------------------------------------|
| *IResourceService* | *...* | *`Resource Get(Guid id)`* | *id must be non-empty; throws `NotFound`* |

## Data Models

| Entity | Field | Type | Nullable | Constraints / validation |
|--------|-------|------|----------|--------------------------|
| *Resource* | *id* | *uuid* | *no* | *primary key* |
| *Resource* | *name* | *string* | *no* | *length 1..200* |

## Event / Message Contracts

| Event | Producer | Consumer | Payload schema | Delivery guarantee |
|-------|----------|----------|----------------|--------------------|
| *ResourceCreated* | *...* | *...* | *{ id, name }* | *at-least-once* |

## Error Taxonomy

| Code | Meaning | Transport mapping | When raised |
|------|---------|-------------------|-------------|
| *NotFound* | *Entity does not exist* | *HTTP 404* | *lookup miss* |
| *Validation* | *Input violates a constraint* | *HTTP 422* | *invalid payload* |

## Contract Coverage Checklist

- [ ] Every endpoint has request/response schemas and error responses
- [ ] Every interface has signatures with invariants and pre/post-conditions
- [ ] Every data model field has a type and constraint
- [ ] Every event/message has a payload schema and delivery guarantee
- [ ] Every error has a code and transport mapping
- [ ] QA confirms the full suite can be authored from this document alone
