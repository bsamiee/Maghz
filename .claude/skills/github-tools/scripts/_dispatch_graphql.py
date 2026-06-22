# ruff: noqa: ARG005
"""GraphQL dispatch handlers for GitHub CLI discussion workflows."""

from collections.abc import Callable, Mapping
import json
from typing import Final


type JsonValue = object
type JsonMap = dict[str, JsonValue]
type Args = dict[str, str]
type Handler = tuple[Callable[[Args], tuple[str, ...]], Callable[[str, Args], JsonMap]]


def _json(output: str) -> JsonValue:
    """Parse JSON output, returning an empty object for empty strings.

    Returns:
        Parsed JSON value.
    """
    data: object = json.loads(output) if output else {}
    return data


def _json_map(output: str) -> JsonMap:
    """Parse JSON output as an object.

    Returns:
        Parsed JSON object, or an empty object when output is not an object.
    """
    match _json(output):
        case Mapping() as data:
            return {str(key): value for key, value in data.items()}
        case _:
            return {}


def _path(value: object, *keys: str) -> object:
    """Project a nested JSON object path.

    Returns:
        Nested value, or an empty object when the path is absent.
    """
    match keys:
        case ():
            return value
        case (head, *tail):
            match value:
                case Mapping() as data:
                    return _path(data.get(head, {}), *tail)
                case _:
                    return {}
        case _:
            return {}


def _repo_vars() -> tuple[str, ...]:
    """Get GraphQL owner/repo vars for current repo.

    Returns:
        `gh api graphql` variable flags for owner and repo.
    """
    from gh import run_command

    ok, out = run_command(("gh", "repo", "view", "--json=owner,name"))
    data = _json_map(out) if ok else {}
    return ("-f", f"owner={_path(data, 'owner', 'login')}", "-f", f"repo={data.get('name', '')}")


def _repo_id() -> str:
    """Get repository node ID.

    Returns:
        Repository GraphQL node ID, or an empty string.
    """
    from gh import run_command

    ok, out = run_command(("gh", "repo", "view", "--json=id"))
    return str(_json_map(out).get("id", "")) if ok else ""


DISCUSSION_LIST_QUERY: Final = (
    "query=query($owner:String!,$repo:String!,$limit:Int!)"
    "{repository(owner:$owner,name:$repo)"
    "{discussions(first:$limit)"
    "{nodes{number title author{login}category{name}createdAt isAnswered}}}}"
)
DISCUSSION_VIEW_QUERY: Final = (
    "query=query($owner:String!,$repo:String!,$num:Int!)"
    "{repository(owner:$owner,name:$repo)"
    "{discussion(number:$num)"
    "{id number title body author{login}category{name}createdAt "
    "answer{body author{login}}comments(first:50){nodes{id body author{login}}}}}}"
)
DISCUSSION_CATEGORY_LIST_QUERY: Final = (
    "query=query($owner:String!,$repo:String!)"
    "{repository(owner:$owner,name:$repo)"
    "{discussionCategories(first:25){nodes{id name emoji description isAnswerable}}}}"
)
DISCUSSION_CREATE_MUTATION: Final = (
    "query=mutation($repoId:ID!,$catId:ID!,$title:String!,$body:String!)"
    "{createDiscussion(input:{repositoryId:$repoId,categoryId:$catId,title:$title,body:$body})"
    "{discussion{id number url}}}"
)


GRAPHQL_CMDS: Final[dict[str, tuple[tuple[str, ...], tuple[str, ...], Handler]]] = {
    # --- Discussions (GraphQL) ---
    "discussion-list": (
        (),
        ("limit",),
        (
            lambda a: ("gh", "api", "graphql", "-f", DISCUSSION_LIST_QUERY, *_repo_vars(), "-F", f"limit={a.get('limit', '30')}"),
            lambda o, a: {"discussions": _path(_json_map(o), "data", "repository", "discussions", "nodes")},
        ),
    ),
    "discussion-view": (
        ("number",),
        (),
        (
            lambda a: ("gh", "api", "graphql", "-f", DISCUSSION_VIEW_QUERY, *_repo_vars(), "-F", f"num={a['number']}"),
            lambda o, a: {"number": a["number"], "discussion": _path(_json_map(o), "data", "repository", "discussion")},
        ),
    ),
    "discussion-category-list": (
        (),
        (),
        (
            lambda a: ("gh", "api", "graphql", "-f", DISCUSSION_CATEGORY_LIST_QUERY, *_repo_vars()),
            lambda o, a: {"categories": _path(_json_map(o), "data", "repository", "discussionCategories", "nodes")},
        ),
    ),
    "discussion-create": (
        ("category_id", "title", "body"),
        (),
        (
            lambda a: (
                "gh",
                "api",
                "graphql",
                "-f",
                DISCUSSION_CREATE_MUTATION,
                "-f",
                f"repoId={_repo_id()}",
                "-f",
                f"catId={a['category_id']}",
                "-f",
                f"title={a['title']}",
                "-f",
                f"body={a['body']}",
            ),
            lambda o, a: {"created": _path(_json_map(o), "data", "createDiscussion", "discussion")},
        ),
    ),
    "discussion-comment": (
        ("discussion_id", "body"),
        ("reply_to",),
        (
            lambda a: (
                "gh",
                "api",
                "graphql",
                "-f",
                (
                    "query=mutation($id:ID!,$body:String!,$replyToId:ID!){addDiscussionComment(input:{discussionId:$id,body:$body,replyToId:$replyToId}){comment{id}}}"
                    if a.get("reply_to")
                    else "query=mutation($id:ID!,$body:String!){addDiscussionComment(input:{discussionId:$id,body:$body}){comment{id}}}"
                ),
                "-f",
                f"id={a['discussion_id']}",
                "-f",
                f"body={a['body']}",
                *(("-f", f"replyToId={a['reply_to']}") if a.get("reply_to") else ()),
            ),
            lambda o, a: {"discussion_id": a["discussion_id"], "commented": True},
        ),
    ),
    "discussion-close": (
        ("discussion_id",),
        ("reason",),
        (
            lambda a: (
                "gh",
                "api",
                "graphql",
                "-f",
                (
                    "query=mutation($id:ID!,$reason:DiscussionCloseReason){closeDiscussion(input:{discussionId:$id,reason:$reason}){discussion{id}}}"
                    if a.get("reason")
                    else "query=mutation($id:ID!){closeDiscussion(input:{discussionId:$id}){discussion{id}}}"
                ),
                "-f",
                f"id={a['discussion_id']}",
                *(("-f", f"reason={a['reason']}") if a.get("reason") else ()),
            ),
            lambda o, a: {"discussion_id": a["discussion_id"], "closed": True, "reason": a.get("reason")},
        ),
    ),
    "discussion-delete": (
        ("discussion_id",),
        (),
        (
            lambda a: (
                "gh",
                "api",
                "graphql",
                "-f",
                "query=mutation($id:ID!){deleteDiscussion(input:{id:$id}){discussion{id}}}",
                "-f",
                f"id={a['discussion_id']}",
            ),
            lambda o, a: {"discussion_id": a["discussion_id"], "deleted": True},
        ),
    ),
}
