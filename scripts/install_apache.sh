#!/bin/bash

set -e

sudo apt update

if ! dpkg -s apache2 >/dev/null 2>&1; then
echo "Installing Apache2..."
sudo apt install -y apache2
else
echo "Apache2 is already installed."
fi

if ! dpkg -s php >/dev/null 2>&1; then
echo "Installing PHP..."
sudo apt install -y php
else
echo "PHP is already installed."
fi

if ! dpkg -s libapache2-mod-php >/dev/null 2>&1; then
echo "Installing Apache PHP module..."
sudo apt install -y libapache2-mod-php
else
echo "Apache PHP module is already installed."
fi

echo "Apache installation completed."
