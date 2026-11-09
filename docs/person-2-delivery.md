# Person 2 delivery — Shared schema, normalization, and data quality

**Member:** Phạm Thị Khánh Ngân (`2474802016786`).

`recipehub/models.py` defines the common RecipeRecord and Ingredient schema. `recipehub/normalize.py` maps raw TheMealDB/Wikibooks snapshots into this format, preserving original wording, measurements, provider IDs, source URLs, license/terms, attribution, and timestamps. `validate_recipe` validates schema version, required source fields, ingredients, arrays, field types, and nonnegative optional minute values at the database boundary.

TheMealDB's numbered ingredient/measurement fields become structured Ingredient objects; the original combined wording remains available. Small, explicit ingredient and unit alias maps support consistent naming without broad semantic guesses. Missing source time, difficulty, allergens, nutrition, or substitutions remain empty/null.

Wikibooks parsing supports list-based and table-based ingredients, mixed/vulgar fractions, wrapped/nested headings, paragraph/list instructions, source-declared equipment and tips, and labeled infobox fields. The parser avoids treating “Preparing the ingredients” as a new ingredient section within the cooking method. Original table cell wording and alternative measures are preserved; measurements are not converted or summed. Explicit infobox time and difficulty are retained, including difficulty image alt text. Ambiguous time ranges stay unknown. Source infobox values remain available in metadata, while recognized geographic labels are extracted from explicit cuisine/origin text instead of treating every cuisine cell as a country.

## Quality and version policy

- Raw snapshots are grouped by provider and provider-record ID. A timezone-aware timestamp comparison selects the latest version.
- Every accepted record uses a stable source-specific ID. Different providers' descriptions of the same dish remain separate.
- Required title/ingredient/instruction checks reject incomplete records. Errors identify the raw file and reason.
- Duplicate candidates are reported by normalized title/region grouping; the pipeline never merges them automatically.
- The quality report includes source counts, missing-field counts, and `processed_files`, the authoritative list of accepted derivatives.
- Outputs and the quality report are replaced atomically. A stale older processed file excluded from the current manifest cannot remain searchable after database synchronization.

## Operation

```powershell
.\.venv\Scripts\python.exe -m recipehub.cli normalize
.\.venv\Scripts\python.exe -m recipehub.cli index
.\.venv\Scripts\python.exe -m recipehub.cli stats
```

The completed local dataset has 137 current recipes: 72 from TheMealDB and 65 from Wikibooks. Three of the 140 retained raw snapshots are superseded provider versions. Missing allergen, nutrition, or substitution information remains unknown rather than being synthesized. See [dataset-summary.json](dataset-summary.json) for the verification snapshot.

## Verification and handoff

Parser tests cover original quantities/provenance, legacy/string MediaWiki HTML formats, nested headings, table ingredients, explicit time/difficulty/tools/tips, mixed fractions, and ambiguous time. Pipeline tests cover collection through indexed/cited retrieval. The database importer validates the complete batch before making changes and honors the processed manifest.

Consumers should follow [integration-contract.md](integration-contract.md). Do not count blank allergen declarations as allergen-free. Source values and text matching do not establish dietary safety, nutrition accuracy, or substitution suitability.
