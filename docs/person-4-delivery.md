# Person 4 delivery — Recipe Atlas website

**Contributor:** Nguyễn Trần Hoàng Nhân (`2474802010272`).  
**Project:** Global Culinary Knowledge Base.  
**Component:** Bilingual recipe discovery website and conversational interface.

## Objective and implementation

The English/Vietnamese website lets a visitor search a multi-region recipe collection, refine the results, inspect a recipe and its provenance, and ask questions with record citations. Questions can be written in either language and answers follow the selected interface language. When Gemini is configured, it can translate recipe content for the selected interface language and trigger web discovery when a requested dish is missing. It consumes the processed RecipeRecord schema already defined by Persons 1–2 and calls Person 3's local HTTP API in API mode. Synthetic fixtures remain available for isolated UI development.

The implementation uses semantic HTML, responsive CSS, and browser JavaScript modules. There is no runtime package installation or build step. A local Python HTTP server serves the files. Node.js is used only for syntax checks and automated frontend tests. Decorative food illustrations are generated with CSS; they are labeled as illustrations rather than presented as source photography.

The visual design uses a cream background, dark green controls, serif headings, a responsive recipe grid, a filter sidebar, a recipe detail dialog, and a separate conversation panel. Narrow screens place the filters above the collection. Form labels, keyboard focus indicators, native modal dialogs, a skip link, live status messages, and reduced-motion styling support accessibility.

## Assignment coverage

| Assigned responsibility | Delivered behavior | Files |
| --- | --- | --- |
| Recipe search and discovery | Search title/description/region/categories/ingredients; stable sorting; six-item pagination; empty and error states. | `frontend/app.js`, `frontend/domain.js` |
| Country, dish type, time, difficulty filters | Dynamic facets, combined filters, reset control, applied-filter chips; unknown times excluded only when a ceiling is active. | `frontend/index.html`, `frontend/domain.js` |
| Recipe details and source attribution | Original ingredient wording, steps, available fields, explicit missing-data labels, provider/original recipe/terms links, attribution, source IDs, timestamps. | `frontend/app.js` |
| Allergy and dietary input | Comma-separated ingredient avoidance; optional requirement for nonempty allergen declarations; clear unknown-data handling. | `frontend/domain.js`, `frontend/index.html` |
| Conversation interface | Suggested prompts, plain-text answers, clickable record citations, follow-up context, new conversation, pending/error states. | `frontend/app.js`, `frontend/api.js` |
| Parallel development using mocks | Eight clearly marked synthetic recipes across five regions; deterministic answers; no AI service or backend required. | `frontend/mock-data.js`, `frontend/domain.js` |
| Backend integration preparation | Configurable API client, bounded timeout, response checks, documented endpoint shapes and CORS requirements. | `frontend/api.js`, `frontend/config.js`, `docs/frontend-api-contract.md` |

## Run and demonstrate

From the repository root:

```powershell
python -m recipehub.cli crawl --max-items 10
python -m recipehub.cli normalize
python -m recipehub.cli build
python -m recipehub.cli serve
```

Visit `http://127.0.0.1:8000` and keep the terminal open. Press `Ctrl+C` to stop. The Python server serves the website and API on the same origin. Opening `index.html` through `file://` does not support this module-based application.

Suggested demonstration:

1. Show the API-mode banner and explain that records come from the project's collected and indexed data.
2. Search for an ingredient that appears in `stats`; inspect the matching records and source attribution.
3. Apply a region/category filter, then exclude an ingredient. Explain that records with unknown cooking times are not treated as known durations.
4. Open a recipe and point out the original ingredient wording, source/terms links, and fields that remain unknown.
5. Ask for its ingredients and preparation steps, then open the citation to show the supporting record.
6. Ask for a source-unsupported substitution or allergy safety judgment. Show that missing information stays unknown and no medical guarantee is made.
7. Show `/api/v1/health`, the SQLite database path, and `config.js`. Explain that mock fixtures are available for UI development but are not collected data.

## Verification

From `frontend/`, run `npm run check` and `npm test` with Node.js 24. The frontend tests exercise combined search/filter behavior, unknown times, original ingredient wording, allergen declaration handling, pagination, safe source URLs, cited follow-ups, unsupported requests, API query encoding, bounded history, invalid payloads, service failures, and timeouts. GitHub Actions runs these alongside the existing Python pipeline tests without installing frontend packages.

Manual browser review should cover desktop and narrow layouts, keyboard navigation, opening/closing detail dialogs, all form controls, citation navigation, chat reset, backend failures, and retries. The local service is provided by `recipehub/api.py`; a public deployment is outside this proof of concept.

The earlier UI/pipeline delivery recorded 18 passing frontend tests and 9 passing Python pipeline tests. Headless Chrome checks were documented at desktop (1440 × 1100) and mobile (390 × 844) sizes for collection loading, search, combined filters, empty results, pagination, missing-field details, cited follow-ups, citation navigation, and conversation reset. Those checks predate Person 3's SQLite/API implementation and do not establish current end-to-end integration or constitute a full accessibility audit.

## Limits and handoff

The synthetic mock mode is a UI development tool, not the project's collected dataset. The default API mode uses the SQLite knowledge base and local HTTP service. Without an optional model, chat uses deterministic retrieval and a limited set of question intents; it does not understand every arbitrary question. An optional OpenAI-compatible model can be configured server-side.

Ingredient avoidance uses text matching against supplied names, original wording, and declared allergens. It does not resolve all aliases, certify dietary categories, detect hidden ingredients, or account for cross-contact. An empty allergen list means unknown. Nutrition and substitutions are displayed only when explicitly supplied by the source. No medical safety guarantees are made.

Applied preferences and conversation context are kept in browser memory. Reloading the page clears them; they are not stored in localStorage. In API mode the server keeps cited-record context in memory for the life of the local service. Starting a new conversation creates a new session; server context is cleared when the service restarts.

The backend handoff is documented in [frontend-api-contract.md](frontend-api-contract.md). The site and API can be demonstrated together with `python -m recipehub.cli serve` after records are collected and indexed.
