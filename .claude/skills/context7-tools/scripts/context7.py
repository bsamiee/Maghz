#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["httpx"]
# ///
"""Context7 CLI — library documentation via REST API.

Commands:
    resolve <library> [query]     List matching library IDs (JSON)
    docs <library-id> <query>     Fetch documentation (plain text)
    lookup <library> <query>      Resolve + fetch in one call (plain text)
"""

from collections.abc import Callable, Mapping
import json
import os
import sys
from typing import Final
from urllib.parse import quote

import httpx


# --- [CONSTANTS] --------------------------------------------------------------
BASE: Final = "https://context7.com"
KEY_ENV: Final = "CONTEXT7_API_KEY"
TIMEOUT: Final = 60
TOKENS: Final = 15000
HELP: Final = __doc__ or ""

# --- [TYPES] ------------------------------------------------------------------
type JsonMap = dict[str, object]
type CommandEntry = tuple[Callable[[tuple[str, ...]], str], int]
type CommandRegistry = dict[str, CommandEntry]


# --- [FUNCTIONS] --------------------------------------------------------------
def _get(path: str) -> JsonMap | str:
    """GET with optional bearer auth.

    Returns:
        JSON object for JSON responses, or response text for other content types.
    """
    headers = {"Authorization": f"Bearer {token}"} if (token := os.environ.get(KEY_ENV)) else {}
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(f"{BASE}{path}", headers=headers)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        match "json" in content_type:
            case True:
                match response.json():
                    case Mapping() as data:
                        return {str(key): value for key, value in data.items()}
                    case _:
                        return {}
            case False:
                return response.text


def _search(lib: str, query: str = "") -> list[JsonMap]:
    """Search libraries.

    Returns:
        Raw library matches returned by Context7.
    """
    query_param = f"&query={quote(query)}" * bool(query)
    match _get(f"/api/v2/libs/search?libraryName={quote(lib)}{query_param}"):
        case Mapping() as data:
            raw = data.get("results", data.get("libraries", [])) or []
            match raw:
                case list() as items:
                    return [{str(key): value for key, value in item.items()} for item in items if isinstance(item, Mapping)]
                case _:
                    return []
        case _:
            return []


def _pick(matches: list[JsonMap]) -> JsonMap | None:
    """Select best match: VIP first, then highest benchmark score.

    Returns:
        Best match when one exists.
    """
    return next((match for match in matches if match.get("vip")), max(matches, key=_score, default=None))


def _score(match: JsonMap) -> float:
    """Project a library match to its benchmark score.

    Returns:
        Numeric benchmark score, or zero when absent or malformed.
    """
    match match.get("benchmarkScore"):
        case int() | float() as score:
            return float(score)
        case _:
            return 0.0


# --- [COMMANDS] ---------------------------------------------------------------
def resolve(lib: str, query: str = "") -> str:
    """Resolve library to matching IDs with scores.

    Returns:
        JSON text with matching library IDs.
    """
    return json.dumps(
        [
            {"id": match["id"], "title": match.get("title", ""), "score": match.get("benchmarkScore", 0), "vip": match.get("vip", False)}
            for match in _search(lib, query)[:5]
        ],
        indent=2,
    )


def docs(lib_id: str, query: str) -> str:
    """Fetch documentation for library ID.

    Returns:
        Plain text documentation.
    """
    lid = lib_id if lib_id.startswith("/") else f"/{lib_id}"
    match _get(f"/api/v2/context?libraryId={quote(lid)}&query={quote(query)}&tokens={TOKENS}"):
        case str(text):
            return f"[{lid}]\n\n{text}"
        case data:
            return json.dumps(data)


def lookup(lib: str, query: str) -> str:
    """Resolve library and fetch documentation.

    Returns:
        Plain text documentation, or an error message.
    """
    match _pick(_search(lib, query)):
        case {"id": lib_id}:
            return docs(str(lib_id), query)
        case _:
            return f"[ERROR] No library found for '{lib}'"


# --- [DISPATCH] ---------------------------------------------------------------
CMDS: Final[CommandRegistry] = {
    "resolve": (lambda args: resolve(args[0], args[1] if len(args) > 1 else ""), 1),
    "docs": (lambda args: docs(args[0], args[1]), 2),
    "lookup": (lambda args: lookup(args[0], args[1]), 2),
}


# --- [ENTRY_POINT] ------------------------------------------------------------
def main() -> int:
    """Dispatch command and print output.

    Returns:
        Process exit code.
    """
    match sys.argv[1:]:
        case [cmd_name, *cmd_args] if entry := CMDS.get(cmd_name):
            fn, argc = entry
            match cmd_args:
                case _ if len(cmd_args) < argc:
                    sys.stdout.write(f"Usage: context7.py {cmd_name} {' '.join(f'<arg{index + 1}>' for index in range(argc))}\n")
                    return 1
                case _:
                    try:
                        sys.stdout.write(fn(tuple(cmd_args[: argc + 1])) + "\n")
                        return 0
                    except httpx.HTTPStatusError as error:
                        sys.stdout.write(f"[ERROR] {error.response.status_code}: {error.response.text[:200]}\n")
                        return 1
                    except httpx.RequestError as error:
                        sys.stdout.write(f"[ERROR] {error}\n")
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
