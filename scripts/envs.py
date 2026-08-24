#!/usr/bin/env python3
"""SYN-670 — the environments this repository publishes, and how each one is composed.

WHY OVERLAYS AND NOT ONE FILE PER ENVIRONMENT. `runtime.json` is the reviewed base and holds every
setting. An environment is that document plus a small, explicit patch: `envs/<name>.json`. The
alternative — a complete copy per environment — was rejected because a copy rots. Preprod exists to
answer "what does production do if I change this one thing", and a 76-key copy stops resembling
production the first time somebody edits the base and forgets the copy. With an overlay, the diff
IS the experiment, and everything not under experiment is inherited by construction.

`envs/prod.json` is therefore empty, and that emptiness is a statement: production runs the
reviewed base, unmodified.

TWO RULES THE MERGE ENFORCES.
  * An overlay may only OVERRIDE a key the base already defines. A key the base has never heard of
    is a typo or a setting that belongs in the base — either way, publishing it would hand a
    service a document its contract cannot explain, so it fails here instead.
  * Keys beginning with `_` are documentation (`_comment`, `_experiment`) and never reach the
    published document. They are how an experiment says what it is testing, in the file the
    experiment lives in.

EVERY PUBLISHED DOCUMENT IS STAMPED with `"env"`. That stamp is what lets a reader refuse a
document meant for somewhere else — the failure this ticket exists for was preprod silently
reading production's config and looking healthy while doing it.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_FILE = ROOT / "runtime.json"
ENV_DIR = ROOT / "envs"
# The document every reader falls back to, and the name of the environment it describes. Kept as a
# constant because both the validator and the publisher have to agree on which env `current/` is.
DEFAULT_ENV = "prod"


def names():
    """Every environment this repository publishes, sorted. The filename IS the environment name."""
    return sorted(path.stem for path in ENV_DIR.glob("*.json"))


def base():
    return json.loads(BASE_FILE.read_text())


def overlay(name):
    """The environment's patch, documentation keys included (the caller decides what to drop)."""
    return json.loads((ENV_DIR / f"{name}.json").read_text())


def merge(name):
    """(document, [problem]) — the base with this environment's overrides applied and stamped.

    Never raises on a bad overlay: the caller reports every problem at once, the way the validator
    reports every bad key at once. A document is returned regardless so a single typo does not hide
    the rest of the checks.
    """
    doc = base()
    problems = []
    for key, value in overlay(name).items():
        if key.startswith("_"):
            continue
        if key not in doc:
            problems.append(
                f"envs/{name}.json: {key} is not a key of runtime.json — an overlay may only "
                f"override an existing setting; add it to runtime.json first"
            )
            continue
        doc[key] = value
    doc["env"] = name
    return doc, problems


def diff(name):
    """{key: (base value, environment value)} — what this environment actually changes."""
    original = base()
    return {
        key: (original[key], value)
        for key, value in overlay(name).items()
        if not key.startswith("_") and key in original and original[key] != value
    }
