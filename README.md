# Synoptic runtime config

This public repository is Synoptic's complete reviewed runtime configuration.

`runtime.json` contains every resolved setting. It has no override/default split. Every schema key
is required, so deleting a setting fails validation instead of silently changing behavior.

## What the schema is, and what owns the truth

`runtime.schema.json` is a **copy** of what the services consume, not the source of it. The real
contract is service-scoped and lives in the application repository (SYN-532), which this public
repository cannot import. So the copy can fall behind, and once did — SYN-532 added 26 keys here
and the schema rejected all of them, which held main red for a day.

The rules that follow:

- **A key the schema does not know is a warning, not a failure.** Every service ignores keys it
  does not consume, so an unrecognised key cannot break production. Add it to the schema when you
  see the warning.
- **A key the schema does know is checked hard** — type and bounds. A wrong type does refuse
  startup, on both tiers.
- **A missing required key still fails**, which is the point of `required`.

The authoritative check runs in the application repository, against this file at its public URL,
over every service contract. It is the only place that can see both sides.

## Change a value

1. Branch from `main`.
2. Edit `runtime.json`.
3. Run `python3 scripts/validate.py`.
4. Open a pull request.
5. Merge after review and passing checks.

The app and data services refresh the raw file every 45 seconds. They retain the last valid
configuration during GitHub or validation failures. A cold-start failure uses code defaults.

## Safety boundary

Never add secrets, tokens, credentials, customer data, or user email addresses. This repository is
public by design so production services can read it without a broad GitHub credential.

The configuration URL is:

`https://raw.githubusercontent.com/synoptic-ai/synoptic-runtime-config/main/runtime.json`
