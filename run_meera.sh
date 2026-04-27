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

# When launched via this script, default to llama.cpp + auto-cached GGUF (override with MEERA_BACKEND=ollama).
export MEERA_BACKEND="${MEERA_BACKEND:-llamacpp}"

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
    curl \
    python3 \
    python3-requests \
    python3-gobject \
    gtk4 \
    libadwaita \
    gobject-introspection-devel \
    cairo-devel
elif [ "$PKG_MANAGER" = "apt" ]; then
  section "Installing system dependencies via apt"
  sudo apt-get update
  sudo apt-get install -y \
    curl \
    python3 python3-requests python3-venv python3-gi \
    gir1.2-gtk-4.0 \
    gir1.2-pango-1.0 \
    libgirepository1.0-dev
else
  echo "Skipping system dependency installation (no supported package manager)."
fi

########################################
# 3–4. Inference backend: llama.cpp (default via script) or Ollama
########################################

# Pinned upstream release: https://github.com/ggml-org/llama.cpp/releases
# Bump tag and SHA256 values together when upgrading.
MEERA_LLAMA_CPP_TAG="${MEERA_LLAMA_CPP_TAG:-b8672}"
MEERA_LLAMA_DL_BASE="https://github.com/ggml-org/llama.cpp/releases/download/${MEERA_LLAMA_CPP_TAG}"
MEERA_LLAMA_DIR_NAME="llama-${MEERA_LLAMA_CPP_TAG}"
MEERA_LLAMA_CACHE="${MEERA_LLAMA_CACHE:-$ROOT_DIR/.cache/meera/llama-cpp}"
# SHA-256 of official GitHub release assets (from API digest field).
MEERA_SHA_LLAMA_UBUNTU_X64="e5274949bd1d94882454abdc9b131cf3e250678026de30fa3b365e4f8f61d824"
MEERA_SHA_LLAMA_UBUNTU_ARM64="2306d31bb232b604fc0478e6c2cf1a673aab8cdcdc782925fed2d7eb51afa825"
MEERA_SHA_LLAMA_OE_X86="cfde7b3bc243a7105a9a9773d78d5635ff446b2a4397d2386d848ff83c637866"
MEERA_SHA_LLAMA_OE_AARCH64="fe75fbdc34214e08ec476430932f6316e46e3d36ed56498628a1a18160537129"

# Default GGUF: same family as Ollama qwen3.5:2b-q4_K_M — Unsloth Q4_K_M on Hugging Face.
MEERA_DEFAULT_GGUF_NAME="Qwen3.5-2B-Q4_K_M.gguf"
MEERA_DEFAULT_GGUF_URL="https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/${MEERA_DEFAULT_GGUF_NAME}"
MEERA_GGUF_CACHE_DIR="${MEERA_GGUF_CACHE_DIR:-$ROOT_DIR/.cache/meera/models}"

# Embedding GGUF (small sentence-transformer for retrieval / RAG).
MEERA_EMBED_DEFAULT_GGUF_NAME="bge-small-en-v1.5-q8_0.gguf"
MEERA_EMBED_DEFAULT_GGUF_URL="https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf/resolve/main/${MEERA_EMBED_DEFAULT_GGUF_NAME}"

