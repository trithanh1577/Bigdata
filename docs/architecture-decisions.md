# Architecture decisions — Global Culinary Knowledge Base

## ADR-001: Use explicit source adapters, not arbitrary crawling

**Decision:** Start with TheMealDB's official recipe API and Wikibooks Cookbook's MediaWiki API. Keep source definitions in `config/recipe_sources.json`; do not crawl unrelated pages or scrape TheMealDB's HTML site.

**Reason:** The assignment needs multi-source collection. These two sources expose structured endpoints, source IDs, and recipe fields that can be mapped into a common format.

**Source caveats:** TheMealDB's free test key is documented for development/educational use; preserve its required attribution and review its terms before public release. Wikibooks text is generally CC BY-SA 4.0/GFDL, but individual page and media notices can differ. Store source URL, terms/license note, and attribution on every record.

## ADR-002: Keep the raw data lake separate from processed records

**Decision:** Save each raw API recipe payload at `data/raw/<source>/runs/<run_id>/records/<hash>.json`. The normalized output is written to `data/processed/recipes/<source>/<record_id>.json`.

**Reason:** Raw snapshots support auditing and rerunning normalization when the parser changes. Processed records serve as a stable input contract for later database/backend work.

**Trade-off:** This local file-based lake is suitable for a course PoC, not a distributed or high-volume deployment. Source images are kept as URLs rather than copied into the repository.

## ADR-003: Preserve versions and provenance; report likely duplicates only

**Decision:** Use a stable ID from provider + provider record ID. Keep one current processed record per source record while retaining every raw crawl snapshot. Compute a normalized title/country grouping key and report collisions as duplicate candidates; never merge candidate recipes automatically.

**Reason:** Recipes with the same dish name can have valid ingredient/step variations. Each source and revision needs to remain attributable.

## ADR-004: Normalize conservatively

**Decision:** Preserve the ingredient wording and measurement as supplied, while adding a lightly normalized name and unit when the conversion is unambiguous. Leave unavailable fields empty. Do not infer allergies, nutrition, difficulty, or substitutions.

**Reason:** Wrong conversions and invented health/safety claims are worse than explicit missing data. Later components can decide how to present incomplete fields.

## ADR-005: Run collection daily/weekly

**Decision:** The local scheduler defaults to daily and supports a configurable day interval.

**Reason:** Recipe sites and APIs do not generally need a 30-minute crawl cadence; the lecturer's example was not a specific recipe requirement. Each API request is delayed; transient network errors, HTTP 429, and HTTP 5xx responses are retried with bounded waits. TheMealDB area cursors and the Wikibooks category continuation token are persisted in `data/state/crawl_cursors.json` so scheduled runs can advance through source results.

## ADR-006: Separate ingestion, backend, and website ownership

**Decision:** Keep source ingestion, normalization, storage/answers, and presentation in separate modules. All four components are implemented. Person 3's SQLite/API backend consumes Person 2's processed manifest and supplies Person 4's website through the shared HTTP contract.

**Reason:** Separating component ownership allows the crawler/normalizer pair and the backend/frontend pair to develop concurrently against the schema and integration contract.

## ADR-007: Build a dependency-free static website with interchangeable data adapters

**Decision:** Use HTML, CSS, and JavaScript modules for the English website. Provide explicit mock/API modes, a synthetic fixture collection, and an implemented frontend API contract. Show missing source fields rather than inferring them, and preserve separate provider records in recipe details and citations.

**Reason:** Person 4 can deliver and demonstrate the interface before Person 3's backend exists. A static website works with the repository's existing Python tooling and requires no frontend build service. Separating the HTTP adapter keeps future integration changes out of the rendering layer.

**Trade-off:** The mock companion and integrated source-extractive companion are deterministic, not LLMs. Dietary exclusions are text matches with incomplete source data. The backend owns retrieval and expiring session context. Production authentication remains outside this local PoC.

## ADR-008: SQLite FTS5 and extractive answers before vector retrieval or an LLM

**Decision:** Store complete schema-validated JSON alongside relational recipe/category/ingredient indexes and a Unicode FTS5 index. Use parameterized SQL, sanitized token-prefix queries, and provider-specific IDs. Answer supported English questions by quoting retrieved fields, with citations to the full source records. Keep unknown fields unknown.

**Reason:** The 100–150-recipe classroom scale does not require a distributed database or embedding service. This baseline is reproducible without API keys, provides exact filters/full-text queries, and makes source grounding auditable.

**Trade-off:** The parser supports bounded English patterns rather than arbitrary natural-language reasoning. FTS prefixes do not provide semantic synonym matching. Vector retrieval and optional grounded generation can be added later without replacing the record/provenance contract.

## ADR-009: Synchronize only accepted processed records and keep session context bounded

**Decision:** Treat the normalizer's `processed_files` manifest as authoritative. Validate the complete import before transactionally updating recipes, category/ingredient indexes, and FTS entries, then remove obsolete derivatives. Preserve the raw snapshots. Keep cited record IDs and literal conversational exclusions under random session tokens, expire inactive context after one hour, and cap sessions at 1,000. Ignore client history for factual grounding.

**Reason:** An invalid newer snapshot must not silently leave its older derivative searchable. Browser-provided text must not become trusted recipe evidence. A small local application needs bounded storage and independent conversations without storing entire question/answer histories.

## ADR-010: Serve the website and API from one local origin

**Decision:** `recipehub serve` exposes the static frontend and `/api/v1/` from loopback, supplying dynamic `/config.js` for API mode. Independent static hosting retains mock mode. CORS is explicit for separate development origins. API responses use JSON errors and no-store caching.

**Reason:** One command runs the complete project and avoids manual browser configuration. The stdlib threaded HTTP server and SQLite require no extra runtime dependencies. This is a local classroom server; a production deployment would need authentication, TLS, and an appropriate application server.
