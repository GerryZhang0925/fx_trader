# Webhooks, streaming, and event envelopes

## Webhook contract

Define registration, verification, delivery, retry, disablement, replay, and observability.

A delivery should include:

- unique delivery/message ID
- event type and version
- occurrence and delivery timestamps
- source and subject
- payload or reference
- signature metadata
- trace/correlation context

## Signing

Use a secret or asymmetric key dedicated to the consumer relationship. Sign a canonical byte sequence that includes timestamp, delivery ID, and raw body. Use constant-time comparison. Support overlapping secrets during rotation.

Reject timestamps outside the replay window and persist delivery IDs for deduplication. Parse only after signature verification when possible.

## Delivery behavior

- acknowledge quickly; process asynchronously
- use bounded exponential backoff with jitter
- define retryable status classes
- cap attempts and age
- expose delivery logs and manual redelivery
- move terminal failures to a dead-letter workflow
- disable or quarantine endpoints that consistently fail or redirect unexpectedly

## CloudEvents and Standard Webhooks

CloudEvents can provide a common event envelope. Standard Webhooks can inform interoperable signing and delivery conventions. Treat both as profiles that must be versioned and tested, not as substitutes for domain schemas.

## Streaming

For SSE define event IDs, retry hints, heartbeat, resume with Last-Event-ID, proxy buffering, and maximum connection duration. For WebSocket define authentication renewal, message schemas, flow control, heartbeat, reconnect, ordering, and connection quotas.
