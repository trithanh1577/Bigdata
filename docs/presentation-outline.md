# Final presentation outline

Use this outline to build the slide deck and coordinate the live defense. Replace the dataset counts on slide 8 with the output of `python -m recipehub.cli stats` after a successful crawl; do not count synthetic mock records as collected data.

## Slide 1 — Project and scope

- Global Culinary Knowledge Base: recipes, ingredients, preparation steps, and source-supported substitutions.
- Multi-region scope, with selectable recipe APIs and publisher websites; Wikibooks and TheMealDB are examples, not mandatory sources.
- Goal: demonstrate the complete collection-to-question-answer flow as a proof of concept.

**Speaker:** Person 1 introduces the problem and topic.

## Slide 2 — Architecture

Show the flow: source APIs → crawler/scheduler → raw data lake → normalization/quality checks → processed JSON → SQLite/FTS knowledge base → HTTP API → website/chat.

Explain that the raw snapshots are retained separately from normalized records so the parser can be rerun and the source provenance can be checked.

**Speaker:** Person 1 walks through collection; Person 2 explains processing; Person 3 explains the knowledge base and API; Person 4 explains the website.

## Slide 3 — Sources and collection

- Show the source configuration, selected regions/categories, rate handling, and source terms/attribution fields. Demonstrate web discovery only if Gemini is configured; it accepts pages with Schema.org Recipe data.
- Demonstrate a crawl run and point to one raw snapshot, run summary, manifest row, and saved cursor.
- Explain the local scheduler interval (the demo can use 30 minutes) and that the machine must stay awake and online.

**Speaker:** Person 1.

## Slide 4 — Normalized data and quality

- Show one processed recipe record and the shared schema.
- Point out original ingredient wording, normalized ingredient names, source URLs, collected time, and missing fields.
- Explain validation and why similar records are flagged rather than automatically merged.

**Speaker:** Person 2.

## Slide 5 — Knowledge Base and API

- Show the `build` command and SQLite database path.
- Demonstrate text search, a region/category filter, ingredient exclusions, and one recipe detail endpoint.
- Explain FTS retrieval and that the HTTP API returns complete recipe records with source provenance.

**Speaker:** Person 3.

## Slide 6 — Website and question answering

- Search for a dish or ingredient in Recipe Atlas.
- Open a result and show its source details and any unavailable fields.
- Ask for ingredients and preparation steps, then follow the citation to the recipe record.
- Ask for a substitution that the source does not document and show that the system reports it as unavailable rather than inventing one.

**Speaker:** Person 4.

## Slide 7 — Allergy preference and limitations

- Exclude an ingredient and show alternative records when the collection contains matches.
- Explain that matching checks recorded ingredient text only; source data may be incomplete, so it cannot guarantee allergy safety or account for cross-contact.
- Explain that deterministic retrieval works without a key; an optional server-side model can phrase answers more flexibly from retrieved evidence.

**Speaker:** Person 3 explains filtering; Person 4 demonstrates the interface.

## Slide 8 — Experiment and observed coverage

Run `python -m recipehub.cli stats` and show the actual raw count, processed count, indexed count, and region coverage. Record the date and any source/API failures observed in the run summary. Do not present the synthetic mock collection as crawler output.

**Speaker:** Person 1 reports crawl behavior; Person 2 reports normalization; Person 3 reports indexed/searchable records.

## Slide 9 — Decisions, limitations, and next steps

- Summarize the key choices from [architecture-decisions.md](architecture-decisions.md).
- State current limits: source coverage, source-provided allergen/substitution completeness, local scheduler, expiring SQLite conversation context, and no public hosting. Retrieval-only mode is limited; the optional model depends on an external provider, network access, quota, and its terms/availability.
- Possible next work: broader permitted sources, change detection, richer evaluation, persistent sessions, and improved retrieval/model grounding.

**Speaker:** One member summarizes; all members answer questions about their component.

## Live demo run order

1. In a terminal, show `crawl`, `normalize`, `build`, and `stats` outputs.
2. Start the site/API with `python -m recipehub.cli serve` and open `http://127.0.0.1:8000`.
3. Search, filter by region, exclude an ingredient, inspect a recipe, and open its citation.
4. Ask for ingredients and preparation steps; show the source citations.
5. Ask for an unavailable substitution and explain why the system does not guess.
6. If a source/API is unavailable during the live demo, show the saved manifest/raw snapshot and explain the failure state instead of implying fresh collection succeeded.
