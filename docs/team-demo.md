# Complete project demonstration

All code, interface text, and delivery documents are in English. The project includes all four members' components: collection, normalization, knowledge base/API, and the website.

## First setup

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:CRAWLER_USER_AGENT = 'GlobalCulinaryKnowledgeBase/1.0 (https://github.com/trithanh1577/Bigdata)'
.\.venv\Scripts\python.exe -m recipehub.cli pipeline --max-items 65
.\.venv\Scripts\python.exe -m recipehub.cli serve
```

Open `http://127.0.0.1:8000`. On this prepared workspace, source data already exists, so only `serve` is needed. On a fresh clone, collect it again; raw source content and the SQLite database are deliberately Git-ignored. External APIs may change or reject requests, and future record counts can differ from the dated verification snapshot.

## Member demonstration sequence

1. **Person 1:** Show source configuration, the 1.5-second delay, and a run summary under `data/raw/<source>/runs/`. Compare two provider payloads, then show source URLs, license/attribution, raw manifest entries, and persisted progress. Explain Cookbook namespace 102 and daily/weekly scheduling.
2. **Person 2:** Show one processed recipe's original ingredient wording next to its structured fields. For Wikibooks, show a recipe with an explicit infobox time/difficulty. Open `data/processed/quality_report.json` and explain accepted files, missing fields, invalid records, and duplicate candidates.
3. **Person 3:** Open `http://127.0.0.1:8000/api/v1/health`. Show source counts and FTS5. Search `/api/v1/recipes?q=chicken`, then demonstrate an exact country or ingredient filter. Explain transactional indexing, provider-specific IDs, source-extractive answers, and expiring conversation context.
4. **Person 4:** Use the connected website. Search `chicken`, filter `Japanese`, reset, and try a 30-minute ceiling. Open a recipe and inspect its provider URL, attribution, terms, original wording, and missing-data labels.
5. **Conversation:** Reset preferences, ask `Find recipes with chicken`, then `What are its ingredients?`, `How do I cook it?`, and `Where does it come from?`. Open a citation and compare the displayed fields with the answer.
6. **Data limits:** Ask for nutrition or substitutions when a source omits them. Turn on the requirement for allergen declarations and explain an empty collection: missing declarations mean unknown, not safe. Show literal ingredient exclusions and the cross-contact limitation.
7. **Responsive UI:** Inspect a narrow viewport, keyboard navigation, Escape to close a detail dialog, and the new-conversation control.

## Checks

Offline checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m compileall -q recipehub
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm run check
npm test
```

With the connected server running and a collected dataset, run `npm run test:integration` from `frontend/`. These explicit checks validate the real frontend HTTP adapter, source records, missing-record errors, named recipe answers, and contextual follow-ups. Node.js 24 is needed for frontend tests; serving the application itself only needs Python and the listed requirements.

The completed local verification passed 33 Python tests, 18 frontend unit tests, and 2 real HTTP integration tests. Chrome checks also passed for the connected website at 1440 × 1100 and 390 × 844 viewports, including source search/detail, keyboard dialog closing, cited follow-ups, reset, and absence of horizontal overflow or runtime JavaScript exceptions.

## Refresh and schedule

Run `pipeline --max-items 20` to collect, normalize, and refresh the database. To inspect stages separately, use `crawl`, `normalize`, and `index`. Select one configured provider with `crawl --source themealdb --max-items 10`. Run `schedule --days 1 --max-items 20` in a separate terminal for daily refresh or use `--days 7` for weekly refresh. These commands use the same `.venv\Scripts\python.exe -m recipehub.cli` prefix. Keep scheduled terminals open; stop them with Ctrl+C.

## Handoff

Review [Person 1](person-1-delivery.md), [Person 2](person-2-delivery.md), [Person 3](person-3-delivery.md), and [Person 4](person-4-delivery.md) delivery reports, the [processed schema](integration-contract.md), and the [HTTP API contract](frontend-api-contract.md). The local app uses no AI keys or vector service. Optional LLM/vector features can be added after this grounded baseline; production hosting would require a separate deployment/security design.
