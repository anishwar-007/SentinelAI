# SentinelAI Execution Protocol

The SentinelAI Execution Protocol is the canonical, language-neutral contract
between telemetry producers and consumers.

It defines execution facts, their ordering, correlation, and stream delivery
semantics. It does not define SDK APIs, persistence, databases, HTTP services,
framework integrations, or customer business models.

## Event envelope

Every event contains:

- `event_id`: globally unique event identifier;
- `event_type`: stable event taxonomy value;
- `occurred_at`: UTC timestamp;
- `execution_id`: correlation identifier shared by one execution;
- `payload`: event-specific immutable data;
- `metadata`: immutable cross-cutting attributes.

The machine-readable envelope is defined by
[`execution-event.schema.json`](execution-event.schema.json).

## Event taxonomy

- `execution.started`
- `execution.completed`
- `execution.failed`
- `execution.cancelled`
- `trace.created`
- `trace.completed`
- `span.started`
- `span.completed`
- `verification.completed`
- `analysis.completed`

## Lifecycle

An execution begins with exactly one `execution.started` event and terminates
with exactly one of:

- `execution.completed`;
- `execution.failed`;
- `execution.cancelled`.

Trace, span, verification, and analysis facts may occur between those
boundaries. Events are append-only facts. Consumers must not mutate or replace
previously observed events.

## Execution Stream

An Execution Stream transports event envelopes from producers to consumers.

- Producers publish facts and do not know which projections consume them.
- Consumers subscribe by event type.
- Delivery order for one producer is publication order.
- Consumer failure handling is a stream implementation concern.
- Persistence is a consumer projection, never a producer responsibility.

## Products

- SDKs implement this protocol and export execution facts.
- SentinelAI Platform consumes facts and builds Execution Views.
- Customer runtimes use SDK instrumentation and contain only business logic.

`ExecutionSnapshot` is an Execution View. It is not the protocol's primary
domain model and is never required for another consumer to process events.
