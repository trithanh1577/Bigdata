from __future__ import annotations

import json
import logging
import re
import secrets
import threading
import time
from typing import Any

from recipehub.config import Settings
from recipehub.gemini import GeminiClient, GeminiUnavailable
from recipehub.knowledge_base import KnowledgeBase, fold, parse_filters, query_tokens
from recipehub.normalize import NormalizationPipeline
from recipehub.recipe_crawler import RecipeCrawler


SESSION_TTL_SECONDS = 3600
MAX_SESSIONS = 1000
REGION_ALIASES = (
    ("italy", "italian"), ("japan", "japanese"), ("vietnam", "vietnamese"),
    ("thailand", "thai"), ("korea", "korean", "south korean", "south korea"),
    ("india", "indian"), ("mexico", "mexican"), ("china", "chinese"),
    ("france", "french"), ("greece", "greek"), ("canada", "canadian"),
    ("britain", "british", "united kingdom"),
)
STOP_WORDS = set("a an the i me my we us you your please can could would should do does did to of for from in on at by some any with and or that this these those it its them their find search show suggest recommend recipe recipes dish dishes meal meals cook cooking make something want like need what which how are is have has goes into about tell try list ingredients ingredient steps step instructions instruction method preparation source sources provenance attribution time minutes minute min under within less than up total takes take difficulty easy hard nutrition calories calorie allergens allergen substitutions substitution substitute replace alternatives alternative instead tools equipment tips tip explain".split())
STOP_WORDS.update("toi minh ban muon lam mon an tim co hay giup nha".split())
LOGGER = logging.getLogger(__name__)


class SessionNotFound(ValueError):
    pass


def contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(fold(phrase)) + r"(?!\w)", text))


def citation(recipe: dict[str, Any]) -> dict[str, str]:
    return {key: recipe[key] for key in ("record_id", "title", "source_name", "source_url")}


