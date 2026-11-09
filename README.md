# Bigdata — Global Culinary Knowledge Base

A multi-region culinary knowledge project: collect recipes from Internet sources, retain raw API snapshots, normalize records into a shared schema, and expose them through a searchable website and source-grounded conversation interface.

**Implemented:** Persons 1–2's crawler, local data lake, and normalization pipeline; Person 4's English website with synthetic demo responses and a configurable HTTP adapter. **Pending:** Person 3's database, search/answer API, and live website integration. The demo is not the collected dataset.

## Run the website — Person 4

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

To connect Person 3's backend, review [the proposed API contract](docs/frontend-api-contract.md), then change `mode` to `"api"` and set `apiBaseUrl` in [`frontend/config.js`](frontend/config.js). No backend is currently provided. API mode shows errors when the service is unavailable and never silently substitutes demo records.

See [Person 4's delivery report and demonstration guide](docs/person-4-delivery.md) for the English component description, assignment coverage, demo script, and handoff limits.

## Architecture and data flow

```text
TheMealDB API ─┐
              ├─> Crawler / scheduler ─> data/raw/ ─> Normalize / validate
Wikibooks API ┘                                                │
                                                              v
                                                    data/processed/
                                                              │
                                             Person 3 database / API (pending)
                                                              │
                                                              v
                                                 Person 4 website (implemented)
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

### Person 3 — Nguyễn Dũng (`2474802015692`) — pending

- Build a database/knowledge base from processed records, with exact queries and full-text search.
- Implement recipe search, filters, details, and source-cited answers through an HTTP API.
- Manage conversation context. If using an LLM, synthesize only retrieved facts and do not invent ingredients, allergens, or nutrition.
- Respect ingredient exclusions and only offer substitutions supported by source data; do not claim medical safety.
- Consider vector retrieval after the SQL/full-text baseline works.
- Review [the website API proposal](docs/frontend-api-contract.md) with Person 4 before integration.

### Person 4 — Nguyễn Trần Hoàng Nhân (`2474802010272`) — implemented with mocks

- Build the English recipe discovery website and conversation interface.
- Display recipes and attribution; offer region/category/time/difficulty filters when values exist.
- Accept ingredient-avoidance preferences and clearly communicate source/data limitations.
- Develop against mock responses in parallel, then connect the backend through the HTTP adapter.

Code is in [`frontend/`](frontend/); the English [delivery report](docs/person-4-delivery.md) describes the implementation and remaining backend dependency.

## Run ingestion and normalization — Persons 1–2

Python 3.11 or later is required. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Before crawling, edit `.env` and replace `CRAWLER_USER_AGENT` with a bot name that includes a real contact email or public project URL, following [Wikimedia's API access policy](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy). Placeholder contact details are rejected. To skip Wikibooks temporarily, set its source configuration to `"enabled": false`. Never commit `.env` or secrets.

Crawl at most ten recipes per enabled source, then normalize and inspect coverage:

```powershell
.\.venv\Scripts\python.exe -m recipehub.cli crawl --max-items 10
.\.venv\Scripts\python.exe -m recipehub.cli normalize
.\.venv\Scripts\python.exe -m recipehub.cli stats
```

Run crawl followed by normalization daily; use `--days 7` for weekly collection. Keep the terminal open and stop with `Ctrl+C`:

```powershell
.\.venv\Scripts\python.exe -m recipehub.cli schedule --days 1 --max-items 10
```

TheMealDB persists its last meal ID per region, while Wikibooks persists category continuation tokens. Progress is stored in `data/state/crawl_cursors.json`. Each raw snapshot appends a manifest entry with run/source IDs, source URL, collection time, and relative snapshot path. Repeated crawls preserve history. Normalization selects the latest snapshot for each provider record. Crawl and normalize commands return nonzero status for source failures or invalid records and print JSON diagnostics.

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

GitHub Actions runs both suites. See the delivery guide for the manual browser demonstration and backend integration checklist.

## Proof-of-concept limits

The crawler/normalizer produces a local data lake, not a distributed storage system. Parser quality depends on source structure. A vector database is an optional retrieval tool and is not itself the entire knowledge base.

The website currently demonstrates its flows against synthetic fixtures. The database, live backend, and LLM answer service are pending. Demo chat supports limited English lookup and follow-up patterns. API integration requires Person 3's compatible implementation and CORS setup.

Current providers do not offer complete structured allergen or substitution data. Empty declarations mean unknown. Ingredient exclusions use text matching and cannot check all aliases, hidden ingredients, or cross-contact. Neither filtering nor conversation should be presented as a medical safety guarantee. Missing source fields remain empty/null and are explicitly labeled in the interface.
