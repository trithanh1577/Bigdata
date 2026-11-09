# Bigdata — Global Culinary Knowledge Base

A multi-region culinary knowledge project: collect recipes from Internet sources, retain raw API snapshots, normalize records into a shared schema, and expose them through a searchable website and source-grounded conversation interface.

**Implemented:** all four members' components: API crawlers, raw/processed data lake, validation reports, SQLite knowledge base with FTS5, an HTTP search/answer service, and the connected English website. The answer service extracts facts from retrieved records and cites them; no LLM key is required. A separate synthetic UI demo remains available.

## Run the complete application

Python 3.11+ with SQLite FTS5 is required. From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Collect and prepare source data on the first run (about several minutes at the configured rate limit):

```powershell
$env:CRAWLER_USER_AGENT = 'GlobalCulinaryKnowledgeBase/1.0 (https://github.com/trithanh1577/Bigdata)'
.\.venv\Scripts\python.exe -m recipehub.cli pipeline --max-items 65
```

Start the connected website and backend:

```powershell
.\.venv\Scripts\python.exe -m recipehub.cli serve
```

Open **http://127.0.0.1:8000**. The server supplies same-origin API configuration automatically and indexes the current processed manifest at startup. If this workspace already contains collected data, run `serve` directly. An empty dataset produces an empty collection; it is never silently replaced with fake recipes. `Ctrl+C` stops the server.

The latest local verification produced **137 indexed recipes** from TheMealDB and Wikibooks Cookbook, with five configured TheMealDB regions (Italian, Japanese, Thai, Vietnamese, Chinese). This is a dated local run, not a guarantee of future API output. Generated data and the database are Git-ignored; a fresh clone must run the pipeline. See [the dataset summary](docs/dataset-summary.json) and [the team demonstration guide](docs/team-demo.md).

## Run the standalone website demo — Person 4

From the repository root, using Python 3.11 or later:

```powershell
python -m http.server 5173 --bind 127.0.0.1 --directory frontend
```

Open **http://127.0.0.1:5173**. Keep the terminal open; press `Ctrl+C` to stop. No npm installation, frontend build, API key, crawler run, or backend is needed for demo mode. Serve the files over HTTP rather than opening `index.html` directly.

The website, **Recipe Atlas**, includes:

- Search by recipe name, ingredient, region, description, or category.
- Country/region, category, total-time, and difficulty filters; title/time sorting; pagination and reset controls.
- Comma-separated ingredient avoidance and an option to require source-declared allergen information.
- Recipe details with original ingredient wording, instructions, source attribution, license/terms links, and collection/update times when available.
- A conversation panel with clickable record citations, follow-up context, and a new-conversation control.
- Responsive layouts, labeled controls, keyboard focus indicators, native detail dialogs, empty/error/loading states, and retry controls.

The default collection contains **eight synthetic teaching records across five regions**. All demo content is labeled; illustrations are decorative. The demo companion performs local deterministic retrieval rather than calling an AI model. Missing fields remain unknown, and ingredient matching does not guarantee dietary safety.

The integrated `serve` command connects Person 3's backend automatically. To serve the frontend on a separate port, follow [the API contract](docs/frontend-api-contract.md), change `mode` to `"api"`, and set `apiBaseUrl` in [`frontend/config.js`](frontend/config.js). API mode shows errors when the service is unavailable and never silently substitutes demo records.

