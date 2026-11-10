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
from recipehub.ingestion_lock import ingestion_lock
from recipehub.knowledge_base import KnowledgeBase, fold, parse_filters, query_tokens
from recipehub.normalize import NormalizationPipeline
from recipehub.recipe_crawler import RecipeCrawler
from recipehub.seed import seed_path


SESSION_TTL_SECONDS = 3600
MAX_SESSIONS = 1000
HISTORY_TURNS = 12
REGION_ALIASES = (
    # Vietnamese names are accent-folded ("Nhật Bản" -> "nhat ban") to match fold(question).
    ("italy", "italian", "mon y", "nuoc y"), ("japan", "japanese", "nhat ban"), ("vietnam", "vietnamese", "viet nam"),
    ("thailand", "thai", "thai lan"), ("korea", "korean", "south korean", "south korea", "han quoc"),
    ("india", "indian", "an do"), ("mexico", "mexican"), ("china", "chinese", "trung quoc", "trung hoa"),
    ("france", "french", "phap"), ("greece", "greek", "hy lap"), ("canada", "canadian"),
    ("britain", "british", "united kingdom", "nuoc anh"),
)
STOP_WORDS = set("a an the i me my we us you your please can could would should do does did to of for from in on at by some any with and or that this these those it its them their find search show suggest recommend recipe recipes dish dishes meal meals cook cooking make something want like need what which how are is have has goes into about tell try list ingredients ingredient steps step instructions instruction method preparation source sources provenance attribution time minutes minute min under within less than up total takes take difficulty easy hard nutrition calories calorie allergens allergen substitutions substitution substitute replace alternatives alternative instead tools equipment tips tip explain".split())
STOP_WORDS.update("toi minh ban muon lam mon an tim co hay giup nha nau trong la gi cua nao the".split())
# Words that only occur in Vietnamese; dish names English speakers also type ("pho", "bun", "bo") are left out.
VIETNAMESE_SIGNALS = set("toi minh ban muon nau mon cach khong duoc giup voi nhung thich canh gi nao bi ung thay".split())
TIME_LIMIT = re.compile(r"(?:under|within|in|less than|up to|duoi|trong vong|trong|khong qua|toi da)\s+(\d{1,5})\s*(?:min(?:ute)?s?|phut)\b")
PLAIN_TEXT = "Write plain text for a chat bubble: no Markdown, no asterisks, no headings; use simple line breaks and '•' for lists."
LOGGER = logging.getLogger(__name__)


class SessionNotFound(ValueError):
    pass


def contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(fold(phrase)) + r"(?!\w)", text))


