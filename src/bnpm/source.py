from __future__ import annotations

from urllib.parse import ParseResult, urlparse

from .errors import BnpmError
from .models import SourceSpec


def parse_plugin(name: str, value: object) -> SourceSpec:
    if isinstance(value, str):
        return _parse_git_source(name, value)
    if isinstance(value, dict):
        return _parse_table(name, value)
    raise BnpmError(f"plugin {name!r} must be a string or table")


def _parse_table(name: str, value: dict[str, object]) -> SourceSpec:
    latest_tag = _read_optional_bool(value, "latest-version-tag")
    keys = [key for key in ("tag", "branch", "rev") if value.get(key)]
    if latest_tag:
        keys.append("latest-version-tag")
    if len(keys) > 1:
        raise BnpmError(
            f"plugin {name!r} can only set one of tag, branch, rev, latest-version-tag"
        )

    tag = _read_optional_str(name, value, "tag")
    branch = _read_optional_str(name, value, "branch")
    rev = _read_optional_str(name, value, "rev")

    if "path" in value:
        path = _read_required_str(name, value, "path")
        if "git" in value:
            raise BnpmError(f"plugin {name!r} cannot set both git and path")
        if keys:
            raise BnpmError(
                f"path plugin {name!r} cannot set tag, branch, rev, or latest-version-tag"
            )
        return SourceSpec(name=name, kind="path", path=path)

    git = _read_required_str(name, value, "git")
    return SourceSpec(
        name=name,
        kind="git",
        git=_normalize_git_url(git),
        tag=tag,
        branch=branch,
        rev=rev,
        latest_tag=latest_tag,
    )


def _parse_git_source(name: str, source: str) -> SourceSpec:
    if source.startswith("http://"):
        raise BnpmError(f"insecure git URL {source!r}; use https://")
    if source.startswith(("https://", "git@")):
        return SourceSpec(name=name, kind="git", git=_normalize_git_url(source))

    parsed = urlparse("dummy://" + source)
    _reject_url_extra(source, parsed)
    _reject_inline_ref(source, parsed)
    clean = parsed.netloc + parsed.path
    parts = [part for part in clean.split("/") if part]
    if len(parts) != 3:
        raise BnpmError(f"unsupported plugin source {source!r}")

    git = f"https://{parts[0]}/{parts[1]}/{parts[2]}.git"
    return SourceSpec(name=name, kind="git", git=git)


def _normalize_git_url(value: str) -> str:
    if value.startswith(("https://", "http://")):
        if value.startswith("http://"):
            raise BnpmError(f"insecure git URL {value!r}; use https://")
        parsed = urlparse(value)
        _reject_url_extra(value, parsed)
        _reject_inline_ref(value, parsed)
    if value.startswith("github.com/"):
        suffix = "" if value.endswith(".git") else ".git"
        return f"https://{value}{suffix}"
    if value.startswith(("https://", "git@")):
        return value
    raise BnpmError(f"unsupported git URL {value!r}")


def _reject_url_extra(source: str, parsed: ParseResult) -> None:
    if parsed.query:
        raise BnpmError(f"query strings are not supported in plugin source {source!r}")
    if parsed.fragment:
        raise BnpmError(f"fragments are not supported in plugin source {source!r}")


def _reject_inline_ref(source: str, parsed: ParseResult) -> None:
    if "@" in parsed.path:
        raise BnpmError(f"inline refs are not supported in plugin source {source!r}")


def _read_required_str(name: str, table: dict[str, object], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise BnpmError(f"plugin {name!r} requires string field {key!r}")
    return value


def _read_optional_str(name: str, table: dict[str, object], key: str) -> str | None:
    if key not in table:
        return None
    return _read_required_str(name, table, key)


def _read_optional_bool(table: dict[str, object], key: str) -> bool:
    value = table.get(key, False)
    if not isinstance(value, bool):
        raise BnpmError(f"field {key!r} must be a boolean")
    return value
