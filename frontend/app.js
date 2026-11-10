import { createClient } from "./api.js";
import { hasMinutes, parseExclusions, safeUrl, timeLabel } from "./domain.js";
import { applyStaticTranslations, currentLanguage, initializeLanguage, setLanguage, t, valueLabel } from "./i18n.js";

const $ = id => document.getElementById(id);
let language = initializeLanguage();
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
let openRecipeId = null;
let startupError = null;
let languageModelAvailable = false;
let webDiscoveryAvailable = false;

function applyLanguage() {
  language = currentLanguage();
  applyStaticTranslations();
  if (!client) {
    if (startupError) {
      try { createClient(window.RECIPEHUB_CONFIG, globalThis.fetch, currentLanguage); }
      catch (error) { startupError = error; }
      $("mode-badge").textContent = t("modeError");
      $("result-count").textContent = t("setupRequired");
      $("results").replaceChildren(statePanel(t("configCheck"), startupError.message));
      $("chat-status").textContent = startupError.message;
    }
    return;
  }
  configureMode();
  renderChips();
  loadFacets();
  loadRecipes();
  if (openRecipeId && $("recipe-dialog").open) openRecipe(openRecipeId);
  else if (!history.length && !chatBusy && $("chat-messages").children.length === 1) resetChat();
}

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
  if (retry) panel.append(button(t("tryAgain"), "secondary-button", retry));
  return panel;
}

function renderChips() {
  const values = [applied.q && t("searchChip", { value: applied.q }), valueLabel(applied.country), valueLabel(applied.category),
    applied.max_minutes && t("timeChip", { value: applied.max_minutes }), valueLabel(applied.difficulty),
    ...(applied.exclude_ingredients ?? []).map(value => t("avoidChip", { value })),
    applied.require_allergens && t("allergensChip")].filter(Boolean);
  $("active-filters").replaceChildren(...values.map(value => element("span", "filter-chip", value)));
}

