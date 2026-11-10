import test from "node:test";
import assert from "node:assert/strict";
import { createClient } from "../api.js";
import { MOCK_RECIPES } from "../mock-data.js";

const config = { mode: "api", apiBaseUrl: "http://localhost:8000/api/v1/" };
const jsonResponse = value => ({ ok: true, json: async () => value });

test("mock client performs the complete flow without fetching", async () => {
  const client = createClient({ mode: "mock" }, () => { throw new Error("Unexpected network request"); });
  assert.equal((await client.facets()).countries.length, 5);
  const result = await client.search({ country: "Japan" });
  assert.equal(result.total, 2);
  assert.equal((await client.recipe(result.items[0].record_id)).title, result.items[0].title);
  const answer = await client.chat({ message: "Find recipes from Japan" });
  assert.equal(answer.citations.length, 2);
  await assert.rejects(() => client.recipe("missing"), /no longer available/);
});

test("live search encodes repeated exclusions, preferences, sort, and page", async () => {
  let called;
  const client = createClient(config, async (url, options) => {
    called = { url: new URL(url), options };
    return jsonResponse({ items: [MOCK_RECIPES[0]], total: 1, page: 2, page_size: 6 });
  });
  await client.search({ q: "rice & beans", country: "Japan", max_minutes: 30, exclude_ingredients: ["soy", "peanut"], require_allergens: true, sort: "time" }, 2);
  assert.equal(called.url.pathname, "/api/v1/recipes");
  assert.equal(called.url.searchParams.get("q"), "rice & beans");
  assert.deepEqual(called.url.searchParams.getAll("exclude_ingredients"), ["soy", "peanut"]);
  assert.equal(called.url.searchParams.get("require_allergens"), "true");
  assert.equal(called.url.searchParams.get("page"), "2");
  assert.equal(called.options.headers.Accept, "application/json");
});

test("record IDs cannot alter the request path", async () => {
  let called;
  const client = createClient(config, async url => { called = url; return jsonResponse(MOCK_RECIPES[0]); });
  await client.recipe("source/id?x=1");
  assert.equal(called, "http://localhost:8000/api/v1/recipes/source%2Fid%3Fx%3D1");
});

test("chat sends the session and bounded history with current preferences", async () => {
  let body;
  const client = createClient(config, async (_url, options) => {
    body = JSON.parse(options.body);
    return jsonResponse({ answer: "Grounded answer", session_id: "session-1", citations: [{ record_id: "record-1", title: "Recipe" }] });
  });
  const history = Array.from({ length: 20 }, (_, i) => ({ role: i % 2 ? "assistant" : "user", content: String(i) }));
  const response = await client.chat({ message: "What are its ingredients?", session_id: "session-1", history, filters: { exclude_ingredients: ["peanut"] } });
  assert.equal(body.session_id, response.session_id);
  assert.equal(body.history.length, 12);
  assert.deepEqual(body.filters.exclude_ingredients, ["peanut"]);
});

test("HTTP, network, invalid JSON, and malformed payload errors never fall back to mocks", async () => {
  const broken = createClient(config, async () => ({ ok: false, status: 503 }));
  await assert.rejects(() => broken.search(), /HTTP 503/);
  const offline = createClient(config, async () => { throw new TypeError("Failed to fetch"); });
  await assert.rejects(() => offline.facets(), /Cannot reach/);
  const invalidJSON = createClient(config, async () => ({ ok: true, json: async () => { throw new SyntaxError(); } }));
  await assert.rejects(() => invalidJSON.search(), /valid JSON/);
  const badShape = createClient(config, async () => jsonResponse({}));
  await assert.rejects(() => badShape.search(), /invalid search/);
  await assert.rejects(() => badShape.recipe("x"), /invalid recipe/);
  await assert.rejects(() => badShape.chat({ message: "hi" }), /invalid conversation/);
  await assert.rejects(() => badShape.facets(), /invalid filter/);
});

test("request timeout aborts fetch and reports a retryable error", async () => {
  const client = createClient({ ...config, timeoutMs: 5 }, (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  }));
  await assert.rejects(() => client.search(), /too long/);
});

test("invalid client configuration fails explicitly", () => {
  assert.throws(() => createClient({ mode: "unknown" }), /mode must be/);
  for (const apiBaseUrl of ["javascript:alert(1)", "", "https://user:pass@example.org", "https://example.org?x=1"]) assert.throws(() => createClient({ mode: "api", apiBaseUrl }), /apiBaseUrl/);
});

test("HTTP errors expose their status so the chat can recover an expired session", async () => {
  const client = createClient(config, async () => ({ ok: false, status: 404, json: async () => ({}) }));
  await assert.rejects(() => client.chat({ message: "hi", session_id: "x".repeat(43) }), error => error.status === 404);
});
