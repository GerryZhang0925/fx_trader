---
name: api-design-skills
description: production-grade api architecture, contract design, security, governance, testing, and troubleshooting for ai agents. use when designing, reviewing, documenting, generating, migrating, or securing rest/http, openapi, asyncapi, graphql, grpc, webhook, event-driven, streaming, internal, partner, or public apis; producing openapi or asyncapi yaml/json, json schema, protobuf, graphql schemas, api blueprints, security profiles, compatibility reports, test plans, implementation prompts, or migration plans; or diagnosing api contract, authentication, authorization, reliability, performance, versioning, and integration failures.
---

# API Design Skills

Design APIs as durable product contracts, not collections of endpoints. Produce implementable artifacts, state assumptions explicitly, and separate normative standards from optional conventions.

## Operating principles

1. Start from consumer jobs, trust boundaries, data ownership, and lifecycle constraints.
2. Select the protocol deliberately; do not default to REST when events, GraphQL, gRPC, or streaming fit better.
3. Treat the machine-readable contract as the source of truth.
4. Prefer secure defaults, least privilege, deny-by-default authorization, and explicit tenant isolation.
5. Design retry, idempotency, concurrency, pagination, errors, observability, and deprecation before implementation.
6. Preserve compatibility unless the user explicitly approves a breaking change.
7. Never invent credentials, live hosts, secrets, production IDs, or unsupported standard features.
8. Distinguish stable standards from drafts and vendor-specific extensions.
9. Generate artifacts that pass the bundled validators before presenting them as production-ready.
10. When current specifications or SDK behavior may have changed, verify official primary sources before finalizing.

## Classify the request

Choose one or combine several modes:

- **Architecture mode**: select protocol, boundaries, resource/event model, deployment shape, and ownership.
- **Contract mode**: generate OpenAPI, AsyncAPI, JSON Schema, GraphQL SDL, protobuf, webhook contracts, examples, and error catalogs.
- **Security mode**: threat-model authentication, authorization, tokens, tenant boundaries, abuse controls, and sensitive data.
- **Audit mode**: inspect an existing API or contract and produce findings, severity, evidence, and remediation.
- **Compatibility mode**: compare versions, classify breaking changes, design migrations, and define deprecation timelines.
- **Troubleshooting mode**: diagnose HTTP, OAuth/OIDC, schema, webhook, GraphQL, gRPC, gateway, CORS, retry, and client failures.
- **Governance mode**: create standards, review gates, lint rules, ownership, lifecycle, documentation, and release policies.

## Intake contract

Collect or infer only what materially changes the design:

- business capability and primary consumers
- public, partner, internal, device, service-to-service, or agent-facing exposure
- synchronous, asynchronous, streaming, or mixed interaction
- expected scale, latency, consistency, availability, and geographic constraints
- data classification, tenancy, regulatory, and audit requirements
- authentication authority and authorization model
- compatibility and versioning constraints
- target languages, gateways, SDKs, and tooling
- existing contracts, payload examples, logs, or failure evidence

If details are missing, proceed with conservative assumptions and list them. Ask a question only when the answer would fundamentally change protocol, security, or data ownership.

## Protocol selection

Use [protocol-selection.md](references/protocol-selection.md).

Default guidance:

- Choose HTTP/REST for resource-oriented, broadly interoperable request/response APIs.
- Choose AsyncAPI-described messaging for event-driven integration and broker-mediated workflows.
- Choose GraphQL when consumer-driven aggregation and graph traversal outweigh cache, authorization, and cost complexity.
- Choose gRPC for strongly typed, low-latency service communication and controlled clients.
- Choose webhooks for provider-initiated notifications to consumer-owned endpoints.
- Choose SSE for one-way server-to-client streams over HTTP; choose WebSocket only for true bidirectional sessions.
- Use a hybrid only when each surface has an explicit ownership and consistency model.

## End-to-end design workflow

1. **Frame the product contract**
   - define consumers, jobs, trust boundaries, ownership, SLOs, and non-goals
   - identify commands, queries, resources, events, and long-running operations
2. **Select the interaction style**
   - justify REST, events, GraphQL, gRPC, webhooks, streaming, or a hybrid
   - record rejected alternatives and tradeoffs
3. **Model domain and data**
   - define stable identifiers, states, invariants, lifecycle, timestamps, money, units, enums, and sensitive fields
   - separate transport models from persistence models
