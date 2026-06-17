#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    check_only = sys.argv[1:] == ["--check-tag"]
    if sys.argv[1:] and not check_only:
        fail("usage: create_forgejo_release.py [--check-tag]")

    project = read_project_metadata()
    package_name = project["name"]
    version = project["version"]
    prerelease = "-" in version
    tag_name = resolve_tag_name()

    if not tag_name:
        fail("GITHUB_REF_NAME, FORGEJO_REF_NAME, or a tag ref is required.")
    if tag_name != f"v{version}":
        fail(f"Tag must match project version. Tag: {tag_name}; expected: v{version}")
    if check_only:
        print(f"Release tag matches project version: {tag_name}")
        return

    server_url = trim_trailing_slash(
        os.environ.get("FORGEJO_SERVER_URL")
        or os.environ.get("GITHUB_SERVER_URL")
        or "https://codeberg.org"
    )
    repository = os.environ.get("FORGEJO_REPOSITORY") or os.environ.get(
        "GITHUB_REPOSITORY"
    )
    token = os.environ.get("FORGEJO_TOKEN") or os.environ.get("GITHUB_TOKEN")

    if not repository:
        fail("FORGEJO_REPOSITORY or GITHUB_REPOSITORY is required.")
    if not token:
        fail("FORGEJO_TOKEN or GITHUB_TOKEN is required.")

    encoded_repository = "/".join(
        quote(part, safe="") for part in repository.split("/")
    )
    release_by_tag_url = (
        f"{server_url}/api/v1/repos/{encoded_repository}/releases/tags/"
        f"{quote(tag_name, safe='')}"
    )
    releases_url = f"{server_url}/api/v1/repos/{encoded_repository}/releases"

    existing_release = request(release_by_tag_url, token, method="GET")
    if existing_release.status == 200:
        release = json.loads(existing_release.body)
        print(f"Forgejo release already exists: {release.get('html_url') or tag_name}")
        return
    if existing_release.status != 404:
        fail_response("Failed to check existing Forgejo release", existing_release)

    create_release = request(
        releases_url,
        token,
        method="POST",
        body={
            "tag_name": tag_name,
            "name": tag_name,
            "body": f"Published {package_name}@{version} to PyPI.",
            "draft": False,
            "prerelease": prerelease,
        },
    )
    if create_release.status == 201:
        release = json.loads(create_release.body)
        print(f"Created Forgejo release: {release.get('html_url') or tag_name}")
        return
    if create_release.status == 409:
        print(f"Forgejo release already exists for {tag_name}.")
        return
    fail_response("Failed to create Forgejo release", create_release)


def read_project_metadata() -> dict[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as file:
        data = tomllib.load(file)
    project = data.get("project")
    if not isinstance(project, dict):
        fail("pyproject.toml must contain a [project] table.")
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        fail("pyproject.toml [project] must contain name and version strings.")
    return {"name": name, "version": version}


class Response:
    def __init__(self, status: int, reason: str, body: str) -> None:
        self.status = status
        self.reason = reason
        self.body = body


def request(url: str, token: str, *, method: str, body: dict | None = None) -> Response:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": f"token {token}",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    forgejo_request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(forgejo_request) as response:
            return Response(
                response.status,
                response.reason,
                response.read().decode("utf-8", errors="replace"),
            )
    except HTTPError as error:
        return Response(
            error.code,
            error.reason,
            error.read().decode("utf-8", errors="replace"),
        )


def resolve_tag_name() -> str | None:
    return (
        os.environ.get("GITHUB_REF_NAME")
        or os.environ.get("FORGEJO_REF_NAME")
        or parse_tag_name(os.environ.get("GITHUB_REF"))
        or parse_tag_name(os.environ.get("FORGEJO_REF"))
    )


def parse_tag_name(ref: str | None) -> str | None:
    prefix = "refs/tags/"
    return ref[len(prefix) :] if ref and ref.startswith(prefix) else None


def trim_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def fail_response(message: str, response: Response) -> None:
    fail(f"{message}: HTTP {response.status} {response.reason}\n{response.body}")


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
