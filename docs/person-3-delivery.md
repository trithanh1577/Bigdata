# Person 3 delivery — Knowledge base, search API, and cited conversation

**Member:** Nguyễn Dũng (`2474802015692`).

## Storage and retrieval

`recipehub/knowledge_base.py` implements SQLite persistence with relational recipe, category, and ingredient tables. Full schema JSON preserves source facts and provenance, and a Unicode FTS5 index covers titles, descriptions, regions, categories, and normalized ingredient names. Geographic labels remain source-derived. Unknown fields remain empty/null.

Indexing reads the authoritative processed manifest and validates the whole batch before a single transaction. It inserts new provider records, updates changed records and search entries, skips identical canonical records, and removes derivatives absent from the accepted snapshot. Raw history is retained. Category and ingredient tables use foreign keys; provider versions remain separate. WAL mode and a separate connection per operation support the local threaded API.

Search supports sanitized, accent-insensitive Unicode token-prefix queries, exact region/category/difficulty/ingredient filters, a total-time ceiling, repeated ingredient exclusions, and a requirement for nonempty source-declared allergen data. User values use SQL parameters; input cannot execute FTS operators. Sorting and pagination are stable. Unknown times are excluded by active ceilings and sorted last otherwise.

## API and website integration

`recipehub/server.py` exposes:

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/health` | Database coverage, source/region counts, engine, answer mode, session TTL. |
| `GET /api/v1/facets` | Nonempty distinct source-derived filter options. |
| `GET /api/v1/recipes` | Search, exact filters, exclusions, sorting, pagination. |
| `GET /api/v1/recipes/{record_id}` | Complete source-specific recipe and provenance. |
| `POST /api/v1/chat` | Extractive English answer, citations, session token. |
| `/` and `/config.js` | Connected website and automatic same-origin API configuration. |

JSON errors distinguish validation failures, missing records/sessions, unsupported media types, blocked origins, oversized bodies, and unavailable storage. CORS allows explicit development origins; static files are limited to the frontend directory. API responses are not cached. The default bind address is loopback.

## Conversation and grounding

`recipehub/conversation.py` retrieves records and quotes supplied facts without calling an LLM. It supports English discovery by title, region, ingredient, and an explicit minute limit. Follow-ups can inspect ingredients, methods, provenance, timing, difficulty, allergens, nutrition, substitutions, tools, and tips. Named dishes are resolved across the full collection; follow-ups refer to the first cited record.

Each record-based answer includes resolvable source-specific citations. Missing facts are explicitly unavailable; substitutions and nutrition are only shown when present in the source record. Safety questions explain unknown declarations and do not certify suitability. Literal natural-language exclusions persist within the conversation and are combined with currently applied frontend preferences. Every follow-up rechecks preferences; earlier context cannot bypass a newly excluded ingredient.

Sessions use random 256-bit bearer tokens. Only last cited record IDs and conversational exclusion terms are stored; full messages are not persisted. Inactive sessions expire after one hour and are cleaned on later chat access; the store is capped at 1,000 sessions. Client-provided history is accepted for compatibility but ignored as evidence. New conversation starts an independent token; it does not immediately erase the expired-to-be prior context.

## Operation and verification

```powershell
.\.venv\Scripts\python.exe -m recipehub.cli index
.\.venv\Scripts\python.exe -m recipehub.cli serve
```

Open `http://127.0.0.1:8000`. The server indexes the accepted processed snapshot at startup. The daily/weekly pipeline also refreshes the database while the server can continue reading it.

Offline tests cover FTS/accent queries, exact filters, exclusions, unknown fields, parameter safety, updates/rollback, manifest synchronization, session isolation/expiry, contextual grounding, supported source facts, and actual HTTP routes/CORS/static boundaries. Frontend `npm run test:integration` additionally connects its real HTTP adapter to collected recipes and checks cited follow-ups. The complete local dataset contains 137 indexed recipes from two sources.

## Limits

This is a local classroom HTTP service with no production authentication or TLS. The English parser supports bounded patterns and literal exclusions; it does not provide general semantic reasoning, comprehensive food aliases, or medical safety assessments. No vector service or LLM is required; these remain optional extensions after the SQL/FTS baseline. The implemented wire contract is [frontend-api-contract.md](frontend-api-contract.md).
