# Data contract: Persons 1–2 → Persons 3–4

This document is a hand-off contract so the backend and website can start against sample/mock data before the crawl has collected the target volume.

## Raw envelope (Person 1 output)

Each provider recipe payload is retained with its provenance:

```json
{
  "source_id": "themealdb",
  "source_name": "TheMealDB",
  "source_record_id": "52772",
  "source_url": "https://www.themealdb.com/meal/52772",
  "source_license": "Use subject to provider terms; attribute source",
  "source_terms_url": "https://www.themealdb.com/terms_of_use.php",
  "attribution": "Recipe data provider",
  "language": "en",
  "collected_at": "2026-10-23T00:00:00+00:00",
  "payload": { "provider": "original API object; retained without normalization" }
}
```

Raw files are written below `data/raw/<source_id>/runs/<run_id>/records/`. Each run also has a `run.json` summary. New runs do not overwrite older raw snapshots.

The crawler saves source progress in `data/state/crawl_cursors.json`: a last-seen meal ID per configured TheMealDB area and the MediaWiki category continuation token for Wikibooks. It also appends one row per raw snapshot to `data/state/crawl_manifest.jsonl`, recording run ID, source, provider record ID, source URL, collection time, and relative raw-file path. Re-crawling a page creates another history row. These files are operational state, not part of the recipe schema, and are ignored by Git.

## Processed recipe record (Person 2 output)

Files are written below `data/processed/recipes/<source_id>/<record_id>.json`.

```json
{
  "schema_version": 1,
  "record_id": "stable-id-for-source-and-source-record",
  "title": "Normalized display title",
  "original_title": "Provider title as received",
  "country_or_region": "Italy",
  "image_url": "https://provider.example/image.jpg",
  "original_recipe_url": "https://original-recipe.example/page",
  "description": "",
  "ingredients": [
    {
      "name": "tomato",
      "original_text": "2 cups chopped tomato",
      "quantity": "2",
      "unit": "cup",
      "notes": ""
    }
  ],
  "servings": "",
  "prep_minutes": null,
  "cook_minutes": null,
  "total_minutes": null,
  "difficulty": "",
  "tools": [],
  "instructions": ["Provider instruction text"],
  "tips": [],
  "substitutions": [],
  "allergens": [],
  "nutrition": null,
  "categories": [],
  "language": "en",
  "source_name": "TheMealDB",
  "source_record_id": "52772",
  "source_url": "https://www.themealdb.com/meal/52772",
  "source_license": "Provider terms / license note",
  "source_terms_url": "https://provider.example/terms",
  "attribution": "Provider attribution text",
  "collected_at": "2026-10-23T00:00:00+00:00",
  "source_updated_at": "",
  "processed_at": "2026-10-23T00:02:00+00:00",
  "content_hash": "sha256",
  "duplicate_group_key": "normalized-title-and-region-key",
  "metadata": {}
}
```

`allergens`, `nutrition`, `difficulty`, `tools`, tips, and substitutions are source-declared fields, not model guesses. Missing values stay empty/null. The record ID is source-specific: two sources describing the same dish remain separate recipe versions.

The currently configured providers do not offer complete structured allergen or substitution data; these fields will commonly be empty. A later allergy filter must treat missing allergen declarations as unknown (not allergen-free) and must not claim medical safety.

## Duplicate policy and later database use

- Multiple raw snapshots of the same provider record are retained; normalization selects the latest snapshot for the processed record.
- Similar title/region records are listed in `data/processed/quality_report.json` as candidate duplicates. Do not delete/merge them without review.
- Person 3 can load these JSON records into relational tables and add SQL/full-text search. Vector search is optional and should index normalized text with the same source metadata.
- Person 4 can render records and citations using `title`, `country_or_region`, `ingredients`, `instructions`, `image_url`, `source_url`, and `attribution`; hide or label fields that are missing.

## Website implementation (Person 4)

The English website in `frontend/` is integrated with Person 3's SQLite/FTS5 backend and source-extractive answer service. Run `python -m recipehub.cli serve` for the complete application; the server supplies same-origin API configuration. The standalone static preview retains synthetic mock records for offline development. See [frontend-api-contract.md](frontend-api-contract.md), [person-3-delivery.md](person-3-delivery.md), and [person-4-delivery.md](person-4-delivery.md).

## Authoritative processed manifest

Normalization now writes `processed_files` in `quality_report.json`, listing accepted recipe files relative to `data/processed/`. It also reports source counts, invalid records, missing fields, and duplicate candidates. Latest snapshots are selected by timezone-aware timestamp comparison. Invalid latest versions are excluded from this manifest even when an older processed file remains on disk. Database indexing validates every manifest entry before a transaction and synchronizes exactly those records, removing stale database/FTS derivatives without deleting raw history. If a processed dataset has no manifest field, indexing uses all `recipes/*/*.json` files. Do not edit generated processed files without updating their authoritative manifest.