function recipeVisual(recipe, index) {
  const visual = element("div", "recipe-visual");
  const palette = ["#e2e8d5", "#efe0c7", "#e1e6d9", "#e7d9bf", "#ede3d5", "#dce5d8"];
  visual.style.setProperty("--card-bg", palette[index % palette.length]);
  const placeholder = () => {
    visual.replaceChildren(element("div", "mini-bowl"), element("span", "illustration-label", t("illustrationLabel")));
    visual.setAttribute("aria-label", t("illustrationAlt"));
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
  body.append(element("p", "recipe-country", valueLabel(recipe.country_or_region) || t("regionUnknown")), element("h3", "", recipe.title),
    element("p", "recipe-summary", recipe.description || t("recipeTeaser")));
  const meta = element("div", "recipe-meta");
  meta.append(element("span", "", `◷ ${timeLabel(recipe.total_minutes, language)}`), element("span", "", valueLabel(recipe.difficulty) || t("difficultyUnknown")));
  body.append(meta, element("p", "recipe-source", `${t("sourceLabel")}: ${recipe.source_name || t("sourceUnknown")}`), button(t("viewRecipe"), "recipe-link", () => openRecipe(recipe.record_id)));
  card.append(body);
  return card;
}

async function loadRecipes() {
  const version = ++searchVersion;
  renderChips();
  $("results-panel").setAttribute("aria-busy", "true");
  $("result-count").textContent = t("loadingFind");
  $("pagination").hidden = true;
  $("results").replaceChildren(statePanel(t("loadingTitle"), t("loadingBody")));
  try {
    const data = await client.search(applied, page);
    if (version !== searchVersion) return;
    page = data.page;
    $("result-count").textContent = `${data.total} ${t(data.total === 1 ? "recipeSingular" : "recipePlural")} ${client.mode === "mock" ? t("demoCollection") : t("found")}`;
    const resultNodes = data.items.length ? data.items.map(recipeCard) : [statePanel(t("emptyTitle"), t("emptyBody"))];
    if (language === "vi" && client.mode === "api" && data.content_translated !== true) {
      resultNodes.unshift(element("p", "translation-notice", t("translationNotice")));
    }
    $("results").replaceChildren(...resultNodes);
    const pages = Math.max(1, Math.ceil(data.total / data.page_size));
    $("pagination").hidden = pages <= 1;
    $("page-label").textContent = t("pageOf", { page, pages });
    $("previous-page").disabled = page <= 1;
    $("next-page").disabled = page >= pages;
  } catch (error) {
    if (version !== searchVersion) return;
    $("result-count").textContent = t("collectionUnavailable");
    $("results").replaceChildren(statePanel(t("collectionErrorTitle"), error.message, loadRecipes));
  } finally {
    if (version === searchVersion) $("results-panel").setAttribute("aria-busy", "false");
  }
}

async function loadFacets() {
  $("facet-error")?.remove(); // language switches reload facets; keep at most one warning
  try {
    const facets = await client.facets();
    for (const [id, key, fallbackKey] of [["country", "countries", "countryAny"], ["category", "categories", "categoryAll"], ["difficulty", "difficulties", "difficultyAny"]]) {
      const select = $(id);
      const current = select.value;
      const labels = facets.labels?.[key] ?? {};
      const label = value => (labels[value] && labels[value] !== value ? labels[value] : valueLabel(value));
      const options = [new Option(t(fallbackKey), ""), ...facets[key].map(value => new Option(label(value), value))];
      select.replaceChildren(...options);
      select.value = current;
    }
  } catch (error) {
    const warning = element("div", "filter-note", `${t("facetError")} ${error.message} `);
    warning.id = "facet-error";
    warning.append(button(t("retryFacets"), "text-button", () => { warning.remove(); loadFacets(); }));
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
  if (!value) return t("notSupplied");
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? t("notSupplied") : date.toLocaleString(language === "vi" ? "vi-VN" : "en-GB", { timeZoneName: "short" });
}

function renderRecipe(recipe) {
  const root = document.createDocumentFragment();
  if (language === "vi" && client.mode === "api" && recipe.content_translated !== true) {
    root.append(element("p", "translation-notice", t("translationNotice")));
  }
  const header = element("div", "detail-header");
  header.append(element("p", "recipe-country", valueLabel(recipe.country_or_region) || t("regionUnknown")));
  const title = element("h2", "", recipe.title);
  title.id = "recipe-dialog-title";
  header.append(title, element("p", "", recipe.description || t("descriptionUnknown")));
  // Keep the source-language title visible in English mode. In Vietnamese mode,
  // the localized title above already represents it, so avoid mixing languages.
  if (language !== "vi" && recipe.original_title && recipe.original_title !== recipe.title) {
    header.append(element("p", "", t("originalTitle", { value: recipe.original_title })));
  }
  root.append(header);
  if (client.mode === "mock") root.append(element("p", "filter-note", t("syntheticNote")));
  const imageUrl = safeUrl(recipe.image_url);
  if (imageUrl) {
    const image = element("img", "detail-image"); image.alt = recipe.title; image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => image.remove(), { once: true }); image.src = imageUrl; root.append(image);
  }
  const badges = element("div", "detail-badges");
  const values = [timeLabel(recipe.total_minutes, language), valueLabel(recipe.difficulty) || t("difficultyUnknown"), recipe.servings ? t("servings", { value: recipe.servings }) : t("servingsUnknown"), ...recipe.categories.map(item => valueLabel(item))];
  if (hasMinutes(recipe.prep_minutes)) values.push(t("prep", { value: recipe.prep_minutes }));
  if (hasMinutes(recipe.cook_minutes)) values.push(t("cook", { value: recipe.cook_minutes }));
  badges.append(...values.map(value => element("span", "", value)));
  root.append(badges);
  const layout = element("div", "detail-layout");
  const ingredients = element("section"); ingredients.append(element("h3", "", t("ingredients")));
  const list = element("ul", "ingredient-list");
  list.append(...recipe.ingredients.map(item => element("li", "", item.original_text || [item.quantity, item.unit, item.name, item.notes].filter(Boolean).join(" "))));
  ingredients.append(list);
  if (!recipe.ingredients.length) ingredients.append(element("p", "", t("ingredientsUnknown")));
  const method = element("section"); method.append(element("h3", "", t("makeIt")));
  const steps = element("ol", "instruction-list"); steps.append(...recipe.instructions.map(step => element("li", "", step))); method.append(steps);
  if (!recipe.instructions.length) method.append(element("p", "", t("instructionsUnknown")));
  layout.append(ingredients, method); root.append(layout);
  root.append(detailSection(t("allergensDiet"), [recipe.allergens.length ? `${t("sourceDeclaredAllergens", { value: recipe.allergens.join(", ") })} ${t("incomplete")}` : t("allergenUnknown"), t("crossContact")]));
  if (recipe.nutrition && Object.keys(recipe.nutrition).length) {
    root.append(detailSection(t("nutritionSource"), Object.entries(recipe.nutrition).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`)));
  } else root.append(detailSection(t("nutrition"), [t("nutritionUnknown")]));
  if (recipe.tools.length) root.append(detailSection(t("tools"), [recipe.tools.join(", ")]));
  if (recipe.tips.length) root.append(detailSection(t("tips"), recipe.tips));
  // Preserve the supplied substitution fields; do not assume provider key names.
  root.append(detailSection(t("substitutions"), recipe.substitutions.length ? recipe.substitutions.map(item => Object.entries(item).map(([key, value]) => `${key}: ${value}`).join("; ")) : [t("substitutionsUnknown")]));
  const source = element("section", "source-box");
  source.append(element("h3", "", t("followSource")), element("p", "", t("provider", { value: recipe.source_name || t("sourceUnknown") })),
    element("p", "", recipe.attribution || t("attributionUnknown")), element("p", "", t("licenseTerms", { value: recipe.source_license || t("notSupplied") })),
    element("p", "", `${t("collected", { value: readableDate(recipe.collected_at) })} · ${t("sourceUpdated", { value: readableDate(recipe.source_updated_at) })}`),
    element("p", "", `${t("record", { value: recipe.record_id })} · ${t("providerId", { value: recipe.source_record_id || t("notSupplied") })}`));
  const links = element("div", "source-links");
  appendLink(links, t("providerRecord"), recipe.source_url); appendLink(links, t("originalRecipe"), recipe.original_recipe_url); appendLink(links, t("licenseLink"), recipe.source_terms_url);
  if (!links.children.length) links.append(element("p", "", t("noExternalLinks")));
  source.append(links); root.append(source);
  const actions = element("div", "detail-actions");
  actions.append(button(t("askRecipe"), "primary-button", () => {
    closeRecipe();
    $("assistant").scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    $("chat-input").value = language === "vi" ? `Nguyên liệu của món ${recipe.title} là gì?` : `What are the ingredients in ${recipe.title}?`;
    $("chat-input").focus({ preventScroll: true });
  }));
  root.append(actions);
  return root;
}

async function openRecipe(id) {
  openRecipeId = id;
  const version = ++detailVersion;
  const loading = statePanel(t("loadingRecipe"), t("fetchingRecipe"));
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
    const panel = statePanel(t("recipeUnavailable"), error.message, () => openRecipe(id));
    panel.querySelector("h3").id = "recipe-dialog-title";
    $("recipe-detail").replaceChildren(panel);
  }
}
function closeRecipe() { detailVersion++; openRecipeId = null; $("recipe-dialog").close(); }

function appendMessage(role, text, citations = [], isError = false, showCitationStatus = false) {
  const message = element("div", `message message-${role}${isError ? " message-error" : ""}`);
  message.append(element("p", "", text));
  if (citations.length) {
    const refs = element("div", "citations");
    citations.forEach((item, index) => {
      refs.append(button(`[${index + 1}] ${item.title}`, "citation-button", () => openRecipe(item.record_id)));
      const link = externalLink(`${item.source_name || t("citationSource")} ↗`, item.source_url);
      if (link) { link.className = "citation-source"; refs.append(link); }
    });
    message.append(refs);
  } else if (showCitationStatus && client.mode === "api") {
    message.append(element("p", "field-help", t("noCitations")));
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
  $("chat-status").textContent = value ? t("chatBusy") : "";
}

function resetChat() {
  chatVersion++;
  history = []; sessionId = null; previousIds = [];
  setChatBusy(false);
  $("chat-messages").replaceChildren();
  $("chat-input").value = "";
  appendMessage("assistant", client.mode === "mock" ? t("greetingMock") : t("greetingApi"));
}

async function sendQuestion(question) {
  if (chatBusy || !question.trim()) return;
  const message = question.trim().slice(0, 1000);
  const version = ++chatVersion;
  appendMessage("user", message);
  $("chat-input").value = "";
  setChatBusy(true);
  try {
    let response;
    try {
      response = await client.chat({ message, filters: applied, session_id: sessionId, history, previousIds, language });
    } catch (error) {
      // The server forgets idle conversations after an hour; start a fresh one instead of failing forever.
      if (error.status !== 404 || !sessionId) throw error;
      sessionId = null; previousIds = [];
      response = await client.chat({ message, filters: applied, session_id: null, history: [], previousIds, language });
    }
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
    $("mode-badge").textContent = t("modeApi");
    $("data-banner").querySelector("strong").textContent = t("dataBannerApiStrong");
    $("data-banner").querySelector("p span[data-i18n]").textContent = t("dataBannerApiText");
    $("assistant-mode-note").textContent = language === "vi" && !languageModelAvailable
      ? t("assistantNoteApiTranslationUnavailable")
      : t("assistantNoteApi", { webSearch: t(webDiscoveryAvailable ? "webSearchEnabled" : "webSearchDisabled") });
  } else {
    $("mode-badge").textContent = t("modeDemo");
    $("data-banner").querySelector("strong").textContent = t("dataBannerStrong");
    $("data-banner").querySelector("p span[data-i18n]").textContent = t("dataBannerText");
    $("assistant-mode-note").textContent = t("assistantNoteDemo");
  }
  $("about-mode").textContent = client.mode === "mock" ? t("aboutModeMock") : t("aboutModeApi");
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
  $("language-toggle").addEventListener("click", () => {
    setLanguage(currentLanguage() === "en" ? "vi" : "en");
    applyLanguage();
  });
  for (const id of ["about-button", "data-info"]) $(id).addEventListener("click", () => $("about-dialog").showModal());
  for (const id of ["recipe-dialog", "about-dialog"]) {
    $(id).addEventListener("click", event => {
      const rect = $(id).getBoundingClientRect();
      if (event.target === $(id) && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) $(id).close();
    });
  }
  $("chat-form").addEventListener("submit", event => { event.preventDefault(); sendQuestion($("chat-input").value); });
  $("chat-suggestions").addEventListener("click", event => {
    const node = event.target.closest("[data-question-en]");
    if (node) sendQuestion(language === "vi" ? node.dataset.questionVi : node.dataset.questionEn);
  });
  $("clear-chat").addEventListener("click", resetChat);
}

async function start() {
  applyStaticTranslations();
  bindEvents();
  try {
    client = createClient(window.RECIPEHUB_CONFIG, globalThis.fetch, currentLanguage);
    if (client.mode === "api") {
      try {
        const health = await client.health();
        languageModelAvailable = health.language_model_available;
        webDiscoveryAvailable = health.web_discovery_available;
      } catch { languageModelAvailable = false; webDiscoveryAvailable = false; }
    }
    configureMode();
    resetChat();
    applied = readFilters();
    await Promise.allSettled([loadFacets(), loadRecipes()]);
  } catch (error) {
    startupError = error;
    $("mode-badge").textContent = t("modeError");
    $("result-count").textContent = t("setupRequired");
    $("results").replaceChildren(statePanel(t("configCheck"), error.message));
    $("chat-status").textContent = error.message;
    document.querySelectorAll("form input, form button, form select").forEach(node => { node.disabled = true; });
  }
}
start();
