// Run explicitly against `python -m recipehub.cli serve`, never during unit tests.
import test from "node:test";
import assert from "node:assert/strict";
import { createClient } from "../api.js";

const base = process.env.RECIPEHUB_TEST_API_URL || "http://127.0.0.1:8000/api/v1";
const client = createClient({ mode: "api", apiBaseUrl: base });

test("real HTTP backend serves source records through the frontend adapter", async () => {
  const facets = await client.facets();
  assert.ok(facets.countries.length > 0, "Collect, normalize, and index recipes first.");
  const page = await client.search({ country: facets.countries[0] });
  assert.ok(page.total > 0);
  assert.ok(page.items.every(item => item.country_or_region === facets.countries[0]));
  const detail = await client.recipe(page.items[0].record_id);
  assert.match(detail.source_url, /^https?:\/\//);
  assert.ok(detail.ingredients.length > 0 && detail.instructions.length > 0);
  assert.ok(!detail.metadata.synthetic, "The integration dataset must contain crawled records.");
  await assert.rejects(() => client.recipe("missing-integration-record"), /HTTP 404/);
});

test("real chat resolves named source records and follows server session context", async () => {
  const first = (await client.search()).items[0];
  assert.ok(first, "Collect, normalize, and index recipes first.");
  const response = await client.chat({ message: `What are the ingredients in ${first.title}?` });
  assert.equal(response.citations[0].record_id, first.record_id);
  assert.ok(response.answer.includes(first.ingredients[0].original_text));
  const next = await client.chat({ message: "How do I cook it?", session_id: response.session_id });
  assert.equal(next.citations[0].record_id, first.record_id);
  assert.ok(next.answer.includes(first.instructions[0]));
});
