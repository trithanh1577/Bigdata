# Website API contract — Person 3 ↔ Person 4

**Status:** implemented by `recipehub/server.py`, `recipehub/knowledge_base.py`, and `recipehub/conversation.py`, and integrated with the website. Run `python -m recipehub.cli serve` for the connected application at `http://127.0.0.1:8000`. The standalone static preview still uses the mock adapter by default.

**Website owner:** Nguyễn Trần Hoàng Nhân — `2474802010272`.

The recipe payload is the processed schema in [integration-contract.md](integration-contract.md) and `recipehub/models.py`. Preserve provider-specific record IDs and provenance. Do not merge recipes with similar titles. Search responses contain complete records in this baseline so both adapters have the same shape.

## Configuration and transport

The website reads `frontend/config.js` at startup:

```javascript
window.RECIPEHUB_CONFIG = {
  mode: "api",
  apiBaseUrl: "http://127.0.0.1:8000/api/v1",
  timeoutMs: 15000,
};
```

The integrated server overrides `/config.js` with same-origin API configuration automatically. Use `mode: "mock"` for independent UI development. API mode never silently falls back to demo data. Browser configuration is public and must not contain secrets. The backend uses SQLite with FTS5, and supports JSON POST preflights for `http://127.0.0.1:5173` and `http://localhost:5173`. Supply repeated `serve --allow-origin` options to replace these cross-origin defaults. The baseline has no production authentication or TLS. For an HTTPS deployment, use an HTTPS API URL or a same-origin reverse proxy.

All successful responses use `application/json`. Use appropriate HTTP status codes (`400`, `404`, `429`, `500`, `503`) for failures. The UI exposes HTTP status, timeouts, connection failures, and invalid response shapes with retry paths; it does not render server error HTML. Record text is rendered as plain text, including conversation answers; source links accept only absolute HTTP(S) URLs.

## GET `/facets`

Return all nonempty distinct values from the current collection, rather than only the current page. Do not invent a difficulty or region for an incomplete record.

```json
{
  "countries": ["India", "Italy", "Japan", "Mexico", "Vietnam"],
  "categories": ["Main course", "Noodles", "Pasta", "Rice", "Salad", "Side dish", "Soup", "Stew", "Tacos"],
  "difficulties": ["Easy", "Medium"]
}
```

These values illustrate the synthetic demo only. Real facets depend on normalized source data.

## GET `/recipes`

| Parameter | Meaning |
| --- | --- |
| `q` | Optional search string. The backend requires all sanitized Unicode token prefixes to match its SQLite FTS5 index of title, description, region, categories, and ingredient names. User input cannot execute FTS operators. The mock uses substring matching of whitespace-separated terms. Both ignore case and accents. |
| `country` | Exact `country_or_region` facet value. |
| `category` | Exact member of `categories`. |
| `difficulty` | Exact source-declared difficulty. |
| `ingredient` | Optional backend-only exact normalized ingredient name. |
| `max_minutes` | Inclusive total-time ceiling. Exclude records with `total_minutes: null` when this filter is active. Do not derive total time from other fields. |
| `exclude_ingredients` | Repeated query parameter, one term per occurrence. Exclude a record when any term occurs in ingredient `name`, ingredient `original_text`, or source-declared `allergens`, ignoring case and accents. |
| `require_allergens` | When `true`, only return records with a nonempty source-declared `allergens` list. This does not imply complete allergen coverage or dietary safety. |
| `sort` | `title` (default) or `time`. Time ascending; unknown time last. Title and then record ID break ties for stable pagination. |
| `page` | One-based page; default `1`. Clamp a page beyond the end to the last page. An empty collection returns page `1`. |
| `page_size` | The website requests `6`. Enforce a backend limit. |

Example: `/recipes?country=Japan&max_minutes=30&exclude_ingredients=peanut&exclude_ingredients=shrimp&page=1&page_size=6&sort=title`.

