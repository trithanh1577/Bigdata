# Website API contract — Person 3 ↔ Person 4

**Status:** proposed integration contract. No HTTP backend exists in this repository yet. Person 3 should review these endpoints before connecting the website to live data. The website currently implements them through a mock adapter; this document does not claim that they are deployed.

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

Use `mode: "mock"` for independent UI development. API mode never silently falls back to demo data. The frontend is static; its configuration is public and must not contain secrets. The current baseline has no authentication, browser storage, database, or API proxy. Configure backend CORS to allow the development origin `http://127.0.0.1:5173` and handle JSON POST preflights. For an HTTPS deployment, use an HTTPS API URL or a same-origin reverse proxy.

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
| `q` | Optional search string. The mock requires every whitespace-separated term to occur in the combined title, description, region, categories, or ingredient names, ignoring case and accents. Person 3 may improve ranking with full-text search. |
| `country` | Exact `country_or_region` facet value. |
| `category` | Exact member of `categories`. |
| `difficulty` | Exact source-declared difficulty. |
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

The client sends at most twelve prior messages, excluding the current message, and carries the returned session ID into the next request. It keeps this state in tab memory; **New conversation** clears it locally and starts with a null session ID. It does not request deletion of backend history. Person 3 owns session isolation, expiration, retention, and retrieval context. Do not trust client-provided history as an authoritative source.

Apply current country/category/time/difficulty/exclusion/allergen preferences to retrieval. Treat the conversational message as the new query; the previous search `q` is context, not a mandatory second query. Re-evaluate preferences on every turn, including follow-ups, so earlier records cannot bypass newly applied exclusions. Citation IDs must resolve through the detail endpoint. The UI opens those records and shows provider links when available.

The backend may use SQL/full-text retrieval with or without an LLM. Answer recipe questions only from retrieved records and cite them. Do not invent missing ingredients, timings, substitutions, allergens, or nutrition. For unsupported requests, explain the limitation and return an empty citation list. The UI labels uncited API responses. Dietary exclusion is assistance with incomplete data, never a medical safety guarantee. The mock only recognizes a limited set of English recipe questions and deliberately declines dietary/safety/substitution requests.

## Integration checklist

1. Load normalized recipe records into Person 3's database without merging provider versions.
2. Implement the four endpoint shapes and CORS behavior above.
3. Test unknown fields, empty results, missing records, and service errors against the UI.
4. Change `frontend/config.js` to API mode and restart/reload the website.
5. Check a search, multiple ingredient exclusions, pagination, a recipe's original wording and source links, and a cited multi-turn conversation.
6. Keep test fixtures clearly separate from crawled records; do not report the eight synthetic records as collected dataset coverage.
