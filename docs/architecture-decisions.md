# Architecture decisions — Global Culinary Knowledge Base

## ADR-001: Use explicit source adapters, not arbitrary crawling

**Decision:** Keep source definitions in `config/recipe_sources.json`. TheMealDB and Wikibooks Cookbook are examples, not mandatory choices. Support explicitly configured recipe pages and Gemini-discovered pages that publish Schema.org `Recipe` JSON-LD. A different page format needs its own adapter; do not crawl unrelated pages or scrape TheMealDB's HTML site.

**Reason:** The assignment lets the operator choose reliable sources. Source adapters preserve IDs and provenance while mapping supported API or Schema.org fields into the common recipe format.

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

## ADR-005: Run collection on a configurable interval

**Decision:** The local scheduler defaults to daily and supports intervals in minutes or days. A 5- or 30-minute schedule is available with `schedule --minutes 5` or `schedule --minutes 30`.

**Reason:** The interval can be selected for the demonstration or source update rate. Each API request is delayed; transient network errors, HTTP 429, and HTTP 5xx responses are retried with bounded waits. TheMealDB area cursors and the Wikibooks category continuation token are persisted in `data/state/crawl_cursors.json` so scheduled runs can advance through source results. The schedule is local and requires the process and computer to remain running.

## ADR-006: Separate ingestion, backend, and website ownership

**Decision:** Keep Person 1's source ingestion/raw lake and Person 2's normalization/quality report separate from Persons 3–4's components. Person 3's SQLite/FTS knowledge base, conversation service, Gemini integration, and HTTP API are implemented in `recipehub/knowledge_base.py`, `recipehub/conversation.py`, `recipehub/gemini.py`, and `recipehub/server.py`. Person 4's website is implemented in `frontend/` and consumes the API by default.

**Reason:** Separating component ownership allows the crawler/normalizer pair and the backend/frontend pair to develop concurrently against the schema and integration contract.

## ADR-007: Build a dependency-free static website with interchangeable data adapters

**Decision:** Use HTML, CSS, and JavaScript modules for the English/Vietnamese website. Provide explicit mock/API modes, a synthetic fixture collection, and a documented frontend API contract. Show missing source fields rather than inferring them, and preserve separate provider records in recipe details and citations.

**Reason:** Person 4 can deliver and demonstrate the interface before Person 3's backend exists. A static website works with the repository's existing Python tooling and requires no frontend build service. Separating the HTTP adapter keeps future integration changes out of the rendering layer.

**Trade-off:** The backend uses deterministic retrieval by default and can optionally call Gemini through Google's native `generateContent` API using a server-side `.env` key. It can translate recipe content for the selected interface language and use Google Search grounding to discover pages that publish Schema.org Recipe JSON-LD. Raw snapshots, normalized records, crawl state, translation cache, conversation context, and the SQLite knowledge base are stored on disk. Dietary exclusions are text matches with incomplete source data. The proof of concept has no authentication or public hosting.

## ADR-008: Serialize data lake updates across threads and processes

**Decision:** Use a reentrant thread lock together with an operating-system file lock at `data/processed/.ingestion.lock`. CLI pipeline/scheduler and on-demand discovery hold the same lock across collection, normalization, and SQLite import. Individual stages also acquire it so standalone commands use the same coordination. Reading the processed manifest and importing its records share that lock.

**Reason:** A scheduler and multiple chat requests can update the same data lake. Serializing writers prevents collisions on temporary filenames and prevents a manifest from changing while it is being imported. Existing raw snapshots and the SQLite schema remain compatible.

**Trade-off:** An ingestion operation waits for another writer to finish. Website searches continue reading the previously committed SQLite records. The scheduler reports expected storage errors and retries at its next interval; it still requires the computer and process to stay running.

## ADR-009: Ship a portable recipe snapshot for deployments

**Decision:** Export indexed source records to the versioned JSON bundle `seed/recipes.json`. On startup, import this bundle into SQLite before serving requests. Seed-aware pipeline imports merge the bundle, processed records, and existing recipes by provider record ID, preferring the newest collection timestamp and then processing timestamp. Without a bundle, the existing processed-manifest synchronization behavior remains available.

**Reason:** Local SQLite files and raw crawl state are ignored by Git. A fresh deployment needs a portable source-backed collection that can be restored without crawling on every startup. Export reads only recipe payloads; conversations, environment settings, and translation caches stay local. Validation completes before database import or atomic bundle replacement.

**Trade-off:** GitHub receives a snapshot when the operator runs `export-seed` and publishes it. New recipes collected on an ephemeral hosted filesystem still need persistent storage or a separate export workflow; startup restores only the bundle included in that deployment. This does not run the local scheduler on Render or publish any changes automatically.
