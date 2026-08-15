#!/usr/bin/env python3
"""Validate runtime.json without third-party dependencies.

WHAT THIS FILE IS, AND WHAT IT IS NOT (SYN-577).

This schema is not the fleet's contract. The contract lives in the services that read this
document -- `data/runtime_config.py CONTRACTS`, `app/src/lib/runtime_config.ts WEB_CONTRACT` and
`data/tasks/sync_dispatcher.py CONSUMED` in the application repo -- and SYN-532 deliberately made
those service-scoped so one service's key cannot break another's startup. This repository is
public and cannot import any of them, so anything stated here is a COPY, and a copy drifts.

It drifted: SYN-532 added 26 behavioural keys to runtime.json, nobody updated this schema, and
`unknown key` turned main red for a day on exactly the keys that were added on purpose. That is
the failure mode this file now refuses to repeat.

The rule that follows from it:

  * A key this schema does not know about is a WARNING, never an error. Every reader in the fleet
    ignores keys it does not consume (SYN-532 changed all of them to do so), so an unrecognised
    key cannot break production -- it can only mean this copy is behind. Failing on it blocks the
    very config commits the services are waiting for, which is strictly worse than the drift.
  * A key this schema DOES know about is still checked hard: type, bounds, and the public-repo
    safety rules. A wrong TYPE does break startup on both tiers, so it stays an error.
  * A key in `required` that is absent is still an error. Deleting a live setting silently changes
    behaviour, which is what `required` exists to prevent.

The authoritative drift check is in the application repo, where the contract actually lives:
`scripts/runtime_config_preflight.py` validates THIS document, fetched from its public URL, against
every service contract. SYN-577 puts it on that repo's CI (pull requests, main, and a daily
schedule) so a divergence between the contract and this file is caught in the repo that can see
both, without either repo needing a credential for the other.
"""

import json
import os
import re
import sys
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
    warnings = []
    for key in schema.get("required", []):
        if key not in config:
            errors.append(f"{key}: required key is missing")
    for key, value in config.items():
        # The safety boundary applies to every key, known or not: this repository is public.
        if SENSITIVE_KEY.search(key):
            errors.append(f"{key}: sensitive keys are forbidden")
        if isinstance(value, str) and EMAIL.search(value):
            errors.append(f"{key}: email addresses are forbidden in this public repository")

        spec = properties.get(key)
        if spec is None:
            warnings.append(
                f"{key}: not in runtime.schema.json -- every service ignores keys it does not "
                f"consume, so this is a stale schema, not a broken config. Add it here."
            )
            continue
        expected = spec["type"]
        valid = (
            expected == "boolean" and isinstance(value, bool)
            or expected == "integer" and isinstance(value, int) and not isinstance(value, bool)
            or expected == "string" and isinstance(value, str)
            and (key == "doc_viewer_users" or bool(value.strip()))
            or expected == "array" and isinstance(value, list)
        )
        if not valid:
            errors.append(f"{key}: expected {expected}")
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            if value < spec.get("minimum", value):
                errors.append(f"{key}: below minimum {spec['minimum']}")
            if value > spec.get("maximum", value):
                errors.append(f"{key}: above maximum {spec['maximum']}")
        if isinstance(value, list):
            item_spec = spec.get("items", {})
            if item_spec.get("type") == "string" and any(
                not isinstance(item, str) or len(item) < item_spec.get("minLength", 0)
                for item in value
            ):
                errors.append(f"{key}: contains an invalid item")
            if (
                spec.get("uniqueItems")
                and len({json.dumps(item, sort_keys=True) for item in value}) != len(value)
            ):
                errors.append(f"{key}: items must be unique")
        if key == "doc_viewer_users" and value:
            errors.append("doc_viewer_users: must stay empty in this public repository")

    # `::warning::` surfaces these on the run summary in GitHub Actions; plain stderr elsewhere.
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") == "true" else "warning: "
    for warning in warnings:
        print(f"{prefix}{warning}", file=sys.stderr)
    if errors:
        raise SystemExit("\n".join(errors))
    known = len(config) - len(warnings)
    print(f"valid: {len(config)} runtime settings ({known} in schema, {len(warnings)} unknown)")


if __name__ == "__main__":
    main()
