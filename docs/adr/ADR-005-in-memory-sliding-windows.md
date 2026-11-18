# ADR-005: Low-Latency In-Memory Sliding Windows vs Distributed Streaming Engines

## Status
Accepted

## Context
Real-time fraud scoring requires evaluating behavioral velocity features: transactions in the last 1/5/60 minutes, rolling amount sums, and geospatial speed. We evaluated Apache Flink, Spark Structured Streaming stateful operations, and dedicated in-memory sliding window stores (Redis / fast deque).

## Decision
We chose **In-Memory Deque / Redis Sliding Window State Stores** embedded in the scoring service.

## Rationale
1. **Ultra-Low Latency:** Microsecond state lookup and eviction ensures total scoring service latency remains $p95 < 20\text{ ms}$ (comfortably within the 200 ms SLA).
2. **Simplified Infrastructure:** Eliminates the operational overhead, checkpoint storage, and cluster coordination complexity of a dedicated Flink cluster for sliding features.
3. **Deterministic Eviction:** Timestamp-based deque eviction (`_evict_stale`) efficiently bounds memory consumption per customer profile.
4. **Horizontal Scalability:** Compatible with Redis clusters partitioned by customer ID when scaling horizontally in multi-instance deployments.

## Consequences
- Single-instance in-memory cache requires Redis clustering or partitioned routing for multi-node production deployment.