4. **Design contract semantics**
   - define operations, schemas, errors, pagination, filtering, sorting, concurrency, idempotency, retries, and caching
5. **Design security**
   - define actors, credentials, token audience, scopes/permissions, object authorization, tenant isolation, abuse controls, and audit events
6. **Design compatibility**
   - define stability, additive-change policy, versioning, deprecation, sunset, migration, and rollback
7. **Generate artifacts**
   - emit the contract and companion blueprint, examples, security profile, test plan, and implementation plan
8. **Validate**
   - run the relevant bundled scripts
   - resolve errors; explain accepted warnings
9. **Handoff**
   - provide ordered implementation steps, ownership, validation gates, and unresolved decisions

## Required design rules

### HTTP and resource APIs

Apply [http-resource-design.md](references/http-resource-design.md), [errors-idempotency-and-concurrency.md](references/errors-idempotency-and-concurrency.md), and [pagination-filtering-and-search.md](references/pagination-filtering-and-search.md).

- Use HTTP methods according to their defined semantics.
- Use nouns for resources and model actions only when they are not natural resource state transitions.
- Keep identifiers opaque and stable.
- Use RFC 9457 Problem Details as the default HTTP error envelope.
- Support conditional requests for mutation conflicts where practical.
- Make retry behavior explicit for every operation.
- Use cursor pagination for mutable or large collections unless offset pagination is demonstrably sufficient.
- Never return unbounded collections.
- Define deterministic ordering for paginated results.
- Use `202 Accepted` plus an operation resource for long-running work.

### OpenAPI and JSON Schema

Apply [openapi-contract-design.md](references/openapi-contract-design.md) and [json-schema-modeling.md](references/json-schema-modeling.md).

- Prefer OpenAPI 3.2 for greenfield work when the declared toolchain supports it.
- Offer OpenAPI 3.1 compatibility mode when generators, gateways, or validators do not support 3.2.
- Declare the exact dialect and avoid ambiguous implementation-defined behavior.
- Give every operation a stable `operationId`.
- Define reusable schemas, parameters, responses, examples, and security schemes under components.
- Set `additionalProperties` deliberately for object schemas.
- Distinguish omitted, null, empty, defaulted, read-only, and write-only values.
- Include success, validation, authentication, authorization, conflict, throttling, and server-failure responses as applicable.
- Do not place real credentials, internal hosts, or production identifiers in examples.

### Event-driven APIs and webhooks

Apply [asyncapi-event-driven-design.md](references/asyncapi-event-driven-design.md) and [webhooks-streaming-and-events.md](references/webhooks-streaming-and-events.md).

- Define event ownership, producer, consumers, delivery semantics, ordering scope, retention, replay, and schema evolution.
- Use immutable facts for events; do not disguise commands as past-tense events.
- Include event ID, source, type, subject, occurrence time, schema version, and correlation/causation metadata where relevant.
- Design consumers to be idempotent and tolerant of duplicates and reordering.
- Sign webhooks, include timestamp and unique delivery ID, define replay window, retry policy, and dead-letter behavior.
- Never rely on IP allowlists as the only webhook authentication control.

### GraphQL

Apply [graphql-design.md](references/graphql-design.md).

- Model business capabilities, not database tables.
- Enforce authorization at resolver and object-field boundaries.
- Define query depth, complexity, timeout, pagination, and batching controls.
- Use cursor connections for large collections.
- Avoid exposing arbitrary filtering, sorting, or introspection in untrusted contexts without policy.
- Treat GraphQL-over-HTTP as a separately versioned transport specification and mark draft-dependent behavior.

### gRPC and protobuf

Apply [grpc-protobuf-design.md](references/grpc-protobuf-design.md).

- Define deadlines, cancellation, retry eligibility, status mapping, and streaming backpressure.
- Never reuse deleted field numbers or names.
- Prefer additive protobuf evolution and reserve removed fields.
- Keep service boundaries domain-oriented and messages transport-specific.
- Define HTTP transcoding only when a coherent HTTP contract exists.

### Authentication and authorization

Apply [authentication-and-authorization.md](references/authentication-and-authorization.md).