See [Person 4's delivery report](docs/person-4-delivery.md) for the English component description, assignment coverage, and standalone demo script.

## Architecture and data flow

```text
TheMealDB API ─┐
              ├─> Crawler / scheduler ─> data/raw/ ─> Normalize / validate
Wikibooks API ┘                                                │
                                                              v
                                                    data/processed/
                                                              │
                                               SQLite FTS5 / HTTP API
                                                              │
                                                              v
                                                  Person 4 website
                                                 ↑
                                      Synthetic mock adapter (default)
```

- **Raw data lake:** retains original JSON, source IDs/URLs, attribution, license/terms notes, collection time, and run metadata.
- **Processed data:** uses one recipe schema across sources and retains original measurements, source provenance, validation errors, and duplicate candidates.
- **Recipe versions:** each provider record remains separate. Similar title/region records are flagged for review rather than merged automatically.
- **Incomplete information:** allergens, nutrition, tips, substitutions, time, and difficulty are only populated when supplied by a source. Images remain provider URLs; the crawler does not download image files.
- **Collection target:** about five countries, 100–150 dishes, two or three sources, and five to eight dish categories. These are project targets, not claims about existing collected data.

The shared processed schema is documented in [integration-contract.md](docs/integration-contract.md). Architectural choices and limits are in [architecture-decisions.md](docs/architecture-decisions.md).

## Data sources

1. **TheMealDB API:** official endpoints using test key `1` for development/education. Preserve attribution and follow [TheMealDB's terms](https://www.themealdb.com/terms_of_use.php). Use the API rather than scraping its website. The free development API is not assumed to authorize a public application release.
2. **Wikibooks Cookbook API:** recipe-category pages via MediaWiki. Preserve attribution and page URLs. Most text is distributed under CC BY-SA 4.0/GFDL, but individual page/media notices may differ; review [Wikibooks copyright policy](https://en.wikibooks.org/wiki/Wikibooks:Copyrights).

Source settings, configured culinary regions, and provenance metadata live in [`config/recipe_sources.json`](config/recipe_sources.json). Review API/robots access, terms, attribution, and storage rights before adding a provider.

## Repository structure

```text
config/recipe_sources.json       API sources and source rules
data/raw/                       Original snapshots by source/run/record
data/processed/recipes/          Normalized records by source
data/processed/quality_report.json
data/state/crawl_cursors.json    Persistent provider progress
data/state/crawl_manifest.jsonl  Snapshot history and provenance
recipehub/
  recipe_crawler.py             Person 1: API adapters and raw lake
  normalize.py                  Person 2: parsing and quality checks
  models.py                     Shared RecipeRecord / Ingredient schema
  text.py                       String cleanup, normalization, IDs/hashes
  config.py                     Paths, source configuration, crawler settings
  cli.py                        crawl / normalize / schedule / stats
  knowledge_base.py             Person 3: SQLite, FTS5, relational filters
  conversation.py               Source-extractive answers and expiring sessions
  server.py                     HTTP API and connected website hosting
frontend/
  index.html                    Person 4: discovery, detail, and chat interface
  styles.css                    Responsive styling and CSS illustrations
  app.js                        Rendering, interactions, and UI state
  api.js                        Interchangeable mock / HTTP clients
  domain.js                     Filtering, pagination, and demo retrieval
  mock-data.js                  Explicitly synthetic recipe fixtures
  config.js                     Browser-visible mode and API URL configuration
  tests/                        Frontend domain and API adapter tests
docs/                           Schema, architecture, API proposal, delivery report
tests/                          Python parser, crawler, and pipeline tests
.github/workflows/ci.yml         Python and frontend checks
.env.example                    Crawler User-Agent / delay / timeout example
```

## Team responsibilities

### Person 1 — Nguyễn Thành Trí (`2474802010400`)

- Review permitted sources; implement API adapters and configuration-driven crawling.
- Save original snapshots under `data/raw/<source>/runs/<run_id>/records/`.
- Preserve source URLs, IDs, attribution, license/terms, and collection time; handle timeouts, HTTP 429, and rate limits.
- Schedule daily or weekly collection; recipes do not need a 30-minute crawl interval.

### Person 2 — Phạm Thị Khánh Ngân (`2474802016786`)

- Co-design the Recipe/Ingredient schema with Person 1.
- Parse snapshots, normalize names/units only when unambiguous, and preserve original quantities.
- Validate required fields; create processed records and quality/duplicate reports.
- Preserve each source/version rather than merging dishes merely because their names match.

**Persons 1–2 coordination:** agree on the schema and a raw-to-processed example first. Person 1 owns `recipe_crawler.py` and source configuration; Person 2 owns normalization/schema. Review the contract together and coordinate edits to shared files.

### Person 3 — Nguyễn Dũng (`2474802015692`) — implemented

- Build a database/knowledge base from processed records, with exact queries and full-text search.
- Implement recipe search, filters, details, and source-cited answers through an HTTP API.
- Manage conversation context. If using an LLM, synthesize only retrieved facts and do not invent ingredients, allergens, or nutrition.
- Respect ingredient exclusions and only offer substitutions supported by source data; do not claim medical safety.
- Consider vector retrieval after the SQL/full-text baseline works.
- Provide the implemented [website API contract](docs/frontend-api-contract.md), including health, search, facets, details, and conversation.

### Person 4 — Nguyễn Trần Hoàng Nhân (`2474802010272`) — implemented and integrated

- Build the English recipe discovery website and conversation interface.
- Display recipes and attribution; offer region/category/time/difficulty filters when values exist.
- Accept ingredient-avoidance preferences and clearly communicate source/data limitations.
- Develop against mock responses in parallel, then connect the backend through the HTTP adapter.

Code is in [`frontend/`](frontend/). English delivery reports are available for [Person 1](docs/person-1-delivery.md), [Person 2](docs/person-2-delivery.md), [Person 3](docs/person-3-delivery.md), and [Person 4](docs/person-4-delivery.md).

## Run ingestion and normalization — Persons 1–2

Python 3.11 or later is required. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Before crawling, ensure `CRAWLER_USER_AGENT` contains a real contact email or public project URL, following [Wikimedia's API access policy](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy). The example uses this project's public repository URL. Placeholder contact details are rejected. To skip Wikibooks temporarily, set its source configuration to `"enabled": false`, or select only TheMealDB with `crawl --source themealdb`. Never commit `.env` or secrets.

Crawl at most ten recipes per enabled source, then normalize and inspect coverage:

```powershell
.\.venv\Scripts\python.exe -m recipehub.cli crawl --max-items 10
.\.venv\Scripts\python.exe -m recipehub.cli normalize
.\.venv\Scripts\python.exe -m recipehub.cli index
.\.venv\Scripts\python.exe -m recipehub.cli stats
```

Run crawl, normalization, and database synchronization daily; use `--days 7` for weekly collection. Keep the terminal open and stop with `Ctrl+C`:

```powershell
.\.venv\Scripts\python.exe -m recipehub.cli schedule --days 1 --max-items 10
```

TheMealDB persists its last meal ID per region, while Wikibooks persists category continuation tokens for Cookbook namespace 102. Progress is stored in `data/state/crawl_cursors.json`. Each raw snapshot appends a manifest entry with run/source IDs, source URL, collection time, and relative snapshot path. Repeated crawls preserve history. Normalization compares timezone-aware collection timestamps and emits an authoritative list of accepted processed files. Indexing synchronizes that list transactionally, removing stale database derivatives while retaining raw history. Crawl and normalize commands return nonzero status for source failures or invalid records and print JSON diagnostics.

Generated data is ignored by Git so raw recipe content, processed records, runtime state, and local databases are not published accidentally.

## Validation

Python pipeline tests use simulated source data without Internet access:

```powershell
.\.venv\Scripts\python.exe -m compileall -q recipehub
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Frontend checks require Node.js 24 and no installed npm packages:

```powershell
cd frontend
npm run check
npm test
```

With the connected server running and collected data available, run the real HTTP frontend integration checks from `frontend/`:

```powershell
npm run test:integration
```

GitHub Actions runs the offline Python and frontend suites. The live integration checks are explicit because they require collected data and a running server. See [the team guide](docs/team-demo.md) for a complete demonstration.

## Proof-of-concept limits

The crawler/normalizer produces a local data lake, not a distributed storage system. Parser quality depends on source structure. A vector database is an optional retrieval tool and is not itself the entire knowledge base.

The complete application is a local classroom PoC. Its HTTP server binds to loopback by default and does not implement production authentication or TLS. The answer service uses deterministic English retrieval and source extraction; it is not a general-purpose language model. Conversation context expires after one hour and is isolated by a random bearer token; only record IDs and conversational exclusion terms are retained, not full message history. A separate mock UI mode remains available for offline presentation.

Current providers do not offer complete structured allergen or substitution data. Empty declarations mean unknown. Ingredient exclusions use text matching and cannot check all aliases, hidden ingredients, or cross-contact. Neither filtering nor conversation should be presented as a medical safety guarantee. Missing source fields remain empty/null and are explicitly labeled in the interface.
