import test from "node:test";
import assert from "node:assert/strict";
import { MOCK_RECIPES } from "../mock-data.js";
import { filterRecipes, buildFacets, mockAnswer, paginate, parseExclusions, safeUrl, timeLabel } from "../domain.js";

test("fixtures preserve source-specific IDs and expose five demo regions", () => {
  assert.equal(new Set(MOCK_RECIPES.map(item => item.record_id)).size, MOCK_RECIPES.length);
  assert.equal(buildFacets(MOCK_RECIPES).countries.length, 5);
  assert.ok(MOCK_RECIPES.every(item => item.metadata.synthetic && !item.source_url));
});

test("search combines words, region, category, and difficulty", () => {
  const result = filterRecipes(MOCK_RECIPES, { q: "BASIL tomato", country: "Italy", category: "Pasta", difficulty: "Easy" });
  assert.deepEqual(result.map(item => item.record_id), ["demo-1"]);
});

test("time filters exclude unknown values and time sorting puts them last", () => {
  assert.equal(timeLabel(null), "Time not supplied");
  assert.equal(timeLabel(0), "0 min");
  assert.ok(!filterRecipes(MOCK_RECIPES, { max_minutes: 60 }).some(item => item.record_id === "demo-7"));
  assert.equal(filterRecipes(MOCK_RECIPES, { sort: "time" }).at(-1).record_id, "demo-7");
});

test("ingredient avoidance checks ingredient wording AND declared allergens", () => {
  const result = filterRecipes(MOCK_RECIPES, { exclude_ingredients: ["peanut", "crustaceans", "wheat"] });
  assert.ok(!result.some(item => ["demo-1", "demo-2", "demo-3", "demo-6", "demo-8"].includes(item.record_id)));
  assert.deepEqual(parseExclusions(" Peanut, ,SHRIMP, peanut "), ["peanut", "shrimp"]);
  const wordingOnly = { ...MOCK_RECIPES[0], ingredients: [{ name: "dressing", original_text: "dressing with peanut oil" }], allergens: [] };
  assert.equal(filterRecipes([wordingOnly], { exclude_ingredients: ["peanut"] }).length, 0);
});

test("empty allergen declarations remain unknown", () => {
  const result = filterRecipes(MOCK_RECIPES, { require_allergens: true });
  assert.ok(result.length > 0);
  assert.ok(result.every(item => item.allergens.length > 0));
  assert.ok(!result.some(item => item.record_id === "demo-4"));
});

test("pagination gives stable non-overlapping pages and clamps out-of-range requests", () => {
  const recipes = filterRecipes(MOCK_RECIPES);
  const first = paginate(recipes, 1);
  const second = paginate(recipes, 2);
  assert.equal(first.items.length, 6);
  assert.equal(second.items.length, 2);
  assert.equal(new Set([...first.items, ...second.items].map(item => item.record_id)).size, 8);
  assert.equal(paginate(recipes, 999).page, 2);
  assert.equal(paginate([], 0).page, 1);
});

test("untrusted source URLs only allow absolute HTTP(S)", () => {
  for (const url of ["javascript:alert(1)", "data:text/html,test", "//example.org", "", "file:///tmp/test"]) assert.equal(safeUrl(url), "");
  assert.equal(safeUrl("https://example.org/recipe"), "https://example.org/recipe");
});

test("demo conversation retrieves cited records then answers a contextual follow-up", () => {
  const answer = mockAnswer(MOCK_RECIPES, "Find recipes with tomato");
  assert.ok(answer.citations.length > 0);
  for (const item of answer.citations) assert.ok(MOCK_RECIPES.find(recipe => recipe.record_id === item.record_id).ingredients.some(ingredient => ingredient.name === "tomato"));
  const followUp = mockAnswer(MOCK_RECIPES, "What are its ingredients?", {}, answer.citations.map(item => item.record_id));
  assert.equal(followUp.citations[0].record_id, answer.citations[0].record_id);
  assert.ok(followUp.answer.includes("•"));
  const steps = mockAnswer(MOCK_RECIPES, "How do I cook it?", {}, followUp.citations.map(item => item.record_id));
  assert.ok(steps.answer.includes("1."));
});

test("demo chat applies exclusions even when earlier context referred to an excluded dish", () => {
  const result = mockAnswer(MOCK_RECIPES, "Find recipes from Japan", { exclude_ingredients: ["soy"] });
  assert.equal(result.citations.length, 0);
  const followUp = mockAnswer(MOCK_RECIPES, "What are its ingredients?", { exclude_ingredients: ["peanut"] }, ["demo-3"]);
  assert.equal(followUp.citations.length, 0);
});

test("demo chat handles time constraints without inventing missing times", () => {
  const answer = mockAnswer(MOCK_RECIPES, "Find recipes under 30 minutes");
  assert.ok(answer.citations.length > 0);
  assert.ok(answer.citations.every(item => MOCK_RECIPES.find(recipe => recipe.record_id === item.record_id).total_minutes <= 30));
});

test("demo abstains on dietary, safety, substitution, nutrition, and unrelated questions", () => {
  for (const question of ["Is it safe for my allergy?", "What can I substitute for peanut?", "How many calories?", "Show vegan recipes", "Is it gluten-free?"]) {
    const answer = mockAnswer(MOCK_RECIPES, question);
    assert.equal(answer.citations.length, 0);
    assert.match(answer.answer, /cannot verify/);
  }
  assert.equal(mockAnswer(MOCK_RECIPES, "Tell me about astronomy").citations.length, 0);
  const exclusion = mockAnswer(MOCK_RECIPES, "Find recipes without peanut");
  assert.equal(exclusion.citations.length, 0);
  assert.match(exclusion.answer, /Ingredients to avoid/);
});
