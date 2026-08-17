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

The app and data services refresh every 45 seconds and retain the last valid configuration through
a read or validation failure.

## How a merge reaches production (SYN-620)

Merging to `main` runs `.github/workflows/publish.yml`, which copies `runtime.json` and
`runtime.schema.json` to `s3://synoptic-lake-369598751884/runtime-config/current/`. **That S3
object is what the services read first**; the raw GitHub URL below is their fallback and their
public entry point.

The reason is staleness, not speed: `raw.githubusercontent.com` is a CDN and can serve a previous
generation for 5-30 minutes, so a 45-second poll against it was a promise about how often we ask,
not about how fresh the answer is. Two rollouts in August 2026 ran the old behaviour for 15-23
minutes after merge because of it. S3 is strongly consistent, so worst-case staleness is now the
poll interval itself.

If the publish job fails, the S3 object keeps its previous contents and readers fall through to
the raw URL — the same behaviour they had before this existed. Nothing here changes where the
truth lives: this repository is still the source, and S3 holds a copy of what `main` already says.

## Safety boundary

Never add secrets, tokens, credentials, customer data, or user email addresses. This repository is
public by design so production services can read it without a broad GitHub credential.

The configuration URL is:

`https://raw.githubusercontent.com/synoptic-ai/synoptic-runtime-config/main/runtime.json`
