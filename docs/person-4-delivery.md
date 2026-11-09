# Person 4 delivery — Recipe Atlas website

**Contributor:** Nguyễn Trần Hoàng Nhân (`2474802010272`).  
**Project:** Global Culinary Knowledge Base.  
**Component:** English recipe discovery website and conversational interface.

## Objective and implementation

The website lets a visitor search a multi-region recipe collection, refine the results, inspect a recipe and its provenance, and ask questions with record citations. It consumes the processed RecipeRecord schema already defined by Persons 1–2. Person 3's database and answer service are separate integration dependencies.

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
python -m http.server 5173 --bind 127.0.0.1 --directory frontend
```

Visit `http://127.0.0.1:5173` and keep the terminal open. Press `Ctrl+C` to stop. Opening `index.html` through `file://` does not support this module-based application; use the HTTP server.

Suggested demonstration:

1. Explain the classroom-demo banner and the distinction between synthetic fixtures and collected recipe records.
2. Search for `tomato`; inspect the applied search chip and the three matching records.
3. Reset. Select `Japan` and apply preferences. Add `soy` under Ingredients to avoid and apply again; the collection becomes empty because both Japanese demo records list soy.
4. Reset. Set total cooking time to 30 minutes. Explain that the soup with unknown time is excluded, rather than assigned an invented duration.
5. Reset. Open Rustic Vegetable Soup on the second page. Point out the original ingredient wording, source box, and unavailable time, difficulty, nutrition, and substitutions.
6. Ask `Find recipes with tomato`, open a citation, then ask `What are its ingredients?` and `How do I cook it?`. Explain that the demo resolves these follow-ups to the first cited record.
7. Ask `Is it safe for my allergy?` to demonstrate the explicit limit, then start a new conversation.
8. Show `config.js` and the proposed API contract for Person 3. Switch to API mode only when a compatible backend is available.

## Verification

From `frontend/`, run `npm run check` and `npm test` with Node.js 24. The frontend tests exercise combined search/filter behavior, unknown times, original ingredient wording, allergen declaration handling, pagination, safe source URLs, cited follow-ups, unsupported requests, API query encoding, bounded history, invalid payloads, service failures, and timeouts. GitHub Actions runs these alongside the existing Python pipeline tests without installing frontend packages.

Manual browser review should cover desktop and narrow layouts, keyboard navigation, opening/closing detail dialogs, all form controls, citation navigation, chat reset, backend failures, and retries. Live backend integration cannot be verified until Person 3 supplies the service.

Local verification completed with 18 passing frontend tests and 9 passing Python pipeline tests. Headless Chrome checks passed at desktop (1440 × 1100) and mobile (390 × 844) viewport sizes: collection loading, search, combined region/ingredient filters, empty results, pagination, missing-field detail display, cited conversation follow-ups, citation navigation, and conversation reset. Neither viewport had horizontal overflow, and no runtime JavaScript exceptions were recorded. This does not establish live backend compatibility or constitute a full accessibility audit.

## Limits and handoff

The local demo is a UI development tool, not the project's collected dataset or a knowledge-base implementation. Its recipes and source declarations are synthetic. The companion performs deterministic lookup; it is not an LLM and does not understand arbitrary questions. No API backend or database is implemented here.

Ingredient avoidance uses text matching against supplied names, original wording, and declared allergens. It does not resolve all aliases, certify dietary categories, detect hidden ingredients, or account for cross-contact. An empty allergen list means unknown. Nutrition and substitutions are displayed only when explicitly supplied by the source. No medical safety guarantees are made.

Applied preferences and conversation context are kept in memory. Reloading the page clears them; they are not stored in localStorage. In API mode the backend receives questions, history, and applied preferences. New conversation resets local context and does not delete remote session records. Person 3 owns backend session privacy and retention.

Person 3 should review [frontend-api-contract.md](frontend-api-contract.md), implement its endpoint shapes, and return the complete processed schema with provenance. The website can then be connected through configuration without replacing the presentation layer.
