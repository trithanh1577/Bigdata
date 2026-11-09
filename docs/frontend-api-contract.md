# Website API contract — Person 3 ↔ Person 4

**Status:** implemented locally by `recipehub/api.py`. The website uses these endpoint shapes in API mode. The service is a local proof of concept; it is not a hosted public deployment.

**Website owner:** Nguyễn Trần Hoàng Nhân — `2474802010272`.

The recipe payload is the processed schema in [integration-contract.md](integration-contract.md) and `recipehub/models.py`. Preserve provider-specific record IDs and provenance. Do not merge recipes with similar titles. Search responses contain complete records in this baseline so both adapters have the same shape.

## Configuration and transport

The website reads `frontend/config.js` at startup:

```javascript
window.RECIPEHUB_CONFIG = {
  mode: "api",
  apiBaseUrl: "http://127.0.0.1:8000/api/v1",
  timeoutMs: 120000,
};
```

Run `python -m recipehub.cli serve` to serve the frontend and API together. The website derives its API base URL from its current origin, so the selected server port can vary. Use `mode: "mock"` only for independent UI development. API mode never silently falls back to demo data. The frontend configuration is public and must not contain secrets. The local service has no authentication or hosted-session persistence. If serving the frontend separately, set `apiBaseUrl` to the API server and configure `RECIPEHUB_CORS_ORIGINS` to include the frontend's exact origin; JSON POST preflights are supported. For an HTTPS deployment, use an HTTPS API URL or a same-origin reverse proxy.

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

The API honors the `Accept-Language` header (`vi` or `en`). With a configured model, `labels` maps each original facet value to its displayed translation and `content_translated` indicates whether translation succeeded. Filter values themselves remain the original stored values.

## GET `/health`

Returns the indexed recipe count plus booleans `language_model_available` and `web_discovery_available`. The latter is true only when a Gemini model is configured; other OpenAI-compatible models can answer and translate but do not enable Google's web search grounding. Gemini chat and translation use Google's native `generateContent` API with the server-side API key.

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

`items` contains full processed recipe objects, not titles or IDs alone. `total` is the count after filtering and before pagination. Return array fields as `[]`, unknown times/nutrition as `null`, and unavailable strings as `""`, following the shared schema. Do not replace missing allergen declarations with a claim that a recipe has no allergens. Responses also include `content_translated`; when it is false, the UI explains that it is showing source-language content. The complete recipe endpoint uses the same translation behavior and leaves the stored source record unchanged.

## GET `/recipes/{record_id}`

Return one complete processed recipe object. The client URL-encodes the opaque record ID. Return `404` if it is unavailable. Source fields include `source_url`, `source_terms_url`, `source_license`, `source_name`, `attribution`, and collection/update times. `original_recipe_url` is an additional link when supplied by the provider. External images remain source URLs and are not copied into this repository.

## POST `/chat`

Example request:

```json
{
  "message": "What are its ingredients?",
  "language": "en",
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

The client carries the returned session ID into the next request. The server keeps the latest five exchanges and cited record IDs in process memory to answer follow-ups; it ignores client-provided history as authoritative evidence. **New conversation** starts a new session. Server sessions and conversation context reset when the local service restarts.

Apply current country/category/time/difficulty/exclusion/allergen preferences to retrieval. The user can ask in English or Vietnamese; if the local English-language records do not match, Gemini translates the search terms into English for retrieval. Answer in the interface language supplied by the client. Treat the conversational message as the new query; the previous search `q` is context, not a mandatory second query. Re-evaluate preferences on every turn, including follow-ups, so earlier records cannot bypass newly applied exclusions. Citation IDs must resolve through the detail endpoint. The UI opens those records and shows provider links when available.

For a new recipe query with no matching record, a configured Gemini model can use Google Search grounding once per distinct query, inspect up to three result pages, and collect only pages containing Schema.org `Recipe` JSON-LD. Accepted pages are written to the raw data lake and manifest, normalized, added to SQLite, and cited in the answer. Other page formats are skipped until an adapter is written. Allergy exclusions are applied when looking for recipe variants; answer only with substitutions explicitly present in source records or alternative recipes whose listed ingredients do not text-match the exclusion. This is not an allergy-safety guarantee. Discovered site reuse terms are not automatically verified; the record preserves its URL and marks terms for review. Gemini Search grounding uses the configured account's quota and may incur usage charges. A quota or rate-limit error prevents live discovery until the account can make requests again. API credentials are server-only in `.env`; never return them to the browser.

The backend may use SQL/full-text retrieval with or without an LLM. Answer recipe questions only from retrieved records and cite them. Do not invent missing ingredients, timings, substitutions, allergens, or nutrition. For unsupported requests, explain the limitation and return an empty citation list. The UI labels uncited API responses. Dietary exclusion is assistance with incomplete data, never a medical safety guarantee. The mock only recognizes a limited set of English recipe questions and deliberately declines dietary/safety/substitution requests.

## Integration checklist

1. Run `python -m recipehub.cli build` after normalization to load processed records into SQLite without merging provider versions.
2. Start the local service with `python -m recipehub.cli serve`; it implements the endpoint shapes and local CORS behavior above.
3. The website defaults to API mode. It does not silently fall back to demo data if the service is unavailable.
4. Demonstrate search, ingredient exclusions, pagination, original wording/source links, and cited follow-up questions.
5. Keep the synthetic UI fixtures clearly separate from crawled records; do not report them as collected dataset coverage.
