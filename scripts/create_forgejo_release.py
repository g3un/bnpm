#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<date>\d{8})\.(?P<patch>0|[1-9]\d*)$"
)


@dataclass(frozen=True)
class Response:
    status: int
    reason: str
    body: bytes

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> dict:
        return json.loads(self.text())


def main() -> None:
    check_only = sys.argv[1:] == ["--check-tag"]
    if sys.argv[1:] and not check_only:
        fail("usage: create_forgejo_release.py [--check-tag]")

    project = read_project(ROOT / "pyproject.toml")
    package_name = project["name"]
    version = project["version"]
    validate_version(version)

    tag_name = require_env("FORGEJO_REF_NAME")
    expected_tag_name = f"v{version}"
    if tag_name != expected_tag_name:
        fail(
            f"Tag must match pyproject.toml version. Tag: {tag_name}; "
            f"expected: {expected_tag_name}"
        )
    if check_only:
        print(f"Release tag matches pyproject.toml version: {tag_name}")
        return

    server_url = trim_trailing_slash(require_env("FORGEJO_SERVER_URL"))
    repository = require_env("FORGEJO_REPOSITORY")
    token = require_env("FORGEJO_TOKEN")

    encoded_repository = "/".join(
        quote(part, safe="") for part in repository.split("/")
    )
    encoded_tag = quote(tag_name, safe="")
    release_by_tag_url = (
        f"{server_url}/api/v1/repos/{encoded_repository}/releases/tags/{encoded_tag}"
    )
    releases_url = f"{server_url}/api/v1/repos/{encoded_repository}/releases"

    existing_release = request(release_by_tag_url, token, method="GET")
    if existing_release.status == 200:
        release = existing_release.json()
        print(f"Forgejo release already exists: {release.get('html_url') or tag_name}")
        return
    if existing_release.status != 404:
        fail_response("Failed to check existing Forgejo release", existing_release)

    create_release = request(
        releases_url,
        token,
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps(
            {
                "tag_name": tag_name,
                "name": tag_name,
                "body": f"Source release for {package_name}@{version}.",
                "draft": False,
                "prerelease": False,
            }
        ).encode(),
    )
    if create_release.status == 201:
        release = create_release.json()
        print(f"Created Forgejo release: {release.get('html_url') or tag_name}")
        return
    if create_release.status == 409:
        print(f"Forgejo release already exists for {tag_name}.")
        return

    fail_response("Failed to create Forgejo release", create_release)


def validate_version(version: str) -> None:
    match = VERSION_PATTERN.fullmatch(version)
    if not match:
        fail(
            "pyproject.toml version must use {major}.YYYYMMDD.{patch} "
            f"with release tag v{{major}}.YYYYMMDD.{{patch}}; got: {version}"
        )
    date = match.group("date")
    try:
        datetime.strptime(date, "%Y%m%d")
    except ValueError:
        fail(f"pyproject.toml version date must be a valid YYYYMMDD date; got: {date}")


def read_project(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    in_project = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            continue
        if not in_project:
            continue
        key, sep, raw_value = line.partition("=")
        key = key.strip()
        if not sep or key not in {"name", "version"}:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            data[key] = value[1:-1]
    missing = {"name", "version"} - data.keys()
    if missing:
        fail(f"pyproject.toml is missing [project] {', '.join(sorted(missing))}.")
    return data


def request(
    url: str,
    token: str,
    *,
    method: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> Response:
    req = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": f"token {token}",
            **(headers or {}),
        },
    )
    try:
        with urlopen(req, timeout=30) as res:  # noqa: S310
            return Response(res.status, res.reason, res.read())
    except HTTPError as exc:
        return Response(exc.code, exc.reason, exc.read())


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"{name} is required.")
    return value


def trim_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def fail_response(message: str, response: Response) -> None:
    fail(f"{message}: HTTP {response.status} {response.reason}\n{response.text()}")


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