if [ "${MEERA_BACKEND:-llamacpp}" = "llamacpp" ]; then
  echo "MEERA_BACKEND=llamacpp — skipping Ollama install/serve/pull."

  # Download official llama.cpp CPU bundle (Ubuntu tarball for apt/Debian; openEuler tarball for dnf/Fedora).
  meera_ensure_llama_bundle() {
    _uarch="$(uname -m)"
    case "$_uarch" in
      x86_64) _larch=x86_64 ;;
      aarch64 | arm64) _larch=aarch64 ;;
      *)
        echo "Unsupported CPU for bundled llama-server: $_uarch"
        echo "Use MEERA_BACKEND=ollama, or an x86_64 / aarch64 Linux system with apt or dnf."
        exit 1
        ;;
    esac
    if [ "$PKG_MANAGER" = "dnf" ]; then
      _lfam=openEuler
      case "$_larch" in
        x86_64)
          _lbun="llama-${MEERA_LLAMA_CPP_TAG}-bin-310p-openEuler-x86.tar.gz"
          _lsha="$MEERA_SHA_LLAMA_OE_X86"
          _lid=openEuler-x86
          ;;
        aarch64)
          _lbun="llama-${MEERA_LLAMA_CPP_TAG}-bin-310p-openEuler-aarch64.tar.gz"
          _lsha="$MEERA_SHA_LLAMA_OE_AARCH64"
          _lid=openEuler-aarch64
          ;;
      esac
    else
      _lfam=ubuntu
      case "$_larch" in
        x86_64)
          _lbun="llama-${MEERA_LLAMA_CPP_TAG}-bin-ubuntu-x64.tar.gz"
          _lsha="$MEERA_SHA_LLAMA_UBUNTU_X64"
          _lid=ubuntu-x64
          ;;
        aarch64)
          _lbun="llama-${MEERA_LLAMA_CPP_TAG}-bin-ubuntu-arm64.tar.gz"
          _lsha="$MEERA_SHA_LLAMA_UBUNTU_ARM64"
          _lid=ubuntu-arm64
          ;;
      esac
      if [ "$PKG_MANAGER" != "apt" ]; then
        echo "Note: package manager is not apt/dnf; using upstream Ubuntu CPU tarball ($_lid)."
      fi
    fi
    _lst="$MEERA_LLAMA_CACHE/$MEERA_LLAMA_CPP_TAG"
    _larc="$_lst/$_lbun"
    _lex="$_lst/$_lid"
    _lbindir="$_lex/$MEERA_LLAMA_DIR_NAME"
    if [ -x "$_lbindir/llama-server" ]; then
      echo "Using cached llama.cpp bundle: $_lbindir"
      _meera_llama_server="$_lbindir/llama-server"
      MEERA_LLAMA_LIB_DIR="$_lbindir"
      return 0
    fi
    section "Downloading llama-server bundle ($MEERA_LLAMA_CPP_TAG, ${_lfam} ${_lid})"
    mkdir -p "$_lst"
    _lurl="${MEERA_LLAMA_DL_BASE}/${_lbun}"
    echo "URL: $_lurl"
    _lpart="$_larc.part"
    if ! command -v curl >/dev/null 2>&1; then
      echo "curl is required to download the llama.cpp bundle."
      exit 1
    fi
    curl -fL --retry 3 -C - --proto '=https' -o "$_lpart" "$_lurl"
    mv -f "$_lpart" "$_larc"
    printf '%s  %s\n' "$_lsha" "$_larc" | sha256sum -c - || {
      echo "SHA256 mismatch for $_larc — remove the file and retry, or bump MEERA_LLAMA_CPP_TAG / checksums in run_meera.sh."
      rm -f "$_larc"
      exit 1
    }
    rm -rf "$_lex"
    mkdir -p "$_lex"
    tar xzf "$_larc" -C "$_lex"
    if [ ! -x "$_lbindir/llama-server" ]; then
      echo "Extracted bundle missing executable: $_lbindir/llama-server"
      exit 1
    fi
    _meera_llama_server="$_lbindir/llama-server"
    MEERA_LLAMA_LIB_DIR="$_lbindir"
  }

  LLAMA_BASE="${MEERA_LLAMACPP_URL:-http://127.0.0.1:8080}"
  LLAMA_BASE="${LLAMA_BASE%/}"
  llama_server_reachable() {
    python3 -c "
import sys, urllib.request
try:
    urllib.request.urlopen('$LLAMA_BASE/v1/models', timeout=3)
    sys.exit(0)
except Exception:
    sys.exit(1)
" >/dev/null 2>&1
  }

  # Resolve GGUF path: explicit env, or cached default (download on first run).
  if [ -z "${MEERA_LLAMACPP_GGUF:-}" ]; then
    _gguf_path="$MEERA_GGUF_CACHE_DIR/$MEERA_DEFAULT_GGUF_NAME"
    if [ -f "$_gguf_path" ] && [ -s "$_gguf_path" ]; then
      echo "Using cached GGUF: $_gguf_path"
    else
      section "Downloading GGUF (first run, ~1.3 GB)"
      echo "Source: $MEERA_DEFAULT_GGUF_URL"
      mkdir -p "$MEERA_GGUF_CACHE_DIR"
      _part="$_gguf_path.part"
      if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 -C - --proto '=https' \
          -o "$_part" "$MEERA_DEFAULT_GGUF_URL"
      else
        echo "curl not found; install curl or download the file manually to:"
        echo "  $_gguf_path"
        exit 1
      fi
      mv -f "$_part" "$_gguf_path"
      echo "Saved: $_gguf_path"
    fi
    export MEERA_LLAMACPP_GGUF="$_gguf_path"
  elif [ ! -f "${MEERA_LLAMACPP_GGUF}" ]; then
    echo "MEERA_LLAMACPP_GGUF points to a missing file: $MEERA_LLAMACPP_GGUF"
    exit 1
  fi

  if llama_server_reachable; then
    echo "llama-server already responding at $LLAMA_BASE"
  else
    meera_ensure_llama_bundle
    LLAMA_BIN="$_meera_llama_server"
    if [ ! -x "$LLAMA_BIN" ]; then
      echo "Bundled llama-server missing or not executable: $LLAMA_BIN"
      exit 1
    fi
    _rest="${LLAMA_BASE#*://}"
    _rest="${_rest%%/*}"
    case "$_rest" in
      *:*)
        _LLAMA_HOST="${_rest%%:*}"
        _LLAMA_PORT="${_rest#*:}"
        ;;
      *)
        _LLAMA_HOST="$_rest"
        _LLAMA_PORT="8080"
        ;;
    esac
    if [ "$_LLAMA_HOST" != "127.0.0.1" ] && [ "$_LLAMA_HOST" != "localhost" ]; then
      echo "Auto-start only works when MEERA_LLAMACPP_URL uses host 127.0.0.1 or localhost"
      echo "(got '$_LLAMA_HOST'). Start llama-server on that host yourself."
      exit 1
    fi
    section "Starting llama-server"
    echo "Model: $MEERA_LLAMACPP_GGUF"
    echo "Log: /tmp/llama_meera.log"
    # One server slot (default llama-server is --parallel auto → 4): sequential turns
    # reuse the same slot/KV cache instead of LRU-picking an empty slot and paying full
    # prompt prefill. To use more slots, pass --parallel N in MEERA_LLAMACPP_SERVER_EXTRA
    # (llama-server uses the last --parallel value if specified twice).
    # shellcheck disable=SC2086
    env LD_LIBRARY_PATH="${MEERA_LLAMA_LIB_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
      "$LLAMA_BIN" -m "$MEERA_LLAMACPP_GGUF" --host "$_LLAMA_HOST" --port "$_LLAMA_PORT" \
      --parallel 1 \
      $MEERA_LLAMACPP_SERVER_EXTRA >/tmp/llama_meera.log 2>&1 &
    _wait=0
    while [ "$_wait" -lt 30 ] && ! llama_server_reachable; do
      sleep 1
      _wait=$((_wait + 1))
    done
    if ! llama_server_reachable; then
      echo "llama-server did not become reachable at $LLAMA_BASE (see /tmp/llama_meera.log)."
      exit 1
    fi
    echo "llama-server is up at $LLAMA_BASE"
  fi

  ##########################################################################
  # Embedding llama-server (small sentence-transformer for retrieval / RAG)
  ##########################################################################
  # Skip with MEERA_DISABLE_EMBED=1 (retrieval will be unavailable, agent
  # falls back to a no-retrieval reply path). Default port 8081.
  if [ "${MEERA_DISABLE_EMBED:-0}" != "1" ]; then
    EMBED_BASE="${MEERA_EMBED_URL:-http://127.0.0.1:8081}"
    EMBED_BASE="${EMBED_BASE%/}"
    embed_server_reachable() {
      python3 -c "
import sys, urllib.request
try:
    urllib.request.urlopen('$EMBED_BASE/v1/models', timeout=3)
    sys.exit(0)
except Exception:
    sys.exit(1)
" >/dev/null 2>&1
    }

    if [ -z "${MEERA_EMBED_GGUF:-}" ]; then
      _embed_gguf_path="$MEERA_GGUF_CACHE_DIR/$MEERA_EMBED_DEFAULT_GGUF_NAME"
      if [ -f "$_embed_gguf_path" ] && [ -s "$_embed_gguf_path" ]; then
        echo "Using cached embedding GGUF: $_embed_gguf_path"
      else
        section "Downloading embedding GGUF (first run, ~37 MB)"
        echo "Source: $MEERA_EMBED_DEFAULT_GGUF_URL"
        mkdir -p "$MEERA_GGUF_CACHE_DIR"
        _embed_part="$_embed_gguf_path.part"
        if command -v curl >/dev/null 2>&1; then
          curl -fL --retry 3 -C - --proto '=https' \
            -o "$_embed_part" "$MEERA_EMBED_DEFAULT_GGUF_URL"
        else
          echo "curl not found; install curl or download the file manually to:"
          echo "  $_embed_gguf_path"
          exit 1
        fi
        mv -f "$_embed_part" "$_embed_gguf_path"
        echo "Saved: $_embed_gguf_path"
      fi
      export MEERA_EMBED_GGUF="$_embed_gguf_path"
    elif [ ! -f "${MEERA_EMBED_GGUF}" ]; then
      echo "MEERA_EMBED_GGUF points to a missing file: $MEERA_EMBED_GGUF"
      exit 1
    fi

    if embed_server_reachable; then
      echo "embedding llama-server already responding at $EMBED_BASE"
    else
      if [ -z "${LLAMA_BIN:-}" ]; then
        meera_ensure_llama_bundle
        LLAMA_BIN="$_meera_llama_server"
      fi
      _erest="${EMBED_BASE#*://}"
      _erest="${_erest%%/*}"
      case "$_erest" in
        *:*)
          _EMBED_HOST="${_erest%%:*}"
          _EMBED_PORT="${_erest#*:}"
          ;;
        *)
          _EMBED_HOST="$_erest"
          _EMBED_PORT="8081"
          ;;
      esac
      if [ "$_EMBED_HOST" != "127.0.0.1" ] && [ "$_EMBED_HOST" != "localhost" ]; then
        echo "Auto-start only works when MEERA_EMBED_URL uses host 127.0.0.1 or localhost"
        echo "(got '$_EMBED_HOST'). Start an embedding llama-server on that host yourself."
        exit 1
      fi
      section "Starting embedding llama-server"
      echo "Model: $MEERA_EMBED_GGUF"
      echo "Log: /tmp/llama_meera_embed.log"
      env LD_LIBRARY_PATH="${MEERA_LLAMA_LIB_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        "$LLAMA_BIN" -m "$MEERA_EMBED_GGUF" --host "$_EMBED_HOST" --port "$_EMBED_PORT" \
        --embeddings -c 512 \
        >/tmp/llama_meera_embed.log 2>&1 &
      _ewait=0
      while [ "$_ewait" -lt 30 ] && ! embed_server_reachable; do
        sleep 1
        _ewait=$((_ewait + 1))
      done
      if ! embed_server_reachable; then
        echo "embedding llama-server did not become reachable at $EMBED_BASE (see /tmp/llama_meera_embed.log)."
        exit 1
      fi
      echo "embedding llama-server is up at $EMBED_BASE"
    fi
    export MEERA_EMBED_URL="$EMBED_BASE"
  else
    echo "MEERA_DISABLE_EMBED=1 — skipping embedding server (retrieval / RAG disabled)."
  fi
else
  if ! command -v ollama >/dev/null 2>&1; then
    section "Installing Ollama"
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "Ollama already installed."
  fi

  section "Ensuring Ollama is running and model is available"

  if ! pgrep -x "ollama" >/dev/null 2>&1; then
    echo "Starting Ollama server..."
    ollama serve >/tmp/ollama_meera.log 2>&1 &
    sleep 3
  else
    echo "Ollama server already running."
  fi

  MODEL_NAME="qwen3.5:2b-q4_K_M"
  echo "Ensuring model '$MODEL_NAME' is available..."
  ollama pull "$MODEL_NAME" || true
fi

########################################
# 5. Run Meera
########################################

section "Launching Meera"

python3 meera.py

