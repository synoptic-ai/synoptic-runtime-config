#!/usr/bin/env python3
"""Validate runtime.json without third-party dependencies."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
SENSITIVE_KEY = re.compile(r"(?:secret|password|credential|private[_-]?key|access[_-]?token)", re.I)


def main():
    config = json.loads((ROOT / "runtime.json").read_text())
    schema = json.loads((ROOT / "runtime.schema.json").read_text())
    if not isinstance(config, dict):
        raise SystemExit("runtime.json must contain one object")

    properties = schema["properties"]
    errors = []
    for key, value in config.items():
        spec = properties.get(key)
        if spec is None:
            errors.append(f"{key}: unknown key")
            continue
        if SENSITIVE_KEY.search(key):
            errors.append(f"{key}: sensitive keys are forbidden")
        expected = spec["type"]
        valid = (
            expected == "boolean" and isinstance(value, bool)
            or expected == "integer" and isinstance(value, int) and not isinstance(value, bool)
            or expected == "string" and isinstance(value, str) and bool(value.strip())
        )
        if not valid:
            errors.append(f"{key}: expected {expected}")
            continue
        if isinstance(value, int):
            if value < spec.get("minimum", value):
                errors.append(f"{key}: below minimum {spec['minimum']}")
            if value > spec.get("maximum", value):
                errors.append(f"{key}: above maximum {spec['maximum']}")
        if isinstance(value, str) and EMAIL.search(value):
            errors.append(f"{key}: email addresses are forbidden in this public repository")

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"valid: {len(config)} runtime settings")


if __name__ == "__main__":
    main()
