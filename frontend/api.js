import { MOCK_RECIPES } from "./mock-data.js";
import { buildFacets, filterRecipes, mockAnswer, paginate, PAGE_SIZE } from "./domain.js";
import { currentLanguage, t } from "./i18n.js";

const arrays = ["ingredients", "instructions", "categories", "allergens", "tips", "substitutions", "tools"];

function checkRecipe(value, language) {
  if (!value || typeof value.record_id !== "string" || !value.record_id || typeof value.title !== "string" || !value.title || arrays.some(key => !Array.isArray(value[key]))) {
    throw new Error(t("apiInvalidRecipe", {}, language));
  }
  return value;
}

export function createClient(config = {}, fetchImpl = globalThis.fetch, languageGetter = currentLanguage) {
  const getLanguage = () => languageGetter?.() === "vi" ? "vi" : "en";
  const tr = (key, values = {}) => t(key, values, getLanguage());
  const mode = config.mode ?? "mock";
  if (!["mock", "api"].includes(mode)) throw new Error(tr("apiInvalidMode"));
  if (mode === "api") {
    try {
      const base = new URL(config.apiBaseUrl);
      if (!["http:", "https:"].includes(base.protocol) || base.search || base.hash || base.username || base.password) throw new Error();
    } catch { throw new Error(tr("apiInvalidConfig")); }
  }
  const baseUrl = String(config.apiBaseUrl ?? "").replace(/\/+$/, "");
  const timeout = config.timeoutMs ?? 120000;

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetchImpl(`${baseUrl}${path}`, { ...options, signal: controller.signal, headers: { Accept: "application/json", "Accept-Language": getLanguage(), ...(options.body ? { "Content-Type": "application/json" } : {}) } });
      if (!response.ok) throw Object.assign(new Error(tr("apiHttp", { status: response.status })), { status: response.status });
      return await response.json();
    } catch (error) {
      if (error.name === "AbortError") throw new Error(tr("apiTimeout"));
      if (error instanceof TypeError) throw new Error(tr("apiNetwork"));
      if (error instanceof SyntaxError) throw new Error(tr("apiJson"));
      throw error;
    } finally { clearTimeout(timer); }
  }

  return {
    mode,
    async health() {
      if (mode === "mock") return { status: "ok", recipes: MOCK_RECIPES.length, language_model_available: false, web_discovery_available: false };
      const value = await request("/health");
      if (value?.status !== "ok" || typeof value.language_model_available !== "boolean" || typeof value.web_discovery_available !== "boolean") throw new Error(tr("apiInvalidHealth"));
      return value;
    },
    async facets() {
      if (mode === "mock") return buildFacets(MOCK_RECIPES);
      const value = await request("/facets");
      if (!["countries", "categories", "difficulties"].every(key => Array.isArray(value?.[key]) && value[key].every(item => typeof item === "string"))) throw new Error(tr("apiInvalidFacets"));
      return value;
    },
    async search(filters = {}, page = 1) {
      if (mode === "mock") return paginate(filterRecipes(MOCK_RECIPES, { ...filters, locale: getLanguage() }), page);
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), sort: filters.sort || "title" });
      for (const key of ["q", "country", "category", "max_minutes", "difficulty"]) if (filters[key]) params.set(key, String(filters[key]));
      for (const value of filters.exclude_ingredients ?? []) params.append("exclude_ingredients", value);
      if (filters.require_allergens) params.set("require_allergens", "true");
      const value = await request(`/recipes?${params}`);
      if (!value || !Array.isArray(value.items) || !Number.isInteger(value.total) || value.total < 0 || !Number.isInteger(value.page) || value.page < 1 || !Number.isInteger(value.page_size) || value.page_size < 1) throw new Error(tr("apiInvalidSearch"));
      value.items.forEach(item => checkRecipe(item, getLanguage()));
      return value;
    },
    async recipe(id) {
      if (mode === "mock") {
        const recipe = MOCK_RECIPES.find(item => item.record_id === id);
        if (!recipe) throw new Error(tr("apiMissingRecipe"));
        return recipe;
      }
      return checkRecipe(await request(`/recipes/${encodeURIComponent(id)}`), getLanguage());
    },
    async chat({ message, filters = {}, session_id = null, history = [], previousIds = [], language = getLanguage() }) {
      if (mode === "mock") return mockAnswer(MOCK_RECIPES, message, filters, previousIds, language);
      const value = await request("/chat", { method: "POST", body: JSON.stringify({ message, filters, session_id, history: history.slice(-12), language }) });
      if (!value || typeof value.answer !== "string" || !Array.isArray(value.citations) || typeof value.session_id !== "string" || value.citations.some(item => typeof item.record_id !== "string" || typeof item.title !== "string")) throw new Error(tr("apiInvalidChat"));
      return value;
    },
  };
}
