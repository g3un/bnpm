from __future__ import annotations

from urllib.parse import ParseResult, urlparse

from .errors import SourceError
from .models import SourceSpec


def parse_plugin(name: str, value: object) -> SourceSpec:
    if isinstance(value, str):
        return _parse_git_source(name, value)
    if isinstance(value, dict):
        return _parse_table(name, value)
    raise SourceError(f"plugin {name!r} must be a string or table")


def _parse_table(name: str, value: dict[str, object]) -> SourceSpec:
    keys = [key for key in ("tag", "branch", "rev") if value.get(key)]
    if len(keys) > 1:
        raise SourceError(f"plugin {name!r} can only set one of tag, branch, rev")

    tag = _read_optional_str(name, value, "tag")
    branch = _read_optional_str(name, value, "branch")
    rev = _read_optional_str(name, value, "rev")

    if "path" in value:
        path = _read_required_str(name, value, "path")
        if "git" in value:
            raise SourceError(f"plugin {name!r} cannot set both git and path")
        if keys:
            raise SourceError(f"path plugin {name!r} cannot set tag, branch, or rev")
        return SourceSpec(name=name, kind="path", path=path)

    git = _read_required_str(name, value, "git")
    return SourceSpec(name=name, kind="git", git=_normalize_git_url(git), tag=tag, branch=branch, rev=rev)


def _parse_git_source(name: str, source: str) -> SourceSpec:
    if source.startswith(("http://", "https://", "git@")):
        return SourceSpec(name=name, kind="git", git=_normalize_git_url(source))

    parsed = urlparse("dummy://" + source)
    _reject_url_extra(source, parsed)
    _reject_inline_ref(source, parsed)
    clean = parsed.netloc + parsed.path
    parts = [part for part in clean.split("/") if part]
    if len(parts) != 3:
        raise SourceError(f"unsupported plugin source {source!r}")

    git = f"https://{parts[0]}/{parts[1]}/{parts[2]}.git"
    return SourceSpec(name=name, kind="git", git=git)


def _normalize_git_url(value: str) -> str:
    if value.startswith(("https://", "http://")):
        parsed = urlparse(value)
        _reject_url_extra(value, parsed)
        _reject_inline_ref(value, parsed)
    if value.startswith("github.com/"):
        return f"https://{value}.git"
    if value.startswith(("https://", "http://", "git@")):
        return value
    raise SourceError(f"unsupported git URL {value!r}")


def _reject_url_extra(source: str, parsed: ParseResult) -> None:
    if parsed.query:
        raise SourceError(f"query strings are not supported in plugin source {source!r}")
    if parsed.fragment:
        raise SourceError(f"fragments are not supported in plugin source {source!r}")


def _reject_inline_ref(source: str, parsed: ParseResult) -> None:
    if "@" in parsed.path:
        raise SourceError(f"inline refs are not supported in plugin source {source!r}")


def _read_required_str(name: str, table: dict[str, object], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise SourceError(f"plugin {name!r} requires string field {key!r}")
    return value


def _read_optional_str(name: str, table: dict[str, object], key: str) -> str | None:
    if key not in table:
        return None
    return _read_required_str(name, table, key)

