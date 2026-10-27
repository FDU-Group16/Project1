#!/usr/bin/env bash
# Optional GitHub Actions opt-in. Use the already configured staging SSH secrets.
set -euo pipefail
set +x
if [[ -z "${STAGING_TEST_ACCOUNTS_JSON:-}" ]]; then
  echo 'No test-account secret configured; test-account initialization skipped.'
  exit 0
fi
if [[ ! "${STAGING_SSH_HOST:-}" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ||
      ! "${STAGING_SSH_USER:-}" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]]; then
  echo 'Valid staging SSH configuration is required.' >&2
  exit 1
fi
ssh_port="${STAGING_SSH_PORT:-22}"
if [[ ! "$ssh_port" =~ ^[0-9]{1,5}$ ]] || (( 10#$ssh_port < 1 || 10#$ssh_port > 65535 )); then
  echo 'Invalid staging SSH port.' >&2
  exit 1
fi
[[ -s "$HOME/.ssh/staging_key" && -s "$HOME/.ssh/known_hosts" ]] || exit 1
# The plaintext mapping goes only through SSH stdin. Never place it in an
# argument, URL, command substitution, remote shell text, or an Actions artifact.
printf '%s' "$STAGING_TEST_ACCOUNTS_JSON" | ssh \
  -p "$ssh_port" -i "$HOME/.ssh/staging_key" -o BatchMode=yes -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$HOME/.ssh/known_hosts" \
  -o ConnectTimeout=15 -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  "${STAGING_SSH_USER}@${STAGING_SSH_HOST}" \
  'bash "$HOME/campus-resource-staging/current/scripts/enable-staging-test-accounts.sh" --course-test-site --credentials-stdin'
