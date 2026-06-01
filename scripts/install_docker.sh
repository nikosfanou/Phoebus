#!/bin/bash

set -e

if command -v docker >/dev/null 2>&1; then
  echo "Docker is already installed:"
  docker --version
  exit 0
fi

echo "Docker not found. Installing Docker..."

# Set up the repository
sudo apt-get update

MISSING_PACKAGES=()

# Installing ca-certificates, curl, gnupg if not already installed
for pkg in ca-certificates curl gnupg; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        MISSING_PACKAGES+=("$pkg")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -ne 0 ]; then
    echo "Installing: ${MISSING_PACKAGES[*]}"
    sudo apt-get install -y "${MISSING_PACKAGES[@]}"
fi

sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Docker installation completed."
docker --version