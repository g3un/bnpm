from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from .errors import SourceError


@dataclass(frozen=True)
class SourceSpec:
    name: str
    kind: str
    git: str | None = None
    path: str | None = None
    tag: str | None = None
    branch: str | None = None
    rev: str | None = None

    @property
    def version(self) -> str | None:
        if self.kind == "path":
            return None
        if self.tag:
            return f"tag:{self.tag}"
        if self.rev:
            return f"rev:{self.rev}"
        if self.branch:
            return f"branch:{self.branch}"
        return "HEAD"


def parse_plugin(name: str, value: object) -> SourceSpec:
    if isinstance(value, str):
        return _parse_shorthand(name, value)
    if isinstance(value, dict):
        return _parse_table(name, value)
    raise SourceError(f"plugin {name!r} must be a string or table")


def _parse_shorthand(name: str, value: str) -> SourceSpec:
    source, sep, ref = value.partition("@")
    spec = _parse_git_source(name, source)
    if sep:
        return SourceSpec(name=spec.name, kind=spec.kind, git=spec.git, tag=ref)
    return spec


def _parse_table(name: str, value: dict[str, object]) -> SourceSpec:
    keys = [key for key in ("tag", "branch", "rev") if value.get(key)]
    if len(keys) > 1:
        raise SourceError(f"plugin {name!r} can only set one of tag, branch, rev")

    tag = _optional_str(name, value, "tag")
    branch = _optional_str(name, value, "branch")
    rev = _optional_str(name, value, "rev")

    if "path" in value:
        path = _required_str(name, value, "path")
        if "git" in value:
            raise SourceError(f"plugin {name!r} cannot set both git and path")
        if keys:
            raise SourceError(f"path plugin {name!r} cannot set tag, branch, or rev")
        return SourceSpec(name=name, kind="path", path=path)

    git = _required_str(name, value, "git")
    return SourceSpec(name=name, kind="git", git=_normalize_git_url(git), tag=tag, branch=branch, rev=rev)


def _parse_git_source(name: str, source: str) -> SourceSpec:
    if source.startswith(("http://", "https://", "git@")):
        return SourceSpec(name=name, kind="git", git=_normalize_git_url(source))

    parsed = urlparse("dummy://" + source)
    query = parse_qs(parsed.query)
    clean = parsed.netloc + parsed.path
    parts = [part for part in clean.split("/") if part]
    if len(parts) != 3:
        raise SourceError(f"unsupported plugin source {source!r}")

    git = f"https://{parts[0]}/{parts[1]}/{parts[2]}.git"
    refs = {key: query[key][0] for key in ("tag", "branch", "rev") if key in query}
    if len(refs) > 1:
        raise SourceError(f"source {source!r} can only set one of tag, branch, rev")
    return SourceSpec(name=name, kind="git", git=git, **refs)


def _normalize_git_url(value: str) -> str:
    if value.startswith("github.com/"):
        return f"https://{value}.git"
    if value.startswith(("https://", "http://", "git@")):
        return value
    raise SourceError(f"unsupported git URL {value!r}")


def _required_str(name: str, table: dict[str, object], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise SourceError(f"plugin {name!r} requires string field {key!r}")
    return value


def _optional_str(name: str, table: dict[str, object], key: str) -> str | None:
    if key not in table:
        return None
    return _required_str(name, table, key)
