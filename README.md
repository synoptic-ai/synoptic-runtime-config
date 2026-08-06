# Synoptic runtime config

This public repository is Synoptic's reviewed runtime-configuration source.

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
