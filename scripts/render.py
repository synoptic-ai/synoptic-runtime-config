#!/usr/bin/env python3
"""SYN-670 — write every environment's merged document into a directory, for the publisher.

One file per environment (`<out>/<name>/runtime.json`), each the base with that environment's
overlay applied and stamped with its own `env`. Rendering is a separate step from uploading so the
workflow uploads bytes that were produced once, checked once, and printed to the run summary —
rather than merging inside a shell loop where a failure is a half-published fleet.

Refuses to write anything if any environment has a problem: publishing a good prod document beside
a broken preprod one is how you get an environment nobody notices is stale.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import envs  # noqa: E402


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    documents, problems = {}, []
    for name in envs.names():
        document, issues = envs.merge(name)
        documents[name] = document
        problems.extend(issues)
    if problems:
        raise SystemExit("\n".join(problems))
    if envs.DEFAULT_ENV not in documents:
        raise SystemExit(f"envs/{envs.DEFAULT_ENV}.json is missing — every reader falls back to it")

    for name, document in documents.items():
        target = out / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "runtime.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        changes = envs.diff(name)
        detail = ", ".join(f"{k}={new!r}" for k, (_old, new) in sorted(changes.items()))
        print(f"rendered {name}: {len(document)} keys{' (' + detail + ')' if detail else ''}")

    # `current/` is what every deployed service reads today and what the public README documents.
    # It stays a byte-identical copy of the default environment until the last reader is moved to
    # an explicit `runtime-config/<env>/` key; it is an alias, never a fourth document to edit.
    alias = out / "current"
    alias.mkdir(parents=True, exist_ok=True)
    (alias / "runtime.json").write_text((out / envs.DEFAULT_ENV / "runtime.json").read_text())
    print(f"rendered current: alias of {envs.DEFAULT_ENV}")


if __name__ == "__main__":
    main()
