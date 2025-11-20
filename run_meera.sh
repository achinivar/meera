#!/bin/bash
set -e

# Simple helper to print section headers
section() {
  echo
  echo "=============================="
  echo "$1"
  echo "=============================="
}

# Detect project root (directory of this script)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

section "Meera setup & launch"

#######################################
# 1. Detect package manager
#######################################

PKG_MANAGER=""
if command -v dnf >/dev/null 2>&1; then
  PKG_MANAGER="dnf"
elif command -v apt-get >/dev/null 2>&1; then
  PKG_MANAGER="apt"
else
  echo "Warning: could not detect supported package manager (dnf/apt)."
  echo "You may need to install system dependencies manually."
fi

########################################
# 2. Install system dependencies
########################################

if [ "$PKG_MANAGER" = "dnf" ]; then
  section "Installing system dependencies via dnf"
  sudo dnf install -y \
    python3 \
    python3-gobject \
    gtk4 \
    libadwaita \
    pip \
    gobject-introspection-devel \
    cairo-devel
elif [ "$PKG_MANAGER" = "apt" ]; then
  section "Installing system dependencies via apt"
  sudo apt-get update
  sudo apt-get install -y \
    python3 python3-venv python3-gi \
    gir1.2-gtk-4.0 \
    gir1.2-pango-1.0 \
    libgirepository1.0-dev
else
  echo "Skipping system dependency installation (no supported package manager)."
fi

########################################
# 3. Install Ollama if missing
########################################

if ! command -v ollama >/dev/null 2>&1; then
  section "Installing Ollama"
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo "Ollama already installed."
fi

########################################
# 4. Ensure Ollama is running & model pulled
########################################

section "Ensuring Ollama is running and model is available"

# Start ollama serve in the background if not already running
if ! pgrep -x "ollama" >/dev/null 2>&1; then
  echo "Starting Ollama server..."
  ollama serve >/tmp/ollama_meera.log 2>&1 &
  # Give it a moment to start
  sleep 3
else
  echo "Ollama server already running."
fi

# Pull a small CPU-friendly model (adjust if backend.py uses a different name)
MODEL_NAME="llama3.2:1b"
echo "Ensuring model '$MODEL_NAME' is available..."
ollama pull "$MODEL_NAME" || true

########################################
# 5. Python installs
########################################

pip install --upgrade pip
pip install requests

########################################
# 6. Run Meera
########################################

section "Launching Meera"

python3 meera.py

