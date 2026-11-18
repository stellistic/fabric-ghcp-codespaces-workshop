#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv sync --frozen
npm ci --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org

# Local settings only: no login, auth status, resource discovery or notebook execution.
fab config set debug_enabled false >/dev/null
fab config set encryption_fallback_enabled false >/dev/null
fab config set check_cli_version_updates false >/dev/null
fab --version
npm run --silent copilot -- --version
uv run --frozen python -m workshop.live --help >/dev/null
printf '%s\n' 'Tools ready. Follow docs/codespaces.md for separate, explicit browser logins.'
