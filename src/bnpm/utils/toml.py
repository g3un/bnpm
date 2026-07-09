from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
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

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        index += 1
        line = _strip_comment(raw_line).strip()
        if not line:
            continue

        if line.startswith("[[") and line.endswith("]]"):
            name = line[2:-2].strip()
            if not name:
                raise ValueError("empty TOML array table name")
            parent, key_name = _resolve_table_parent(data, name)
            array = parent.setdefault(key_name, [])
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
            parent, key_name = _resolve_table_parent(data, name)
            table = parent.setdefault(key_name, {})
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
        raw_value = value.strip()
        if raw_value == "[":
            raw_value, index = _collect_multiline_array(lines, index)
        if current_array is None and key in current:
            raise ValueError(f"duplicate TOML key: {key}")
        current[key] = _parse_value(raw_value)

    return data


def _collect_multiline_array(lines: list[str], start: int) -> tuple[str, int]:
    values = []
    index = start
    while index < len(lines):
        line = _strip_comment(lines[index]).strip()
        index += 1
        if not line:
            continue
        if line == "]":
            return f"[{', '.join(values)}]", index
        values.append(line.removesuffix(",").strip())
    raise ValueError("unterminated TOML array")


def _parse_value(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return _parse_string(value)
    if value.startswith("[") and value.endswith("]"):
        return _parse_array(value)
    if value.startswith("{") and value.endswith("}"):
        return _parse_inline_table(value)
    if value in {"true", "false"}:
        return value == "true"
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


def _parse_array(value: str) -> list[Any]:
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [_parse_value(item.strip()) for item in _split_commas(inner)]


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


def _resolve_table_parent(
    data: dict[str, Any], name: str
) -> tuple[dict[str, Any], str]:
    parts = [part.strip() for part in name.split(".")]
    if not parts or any(not part for part in parts):
        raise ValueError(f"invalid TOML table name: {name}")
    current = data
    for part in parts[:-1]:
        value = current.setdefault(part, {})
        if not isinstance(value, dict):
            raise ValueError(f"TOML key {part!r} is not a table")
        current = value
    return current, parts[-1]


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