class ConversationService:
    """Retrieve source recipes first, then use optional Gemini for grounded chat."""

    def __init__(self, store: KnowledgeBase, settings: Settings | None = None, crawler: RecipeCrawler | None = None) -> None:
        self.store = store
        self.settings = settings or Settings()
        self.gemini = GeminiClient(self.settings)
        self.crawler = crawler or RecipeCrawler(self.settings)
        self._discovery_lock = threading.Lock()
        self._discovered: set[str] = set()

    def _context(self, session_id: str | None) -> tuple[str, dict[str, Any]]:
        now = time.time()
        row = None
        with self.store.connect() as db:
            db.execute("DELETE FROM chat_sessions WHERE updated_at<?", (now - SESSION_TTL_SECONDS,))
            if session_id:
                row = db.execute("SELECT context FROM chat_sessions WHERE session_id=?", (session_id,)).fetchone()
        if session_id:
            if row is None:
                raise SessionNotFound("Conversation expired or not found. Start a new conversation.")
            return session_id, json.loads(row["context"])
        return secrets.token_urlsafe(32), {"record_ids": [], "exclusions": []}

    def _save(self, session_id: str, context: dict[str, Any]) -> None:
        with self.store.connect() as db:
            db.execute("INSERT INTO chat_sessions VALUES (?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET updated_at=excluded.updated_at, context=excluded.context", (session_id, time.time(), json.dumps(context)))
            db.execute("DELETE FROM chat_sessions WHERE session_id IN (SELECT session_id FROM chat_sessions ORDER BY updated_at DESC LIMIT -1 OFFSET ?)", (MAX_SESSIONS,))

    @staticmethod
    def _intent(question: str) -> str:
        if re.search(r"allerg|safe|free\b|vegan|vegetarian|halal|kosher|diet|di ung|an toan", question):
            return "allergens"
        if re.search(r"nutrition|calori|protein|carb|fat content|dinh duong", question):
            return "nutrition"
        if re.search(r"substitut|replac|instead|alternative|thay the|doi nguyen lieu", question):
            return "substitutions"
        if re.search(r"\b(step|steps|instruction|instructions|method|procedure)\b|how (do|to|can)|cach nau|che bien|huong dan|cac buoc", question):
            return "instructions"
        if re.search(r"ingredient|what goes into|nguyen lieu|thanh phan", question):
            return "ingredients"
        if re.search(r"\b(source|sources|provenance|attribution|license|collected)\b|where.*come from|nguon o dau", question):
            return "source"
        if re.search(r"how long|\b(timing|time|duration)\b|bao lau|thoi gian", question):
            return "time"
        if re.search(r"\b(difficulty|difficult|easy|hard)\b|do kho", question):
            return "difficulty"
        if re.search(r"\b(tool|tools|equipment)\b", question):
            return "tools"
        if re.search(r"\b(tip|tips)\b", question):
            return "tips"
        return "discover"

    def _retrieve(self, question: str, preferences: dict[str, Any], search_query: str = "") -> list[dict[str, Any]]:
        filters = {**preferences, "q": ""}
        remainder = question
        facets = self.store.facets()
        for region in sorted(facets["countries"], key=len, reverse=True):
            aliases = {fold(region)}
            for group in REGION_ALIASES:
                if fold(region) in group:
                    aliases.update(group)
            match = next((alias for alias in sorted(aliases, key=len, reverse=True) if contains_phrase(remainder, alias)), None)
            if match:
                # An explicit question can narrow but cannot bypass a country
                # preference selected by the visitor.
                if preferences["country"] and preferences["country"] != region:
                    return []
                filters["country"] = region
                remainder = re.sub(r"(?<!\w)" + re.escape(match) + r"(?!\w)", " ", remainder)
                break
        max_time = re.search(r"(?:under|within|in|less than|up to)\s+(\d{1,5})\s*(?:min(?:ute)?s?)\b", remainder)
        if max_time:
            minutes = int(max_time[1])
            filters["max_minutes"] = min(minutes, preferences["max_minutes"]) if preferences["max_minutes"] is not None else minutes
            remainder = remainder[:max_time.start()] + " " + remainder[max_time.end():]
        # Prefer a named record before stripping conversational filler words.
        direct = self.store.named_in(question, filters)
        if not direct and search_query and search_query != question:
            direct = self.store.named_in(search_query, filters)
        if direct:
            return direct[:3]
        terms = [word for word in query_tokens(remainder) if word not in STOP_WORDS]
        if not terms and search_query:
            terms = [word for word in query_tokens(search_query) if word not in STOP_WORDS]
        filters["q"] = " ".join(terms)
        return self.store.search(filters, page_size=3)["items"]

    def _english_search_query(self, message: str) -> str:
        if not self.gemini.available:
            return ""
        try:
            response = self.gemini.generate(
                "Convert the user's recipe request into concise English search terms. Keep dish and ingredient names "
                "accurate. Do not answer the question. Return only JSON with a string field named query.",
                json.dumps({"request": message}, ensure_ascii=False),
                max_tokens=120,
                json_response=True,
            )
            value = json.loads(response).get("query", "")
            return value.strip() if isinstance(value, str) else ""
        except (GeminiUnavailable, ValueError, TypeError, AttributeError):
            return ""

    def _discover_and_index(self, query: str, language: str, exclusions: list[str]) -> bool:
        if not self.gemini.web_discovery_available:
            return False
        query_key = fold(query) + "\0" + " ".join(sorted(fold(item) for item in exclusions))
        with self._discovery_lock:
            if query_key in self._discovered:
                return False
            self._discovered.add(query_key)
        success = False
        try:
            pages = self.gemini.search_recipe_pages(query, language, exclusions)
            if not pages:
                return False
            saved = self.crawler.collect_discovered_recipe_pages(pages)
            if not saved:
                return False
            normalized = NormalizationPipeline(self.settings).run()
            imported = self.store.import_processed(self.settings.processed_dir)
            indexed_count = imported.get("inserted", 0) + imported.get("updated", 0) + imported.get("unchanged", 0)
            LOGGER.info("Recipe discovery saved %s page(s); normalized %s and indexed %s recipe(s)", saved, normalized.get("processed", 0), indexed_count)
            success = True
            return True
        except (GeminiUnavailable, OSError, ValueError, TypeError) as exc:
            LOGGER.warning("Recipe discovery failed (%s)", getattr(exc, "status_code", None) or type(exc).__name__)
            return False
        finally:
            if not success:
                with self._discovery_lock:
                    self._discovered.discard(query_key)

    def _grounded_answer(
        self, message: str, preferences: dict[str, Any], recipes: list[dict[str, Any]], language: str
    ) -> str | None:
        if not self.gemini.available:
            return None
        target = "Vietnamese" if language == "vi" else "English"
        records = []
        for recipe in recipes:
            records.append({key: recipe.get(key) for key in (
                "record_id", "title", "country_or_region", "description", "ingredients", "instructions",
                "prep_minutes", "cook_minutes", "total_minutes", "difficulty", "substitutions", "allergens",
                "nutrition", "source_name", "source_url", "attribution",
            )})
        system = (
            f"You are a culinary assistant. Answer in {target}. Use only the supplied recipe records and the user's "
            "question. Do not invent ingredients, cooking steps, times, nutrition, or substitutions. State when a source "
            "does not provide a fact. For allergies, explain that ingredient lists may be incomplete and cross-contact "
            "cannot be assessed; never guarantee that food is safe. The application will show source citations separately."
        )
        try:
            return self.gemini.generate(
                system,
                json.dumps({"question": message, "preferences": preferences, "recipes": records}, ensure_ascii=False),
                max_tokens=900,
            )
        except GeminiUnavailable:
            return None

    @staticmethod
    def _record_answer(recipe: dict[str, Any], intent: str) -> str:
        heading = recipe["title"] + "\n\n"
        if intent == "ingredients":
            text = "\n".join(f"• {item['original_text']}" for item in recipe["ingredients"])
        elif intent == "instructions":
            text = "\n".join(f"{index}. {step}" for index, step in enumerate(recipe["instructions"], 1))
        elif intent == "source":
            text = f"Provider: {recipe['source_name']}\n{recipe['attribution']}\nSource: {recipe['source_url']}\nLicense / terms: {recipe['source_license']}\nCollected: {recipe['collected_at']}"
        elif intent == "time":
            supplied = [f"{label}: {recipe[key]} minutes" for key, label in (("prep_minutes", "Preparation"), ("cook_minutes", "Cooking"), ("total_minutes", "Total")) if recipe[key] is not None]
            text = "\n".join(supplied) if supplied else "The source does not supply structured preparation, cooking, or total time. I will not infer it from the instructions."
        elif intent == "difficulty":
            text = f"Source-declared difficulty: {recipe['difficulty']}" if recipe["difficulty"] else "The source does not supply a difficulty rating."
        elif intent == "allergens":
            text = f"Source-declared allergens: {', '.join(recipe['allergens'])}. This list may be incomplete." if recipe["allergens"] else "The source does not supply structured allergen declarations. Allergen status is unknown."
            text += "\nI cannot certify dietary suitability or medical safety. Text exclusions do not detect all aliases, hidden ingredients, or cross-contact."
        elif intent == "nutrition":
            text = "Source-declared nutrition:\n" + json.dumps(recipe["nutrition"], ensure_ascii=False, indent=2) if recipe["nutrition"] else "The source does not supply structured nutrition information. I will not estimate it."
        elif intent == "substitutions":
            text = "Source-declared substitutions:\n" + "\n".join("; ".join(f"{key}: {value}" for key, value in item.items()) for item in recipe["substitutions"]) if recipe["substitutions"] else "The source does not supply substitutions. I will not invent an alternative ingredient."
        else:
            values = recipe[intent]
            text = "\n".join(f"• {item}" for item in values) if values else f"The source does not supply {intent}."
        return heading + text + "\n\nSee the cited record for the original source and its attribution."

    def answer(
        self,
        message: str,
        filters: dict[str, Any] | None = None,
        session_id: str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        if not isinstance(message, str) or not message.strip() or len(message) > 1000:
            raise ValueError("message must contain 1–1000 characters")
        language = language if language in {"en", "vi"} else "en"
        if session_id is not None and (not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", session_id)):
            raise ValueError("session_id must be null or a valid conversation token")
        preferences = parse_filters(filters or {})
        session_id, context = self._context(session_id)
        question = fold(message)
        # Natural-language avoidance is conservative text extraction. Terms are
        # retained for the session; a new conversation clears them.
        negative = re.search(
            r"\b(?:without|avoid|avoiding|exclude|excluding|allergic to|di ung(?: voi)?|tranh|khong an|khong dung)\s+(.+?)(?=\s+(?:under|within|from|in \d|with|nhung|but)\b|[,;.!?]|$)",
            question,
        )
        if negative:
            extra = [item.strip() for item in re.split(r",|\band\b|\bor\b|\bva\b|\bhoac\b", negative[1]) if item.strip()]
            context["exclusions"] = list(dict.fromkeys([*context.get("exclusions", []), *extra]))[:20]
            question = question[:negative.start()] + " " + question[negative.end():]
        preferences["exclude_ingredients"] = list(dict.fromkeys([*preferences["exclude_ingredients"], *context.get("exclusions", [])]))[:20]
        intent = self._intent(question)
        follow_up = bool(re.search(r"\b(it|its|this|that|them|their|those|these)\b", question)) or (intent != "discover" and not [word for word in query_tokens(question) if word not in STOP_WORDS])
        has_context = bool(context.get("record_ids"))
        records = self.store.eligible(context.get("record_ids", []), preferences) if follow_up else []
        search_query = ""
        if not (follow_up and has_context):
            records = self._retrieve(question, preferences)
        if not records and language == "vi":
            search_query = self._english_search_query(message)
            if search_query:
                records = self._retrieve(search_query, preferences, search_query)
        if not records and self.gemini.web_discovery_available:
            if self._discover_and_index(message, language, preferences["exclude_ingredients"]):
                if not search_query and language == "vi":
                    search_query = self._english_search_query(message)
                records = self._retrieve(search_query or question, preferences, search_query)
        if not records:
            text = (
                "Chưa tìm thấy công thức phù hợp trong bộ sưu tập hoặc trên các trang đã tìm được. Hãy thử tên món khác hoặc nới bộ lọc."
                if language == "vi"
                else "I could not find a matching recipe in the collection or on the recipe pages searched. Try another dish name or relax the filters."
            )
        else:
            if intent != "discover":
                records = records[:1]
            lines = []
            for recipe in records:
                timing = f"{recipe['total_minutes']} minutes" if recipe["total_minutes"] is not None else "time not supplied"
                lines.append(f"• {recipe['title']} — {recipe['country_or_region'] or 'region not supplied'}; {timing}.")
            fallback = (
                self._record_answer(records[0], intent)
                if intent != "discover"
                else "Here are source records matching your question and preferences:\n\n" + "\n".join(lines) + "\n\nOpen a citation for the full recipe."
            )
            text = self._grounded_answer(message, preferences, records, language) or fallback
        if preferences["exclude_ingredients"]:
            suffix = (
                "\n\nĐã loại trừ theo nội dung nguyên liệu được ghi nhận: " + ", ".join(preferences["exclude_ingredients"]) + ". Điều này không bảo đảm món ăn an toàn cho dị ứng."
                if language == "vi"
                else "\n\nText exclusions applied: " + ", ".join(preferences["exclude_ingredients"]) + ". This does not guarantee dietary safety."
            )
            text += suffix
        if records:
            context["record_ids"] = [record["record_id"] for record in records]
        self._save(session_id, context)
        return {"answer": text, "session_id": session_id, "citations": [citation(record) for record in records]}
