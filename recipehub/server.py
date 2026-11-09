from __future__ import annotations

import json
import logging
import mimetypes
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from recipehub.conversation import ConversationService, SessionNotFound
from recipehub.knowledge_base import KnowledgeBase


MAX_BODY_BYTES = 32_768
LOGGER = logging.getLogger(__name__)


class RecipeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], store: KnowledgeBase, frontend_dir: Path, allowed_origins: list[str] | None = None):
        self.store = store
        self.conversation = ConversationService(store)
        self.frontend_dir = frontend_dir.resolve()
        self.allowed_origins = set(allowed_origins or ["http://127.0.0.1:5173", "http://localhost:5173"])
        super().__init__(address, RecipeHandler)


class RecipeHandler(BaseHTTPRequestHandler):
    server: RecipeServer

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Vary", "Origin")
        origin = self.headers.get("Origin", "")
        if origin in self.server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        self.end_headers()

    def _json(self, value: Any, status: int = 200) -> None:
        content = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(content))
        self.wfile.write(content)

    def _error(self, status: int, message: str) -> None:
        self._json({"error": {"status": status, "message": message}}, status)

    def do_OPTIONS(self) -> None:
        if self.headers.get("Origin", "") not in self.server.allowed_origins:
            self._error(403, "Origin is not allowed")
            return
        self._headers(204, "application/json", 0)

    def do_GET(self) -> None:
        try:
            self._get()
        except (ValueError, TypeError) as exc:
            self._error(400, str(exc))
        except sqlite3.Error:
            LOGGER.exception("Knowledge base query failed")
            self._error(503, "The knowledge base is temporarily unavailable")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _get(self) -> None:
        parts = urlsplit(self.path)
        path = parts.path
        if path == "/api/v1/health":
            self._json({"status": "ok", **self.server.store.stats(), "answer_mode": "source-extractive", "session_ttl_seconds": 3600})
        elif path == "/api/v1/facets":
            self._json(self.server.store.facets())
        elif path == "/api/v1/recipes":
            query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=50)
            valid = {"q", "country", "category", "max_minutes", "difficulty", "ingredient", "exclude_ingredients", "require_allergens", "sort", "page", "page_size"}
            if query.keys() - valid:
                raise ValueError("Unknown search parameter")
            if any(len(values) != 1 for key, values in query.items() if key != "exclude_ingredients"):
                raise ValueError("Only exclude_ingredients may be repeated")
            filters = {key: values[0] for key, values in query.items() if key not in {"exclude_ingredients", "page", "page_size", "require_allergens"}}
            filters["exclude_ingredients"] = query.get("exclude_ingredients", [])
            declared = query.get("require_allergens", ["false"])[0]
            if declared not in {"true", "false"}:
                raise ValueError("require_allergens must be true or false")
            filters["require_allergens"] = declared == "true"
            page = int(query.get("page", ["1"])[0])
            size = int(query.get("page_size", ["6"])[0])
            self._json(self.server.store.search(filters, page, size))
        elif path.startswith("/api/v1/recipes/"):
            record_id = unquote(path.removeprefix("/api/v1/recipes/"))
            recipe = self.server.store.recipe(record_id)
            if recipe is None:
                self._error(404, "Recipe not found")
            else:
                self._json(recipe)
        elif path.startswith("/api/"):
            self._error(404, "API route not found")
        elif path == "/config.js":
            # Same-origin startup connects the existing frontend automatically;
            # serving frontend/ independently still uses its static mock config.
            content = b'window.RECIPEHUB_CONFIG = { mode: "api", apiBaseUrl: window.location.origin + "/api/v1", timeoutMs: 15000 };'
            self._headers(200, "text/javascript; charset=utf-8", len(content))
            self.wfile.write(content)
        else:
            relative = "index.html" if path == "/" else unquote(path).lstrip("/")
            candidate = (self.server.frontend_dir / relative).resolve()
            allowed = {".html", ".css", ".js", ".svg"}
            if not candidate.is_relative_to(self.server.frontend_dir) or candidate.suffix not in allowed or "tests" in candidate.relative_to(self.server.frontend_dir).parts or not candidate.is_file():
                self._error(404, "File not found")
                return
            content = candidate.read_bytes()
            kind = "text/javascript" if candidate.suffix == ".js" else mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self._headers(200, kind + "; charset=utf-8", len(content))
            self.wfile.write(content)

    def do_POST(self) -> None:
        try:
            if urlsplit(self.path).path != "/api/v1/chat":
                self._error(404, "API route not found")
                return
            origin = self.headers.get("Origin")
            same_origins = {f"http://{host}:{self.server.server_port}" for host in ("127.0.0.1", "localhost")}
            if origin and origin not in self.server.allowed_origins | same_origins:
                self._error(403, "Origin is not allowed")
                return
            if self.headers.get_content_type() != "application/json":
                self._error(415, "Content-Type must be application/json")
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= MAX_BODY_BYTES:
                self._error(413, f"Request body must contain 1–{MAX_BODY_BYTES} bytes")
                return
            self.connection.settimeout(15)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
            if body.keys() - {"message", "filters", "session_id", "history"}:
                raise ValueError("Unknown chat request field")
            history = body.get("history", [])
            if not isinstance(history, list) or len(history) > 12:
                raise ValueError("history must be an array of at most 12 prior messages")
            # Client history is accepted for contract compatibility, but recipe
            # context is loaded from the server session, never fabricated text.
            answer = self.server.conversation.answer(body.get("message"), body.get("filters"), body.get("session_id"))
            self._json(answer)
        except SessionNotFound as exc:
            self._error(404, str(exc))
        except (ValueError, TypeError, UnicodeError) as exc:
            self._error(400, str(exc))
        except sqlite3.Error:
            LOGGER.exception("Conversation store failed")
            self._error(503, "The conversation store is temporarily unavailable")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except TimeoutError:
            self._error(408, "Request body timed out")

    def log_message(self, format: str, *args: Any) -> None:
        # Avoid putting dietary terms, search queries, or session tokens in logs.
        LOGGER.info("%s %s", self.command, urlsplit(self.path).path)


def serve(store: KnowledgeBase, frontend_dir: Path, host: str = "127.0.0.1", port: int = 8000, allowed_origins: list[str] | None = None) -> None:
    server = RecipeServer((host, port), store, frontend_dir, allowed_origins)
    print(f"Recipe Atlas: http://{host}:{server.server_port} — {store.stats()['recipes']} indexed recipes", flush=True)
    print("API: /api/v1/health · /facets · /recipes · /chat. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped.")
    finally:
        server.server_close()
