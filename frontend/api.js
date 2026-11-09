import { MOCK_RECIPES } from "./mock-data.js";
import { buildFacets, filterRecipes, mockAnswer, paginate, PAGE_SIZE } from "./domain.js";

const arrays = ["ingredients", "instructions", "categories", "allergens", "tips", "substitutions", "tools"];

function checkRecipe(value) {
  if (!value || typeof value.record_id !== "string" || !value.record_id || typeof value.title !== "string" || !value.title || arrays.some(key => !Array.isArray(value[key]))) {
    throw new Error("The API returned an invalid recipe record. Check the frontend API contract.");
  }
  return value;
}

export function createClient(config = {}, fetchImpl = globalThis.fetch) {
  const mode = config.mode ?? "mock";
  if (!["mock", "api"].includes(mode)) throw new Error('Configuration mode must be "mock" or "api".');
  if (mode === "api") {
    try {
      const base = new URL(config.apiBaseUrl);
      if (!["http:", "https:"].includes(base.protocol) || base.search || base.hash || base.username || base.password) throw new Error();
    } catch { throw new Error("Configure apiBaseUrl as an HTTP(S) URL without credentials, a query, or a fragment."); }
  }
  const baseUrl = String(config.apiBaseUrl ?? "").replace(/\/+$/, "");
  const timeout = config.timeoutMs ?? 15000;

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetchImpl(`${baseUrl}${path}`, { ...options, signal: controller.signal, headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}) } });
      if (!response.ok) throw new Error(`The recipe service returned HTTP ${response.status}. Please try again.`);
      return await response.json();
    } catch (error) {
      if (error.name === "AbortError") throw new Error("The recipe service took too long to respond. Please try again.");
      if (error instanceof TypeError) throw new Error("Cannot reach the recipe service. Check its address, availability, and CORS configuration.");
      if (error instanceof SyntaxError) throw new Error("The recipe service did not return valid JSON.");
      throw error;
    } finally { clearTimeout(timer); }
  }

  return {
    mode,
    async facets() {
      if (mode === "mock") return buildFacets(MOCK_RECIPES);
      const value = await request("/facets");
      if (!["countries", "categories", "difficulties"].every(key => Array.isArray(value?.[key]) && value[key].every(item => typeof item === "string"))) throw new Error("The API returned invalid filter options.");
      return value;
    },
    async search(filters = {}, page = 1) {
      if (mode === "mock") return paginate(filterRecipes(MOCK_RECIPES, filters), page);
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), sort: filters.sort || "title" });
      for (const key of ["q", "country", "category", "max_minutes", "difficulty"]) if (filters[key]) params.set(key, String(filters[key]));
      for (const value of filters.exclude_ingredients ?? []) params.append("exclude_ingredients", value);
      if (filters.require_allergens) params.set("require_allergens", "true");
      const value = await request(`/recipes?${params}`);
      if (!value || !Array.isArray(value.items) || !Number.isInteger(value.total) || value.total < 0 || !Number.isInteger(value.page) || value.page < 1 || !Number.isInteger(value.page_size) || value.page_size < 1) throw new Error("The API returned an invalid search response.");
      value.items.forEach(checkRecipe);
      return value;
    },
    async recipe(id) {
      if (mode === "mock") {
        const recipe = MOCK_RECIPES.find(item => item.record_id === id);
        if (!recipe) throw new Error("That recipe is no longer available.");
        return recipe;
      }
      return checkRecipe(await request(`/recipes/${encodeURIComponent(id)}`));
    },
    async chat({ message, filters = {}, session_id = null, history = [], previousIds = [] }) {
      if (mode === "mock") return mockAnswer(MOCK_RECIPES, message, filters, previousIds);
      const value = await request("/chat", { method: "POST", body: JSON.stringify({ message, filters, session_id, history: history.slice(-12) }) });
      if (!value || typeof value.answer !== "string" || !Array.isArray(value.citations) || typeof value.session_id !== "string" || value.citations.some(item => typeof item.record_id !== "string" || typeof item.title !== "string")) throw new Error("The API returned an invalid conversation response.");
      return value;
    },
  };
}