- Separate authentication from authorization.
- Prefer standards-based OAuth/OIDC for delegated access and workload identity appropriate to the environment.
- Follow OAuth Security BCP; do not use implicit grant or resource-owner password credentials.
- Validate issuer, audience, signature algorithm, time claims, and token type.
- Prefer short-lived tokens; rotate credentials and signing keys.
- Use sender-constrained tokens such as DPoP or mTLS for elevated-risk contexts when supported.
- Authorize every object and operation server-side; never trust client-provided tenant or role claims without validation.
- Avoid API keys for end-user authorization or fine-grained access control.

### Security

Apply [api-security-threat-model.md](references/api-security-threat-model.md).

At minimum address:

- broken object-level and function-level authorization
- broken authentication
- unrestricted resource consumption
- unsafe mass assignment/property authorization
- SSRF and unsafe outbound calls
- inventory and version sprawl
- unsafe consumption of third-party APIs
- injection, deserialization, file upload, and content-type confusion
- cross-tenant leakage and cache-key mistakes
- secrets, logs, telemetry, and example-data exposure
- webhook replay and signature confusion
- GraphQL complexity and gRPC reflection exposure

## Output requirements

Match the user's requested format. For a complete design, provide:

1. executive architecture summary
2. assumptions and open decisions
3. protocol decision record
4. domain/resource/event model
5. authentication and authorization model
6. API security profile and threat model
7. machine-readable contract
8. errors, idempotency, concurrency, pagination, and lifecycle rules
9. compatibility and deprecation policy
10. testing and conformance plan
11. observability and operational plan
12. implementation sequence and quality gates

Use [output-templates.md](references/output-templates.md) for exact structures.

## Machine-readable artifacts

Generate one or more as applicable:

- `api-blueprint.json`
- `openapi.yaml` or `openapi.json`
- `asyncapi.yaml` or `asyncapi.json`
- `schemas/*.schema.json`
- `schema.graphql`
- `service.proto`
- `webhook-contract.json`
- `problem-catalog.json`
- `api-security-profile.json`
- `compatibility-report.json`
- `contract-test-plan.json`

Keep commentary outside JSON/YAML code blocks. Ensure JSON is strict JSON without comments or trailing commas.

## Validation workflow

Run the scripts that match the artifacts:

```bash
python scripts/validate_api_blueprint.py api-blueprint.json
python scripts/audit_openapi.py openapi.yaml
python scripts/validate_asyncapi.py asyncapi.yaml
python scripts/compare_openapi_contracts.py old-openapi.yaml new-openapi.yaml
python scripts/audit_api_package.py /path/to/api-package
```

Treat validator errors as blockers. Warnings require an explicit rationale before calling the output production-ready.

## Reference routing

- Protocol choice: [protocol-selection.md](references/protocol-selection.md)
- HTTP resources and methods: [http-resource-design.md](references/http-resource-design.md)
- OpenAPI: [openapi-contract-design.md](references/openapi-contract-design.md)
- JSON Schema: [json-schema-modeling.md](references/json-schema-modeling.md)
- AsyncAPI/events: [asyncapi-event-driven-design.md](references/asyncapi-event-driven-design.md)
- GraphQL: [graphql-design.md](references/graphql-design.md)
- gRPC/protobuf: [grpc-protobuf-design.md](references/grpc-protobuf-design.md)
- OAuth/OIDC and authorization: [authentication-and-authorization.md](references/authentication-and-authorization.md)
- Threat modeling: [api-security-threat-model.md](references/api-security-threat-model.md)
- Errors/retries/concurrency: [errors-idempotency-and-concurrency.md](references/errors-idempotency-and-concurrency.md)
- Pagination/filtering/search: [pagination-filtering-and-search.md](references/pagination-filtering-and-search.md)
- Webhooks/streams/events: [webhooks-streaming-and-events.md](references/webhooks-streaming-and-events.md)
- Compatibility/lifecycle: [versioning-compatibility-and-lifecycle.md](references/versioning-compatibility-and-lifecycle.md)
- Testing: [testing-contract-and-conformance.md](references/testing-contract-and-conformance.md)
- Operations: [observability-performance-and-reliability.md](references/observability-performance-and-reliability.md)
- Governance and DX: [governance-and-developer-experience.md](references/governance-and-developer-experience.md)
- Audit/troubleshooting: [audit-and-troubleshooting.md](references/audit-and-troubleshooting.md)
- Output formats: [output-templates.md](references/output-templates.md)
- Standards provenance: [source-notes.md](references/source-notes.md)
