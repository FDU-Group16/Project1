#!/usr/bin/env bash
set -euo pipefail

: "${STAGING_IMAGE_PREFIX:?STAGING_IMAGE_PREFIX is required}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
if [[ ! "$STAGING_IMAGE_PREFIX" =~ ^ghcr\.io/[a-z0-9][a-z0-9._/-]*$ ]]; then
  echo "Expected a lowercase GHCR image prefix" >&2
  exit 1
fi

source_image="$(cat docker/staging-postgres-image.txt)"
if [[ ! "$source_image" =~ ^docker\.io/library/postgres:18-alpine@sha256:[0-9a-f]{64}$ ]]; then
  echo "Expected an immutable PostgreSQL 18 image reference" >&2
  exit 1
fi
mirror_repository="${STAGING_IMAGE_PREFIX}-postgres"
mirror_tag="${mirror_repository}:sha256-${source_image##*@sha256:}"

# A stable tag avoids downloading/pushing the database on each application commit.
if ! digest="$(docker buildx imagetools inspect "$mirror_tag" --format '{{.Manifest.Digest}}' 2>/dev/null)"; then
  docker pull --platform linux/amd64 "$source_image"
  docker tag "$source_image" "$mirror_tag"
  docker push "$mirror_tag"
  digest="$(docker buildx imagetools inspect "$mirror_tag" --format '{{.Manifest.Digest}}')"
fi
if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Registry did not return a valid PostgreSQL digest" >&2
  exit 1
fi
printf 'image=%s@%s\n' "$mirror_repository" "$digest" >> "$GITHUB_OUTPUT"