Response envelope:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 6
}
```

`items` contains full processed recipe objects, not titles or IDs alone. `total` is the count after filtering and before pagination. Return array fields as `[]`, unknown times/nutrition as `null`, and unavailable strings as `""`, following the shared schema. Do not replace missing allergen declarations with a claim that a recipe has no allergens.

## GET `/recipes/{record_id}`

Return one complete processed recipe object. The client URL-encodes the opaque record ID. Return `404` if it is unavailable. Source fields include `source_url`, `source_terms_url`, `source_license`, `source_name`, `attribution`, and collection/update times. `original_recipe_url` is an additional link when supplied by the provider. External images remain source URLs and are not copied into this repository.

## POST `/chat`

Example request:

```json
{
  "message": "What are its ingredients?",
  "session_id": null,
  "history": [
    {"role": "user", "content": "Find recipes from Japan"},
    {"role": "assistant", "content": "An earlier source-grounded answer"}
  ],
  "filters": {
    "q": "",
    "country": "Japan",
    "category": "",
    "difficulty": "",
    "max_minutes": 30,
    "exclude_ingredients": ["peanut"],
    "require_allergens": false,
    "sort": "title"
  }
}
```

Example response shape (placeholder values, not actual recipe data):

```json
{
  "answer": "Answer supported by the retrieved recipe record.",
  "session_id": "opaque-backend-session-id",
  "citations": [
    {
      "record_id": "provider-specific-record-id",
      "title": "Source recipe title",
      "source_name": "Provider name",
      "source_url": "https://provider.example/recipe"
    }
  ]
}
```

The client sends at most twelve prior messages, excluding the current message, and carries the returned session ID into the next request. The backend accepts that history for compatibility but ignores it for grounding. It retains only the last cited record IDs and conversational exclusion terms under a random 256-bit bearer token in SQLite. Full message history is not persisted. Sessions expire after one hour without activity and are removed lazily on the next chat request; the store is capped at 1,000 sessions. An unknown/expired token returns `404`. **New conversation** clears browser memory and starts with a null token; old backend context expires independently. Do not share session tokens.

Apply current country/category/time/difficulty/exclusion/allergen preferences to retrieval. Treat the conversational message as the new query; the previous search `q` is context, not a mandatory second query. Re-evaluate preferences on every turn, including follow-ups, so earlier records cannot bypass newly applied exclusions. Citation IDs must resolve through the detail endpoint. The UI opens those records and shows provider links when available.

The implemented backend uses SQL/FTS retrieval and source extraction, without an LLM. It supports English discovery by region, ingredient, title, and an explicit minute limit, followed by questions about ingredients, steps, sources, time, difficulty, allergens, nutrition, substitutions, tools, and tips. Unsupported requests explain the limit. Missing facts are labeled rather than invented; record-based answers include citations even when explaining a field's absence. Text following `without`, `avoid`, `exclude`, or `allergic to` is treated as literal comma/and/or-separated avoidance terms. These extra exclusions persist until a new conversation. No alias or hidden-ingredient coverage is guaranteed. Dietary exclusion never certifies medical safety. The standalone mock has a smaller set of English patterns and declines dietary/safety/substitution requests.

## Health and errors

`GET /health` returns `status`, indexed recipe count, source/region counts, search engine, `answer_mode: "source-extractive"`, and `session_ttl_seconds: 3600`. An empty collection is a valid healthy state. Search page size is capped at 100. Chat messages are limited to 1,000 characters, request bodies to 32 KiB, and exclusions to 20 terms of at most 100 characters each. Error bodies use `{"error":{"status":400,"message":"Reason"}}`; the frontend renders the reason as plain text. API and configuration responses are not cached.

## Integration checklist

1. Load normalized recipe records into Person 3's database without merging provider versions.
2. Start the implemented service with `python -m recipehub.cli serve`.
3. Test unknown fields, empty results, missing records, and service errors against the UI.
4. Use the integrated same-origin website, or configure a separately served frontend to use API mode.
5. Check a search, multiple ingredient exclusions, pagination, a recipe's original wording and source links, and a cited multi-turn conversation.
6. Keep test fixtures clearly separate from crawled records; do not report the eight synthetic records as collected dataset coverage.
