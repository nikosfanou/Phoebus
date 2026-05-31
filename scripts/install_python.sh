#!/bin/bash

set -e

sudo apt update

if ! command -v python3.10 >/dev/null 2>&1; then
    echo "Installing Python 3.10..."
    sudo apt install -y python3.10
else
    echo "Python 3.10 is already installed."
fi

if ! dpkg -s python3.10-venv >/dev/null 2>&1; then
    echo "Installing python3.10-venv..."
    sudo apt install -y python3.10-venv
fi

if ! dpkg -s python3.10-dev >/dev/null 2>&1; then
    echo "Installing python3.10-dev..."
    sudo apt install -y python3.10-dev
fi

if ! python3.10 -m pip --version >/dev/null 2>&1; then
    echo "Installing pip..."
    sudo apt install -y python3-pip
else
    echo "pip is already installed."
fi

echo "Python installation completed."