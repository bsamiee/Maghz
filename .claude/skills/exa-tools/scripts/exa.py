#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["httpx"]
# ///
"""Exa AI CLI — semantic web search via REST API.

Commands:
    search <query> [type] [num]   Web search (type: auto|neural|keyword|fast|deep, default: auto 8)
    code <query> [num]            Code search via GitHub (default: 10 results)
    find-similar <url> [num]      Find pages similar to URL (default: 10 results)
    answer <query>                AI-generated answer with citations
"""

from collections.abc import Callable, Mapping
import json
import os
import sys
from typing import Final

import httpx


# --- [CONSTANTS] --------------------------------------------------------------
BASE: Final = "https://api.exa.ai"
KEY_ENV: Final = "EXA_API_KEY"
TIMEOUT: Final = 60
TIMEOUT_ANSWER: Final = 240
MAX_CHARS: Final = 10000
VALID_TYPES: Final = frozenset({"auto", "neural", "keyword", "fast", "deep"})
HELP: Final = __doc__ or ""

# --- [TYPES] ------------------------------------------------------------------
type JsonMap = dict[str, object]
type CommandEntry = tuple[Callable[[tuple[str, ...]], JsonMap], int]
type CommandRegistry = dict[str, CommandEntry]


# --- [FUNCTIONS] --------------------------------------------------------------
def _post(path: str, body: JsonMap, timeout: int = TIMEOUT) -> JsonMap:
    """POST JSON with API key auth.

    Returns:
        JSON object returned by the Exa API.
    """
    headers = {"x-api-key": os.environ.get(KEY_ENV, ""), "Content-Type": "application/json"}
    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{BASE}{path}", headers=headers, json=body)
        response.raise_for_status()
        match response.json():
            case Mapping() as data:
                return {str(key): value for key, value in data.items()}
            case _:
                return {}


def _search_body(query: str, num: int, type_: str, category: str | None = None) -> JsonMap:
    """Build search request body.

    Returns:
        Request JSON body.
    """
    body: JsonMap = {"query": query, "numResults": num, "type": type_, "contents": {"text": True}}
    return {**body, "category": category} if category else body


# --- [COMMANDS] ---------------------------------------------------------------
def search(query: str, type_: str = "auto", num: str = "8") -> JsonMap:
    """Web search with text content retrieval.

    Returns:
        Search result envelope.
    """
    match type_:
        case t if t in VALID_TYPES:
            data = _post("/search", _search_body(query, int(num), t))
            return {"status": "success", "query": query, "results": data.get("results", [])}
        case invalid:
            return {"status": "error", "message": f"Invalid type '{invalid}'. Use: {', '.join(sorted(VALID_TYPES))}"}


def code(query: str, num: str = "10") -> JsonMap:
    """Code context search via GitHub category.

    Returns:
        Code search result envelope.
    """
    data = _post("/search", _search_body(query, int(num), "auto", "github"))
    return {"status": "success", "query": query, "context": data.get("results", [])}


def find_similar(url: str, num: str = "10") -> JsonMap:
    """Find pages similar in meaning to the given URL.

    Returns:
        Similar-page result envelope.
    """
    body: JsonMap = {"url": url, "numResults": int(num), "contents": {"text": True}}
    data = _post("/findSimilar", body)
    return {"status": "success", "url": url, "results": data.get("results", [])}


def answer(query: str) -> JsonMap:
    """AI-generated answer with web sources.

    Returns:
        Answer result envelope.
    """
    body: JsonMap = {"query": query, "text": True}
    data = _post("/answer", body, TIMEOUT_ANSWER)
    return {"status": "success", "query": query, "answer": data.get("answer", ""), "sources": data.get("results", [])}


# --- [DISPATCH] ---------------------------------------------------------------
CMDS: Final[CommandRegistry] = {
    "search": (lambda args: search(args[0], args[1] if len(args) > 1 else "auto", args[2] if len(args) > 2 else "8"), 1),
    "code": (lambda args: code(args[0], args[1] if len(args) > 1 else "10"), 1),
    "find-similar": (lambda args: find_similar(args[0], args[1] if len(args) > 1 else "10"), 1),
    "answer": (lambda args: answer(args[0]), 1),
}


# --- [ENTRY_POINT] ------------------------------------------------------------
def main() -> int:
    """Dispatch command and print JSON output.

    Returns:
        Process exit code.
    """
    match sys.argv[1:]:
        case [cmd_name, *cmd_args] if entry := CMDS.get(cmd_name):
            fn, argc = entry
            match cmd_args:
                case _ if len(cmd_args) < argc:
                    sys.stdout.write(f"Usage: exa.py {cmd_name} {' '.join(f'<arg{index + 1}>' for index in range(argc))}\n")
                    return 1
                case _:
                    try:
                        result = fn(tuple(cmd_args[: argc + 2]))
                        sys.stdout.write(json.dumps(result, indent=2) + "\n")
                        return 0 if result["status"] == "success" else 1
                    except httpx.HTTPStatusError as error:
                        sys.stdout.write(
                            json.dumps({"status": "error", "code": error.response.status_code, "message": error.response.text[:200]}) + "\n"
                        )
                        return 1
                    except httpx.RequestError as error:
                        sys.stdout.write(json.dumps({"status": "error", "message": str(error)}) + "\n")
                        return 1
        case [cmd_name, *_]:
            sys.stdout.write(f"[ERROR] Unknown command '{cmd_name}'\n\n")
            sys.stdout.write(HELP + "\n")
            return 1
        case _:
            sys.stdout.write(HELP + "\n")
            return 1


if __name__ == "__main__":
    sys.exit(main())