def response_language(message: str, preferred: str) -> str:
    """Use the language of a clearly Vietnamese question; otherwise keep the UI choice."""
    if re.search(r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", message):
        return "vi"
    if set(query_tokens(message)) & VIETNAMESE_SIGNALS:
        return "vi"
    return preferred if preferred in {"en", "vi"} else "en"


def plain_text(text: str) -> str:
    """The chat bubble shows raw text, so drop Markdown the model may still emit."""
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    return re.sub(r"^\s*[*-]\s+", "• ", text, flags=re.M)


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
        if re.search(r"\b(difficulty|difficult|easy|hard)\b|do kho|đo kho", question):
            return "difficulty"
        if re.search(r"\b(tool|tools|equipment)\b", question):
            return "tools"
        if re.search(r"\b(tip|tips)\b", question):
            return "tips"
        return "discover"

    def _retrieve(self, question: str, preferences: dict[str, Any], search_query: str = "") -> list[dict[str, Any]]:
        filters = {**preferences, "q": ""}
        remainder = question
        region_matched = False
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
                region_matched = True
                remainder = re.sub(r"(?<!\w)" + re.escape(match) + r"(?!\w)", " ", remainder)
                break
        max_time = TIME_LIMIT.search(remainder)
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
        # Removing conversational filler must not turn a greeting into a search
        # for every recipe. Empty queries are useful only for explicit recipe
        # requests or a region/time mentioned in the question itself.
        recipe_request = bool(re.search(
            r"\b(recipe|recipes|dish|dishes|meal|meals|cook|cooking|make|find|search|suggest|recommend|mon|nau|tim)\b",
            question,
        ))
        if not terms and not (recipe_request or max_time or region_matched):
            return []
        # Keep within the search API's 200-character limit for long chat messages.
        filters["q"] = " ".join(terms)[:200]
        return self.store.search(filters, page_size=3)["items"]

    def _search_intent(self, message: str, history: list[dict[str, str]]) -> tuple[bool, str]:
        """Ask Gemini whether the turn needs a recipe lookup and for which dish (in English)."""
        if not self.gemini.available:
            return False, ""
        try:
            response = self.gemini.generate(
                "Decide whether the user's latest message asks about a specific dish or recipe (how to cook it, its "
                "ingredients, steps, time, or finding dishes). Use the earlier conversation to resolve words like 'it' "
                "or 'món đó'. Greetings, small talk, and general kitchen questions are not recipe requests. "
                "Return only JSON: {\"recipe_request\": boolean, \"query\": concise English dish or ingredient search "
                "terms, or an empty string}. Do not answer the question.",
                json.dumps({"message": message}, ensure_ascii=False),
                max_tokens=120,
                json_response=True,
                history=history,
            )
            value = json.loads(response)
            query = value.get("query", "")
            return value.get("recipe_request") is True, query.strip() if isinstance(query, str) else ""
        except (ValueError, TypeError, AttributeError):
            # GeminiUnavailable propagates so the caller can report quota/connection errors.
            return False, ""

    def _discover_and_index(self, query: str, language: str, exclusions: list[str]) -> tuple[bool, str, int | None]:
        if not self.gemini.web_discovery_available:
            return False, "not_configured", None
        query_key = fold(query) + "\0" + " ".join(sorted(fold(item) for item in exclusions))
        with self._discovery_lock:
            if query_key in self._discovered:
                return False, "already_attempted", None
            self._discovered.add(query_key)
        success = False
        try:
            pages = self.gemini.search_recipe_pages(query, language, exclusions)
            if not pages:
                return False, "no_search_results", None
            # Share the same process/thread lock as the CLI scheduler. Publish
            # the raw data, normalized manifest, and SQLite update together.
            with ingestion_lock(self.settings.processed_dir):
                saved = self.crawler.collect_discovered_recipe_pages(pages)
                if not saved:
                    return False, "no_recipe_jsonld", None
                normalized = NormalizationPipeline(self.settings).run()
                imported = self.store.import_processed(self.settings.processed_dir, seed_file=seed_path(self.settings))
            indexed_count = imported.get("inserted", 0) + imported.get("updated", 0) + imported.get("unchanged", 0)
            LOGGER.info("Recipe discovery saved %s page(s); normalized %s and indexed %s recipe(s)", saved, normalized.get("processed", 0), indexed_count)
            success = True
            return True, "indexed", None
        except (GeminiUnavailable, OSError, ValueError, TypeError) as exc:
            LOGGER.warning("Recipe discovery failed (%s)", getattr(exc, "status_code", None) or type(exc).__name__)
            return False, "gemini_error" if isinstance(exc, GeminiUnavailable) else "collection_error", getattr(exc, "status_code", None)
        finally:
            if not success:
                with self._discovery_lock:
                    self._discovered.discard(query_key)

    def _grounded_answer(
        self, message: str, preferences: dict[str, Any], recipes: list[dict[str, Any]], language: str,
        history: list[dict[str, str]] | None = None,
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
            f"You are a friendly kitchen assistant chatting naturally with the user. Answer in {target}, translating "
            "recipe content when needed. For recipe facts use only the supplied recipe records. Do not invent "
            "ingredients, cooking steps, times, nutrition, or substitutions. State when a source does not provide a fact. "
            "For allergies, explain that ingredient lists may be incomplete and cross-contact cannot be assessed; never "
            "guarantee that food is safe. The application will show source citations separately. " + PLAIN_TEXT
        )
        try:
            return plain_text(self.gemini.generate(
                system,
                json.dumps({"question": message, "preferences": preferences, "recipes": records}, ensure_ascii=False),
                max_tokens=900,
                history=history,
            ))
        except GeminiUnavailable:
            return None

    def _free_answer(
        self, message: str, language: str, history: list[dict[str, str]], recipe_missing: bool, exclusions: list[str] | None = None,
    ) -> str | None:
        """Ordinary assistant chat for turns that have no matching source record."""
        if not self.gemini.available:
            return None
        target = "Vietnamese" if language == "vi" else "English"
        system = (
            f"You are a friendly kitchen assistant on a recipe website. Reply in {target} and chat naturally like a "
            "normal AI assistant: greetings, follow-up questions, cooking techniques, and food culture are welcome. "
            "Keep answers concise. Never guarantee that a food is safe for an allergy or diet. " + PLAIN_TEXT
        )
        if exclusions:
            # Without this, a general-knowledge recipe could include the user's allergen.
            system += " The user avoids or is allergic to: " + ", ".join(exclusions) + ". Do not suggest these ingredients."
        if recipe_missing:
            system += (
                " The site's collection and its web search found no source recipe for this request. You may give a "
                "general-knowledge recipe, but say clearly at the start that it is not from a cited source and that "
                "quantities should be checked."
            )
        try:
            return plain_text(self.gemini.generate(system, message, max_tokens=900, history=history))
        except GeminiUnavailable:
            return None

    @staticmethod
    def _record_answer(recipe: dict[str, Any], intent: str, language: str = "en") -> str:
        vi = language == "vi"
        heading = recipe["title"] + "\n\n"
        if intent == "ingredients":
            text = "\n".join(f"• {item['original_text']}" for item in recipe["ingredients"])
        elif intent == "instructions":
            text = "\n".join(f"{index}. {step}" for index, step in enumerate(recipe["instructions"], 1))
        elif intent == "source":
            text = (
                f"Nhà cung cấp: {recipe['source_name']}\n{recipe['attribution']}\nNguồn: {recipe['source_url']}\nGiấy phép / điều khoản: {recipe['source_license']}\nThu thập lúc: {recipe['collected_at']}"
                if vi else
                f"Provider: {recipe['source_name']}\n{recipe['attribution']}\nSource: {recipe['source_url']}\nLicense / terms: {recipe['source_license']}\nCollected: {recipe['collected_at']}"
            )
        elif intent == "time":
            labels = (("prep_minutes", "Chuẩn bị"), ("cook_minutes", "Nấu"), ("total_minutes", "Tổng")) if vi else (("prep_minutes", "Preparation"), ("cook_minutes", "Cooking"), ("total_minutes", "Total"))
            unit = "phút" if vi else "minutes"
            supplied = [f"{label}: {recipe[key]} {unit}" for key, label in labels if recipe[key] is not None]
            missing = "Nguồn không cung cấp thời gian chuẩn bị, nấu hoặc tổng thời gian. Mình sẽ không tự suy đoán." if vi else "The source does not supply structured preparation, cooking, or total time. I will not infer it from the instructions."
            text = "\n".join(supplied) if supplied else missing
        elif intent == "difficulty":
            if vi:
                text = f"Độ khó do nguồn khai báo: {recipe['difficulty']}" if recipe["difficulty"] else "Nguồn không cung cấp độ khó."
            else:
                text = f"Source-declared difficulty: {recipe['difficulty']}" if recipe["difficulty"] else "The source does not supply a difficulty rating."
        elif intent == "allergens":
            if vi:
                text = f"Chất gây dị ứng do nguồn khai báo: {', '.join(recipe['allergens'])}. Danh sách này có thể chưa đầy đủ." if recipe["allergens"] else "Nguồn không khai báo chất gây dị ứng. Tình trạng dị ứng chưa rõ."
                text += "\nMình không thể xác nhận món ăn phù hợp chế độ ăn hay an toàn y tế. Bộ lọc chữ không phát hiện mọi tên gọi khác, nguyên liệu ẩn hoặc nhiễm chéo."
            else:
                text = f"Source-declared allergens: {', '.join(recipe['allergens'])}. This list may be incomplete." if recipe["allergens"] else "The source does not supply structured allergen declarations. Allergen status is unknown."
                text += "\nI cannot certify dietary suitability or medical safety. Text exclusions do not detect all aliases, hidden ingredients, or cross-contact."
        elif intent == "nutrition":
            if recipe["nutrition"]:
                text = ("Dinh dưỡng do nguồn khai báo:\n" if vi else "Source-declared nutrition:\n") + json.dumps(recipe["nutrition"], ensure_ascii=False, indent=2)
            else:
                text = "Nguồn không cung cấp thông tin dinh dưỡng. Mình sẽ không tự ước tính." if vi else "The source does not supply structured nutrition information. I will not estimate it."
        elif intent == "substitutions":
            if recipe["substitutions"]:
                text = ("Nguyên liệu thay thế do nguồn nêu:\n" if vi else "Source-declared substitutions:\n") + "\n".join("; ".join(f"{key}: {value}" for key, value in item.items()) for item in recipe["substitutions"])
            else:
                text = "Nguồn không nêu nguyên liệu thay thế. Mình sẽ không tự bịa ra." if vi else "The source does not supply substitutions. I will not invent an alternative ingredient."
        else:
            values = recipe[intent]
            missing = {"tools": "dụng cụ", "tips": "mẹo"}.get(intent, intent)
            text = "\n".join(f"• {item}" for item in values) if values else (f"Nguồn không cung cấp {missing}." if vi else f"The source does not supply {intent}.")
        footer = "Mở bản ghi được trích dẫn để xem nguồn gốc và thông tin ghi công." if vi else "See the cited record for the original source and its attribution."
        return heading + text + "\n\n" + footer

    def answer(
        self,
        message: str,
        filters: dict[str, Any] | None = None,
        session_id: str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        if not isinstance(message, str) or not message.strip() or len(message) > 1000:
            raise ValueError("message must contain 1–1000 characters")
        language = response_language(message, language)
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
            # 100 characters per term is the search API's limit.
            extra = [item.strip()[:100] for item in re.split(r",|\band\b|\bor\b|\bva\b|\bhoac\b", negative[1]) if item.strip()]
            context["exclusions"] = list(dict.fromkeys([*context.get("exclusions", []), *extra]))[:20]
            question = question[:negative.start()] + " " + question[negative.end():]
        preferences["exclude_ingredients"] = list(dict.fromkeys([*preferences["exclude_ingredients"], *context.get("exclusions", [])]))[:20]
        intent = self._intent(question)
        follow_up = (
            bool(re.search(r"\b(it|its|this|that|them|their|those|these)\b", question))
            # Vietnamese pronouns (nó, này, đó, ấy, chúng) after accent folding.
            or (language == "vi" and bool(re.search(r"\b(no|nay|do|ay|chung)\b", question)))
            or (intent != "discover" and not [word for word in query_tokens(question) if word not in STOP_WORDS])
        )
        # A named dish takes precedence over pronouns elsewhere in the same
        # message. Check names without preferences first, so an excluded named
        # dish cannot accidentally fall back to the previous eligible recipe.
        if self.store.named_in(question, {}):
            follow_up = False
        has_context = bool(context.get("record_ids"))
        history = context.get("history", [])
        records = self.store.eligible(context.get("record_ids", []), preferences) if follow_up else []
        # The previous recipe no longer fits newly applied exclusions: do not answer it from memory.
        context_excluded = follow_up and has_context and not records
        search_query = ""
        wants_recipe = False
        discovery_state = "not_configured" if not self.gemini.web_discovery_available else "not_attempted"
        discovery_status: int | None = None
        if not follow_up:
            records = self._retrieve(question, preferences)
        if not records and not context_excluded and self.gemini.available:
            try:
                wants_recipe, search_query = self._search_intent(message, history)
            except GeminiUnavailable as exc:
                discovery_state, discovery_status = "gemini_error", exc.status_code
            if wants_recipe and search_query:
                records = self._retrieve(fold(search_query), preferences, fold(search_query))
            if not records and wants_recipe and self.gemini.web_discovery_available:
                discovered, discovery_state, discovery_status = self._discover_and_index(search_query or message, language, preferences["exclude_ingredients"])
                if discovered:
                    records = self._retrieve(fold(search_query) or question, preferences, fold(search_query))
        free_text = None
        if not records and not context_excluded and discovery_state != "gemini_error":
            free_text = self._free_answer(message, language, history, wants_recipe, preferences["exclude_ingredients"])
        if not records and free_text:
            text = free_text
        elif not records and context_excluded:
            text = (
                "Món trước đó không còn phù hợp với các nguyên liệu cần tránh hiện tại, nên mình không trả lời về nó. Hãy hỏi một món khác nhé."
                if language == "vi" else
                "The previous recipe no longer matches your current exclusions, so I will not answer about it. Ask about another dish."
            )
        elif not records and follow_up and not has_context:
            text = (
                "Bạn đang hỏi về món nào? Hãy cho mình biết tên món trước nhé."
                if language == "vi" else
                "Which dish do you mean? Tell me the dish name first."
            )
        elif not records and re.fullmatch(
            r"(?:hi|hello|hey|how are you|thanks|thank you|xin chao|chao ban|cam on)[\s.!?,]*",
            question,
        ):
            text = (
                "Chào bạn! Mình có thể giúp tìm món, nguyên liệu và cách nấu trong bộ sưu tập. Bạn muốn nấu món gì?"
                if language == "vi" else
                "Hello! I can help find dishes, ingredients, and cooking steps in the collection. What would you like to cook?"
            )
        elif not records:
            if discovery_state == "gemini_error" and discovery_status == 429:
                text = (
                    "Mình chưa tìm thêm trên web được vì Gemini đang hết lượt dùng (lỗi 429). Hãy thử lại sau ít phút."
                    if language == "vi" else
                    "I could not search the web because Gemini is out of quota for now (HTTP 429). Try again in a few minutes."
                )
            elif discovery_state == "gemini_error":
                if discovery_status and discovery_status >= 500:
                    # 5xx is Google's side (overloaded); the key and settings are fine.
                    text = (
                        f"Mình chưa tìm thêm trên web được vì máy chủ Gemini đang quá tải tạm thời (lỗi {discovery_status}). Hãy thử lại sau ít phút."
                        if language == "vi" else
                        f"I could not search the web because Gemini's servers are temporarily overloaded (HTTP {discovery_status}). Try again in a few minutes."
                    )
                elif discovery_status:
                    text = (
                        f"Gemini chưa thể tìm công thức (HTTP {discovery_status}). Hãy kiểm tra khóa API, quyền truy cập và kết nối rồi thử lại."
                        if language == "vi" else
                        f"Gemini could not search for a recipe (HTTP {discovery_status}). Check the API key, access, and connection, then retry."
                    )
                else:
                    text = (
                        "Gemini chưa thể tìm công thức do lỗi kết nối hoặc phản hồi API không hợp lệ. Hãy kiểm tra kết nối rồi thử lại."
                        if language == "vi" else
                        "Gemini could not search because of a network or API response error. Check the connection, then retry."
                    )
            elif discovery_state == "no_recipe_jsonld":
                text = (
                    "Mình tìm được trang nhưng chưa thu thập được trang nào có dữ liệu Recipe JSON-LD mà hệ thống hỗ trợ. Thử cách viết tên món khác hoặc chọn món khác nhé."
                    if language == "vi" else
                    "Search returned pages, but none could be collected as a supported Schema.org Recipe record. Try another spelling or dish."
                )
            elif discovery_state == "no_search_results":
                text = (
                    "Chưa tìm được trang công thức phù hợp trên web. Hãy thử tên món khác hoặc viết tên món bằng tiếng Anh."
                    if language == "vi" else
                    "Web search did not return a matching recipe page. Try another dish name or its English name."
                )
            elif discovery_state == "indexed":
                text = (
                    "Mình đã thu thập trang công thức nhưng chưa tìm thấy bản ghi khớp với câu hỏi. Hãy thử tên tiếng Anh hoặc cách viết khác của món."
                    if language == "vi" else
                    "I collected a recipe page but could not match its indexed record to the question. Try the English name or another spelling."
                )
            elif discovery_state == "not_configured":
                text = (
                    "Món này chưa có trong bộ sưu tập và Gemini chưa được cấu hình để tìm trên web."
                    if language == "vi" else
                    "This dish is not in the collection, and Gemini web discovery is not configured."
                )
            else:
                text = (
                    "Chưa tìm thấy công thức phù hợp trong bộ sưu tập hoặc trên web. Hãy thử tên món khác hoặc nới bộ lọc."
                    if language == "vi" else
                    "I could not find a matching recipe in the collection or on the web. Try another dish name or relax the filters."
                )
            time_limit = TIME_LIMIT.search(question)
            if time_limit and discovery_state in {"gemini_error", "not_configured", "not_attempted"}:
                # Most sources (TheMealDB) publish no cooking time, so time-only questions rarely match.
                local = (
                    f"Chưa có món nào trong bộ sưu tập ghi tổng thời gian nấu tối đa {time_limit[1]} phút. Nhiều nguồn (như TheMealDB) không ghi thời gian nấu, nên bộ lọc thời gian thường không có kết quả."
                    if language == "vi" else
                    f"No recipe in the collection lists a total time of {time_limit[1]} minutes or less. Many sources (such as TheMealDB) publish no cooking time."
                )
                text = local if discovery_state != "gemini_error" else local + "\n\n" + text
        else:
            if intent != "discover":
                records = records[:1]
            vi = language == "vi"
            lines = []
            for recipe in records:
                if recipe["total_minutes"] is not None:
                    timing = f"{recipe['total_minutes']} {'phút' if vi else 'minutes'}"
                else:
                    timing = "chưa có thời gian" if vi else "time not supplied"
                region = recipe["country_or_region"] or ("chưa rõ vùng miền" if vi else "region not supplied")
                lines.append(f"• {recipe['title']} — {region}; {timing}.")
            if intent != "discover":
                fallback = self._record_answer(records[0], intent, language)
            elif vi:
                fallback = "Đây là các công thức phù hợp với câu hỏi và lựa chọn của bạn:\n\n" + "\n".join(lines) + "\n\nMở trích dẫn để xem công thức đầy đủ."
            else:
                fallback = "Here are source records matching your question and preferences:\n\n" + "\n".join(lines) + "\n\nOpen a citation for the full recipe."
            text = self._grounded_answer(message, preferences, records, language, history) or fallback
        if preferences["exclude_ingredients"]:
            suffix = (
                "\n\nĐã loại trừ theo nội dung nguyên liệu được ghi nhận: " + ", ".join(preferences["exclude_ingredients"]) + ". Điều này không bảo đảm món ăn an toàn cho dị ứng."
                if language == "vi"
                else "\n\nText exclusions applied: " + ", ".join(preferences["exclude_ingredients"]) + ". This does not guarantee dietary safety."
            )
            text += suffix
        if records:
            context["record_ids"] = [record["record_id"] for record in records]
        # Keep a short server-side transcript so Gemini can follow the conversation.
        context["history"] = [*history, {"role": "user", "text": message}, {"role": "model", "text": text[:2000]}][-HISTORY_TURNS:]
        self._save(session_id, context)
        return {"answer": text, "session_id": session_id, "citations": [citation(record) for record in records], "language": language}
