# Person 1 delivery — API collection and raw data lake

**Member:** Nguyễn Thành Trí (`2474802010400`).

The collector in `recipehub/recipe_crawler.py` uses TheMealDB's official V1 endpoints and the Wikibooks MediaWiki API. Source URLs, attribution, license/terms notes, provider IDs, language, and collection timestamps accompany every original payload. Images remain source URLs. No website HTML is scraped from TheMealDB.

TheMealDB collection rotates through configured Italian, Japanese, Thai, Vietnamese, and Chinese regions and persists the last ID per region. The regional list and meal filters are queried before detail lookups. Chinese replaces an originally configured region that returned no recipes during live verification; available geographic labels do not guarantee a populated provider filter.

Wikibooks recipes are collected from `Category:Recipes` in **Cookbook namespace 102**. The original namespace-0 query missed the actual recipe pages; it has been corrected and regression-tested. Category continuation tokens persist between runs. Repeated pagination tokens and provider-level JSON errors are reported instead of causing an endless loop or silent empty output.

Raw snapshots use `data/raw/<source>/runs/<run_id>/records/`, and each run has a summary. The crawler appends URL/snapshot history to `data/state/crawl_manifest.jsonl` and saves progress atomically to `crawl_cursors.json`. Re-crawling preserves history. Successful writes retain original API objects before normalization.

Requests use a descriptive User-Agent containing a real project URL, a configured delay (1.5 seconds by default), timeout handling, and bounded retries for connection failures, HTTP 429, and HTTP 5xx. Numeric and HTTP-date Retry-After values are handled. Wikimedia placeholders are rejected. Source terms and attribution notes remain explicit in configuration.

## Operation

```powershell
$env:CRAWLER_USER_AGENT = 'GlobalCulinaryKnowledgeBase/1.0 (https://github.com/trithanh1577/Bigdata)'
.\.venv\Scripts\python.exe -m recipehub.cli crawl --max-items 65
.\.venv\Scripts\python.exe -m recipehub.cli crawl --source themealdb --max-items 5
.\.venv\Scripts\python.exe -m recipehub.cli schedule --days 7 --max-items 20
```

The scheduler runs collection, normalization, and database synchronization sequentially. It requires an open terminal and stops with Ctrl+C. Daily is the default; weekly is optional. This is a local scheduler, not a hosted task service.

## Verification and handoff

Offline tests cover regional rotation/cursor progress, Cookbook namespace and pagination, malformed provider responses, contact requirements, API-level errors, and transient server retries. The end-to-end pipeline test carries simulated source payloads through raw snapshots, normalization, database indexing, and a cited answer.

The completed local run retained 140 raw snapshots across both providers, including later regional verification runs. Snapshot count differs from current recipe count because raw history includes repeated provider records. See [dataset-summary.json](dataset-summary.json) for aggregate verification metrics. Generated source content is Git-ignored and must be collected again on a fresh clone.

Source policy references: [TheMealDB API](https://www.themealdb.com/api.php), [TheMealDB terms](https://www.themealdb.com/terms_of_use.php), [Wikimedia access policy](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy). Source availability, payload structure, and permissions should be reviewed again before public deployment or adding providers.
