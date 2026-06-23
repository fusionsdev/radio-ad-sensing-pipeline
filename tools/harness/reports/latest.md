# Harness Report

**Timestamp:** 2026-06-23T14:47:13Z
**Status:** pass
**Overnight readiness:** ready

## Failed checks
- **headroom** / proxy_port: 127.0.0.1:8787 not reachable (optional)
- **headroom** / proxy_health: port unreachable

## Recommended actions
- Start local proxy: headroom proxy --memory --code-graph
- Ensure headroom proxy responds on GET /health

## Memory Health

**Memory Health:** PASS

- **Core Files:** PASS
- **Runbooks:** PASS
- **Stations:** PASS
- **Decisions:** PASS
- **Freshness:** PASS
- **Links:** PASS

## Headroom Status

**Headroom:** WARNING
**Proxy Reachable:** WARNING
**Health:** WARNING
**Agent Files:** PASS
**Config:** PASS

## Observability Status

**Observability:** PASS
**Metrics Freshness:** PASS
**Analytics Report:** PASS

## Harness summary
- **classifier**: pass
- **dashboard**: pass
- **self_healing**: pass
- **station**: pass
- **hermes**: pass
- **decision**: pass
- **memory**: pass
- **headroom**: pass
- **observability**: pass
