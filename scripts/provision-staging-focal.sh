#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != 0 ]]; then
  echo "Run as root on the staging server" >&2
  exit 1
fi

# Docker stopped publishing new packages for Ubuntu 20.04. This pinned setup
# is only for the existing course staging server, which cannot reach the
# default overseas apt sources.
. /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 20.04 ||
      "$(dpkg --print-architecture)" != amd64 ]]; then
  echo "This installer is limited to Ubuntu 20.04 amd64" >&2
  exit 1
fi

source_file=/etc/apt/sources.list
backup_file=/etc/apt/sources.list.before-staging-mirror
if [[ ! -f "$backup_file" ]]; then
  cp -p "$source_file" "$backup_file"
fi
sed -i \
  -e 's#http://archive.ubuntu.com/ubuntu#https://mirrors.aliyun.com/ubuntu#g' \
  -e 's#http://security.ubuntu.com/ubuntu#https://mirrors.aliyun.com/ubuntu#g' \
  "$source_file"

install -m 0755 -d /etc/apt/keyrings
curl -4 -fsSL --max-time 20 \
  https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
# This hash was compared with Docker's official signing key before use.
printf '%s  %s\n' \
  '1500c1f56fa9e26b9b8f42452a553675796ade0807cdce11975eb98170b3a570' \
  /etc/apt/keyrings/docker.asc | sha256sum -c -
chmod a+r /etc/apt/keyrings/docker.asc
printf '%s\n' \
  'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.aliyun.com/docker-ce/linux/ubuntu focal stable' \
  > /etc/apt/sources.list.d/docker.list

apt-get update
packages=(
  'docker-ce=5:28.1.1-1~ubuntu.20.04~focal'
  'docker-ce-cli=5:28.1.1-1~ubuntu.20.04~focal'
  'containerd.io=1.7.27-1'
  'docker-buildx-plugin=0.23.0-1~ubuntu.20.04~focal'
  'docker-compose-plugin=2.35.1-1~ubuntu.20.04~focal'
)
plan="$(apt-get -s -o APT::Install-Recommends=false install "${packages[@]}")"
printf '%s\n' "$plan"
if grep -q '^Remv ' <<< "$plan"; then
  echo "Refusing to remove existing packages" >&2
  exit 1
fi
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  -o APT::Install-Recommends=false "${packages[@]}"
systemctl enable --now docker
docker info >/dev/null
docker compose version
