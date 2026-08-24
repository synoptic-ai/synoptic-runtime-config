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

SYN-670 — EVERY PUBLISHED DOCUMENT IS CHECKED, not only the base. `runtime.json` is now the base of
one document per environment (`envs/<name>.json` overlays it — see scripts/envs.py), and it is the
MERGED documents that services read. Validating only the base would let a one-key preprod overlay
publish a wrong type to a running environment through a green check, so each merged document goes
through exactly the same rules, named by its environment in the output.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import envs  # noqa: E402  (same directory; keeps this dependency-free)

ROOT = Path(__file__).resolve().parents[1]
EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
SENSITIVE_KEY = re.compile(r"(?:secret|password|credential|private[_-]?key|access[_-]?token)", re.I)


def check(config, schema, label):
    """([error], [warning]) for one complete document, named by `label` in every message."""
    if not isinstance(config, dict):
        return [f"{label}: must contain one object"], []

    properties = schema["properties"]
    errors = []
    warnings = []
    # Naming the document on every message is the whole point of validating more than one: without
    # it, "tree_max_leaf_calls: expected integer" says nothing about WHERE the bad value lives.
    at = f"{label}: "
    for key in schema.get("required", []):
        if key not in config:
            errors.append(f"{at}{key}: required key is missing")
    for key, value in config.items():
        # The safety boundary applies to every key, known or not: this repository is public.
        if SENSITIVE_KEY.search(key):
            errors.append(f"{at}{key}: sensitive keys are forbidden")
        if isinstance(value, str) and EMAIL.search(value):
            errors.append(f"{at}{key}: email addresses are forbidden in this public repository")

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
            errors.append(f"{at}{key}: expected {expected}")
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            if value < spec.get("minimum", value):
                errors.append(f"{at}{key}: below minimum {spec['minimum']}")
            if value > spec.get("maximum", value):
                errors.append(f"{at}{key}: above maximum {spec['maximum']}")
        if isinstance(value, list):
            item_spec = spec.get("items", {})
            if item_spec.get("type") == "string" and any(
                not isinstance(item, str) or len(item) < item_spec.get("minLength", 0)
                for item in value
            ):
                errors.append(f"{at}{key}: contains an invalid item")
            if (
                spec.get("uniqueItems")
                and len({json.dumps(item, sort_keys=True) for item in value}) != len(value)
            ):
                errors.append(f"{at}{key}: items must be unique")
        if key == "doc_viewer_users" and value:
            errors.append(f"{at}doc_viewer_users: must stay empty in this public repository")

    return errors, warnings


def main():
    schema = json.loads((ROOT / "runtime.schema.json").read_text())
    errors, warnings = check(envs.base(), schema, "runtime.json")

    # `env` is stamped by the publisher, not written by hand, so the schema does not carry it and
    # the unknown-key warning below would fire once per environment for a key this repository
    # itself adds. Reporting it would train the reader to ignore the warning that matters.
    documents = {}
    for name in envs.names():
        document, problems = envs.merge(name)
        documents[name] = document
        errors.extend(problems)
        env_errors, env_warnings = check(
            {k: v for k, v in document.items() if k != "env"}, schema, f"env {name}")
        errors.extend(env_errors)
        warnings.extend(w for w in env_warnings if w not in warnings)

    # `::warning::` surfaces these on the run summary in GitHub Actions; plain stderr elsewhere.
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") == "true" else "warning: "
    for warning in warnings:
        print(f"{prefix}{warning}", file=sys.stderr)
    if errors:
        raise SystemExit("\n".join(errors))

    base = envs.base()
    known = len(base) - len(warnings)
    print(f"valid: {len(base)} runtime settings ({known} in schema, {len(warnings)} unknown)")
    for name in envs.names():
        changes = envs.diff(name)
        detail = ", ".join(f"{k}: {old!r} -> {new!r}" for k, (old, new) in sorted(changes.items()))
        print(f"valid: env {name} = base{' + ' + detail if detail else ' (no overrides)'}")


if __name__ == "__main__":
    main()
