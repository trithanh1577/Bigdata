# Person 3 delivery — Knowledge Base and HTTP API

**Contributor:** Nguyễn Dũng (`2474802015692`).
**Component:** local recipe database, retrieval endpoints, and source-grounded chat service.

## Implementation

- `recipehub/knowledge_base.py` rebuilds a SQLite database from normalized JSON records. It preserves provider-specific record IDs and stores each complete record as JSON.
- SQLite FTS5 indexes recipe titles, descriptions, regions, categories, and ingredient wording. If the local Python SQLite build does not include FTS5, the knowledge base falls back to text matching.
- Search supports query terms, region, category, difficulty, maximum total time, ingredient exclusions, declared-allergen filtering, sorting, and pagination. Unknown cooking times are excluded when a time ceiling is active.
- `recipehub/api.py` implements the frontend contract: `/api/v1/facets`, `/api/v1/recipes`, `/api/v1/recipes/{record_id}`, and `/api/v1/chat`. It also provides `/api/v1/health`.
- The same local HTTP server serves `frontend/`, so the website and API run at `http://127.0.0.1:8000` without a separate web framework or external model service.
- Without a model configured, conversation responses are deterministic retrieval from indexed records. An optional OpenAI-compatible chat completion endpoint can phrase answers more flexibly using only retrieved records. The key is read from the server-side `.env`, never from the browser. Short follow-ups use the session's latest citation IDs.

## Build and run

```powershell
python -m recipehub.cli crawl --max-items 10
python -m recipehub.cli normalize
python -m recipehub.cli build
python -m recipehub.cli serve
```

For recurring collection, run `python -m recipehub.cli schedule --minutes 30 --max-items 10` in a second terminal. The first run starts immediately; later runs are spaced 30 minutes apart by start time.

The database is generated at `data/state/recipes.sqlite3` and is ignored by Git. Run `build` again after importing or normalizing new data. The local scheduler performs crawl, normalization, and index rebuild on each run.

## Limits

This is a local course proof of concept. Conversation sessions live in memory and reset when the server restarts. There is no authentication, public deployment, or hosted database. Without an optional model, full-text matching and rule-based intents do not interpret every natural-language request. Ingredient exclusions cannot establish medical safety; source allergen data may be incomplete. Empty source fields remain unknown rather than inferred.
