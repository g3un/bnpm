from __future__ import annotations

from dataclasses import replace
import re

from .models import LockedPackage, LockedPlugin


REQ_NAME_RE = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def lock_dependencies(
    plugins: list[LockedPlugin],
    packages: list[LockedPackage],
) -> tuple[list[LockedPlugin], list[LockedPackage]]:
    pins = {_normalize_name(package.name): _format_pin(package) for package in packages}
    locked_plugins = [
        replace(
            plugin,
            dependencies=_resolve_pins(plugin.requirements or [], pins),
            requirements=None,
        )
        for plugin in plugins
    ]
    locked_packages = [
        replace(package, dependencies=_resolve_pins(package.dependencies or [], pins))
        for package in packages
    ]
    return locked_plugins, locked_packages


def _resolve_pins(requirements: list[str], pins: dict[str, str]) -> list[str]:
    resolved = []
    for requirement in requirements:
        name = _parse_requirement_name(requirement)
        if name is None:
            continue
        pin = pins.get(_normalize_name(name))
        if pin is not None:
            resolved.append(pin)
    return sorted(set(resolved))


def _parse_requirement_name(requirement: str) -> str | None:
    match = REQ_NAME_RE.match(requirement)
    if match is None:
        return None
    return match.group(1)


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _format_pin(package: LockedPackage) -> str:
    version = package.version.removeprefix("pypi:")
    return f"{package.name}=={version}"
