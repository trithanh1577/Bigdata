import { createClient } from "./api.js";
import { hasMinutes, parseExclusions, safeUrl, timeLabel } from "./domain.js";

const $ = id => document.getElementById(id);
function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "") node.textContent = text;
  return node;
}
function button(text, className, action) {
  const node = element("button", className, text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}
function externalLink(text, url) {
  const href = safeUrl(url);
  if (!href) return null;
  const link = element("a", "", text);
  link.href = href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}
function appendLink(parent, text, url) {
  const link = externalLink(text, url);
  if (link) parent.append(link);
}

let client;
let applied = {};
let page = 1;
let searchVersion = 0;
let detailVersion = 0;
let chatVersion = 0;
let history = [];
let sessionId = null;
let previousIds = [];
let chatBusy = false;

function readFilters() {
  return {
    q: $("search").value.trim(), country: $("country").value,
    category: $("category").value, max_minutes: $("max-minutes").value ? Number($("max-minutes").value) : null,
    difficulty: $("difficulty").value, exclude_ingredients: parseExclusions($("exclude").value),
    require_allergens: $("require-allergens").checked, sort: $("sort").value,
  };
}

function statePanel(title, message, retry) {
  const panel = element("div", "empty-state");
  panel.append(element("h3", "", title), element("p", "", message));
  if (retry) panel.append(button("Try again", "secondary-button", retry));
  return panel;
}

function renderChips() {
  const values = [applied.q && `Search: ${applied.q}`, applied.country, applied.category,
    applied.max_minutes && `Up to ${applied.max_minutes} min`, applied.difficulty,
    ...(applied.exclude_ingredients ?? []).map(value => `Avoid: ${value}`),
    applied.require_allergens && "Allergen declarations available"].filter(Boolean);
  $("active-filters").replaceChildren(...values.map(value => element("span", "filter-chip", value)));
}

function recipeVisual(recipe, index) {
  const visual = element("div", "recipe-visual");
  const palette = ["#e2e8d5", "#efe0c7", "#e1e6d9", "#e7d9bf", "#ede3d5", "#dce5d8"];
  visual.style.setProperty("--card-bg", palette[index % palette.length]);
  const placeholder = () => {
    visual.replaceChildren(element("div", "mini-bowl"), element("span", "illustration-label", "Illustration · not a dish photo"));
    visual.setAttribute("aria-label", "Decorative food illustration; not a photograph of this recipe");
    visual.setAttribute("role", "img");
  };
  const imageUrl = safeUrl(recipe.image_url);
  if (imageUrl) {
    const img = element("img");
    img.alt = recipe.title;
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("error", placeholder, { once: true });
    img.src = imageUrl;
    visual.append(img);
  } else placeholder();
  return visual;
}

function recipeCard(recipe, index) {
  const card = element("article", "recipe-card");
  card.append(recipeVisual(recipe, index));
  const body = element("div", "recipe-body");
  body.append(element("p", "recipe-country", recipe.country_or_region || "Region not supplied"), element("h3", "", recipe.title),
    element("p", "recipe-summary", recipe.description || "Open this recipe to explore its ingredients and method."));
  const meta = element("div", "recipe-meta");
  meta.append(element("span", "", `◷ ${timeLabel(recipe.total_minutes)}`), element("span", "", recipe.difficulty || "Difficulty not supplied"));
  body.append(meta, element("p", "recipe-source", `Source: ${recipe.source_name || "Not supplied"}`), button("View recipe", "recipe-link", () => openRecipe(recipe.record_id)));
  card.append(body);
  return card;
}

async function loadRecipes() {
  const version = ++searchVersion;
  renderChips();
  $("results-panel").setAttribute("aria-busy", "true");
  $("result-count").textContent = "Finding your next favorite…";
  $("pagination").hidden = true;
  $("results").replaceChildren(statePanel("A moment at the table…", "Loading recipe records."));
  try {
    const data = await client.search(applied, page);
    if (version !== searchVersion) return;
    page = data.page;
    $("result-count").textContent = `${data.total} ${data.total === 1 ? "recipe" : "recipes"} ${client.mode === "mock" ? "in the demo collection" : "found"}`;
    $("results").replaceChildren(...(data.items.length ? data.items.map(recipeCard) : [statePanel("A different kind of adventure?", "No recipes match all of these preferences. Try a broader search or reset the filters.")]));
    const pages = Math.max(1, Math.ceil(data.total / data.page_size));
    $("pagination").hidden = pages <= 1;
    $("page-label").textContent = `Page ${page} of ${pages}`;
    $("previous-page").disabled = page <= 1;
    $("next-page").disabled = page >= pages;
  } catch (error) {
    if (version !== searchVersion) return;
    $("result-count").textContent = "Collection unavailable";
    $("results").replaceChildren(statePanel("The collection couldn't load.", error.message, loadRecipes));
  } finally {
    if (version === searchVersion) $("results-panel").setAttribute("aria-busy", "false");
  }
}

async function loadFacets() {
  try {
    const facets = await client.facets();
    for (const [id, key, fallback] of [["country", "countries", "Anywhere in the world"], ["category", "categories", "All categories"], ["difficulty", "difficulties", "Any difficulty"]]) {
      const select = $(id);
      const current = select.value;
      const options = [new Option(fallback, ""), ...facets[key].map(value => new Option(value, value))];
      select.replaceChildren(...options);
      select.value = current;
    }
  } catch (error) {
    const warning = element("div", "filter-note", `Filter options unavailable. ${error.message} `);
    warning.id = "facet-error";
    warning.append(button("Retry filter options", "text-button", () => { warning.remove(); loadFacets(); }));
    $("filter-form").prepend(warning);
  }
}

function applyFilters(event) {
  event?.preventDefault();
  applied = readFilters();
  page = 1;
  loadRecipes();
}

function detailSection(title, lines) {
  const section = element("section", "detail-extra");
  section.append(element("h3", "", title));
  for (const line of lines) section.append(element("p", "", line));
  return section;
}

function readableDate(value) {
  if (!value) return "Not supplied";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not supplied" : date.toLocaleString("en-GB", { timeZoneName: "short" });
}

function renderRecipe(recipe) {
  const root = document.createDocumentFragment();
  const header = element("div", "detail-header");
  header.append(element("p", "recipe-country", recipe.country_or_region || "Region not supplied"));
  const title = element("h2", "", recipe.title);
  title.id = "recipe-dialog-title";
  header.append(title, element("p", "", recipe.description || "Description not supplied."));
  if (recipe.original_title && recipe.original_title !== recipe.title) header.append(element("p", "", `Original title: ${recipe.original_title}`));
  root.append(header);
  if (client.mode === "mock") root.append(element("p", "filter-note", "Synthetic classroom example. This is not a crawled source recipe."));
  const imageUrl = safeUrl(recipe.image_url);
  if (imageUrl) {
    const image = element("img", "detail-image"); image.alt = recipe.title; image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => image.remove(), { once: true }); image.src = imageUrl; root.append(image);
  }
  const badges = element("div", "detail-badges");
  const values = [timeLabel(recipe.total_minutes), recipe.difficulty || "Difficulty not supplied", recipe.servings ? `Servings: ${recipe.servings}` : "Servings not supplied", ...recipe.categories];
  if (hasMinutes(recipe.prep_minutes)) values.push(`Prep: ${recipe.prep_minutes} min`);
  if (hasMinutes(recipe.cook_minutes)) values.push(`Cook: ${recipe.cook_minutes} min`);
  badges.append(...values.map(value => element("span", "", value)));
  root.append(badges);
  const layout = element("div", "detail-layout");
  const ingredients = element("section"); ingredients.append(element("h3", "", "Ingredients"));
  const list = element("ul", "ingredient-list");
  list.append(...recipe.ingredients.map(item => element("li", "", item.original_text || [item.quantity, item.unit, item.name, item.notes].filter(Boolean).join(" "))));
  ingredients.append(list);
  if (!recipe.ingredients.length) ingredients.append(element("p", "", "Ingredients not supplied."));
  const method = element("section"); method.append(element("h3", "", "Let's make it"));
  const steps = element("ol", "instruction-list"); steps.append(...recipe.instructions.map(step => element("li", "", step))); method.append(steps);
  if (!recipe.instructions.length) method.append(element("p", "", "Instructions not supplied."));
  layout.append(ingredients, method); root.append(layout);
  root.append(detailSection("Allergens & dietary information", [recipe.allergens.length ? `Source-declared allergens: ${recipe.allergens.join(", ")}. This list may be incomplete.` : "No source-declared allergen information is available. Allergen status is unknown.", "Text filters cannot verify dietary suitability or cross-contact risk."]));
  if (recipe.nutrition && Object.keys(recipe.nutrition).length) {
    root.append(detailSection("Source-declared nutrition", Object.entries(recipe.nutrition).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`)));
  } else root.append(detailSection("Nutrition", ["Not supplied by the source."]));
  if (recipe.tools.length) root.append(detailSection("Tools", [recipe.tools.join(", ")]));
  if (recipe.tips.length) root.append(detailSection("Source tips", recipe.tips));
  // Preserve the supplied substitution fields; do not assume provider key names.
  root.append(detailSection("Source-declared substitutions", recipe.substitutions.length ? recipe.substitutions.map(item => Object.entries(item).map(([key, value]) => `${key}: ${value}`).join("; ")) : ["No substitutions supplied. The companion will not invent replacements."]));
  const source = element("section", "source-box");
  source.append(element("h3", "", "Follow the source"), element("p", "", `Provider: ${recipe.source_name || "Not supplied"}`),
    element("p", "", recipe.attribution || "Attribution not supplied."), element("p", "", `License / terms: ${recipe.source_license || "Not supplied"}`),
    element("p", "", `Collected: ${readableDate(recipe.collected_at)} · Source updated: ${readableDate(recipe.source_updated_at)}`),
    element("p", "", `Record: ${recipe.record_id} · Provider ID: ${recipe.source_record_id || "Not supplied"}`));
  const links = element("div", "source-links");
  appendLink(links, "Provider record ↗", recipe.source_url); appendLink(links, "Original recipe ↗", recipe.original_recipe_url); appendLink(links, "License / terms ↗", recipe.source_terms_url);
  if (!links.children.length) links.append(element("p", "", "No external source links supplied."));
  source.append(links); root.append(source);
  const actions = element("div", "detail-actions");
  actions.append(button("Ask about this recipe →", "primary-button", () => {
    closeRecipe();
    $("assistant").scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    $("chat-input").value = `What are the ingredients in ${recipe.title}?`;
    $("chat-input").focus({ preventScroll: true });
  }));
  root.append(actions);
  return root;
}

async function openRecipe(id) {
  const version = ++detailVersion;
  const loading = statePanel("Loading recipe…", "Fetching the full recipe and source details.");
  loading.querySelector("h3").id = "recipe-dialog-title";
  $("recipe-detail").replaceChildren(loading);
  if (!$("recipe-dialog").open) $("recipe-dialog").showModal();
  try {
    const recipe = await client.recipe(id);
    if (version !== detailVersion || !$("recipe-dialog").open) return;
    $("recipe-detail").replaceChildren(renderRecipe(recipe));
    $("recipe-dialog").scrollTop = 0;
  } catch (error) {
    if (version !== detailVersion || !$("recipe-dialog").open) return;
    const panel = statePanel("Recipe unavailable", error.message, () => openRecipe(id));
    panel.querySelector("h3").id = "recipe-dialog-title";
    $("recipe-detail").replaceChildren(panel);
  }
}
function closeRecipe() { detailVersion++; $("recipe-dialog").close(); }

function appendMessage(role, text, citations = [], isError = false, showCitationStatus = false) {
  const message = element("div", `message message-${role}${isError ? " message-error" : ""}`);
  message.append(element("p", "", text));
  if (citations.length) {
    const refs = element("div", "citations");
    citations.forEach((item, index) => {
      refs.append(button(`[${index + 1}] ${item.title}`, "citation-button", () => openRecipe(item.record_id)));
      const link = externalLink(`${item.source_name || "Source"} ↗`, item.source_url);
      if (link) { link.className = "citation-source"; refs.append(link); }
    });
    message.append(refs);
  } else if (showCitationStatus && client.mode === "api") {
    message.append(element("p", "field-help", "No recipe citations supplied for this response."));
  }
  $("chat-messages").append(message);
  // Limit rendered history as well as the request context; preferences stay in memory only.
  while ($("chat-messages").children.length > 40) $("chat-messages").firstElementChild.remove();
  $("chat-messages").scrollTop = $("chat-messages").scrollHeight;
}

function setChatBusy(value) {
  chatBusy = value;
  $("send-chat").disabled = value;
  $("chat-input").disabled = value;
  $("chat-suggestions").querySelectorAll("button").forEach(node => { node.disabled = value; });
  $("chat-status").textContent = value ? "Looking through the recipe records…" : "";
}

function resetChat() {
  chatVersion++;
  history = []; sessionId = null; previousIds = [];
  setChatBusy(false);
  $("chat-messages").replaceChildren();
  $("chat-input").value = "";
  appendMessage("assistant", client.mode === "mock" ? "Hello, curious cook. I can help you explore this synthetic demo collection. Ask for a dish, an ingredient, or a region; every recipe answer links to its demo records." : "Hello, curious cook. Ask about a dish, ingredient, or region. I will display the backend's answer with the recipe records it cites. Missing source data stays unknown.");
}

async function sendQuestion(question) {
  if (chatBusy || !question.trim()) return;
  const message = question.trim().slice(0, 1000);
  const version = ++chatVersion;
  appendMessage("user", message);
  $("chat-input").value = "";
  setChatBusy(true);
  try {
    const response = await client.chat({ message, filters: applied, session_id: sessionId, history, previousIds });
    if (version !== chatVersion) return;
    appendMessage("assistant", response.answer, response.citations, false, true);
    sessionId = response.session_id;
    previousIds = response.citations.map(item => item.record_id);
    history.push({ role: "user", content: message }, { role: "assistant", content: response.answer });
    history = history.slice(-12);
  } catch (error) {
    if (version !== chatVersion) return;
    appendMessage("assistant", error.message, [], true);
    $("chat-input").value = message;
  } finally {
    if (version === chatVersion) { setChatBusy(false); $("chat-input").focus({ preventScroll: true }); }
  }
}

function configureMode() {
  if (client.mode === "api") {
    $("mode-badge").textContent = "Backend API mode";
    $("data-banner").querySelector("p").textContent = "Connected mode: recipe records and answers come from your configured backend. Source links and missing data are shown on each record. Ingredient filters cannot guarantee dietary safety.";
    $("assistant-mode-note").textContent = "Answers are supplied by the configured backend. Follow the citations to inspect the records behind each answer.";
  }
  $("about-mode").textContent = client.mode === "mock" ? "Demo mode uses eight synthetic classroom recipe records and a deterministic local lookup. It makes no network requests to an API or AI model. Dish illustrations are decorative, not photos of the recipes." : "API mode calls Person 3's configured backend for search, detail, filter options, and conversation. If the backend is unavailable, the interface shows an error and lets you retry. It does not silently replace live records with demo data.";
}

function bindEvents() {
  $("search-form").addEventListener("submit", applyFilters);
  $("filter-form").addEventListener("submit", applyFilters);
  $("sort").addEventListener("change", () => { applied = { ...applied, sort: $("sort").value }; page = 1; loadRecipes(); });
  $("reset-filters").addEventListener("click", () => { $("filter-form").reset(); $("search-form").reset(); $("sort").value = "title"; applyFilters(); });
  $("previous-page").addEventListener("click", () => { if (page > 1) { page--; loadRecipes(); } });
  $("next-page").addEventListener("click", () => { page++; loadRecipes(); });
  $("close-recipe").addEventListener("click", closeRecipe);
  $("recipe-dialog").addEventListener("cancel", () => { detailVersion++; });
  $("close-about").addEventListener("click", () => $("about-dialog").close());
  for (const id of ["about-button", "data-info"]) $(id).addEventListener("click", () => $("about-dialog").showModal());
  for (const id of ["recipe-dialog", "about-dialog"]) {
    $(id).addEventListener("click", event => {
      const rect = $(id).getBoundingClientRect();
      if (event.target === $(id) && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) $(id).close();
    });
  }
  $("chat-form").addEventListener("submit", event => { event.preventDefault(); sendQuestion($("chat-input").value); });
  $("chat-suggestions").addEventListener("click", event => { const node = event.target.closest("[data-question]"); if (node) sendQuestion(node.dataset.question); });
  $("clear-chat").addEventListener("click", resetChat);
}

async function start() {
  try {
    client = createClient(window.RECIPEHUB_CONFIG);
    configureMode();
    bindEvents();
    resetChat();
    applied = readFilters();
    await Promise.allSettled([loadFacets(), loadRecipes()]);
  } catch (error) {
    $("mode-badge").textContent = "Configuration error";
    $("result-count").textContent = "Setup required";
    $("results").replaceChildren(statePanel("Check the website configuration.", error.message));
    $("chat-status").textContent = error.message;
    document.querySelectorAll("form input, form button, form select").forEach(node => { node.disabled = true; });
  }
}
start();
