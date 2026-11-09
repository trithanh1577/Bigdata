export const PAGE_SIZE = 6;

export function normalized(value) {
  return String(value ?? "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

export function parseExclusions(value) {
  return [...new Set(String(value ?? "").split(",").map(normalized).filter(Boolean))];
}

export function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : "";
  } catch { return ""; }
}

export function hasMinutes(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

export function timeLabel(value) {
  return hasMinutes(value) ? `${value} min` : "Time not supplied";
}

export function matchesPreferences(recipe, filters = {}) {
  if (filters.country && recipe.country_or_region !== filters.country) return false;
  if (filters.category && !recipe.categories.includes(filters.category)) return false;
  if (filters.difficulty && recipe.difficulty !== filters.difficulty) return false;
  if (filters.max_minutes && (!hasMinutes(recipe.total_minutes) || recipe.total_minutes > Number(filters.max_minutes))) return false;
  if (filters.require_allergens && recipe.allergens.length === 0) return false;
  const text = normalized([...recipe.ingredients.map(item => `${item.name} ${item.original_text}`), ...recipe.allergens].join(" "));
  return !(filters.exclude_ingredients ?? []).some(term => text.includes(normalized(term)));
}

export function filterRecipes(recipes, filters = {}) {
  const query = normalized(filters.q);
  const words = query.split(/\s+/).filter(Boolean);
  const result = recipes.filter(recipe => {
    const text = normalized([recipe.title, recipe.description, recipe.country_or_region, ...recipe.categories, ...recipe.ingredients.map(item => item.name)].join(" "));
    return words.every(word => text.includes(word)) && matchesPreferences(recipe, filters);
  });
  return result.sort((a, b) => {
    if (filters.sort === "time") {
      const delta = (hasMinutes(a.total_minutes) ? a.total_minutes : Infinity) - (hasMinutes(b.total_minutes) ? b.total_minutes : Infinity);
      if (delta && !Number.isNaN(delta)) return delta;
    }
    return a.title.localeCompare(b.title, "en") || a.record_id.localeCompare(b.record_id);
  });
}

export function paginate(items, page = 1, pageSize = PAGE_SIZE) {
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const current = Math.max(1, Math.min(totalPages, Math.trunc(Number(page)) || 1));
  return { items: items.slice((current - 1) * pageSize, current * pageSize), total: items.length, page: current, page_size: pageSize };
}

export function buildFacets(recipes) {
  const values = key => [...new Set(recipes.flatMap(recipe => recipe[key]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "en"));
  return { countries: values("country_or_region"), categories: values("categories"), difficulties: values("difficulty") };
}

function citation(recipe) {
  return { record_id: recipe.record_id, title: recipe.title, source_name: recipe.source_name, source_url: recipe.source_url };
}

// Deterministic mock retrieval, never a substitute for Person 3's answer service.
export function mockAnswer(recipes, message, filters = {}, previousIds = []) {
  const question = normalized(message);
  const eligible = filterRecipes(recipes, { ...filters, q: "" });
  const direct = eligible.find(recipe => question.includes(normalized(recipe.title)));
  const followUp = /\b(it|its|that|those|them|this|these)\b/.test(question) || /^(what are the ingredients|how do i (make|cook)|show (me )?(the )?steps)/.test(question);
  const ingredientQuestion = /ingredient|what goes into/.test(question);
  const methodQuestion = /step|instruction|how (do|to)|method/.test(question);
  const contextual = direct ? [direct] : followUp ? eligible.filter(recipe => previousIds.includes(recipe.record_id)) : [];
  if (contextual.length && (ingredientQuestion || methodQuestion)) {
    const selected = contextual[0];
    const text = methodQuestion ? selected.instructions.map((step, i) => `${i + 1}. ${step}`).join("\n") : selected.ingredients.map(item => `• ${item.original_text}`).join("\n");
    return { answer: `${selected.title}\n\n${text}\n\nSynthetic demo record. Allergen data may be incomplete.`, citations: [citation(selected)], session_id: "local-demo" };
  }
  if (/allerg|safe|nutrition|calori|substitut|instead|replace|protein|gluten.free|vegan|vegetarian|halal|kosher|dairy.free|nut.free/.test(question)) {
    return { answer: "The demo cannot verify dietary suitability, medical safety, nutrition, or ingredient substitutions. Use Ingredients to avoid to exclude text matches, then check the full source record. Missing allergen information means unknown. The demo does not invent missing facts.", citations: [], session_id: "local-demo" };
  }
  if (/\b(without|avoid|exclude|excluding|no)\b/.test(question)) {
    return { answer: "For ingredient exclusions, enter comma-separated terms in Ingredients to avoid above and apply preferences first. The demo does not interpret exclusion requests in free text. Applied exclusions will also constrain the next recipe lookup.", citations: [], session_id: "local-demo" };
  }
  const maxTime = question.match(/(?:under|within|in|less than|up to)\s+(\d+)\s*(?:min|minute)/);
  let candidates = maxTime ? eligible.filter(recipe => hasMinutes(recipe.total_minutes) && recipe.total_minutes <= Number(maxTime[1])) : eligible;
  const requestedRegion = buildFacets(recipes).countries.find(region => question.includes(normalized(region)));
  const requestedIngredients = [...new Set(recipes.flatMap(recipe => recipe.ingredients.map(item => normalized(item.name))))].filter(name => question.includes(name));
  if (direct) candidates = candidates.filter(recipe => recipe.record_id === direct.record_id);
  if (requestedRegion) candidates = candidates.filter(recipe => recipe.country_or_region === requestedRegion);
  if (requestedIngredients.length) candidates = candidates.filter(recipe => requestedIngredients.every(name => recipe.ingredients.some(item => normalized(item.name).includes(name))));
  const isDiscovery = /\b(recipe|dish|find|suggest|show|cook|meal|recommend|something)\b/.test(question) || requestedRegion || requestedIngredients.length || maxTime || direct;
  if (!isDiscovery || ((ingredientQuestion || methodQuestion) && !contextual.length && !direct)) {
    return { answer: "I can look up the demo recipes by dish name, region, ingredient, or cooking time. Try “Find recipes with tomato” or open a recipe and ask about its ingredients or steps. I do not have enough recipe context for that question yet.", citations: [], session_id: "local-demo" };
  }
  const selected = candidates.slice(0, 3);
  if (!selected.length) return { answer: "I couldn't find a demo recipe matching that question and your applied preferences. Try a different ingredient or adjust the filters above.", citations: [], session_id: "local-demo" };
  return {
    answer: `Here ${selected.length === 1 ? "is a demo recipe" : "are a few demo recipes"} matching your question and applied preferences:\n\n${selected.map(recipe => `• ${recipe.title} — ${recipe.country_or_region}; ${timeLabel(recipe.total_minutes)}.`).join("\n")}\n\nOpen a cited record for the full recipe, or ask “What are its ingredients?” about the first result. These are synthetic examples.`,
    citations: selected.map(citation), session_id: "local-demo",
  };
}
