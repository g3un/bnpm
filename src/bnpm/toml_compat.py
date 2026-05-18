from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore[assignment]


def load_toml(path: Path) -> dict[str, Any]:
    if tomllib is not None:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    return _parse_subset(path.read_text(encoding="utf-8"))


def _parse_subset(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current: dict[str, Any] = data
    current_array: list[dict[str, Any]] | None = None

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line:
            continue

        if line.startswith("[[") and line.endswith("]]"):
            name = line[2:-2].strip()
            if not name:
                raise ValueError("empty TOML array table name")
            array = data.setdefault(name, [])
            if not isinstance(array, list):
                raise ValueError(f"TOML key {name!r} is not an array")
            table: dict[str, Any] = {}
            array.append(table)
            current = table
            current_array = array
            continue

        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if not name:
                raise ValueError("empty TOML table name")
            table = data.setdefault(name, {})
            if not isinstance(table, dict):
                raise ValueError(f"TOML key {name!r} is not a table")
            current = table
            current_array = None
            continue

        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"invalid TOML line: {raw_line}")
        key = key.strip()
        if not key:
            raise ValueError(f"invalid TOML key: {raw_line}")
        if current_array is None and key in current:
            raise ValueError(f"duplicate TOML key: {key}")
        current[key] = _parse_value(value.strip())

    return data


def _parse_value(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return _parse_string(value)
    if value.startswith("{") and value.endswith("}"):
        return _parse_inline_table(value)
    if value.isdigit():
        return int(value)
    raise ValueError(f"unsupported TOML value: {value}")


def _parse_inline_table(value: str) -> dict[str, Any]:
    inner = value[1:-1].strip()
    if not inner:
        return {}
    table: dict[str, Any] = {}
    for item in _split_commas(inner):
        key, sep, raw_value = item.partition("=")
        if not sep:
            raise ValueError(f"invalid inline TOML table item: {item}")
        key = key.strip()
        if key in table:
            raise ValueError(f"duplicate TOML inline table key: {key}")
        table[key] = _parse_value(raw_value.strip())
    return table


def _parse_string(value: str) -> str:
    result = []
    escaped = False
    for char in value[1:-1]:
        if escaped:
            escapes = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}
            result.append(escapes.get(char, char))
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            result.append(char)
    if escaped:
        raise ValueError("unterminated TOML string escape")
    return "".join(result)


def _split_commas(value: str) -> list[str]:
    items = []
    start = 0
    in_string = False
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if char == "," and not in_string:
            items.append(value[start:index].strip())
            start = index + 1
    items.append(value[start:].strip())
    return [item for item in items if item]


def _strip_comment(line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if char == "#" and not in_string:
            return line[:index]
    return line
