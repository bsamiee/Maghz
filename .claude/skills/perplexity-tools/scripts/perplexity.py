#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["httpx"]
# ///
"""Perplexity AI CLI — web research via REST API.

Commands:
    ask <query>                   Quick question with citations (sonar)
    pro <query>                   Deeper retrieval with 2x results (sonar-pro)
    research <query> [strip]      Deep research (sonar-deep-research, strip=strip thinking)
    reason <query> [strip]        Reasoning task (sonar-reasoning-pro, strip=strip thinking)
    search <query> [max] [country] Web search returning citations (default: 10)
"""

from collections.abc import Callable, Mapping
import json
import os
import re
import sys
from typing import Final

import httpx


# --- [CONSTANTS] --------------------------------------------------------------
BASE: Final = "https://api.perplexity.ai"
KEY_ENV: Final = "PERPLEXITY_API_KEY"
TIMEOUT: Final = 240
TIMEOUT_DEEP: Final = 600
MAX_RESULTS: Final = 10

MODEL_ASK: Final = "sonar"
MODEL_PRO: Final = "sonar-pro"
MODEL_RESEARCH: Final = "sonar-deep-research"
MODEL_REASON: Final = "sonar-reasoning-pro"
HELP: Final = __doc__ or ""

# --- [TYPES] ------------------------------------------------------------------
type JsonMap = dict[str, object]
type CommandEntry = tuple[Callable[[tuple[str, ...]], JsonMap], int, str, int]
type CommandRegistry = dict[str, CommandEntry]


# --- [FUNCTIONS] --------------------------------------------------------------
def _post(model: str, messages: list[JsonMap], timeout: int) -> JsonMap:
    """POST to chat completions endpoint.

    Returns:
        JSON object returned by the Perplexity API.
    """
    headers = {"Authorization": f"Bearer {os.environ.get(KEY_ENV, '')}", "Content-Type": "application/json"}
    body = {"model": model, "messages": messages}
    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{BASE}/chat/completions", headers=headers, json=body)
        response.raise_for_status()
        match response.json():
            case Mapping() as data:
                return {str(key): value for key, value in data.items()}
            case _:
                return {}


def _content(response: JsonMap) -> str:
    """Extract content from response.

    Returns:
        Message content string.
    """
    match response.get("choices"):
        case [{"message": {"content": content}}, *_]:
            return str(content)
        case _:
            return ""


def _citations(response: JsonMap) -> list[object]:
    """Extract citations from response.

    Returns:
        Citation rows.
    """
    match response.get("citations"):
        case list() as citations:
            return citations
        case _:
            return []


def _strip_think(content: str, should_strip: bool) -> str:
    """Remove <think> tags when requested.

    Returns:
        Content with optional thinking block removal applied.
    """
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip() if should_strip else content


# --- [COMMANDS] ---------------------------------------------------------------
def ask(query: str) -> JsonMap:
    """Quick question with citations.

    Returns:
        Answer envelope.
    """
    response = _post(MODEL_ASK, [{"role": "user", "content": query}], TIMEOUT)
    return {"status": "success", "query": query, "response": _content(response), "citations": _citations(response)}


def pro(query: str) -> JsonMap:
    """Deeper retrieval with enhanced search and 2x results.

    Returns:
        Pro answer envelope.
    """
    response = _post(MODEL_PRO, [{"role": "user", "content": query}], TIMEOUT)
    return {"status": "success", "query": query, "response": _content(response), "citations": _citations(response)}


def research(query: str, strip: str = "") -> JsonMap:
    """Deep research with optional thinking removal.

    Returns:
        Research answer envelope.
    """
    response = _post(MODEL_RESEARCH, [{"role": "user", "content": query}], TIMEOUT_DEEP)
    return {"status": "success", "query": query, "response": _strip_think(_content(response), strip == "strip"), "citations": _citations(response)}


def reason(query: str, strip: str = "") -> JsonMap:
    """Reasoning task with optional thinking removal.

    Returns:
        Reasoning answer envelope.
    """
    response = _post(MODEL_REASON, [{"role": "user", "content": query}], TIMEOUT_DEEP)
    return {"status": "success", "query": query, "response": _strip_think(_content(response), strip == "strip")}


def search(query: str, max_: str = "10", country: str = "") -> JsonMap:
    """Web search returning citations.

    Returns:
        Search result envelope.
    """
    prompt = f"Search: {query}" + (f" (focus: {country})" if country else "")
    response = _post(MODEL_ASK, [{"role": "user", "content": prompt}], TIMEOUT)
    return {"status": "success", "query": query, "results": _citations(response)[: int(max_)]}


# --- [DISPATCH] ---------------------------------------------------------------
CMDS: Final[CommandRegistry] = {
    "ask": (lambda args: ask(args[0]), 1, MODEL_ASK, TIMEOUT),
    "pro": (lambda args: pro(args[0]), 1, MODEL_PRO, TIMEOUT),
    "research": (lambda args: research(args[0], args[1] if len(args) > 1 else ""), 1, MODEL_RESEARCH, TIMEOUT_DEEP),
    "reason": (lambda args: reason(args[0], args[1] if len(args) > 1 else ""), 1, MODEL_REASON, TIMEOUT_DEEP),
    "search": (lambda args: search(args[0], args[1] if len(args) > 1 else "10", args[2] if len(args) > 2 else ""), 1, MODEL_ASK, TIMEOUT),
}


# --- [ENTRY_POINT] ------------------------------------------------------------
def main() -> int:
    """Dispatch command and print JSON output.

    Returns:
        Process exit code.
    """
    match sys.argv[1:]:
        case [cmd_name, *cmd_args] if entry := CMDS.get(cmd_name):
            fn, argc, _, _ = entry
            match cmd_args:
                case _ if len(cmd_args) < argc:
                    sys.stdout.write(f"Usage: perplexity.py {cmd_name} {' '.join(f'<arg{index + 1}>' for index in range(argc))}\n")
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
