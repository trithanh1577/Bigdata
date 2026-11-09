from __future__ import annotations

import json
import re
import secrets
import time
from typing import Any

from recipehub.knowledge_base import KnowledgeBase, fold, parse_filters, query_tokens


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


class SessionNotFound(ValueError):
    pass


def contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(fold(phrase)) + r"(?!\w)", text))


def citation(recipe: dict[str, Any]) -> dict[str, str]:
    return {key: recipe[key] for key in ("record_id", "title", "source_name", "source_url")}


class ConversationService:
    """Source-extractive answers; server-owned context, no generative model."""

    def __init__(self, store: KnowledgeBase) -> None:
        self.store = store

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
        if re.search(r"allerg|safe|free\b|vegan|vegetarian|halal|kosher|diet", question):
            return "allergens"
        if re.search(r"nutrition|calori|protein|carb|fat content", question):
            return "nutrition"
        if re.search(r"substitut|replac|instead|alternative", question):
            return "substitutions"
        if re.search(r"\b(step|steps|instruction|instructions|method|procedure)\b|how (do|to|can)", question):
            return "instructions"
        if re.search(r"ingredient|what goes into", question):
            return "ingredients"
        if re.search(r"\b(source|sources|provenance|attribution|license|collected)\b|where.*come from", question):
            return "source"
        if re.search(r"how long|\b(timing|time|duration)\b", question):
            return "time"
        if re.search(r"\b(difficulty|difficult|easy|hard)\b", question):
            return "difficulty"
        if re.search(r"\b(tool|tools|equipment)\b", question):
            return "tools"
        if re.search(r"\b(tip|tips)\b", question):
            return "tips"
        return "discover"

    def _retrieve(self, question: str, preferences: dict[str, Any]) -> list[dict[str, Any]]:
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
        if direct:
            return direct[:3]
        terms = [word for word in query_tokens(remainder) if word not in STOP_WORDS]
        filters["q"] = " ".join(terms)
        return self.store.search(filters, page_size=3)["items"]

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

    def answer(self, message: str, filters: dict[str, Any] | None = None, session_id: str | None = None) -> dict[str, Any]:
        if not isinstance(message, str) or not message.strip() or len(message) > 1000:
            raise ValueError("message must contain 1–1000 characters")
        if session_id is not None and (not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", session_id)):
            raise ValueError("session_id must be null or a valid conversation token")
        preferences = parse_filters(filters or {})
        session_id, context = self._context(session_id)
        question = fold(message)
        # Natural-language avoidance is conservative text extraction. Terms are
        # retained for the session; a new conversation clears them.
        negative = re.search(r"\b(?:without|avoid|avoiding|exclude|excluding|allergic to)\s+(.+?)(?=\s+(?:under|within|from|in \d|with)\b|[.!?]|$)", question)
        if negative:
            extra = [item.strip() for item in re.split(r",|\band\b|\bor\b", negative[1]) if item.strip()]
            context["exclusions"] = list(dict.fromkeys([*context.get("exclusions", []), *extra]))[:20]
            question = question[:negative.start()] + " " + question[negative.end():]
        preferences["exclude_ingredients"] = list(dict.fromkeys([*preferences["exclude_ingredients"], *context.get("exclusions", [])]))[:20]
        intent = self._intent(question)
        follow_up = bool(re.search(r"\b(it|its|this|that|them|their|those|these)\b", question)) or (intent != "discover" and not [word for word in query_tokens(question) if word not in STOP_WORDS])
        has_context = bool(context.get("record_ids"))
        records = self.store.eligible(context.get("record_ids", []), preferences) if follow_up else []
        if not (follow_up and has_context):
            records = self._retrieve(question, preferences)
        generic = not [word for word in query_tokens(question) if word not in STOP_WORDS]
        contextual_without_record = follow_up and not context.get("record_ids") and generic
        supported_request = bool(re.search(r"\b(recipe|recipes|dish|dishes|find|suggest|search|meal|meals|cook|show|recommend|make|ingredient|ingredients)\b", question)) or bool(records and not generic)
        if contextual_without_record or not supported_request and not (follow_up and records):
            records = []
            text = "I can search the recipe collection and quote supplied ingredients, steps, timing, nutrition, allergens, or substitutions. Ask for a dish, region, or ingredient first, then ask a follow-up about a cited record. I do not invent missing source facts."
        elif not records:
            text = "No recipe matches that question and the current preferences. Try a different term or relax the filters. Missing time or allergen fields are not treated as known values."
        elif intent != "discover":
            records = records[:1]
            text = self._record_answer(records[0], intent)
        else:
            lines = []
            for recipe in records:
                timing = f"{recipe['total_minutes']} minutes" if recipe["total_minutes"] is not None else "time not supplied"
                lines.append(f"• {recipe['title']} — {recipe['country_or_region'] or 'region not supplied'}; {timing}.")
            text = "Here are source records matching your question and preferences:\n\n" + "\n".join(lines) + "\n\nOpen a citation for the full recipe. Follow-up questions refer to the first cited record."
        if preferences["exclude_ingredients"]:
            text += "\n\nText exclusions applied: " + ", ".join(preferences["exclude_ingredients"]) + ". This does not guarantee dietary safety."
        if records:
            context["record_ids"] = [record["record_id"] for record in records]
        self._save(session_id, context)
        return {"answer": text, "session_id": session_id, "citations": [citation(record) for record in records]}
