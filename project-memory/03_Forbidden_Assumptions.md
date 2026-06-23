# Forbidden Assumptions

Agents must **not** assume the following without explicit evidence in config or operator confirmation.

## AI / APIs

- ❌ Gemini, Claude API, or OpenAI are available
- ❌ Cloud LLM is the default extraction path
- ✅ Default: Hermes local + Ollama on-box

## Detection scope

- ❌ Tax relief, insurance, auto financing, window/HVAC financing, supplements, identity protection are in scope
- ❌ Single-word keyword match (`loan`, `cash`, `credit`) is sufficient
- ✅ Consumer personal loans only — phrase-level classifier + taxonomy exclusions

## Data sources

- ❌ `data/pipeline.db` on Windows host is fresh during Docker ingest
- ❌ `keyword_hits` alone proves loan signal
- ❌ `exports/*` snapshots are live truth
- ✅ Live DB inside `radio-worker` container at `/app/data/pipeline.db`

## Infrastructure

- ❌ Harness may mutate production DB
- ❌ Harness may restart containers without `--execute-self-heal`
- ❌ Redis/Postgres exist in this stack
- ✅ SQLite WAL queue; bounded chunk backlog with drop-oldest

## Architecture

- ❌ `fingerprints.chromaprint_vector` is a hash (it is a BLOB feature vector)
- ❌ LLM schema includes `station` or `timestamp` (injected separately)
- ❌ Fingerprinting skips transcription (annotation only — zero recall loss design)
- ❌ `shared/` may import GPU/ML dependencies

## Station operations

- ❌ All stations in `stations.yaml` are enabled (most are disabled for URL rot / harvest pause)
- ❌ AGENTS.md station list is current without checking `.hermes.md`
- ✅ Operator-maintained enable flags + batch rotation policy in Hermes context

## Related notes

- [[02_Operating_Policy]]
- [[Glossary]]