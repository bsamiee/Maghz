#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["httpx"]
# ///
"""Tavily AI CLI -- web search, extraction, crawling, and research via REST API.

Commands:
    search   --query TEXT [--topic general|news] [--search-depth basic|advanced] [--max-results N]
    extract  --urls URL1,URL2 [--extract-depth basic|advanced] [--format markdown|text]
    crawl    --url URL [--max-depth N] [--max-breadth N] [--limit N]
    map      --url URL [--max-depth N] [--max-breadth N] [--limit N]
    research --query TEXT [--model mini|pro|auto]
"""
# LOC: 191

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import reduce
import json
import os
import sys
from typing import Final, Protocol

import httpx
from tavily_commands import crawl, extract, map_site, research, search


# --- [CONSTANTS] --------------------------------------------------------------
BASE: Final = "https://api.tavily.com"
KEY_ENV: Final = "TAVILY_API_KEY"
TIMEOUT: Final = 120
HELP: Final = __doc__ or ""
type JsonMap = dict[str, object]


class PostFn(Protocol):
    """HTTP POST boundary used by Tavily command rows."""

    def __call__(self, path: str, body: JsonMap, timeout: int = TIMEOUT) -> JsonMap:
        """Send one Tavily request.

        Returns:
            JSON object returned by Tavily.
        """
        ...


BOOL_FLAGS: Final = frozenset({"include_images", "include_image_descriptions", "include_raw_content", "include_favicon", "allow_external"})

INT_FLAGS: Final = frozenset({"max_results", "days", "max_depth", "max_breadth", "limit"})

REQUIRED: Final[dict[str, str]] = {"search": "query", "extract": "urls", "crawl": "url", "map": "url", "research": "query"}


# --- [FUNCTIONS] --------------------------------------------------------------
def _post(path: str, body: JsonMap, timeout: int = TIMEOUT) -> JsonMap:
    """POST JSON with API key.

    Returns:
        JSON object returned by Tavily.
    """
    body["api_key"] = os.environ.get(KEY_ENV, "")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{BASE}{path}", json=body)
        response.raise_for_status()
        match response.json():
            case Mapping() as data:
                return {str(key): value for key, value in data.items()}
            case _:
                return {}


@dataclass(frozen=True, slots=True, kw_only=True)
class _FlagState:
    """Immutable accumulator for flag parsing fold."""

    opts: JsonMap
    skip_next: bool


def _parse_flags(args: tuple[str, ...]) -> JsonMap:
    """Parse --flag value and --flag=value patterns via functional fold.

    Returns:
        Parsed flag map.
    """

    def _fold(state: _FlagState, indexed: tuple[int, str]) -> _FlagState:
        """Process a single argument in the fold.

        Returns:
            Updated flag parse state.
        """
        index, arg = indexed
        match (state.skip_next, arg.startswith("--")):
            case (True, _):
                return _FlagState(opts=state.opts, skip_next=False)
            case (_, True):
                raw = arg[2:].replace("-", "_")
                match raw.split("=", 1):
                    case [key, val]:
                        return _FlagState(opts={**state.opts, key: int(val) if key in INT_FLAGS else val}, skip_next=False)
                    case [key] if key in BOOL_FLAGS:
                        return _FlagState(opts={**state.opts, key: True}, skip_next=False)
                    case [key]:
                        next_index = index + 1
                        has_value = next_index < len(args) and not args[next_index].startswith("--")
                        value = args[next_index] if has_value else True
                        parsed = int(value) if key in INT_FLAGS and isinstance(value, str) else value
                        return _FlagState(opts={**state.opts, key: parsed}, skip_next=has_value)
                    case _:
                        return state
            case _:
                return state

    return reduce(_fold, enumerate(args), _FlagState(opts={}, skip_next=False)).opts


# --- [DISPATCH_TABLES] --------------------------------------------------------
COMMAND_TABLE: Final[dict[str, Callable[[JsonMap, PostFn], JsonMap]]] = {
    "search": search,
    "extract": extract,
    "crawl": crawl,
    "map": map_site,
    "research": research,
}


# --- [ENTRY_POINT] ------------------------------------------------------------
def main() -> int:
    """Dispatch command and print JSON output.

    Returns:
        Process exit code.
    """
    match sys.argv[1:]:
        case [command, *rest] if command in COMMAND_TABLE:
            opts = _parse_flags(tuple(rest))
            required_flag = REQUIRED[command]
            if required_flag not in opts:
                sys.stdout.write(f"[ERROR] Missing required: --{required_flag.replace('_', '-')}\n")
                return 1
            try:
                result = COMMAND_TABLE[command](opts, _post)
                sys.stdout.write(json.dumps(result, indent=2) + "\n")
                return 0 if result["status"] == "success" else 1
            except httpx.HTTPStatusError as error:
                sys.stdout.write(json.dumps({"status": "error", "code": error.response.status_code, "message": error.response.text[:200]}) + "\n")
                return 1
            except httpx.RequestError as error:
                sys.stdout.write(json.dumps({"status": "error", "message": str(error)}) + "\n")
                return 1
        case [command, *_]:
            sys.stdout.write(f"[ERROR] Unknown command '{command}'\n\n")
            sys.stdout.write(HELP + "\n")
            return 1
        case _:
            sys.stdout.write(HELP + "\n")
            return 1


if __name__ == "__main__":
    sys.exit(main())
