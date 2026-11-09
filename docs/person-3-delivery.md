# Person 3 delivery — Knowledge Base, API, and Gemini integration

**Contributor:** Nguyễn Dũng (`2474802015692`).
**Component:** SQLite knowledge base, retrieval, HTTP API, source-grounded chat, and optional Gemini integration.

## Implementation

- `recipehub/knowledge_base.py` imports normalized RecipeRecord files into SQLite and indexes recipe titles, descriptions, regions, categories, and ingredients with FTS5. Search supports filters, sorting, pagination, and ingredient exclusions.
- `recipehub/conversation.py` searches the collection before answering, keeps short-lived session context in SQLite, applies ingredient exclusions again on follow-up questions, and returns citations for retrieved records.
- `recipehub/server.py` implements `/api/v1/health`, `/facets`, `/recipes`, `/recipes/{record_id}`, and `/chat`, and serves the files in `frontend/` from the same local origin.
- `recipehub/gemini.py` sends model requests from the server using `RECIPEHUB_LLM_API_KEY`; the browser never receives this key. Gemini can produce answers grounded in retrieved records, translate recipe fields for the selected interface language, and use Google Search grounding to find missing recipes.
- Web-discovered pages are collected only when they contain Schema.org `Recipe` JSON-LD. Their original URL is retained, and the page is saved, normalized, and indexed before it can be cited. Reuse terms must still be checked by the project team.
- Successful translations are cached in `data/state/translation_cache.json`. The recipe source record itself is not overwritten by translated display text.

## Build and run

```powershell
.\.venv\Scripts\python.exe -m recipehub.cli crawl --max-items 10
.\.venv\Scripts\python.exe -m recipehub.cli normalize
.\.venv\Scripts\python.exe -m recipehub.cli build
.\.venv\Scripts\python.exe -m recipehub.cli serve
```

The service opens at `http://127.0.0.1:8000`. For recurring collection, run `python -m recipehub.cli schedule --minutes 30 --max-items 10` in a second terminal. The scheduler starts immediately, then repeats at the selected interval while that process and computer remain running.

The SQLite database is generated at `data/knowledge_base.sqlite3`; raw and processed records and crawler state are stored under `data/`. These files persist when the website server stops. Conversation context is stored in SQLite and expires after one hour.

## Limits

This is a local course proof of concept without authentication or public hosting. Gemini is optional and depends on a valid key, model access, network availability, and account quota. When it is unavailable, the knowledge base and deterministic retrieval remain usable, but natural-language generation, web discovery, and translation may not work. Only source-supported facts are used for recipe details; allergy exclusions are text matching and cannot establish medical safety. Missing fields remain unknown.
