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

## ADR-006: Current implementation stops at the normalized data contract

**Decision:** Implement Person 1's source ingestion/raw lake and Person 2's normalization/quality report only. Relational knowledge base, full-text/vector retrieval, LLM/API backend, and user-facing website are handed off to Persons 3 and 4.

**Reason:** Separating component ownership allows the crawler/normalizer pair and the backend/frontend pair to develop concurrently against the schema and integration contract.
