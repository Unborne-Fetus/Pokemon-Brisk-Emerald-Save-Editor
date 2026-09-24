#!/usr/bin/env bash
set -e
echo "==================================="
echo "  Brisk Dex - build the installer"
echo "==================================="
echo
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is not installed or not on PATH."
  echo "Download it from https://nodejs.org, install it, then run this again."
  read -p "Press Enter to exit..."
  exit 1
fi
echo "Installing dependencies (first run only, this can take a few minutes)..."
npm install
echo
echo "Building..."
npm run dist
echo
echo "Done! Find the installer in the dist/ folder."
read -p "Press Enter to exit..."
