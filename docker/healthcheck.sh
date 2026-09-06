#!/bin/sh
# SPDX-FileCopyrightText: 2026 Jonas Kaninda
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Container health check for both Posta roles.
#
set -eu

PORT="${POSTA_WORKER_HEALTH_PORT:-${POSTA_PORT:-9000}}"
PATH_="${POSTA_HEALTHCHECK_PATH:-/healthz}"
URL="http://127.0.0.1:${PORT}${PATH_}"

if wget --quiet --spider --timeout=3 --tries=1 "$URL" 2>/dev/null; then
  exit 0
fi

echo "posta healthcheck failed: ${URL}" >&2
exit 1
