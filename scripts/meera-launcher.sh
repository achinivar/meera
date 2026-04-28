#!/usr/bin/env bash
set -euo pipefail

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
MEERA_CONFIG_DIR="$XDG_CONFIG_HOME/meera"
MEERA_LAUNCHER_CONFIG="$MEERA_CONFIG_DIR/launcher.env"

if [ ! -r "$MEERA_LAUNCHER_CONFIG" ]; then
  printf 'Error: Meera launcher config missing: %s\n' "$MEERA_LAUNCHER_CONFIG" >&2
  exit 1
fi

# shellcheck disable=SC1090
. "$MEERA_LAUNCHER_CONFIG"

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"

MEERA_DATA_DIR="$XDG_DATA_HOME/meera"
MEERA_APP_DIR="$MEERA_DATA_DIR/app"
MEERA_CONFIG_DIR="$XDG_CONFIG_HOME/meera"
MEERA_CACHE_DIR="$XDG_CACHE_HOME/meera"
MEERA_MODEL_DIR="$MEERA_CACHE_DIR/models"
MEERA_LLAMA_CACHE="$MEERA_CACHE_DIR/llama-cpp"
MEERA_LOG_DIR="$MEERA_CACHE_DIR/logs"
MEERA_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/meera"
MEERA_CHAT_PID="$MEERA_RUNTIME_DIR/llama-chat.pid"
MEERA_EMBED_PID="$MEERA_RUNTIME_DIR/llama-embed.pid"
MEERA_STATE_FILE="$MEERA_RUNTIME_DIR/servers.env"
MEERA_SETUP_COMPLETE_FILE="$MEERA_CONFIG_DIR/setup-complete"
MEERA_BIN="$HOME/.local/bin/meera"
MEERA_DESKTOP_FILE="$XDG_DATA_HOME/applications/local.meera.Meera.desktop"
MEERA_AUTOSTART_FILE="$XDG_CONFIG_HOME/autostart/meera.desktop"
MEERA_ICON_FILE="$XDG_DATA_HOME/icons/hicolor/256x256/apps/meera.png"

section() { printf '\n==> %s\n' "$1" >&2; }
info() { printf '%s\n' "$1"; }
warn() { printf 'Warning: %s\n' "$1" >&2; }
die() { printf 'Error: %s\n' "$1" >&2; exit 1; }

remove_dir_if_exists() {
  _dir="$1"
  [ -n "$_dir" ] || die "Refusing to remove an empty path"
  [ "$_dir" != "/" ] || die "Refusing to remove /"
  [ -d "$_dir" ] || return 0
  rm -r "$_dir"
}

check_python() { command -v python3 >/dev/null 2>&1; }
check_requests() { python3 -c 'import requests' >/dev/null 2>&1; }
check_gtk() { python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0"); gi.require_version("Gio", "2.0"); from gi.repository import Gtk, Gdk, Gio, Pango' >/dev/null 2>&1; }
check_curl() { command -v curl >/dev/null 2>&1; }

download_file() {
  _url="$1"; _dest="$2"; _sha="${3:-}"; _part="${_dest}.part"
  curl -fL --retry 3 -C - --proto '=https' -o "$_part" "$_url"
  if [ -n "$_sha" ]; then
    printf '%s  %s\n' "$_sha" "$_part" | sha256sum -c - >/dev/null || {
      rm -f "$_part"
      die "SHA256 mismatch for $_url"
    }
  fi
  mv -f "$_part" "$_dest"
}

has_render_node() {
  [ -e /dev/dri/renderD128 ] || [ -e /dev/dri/renderD129 ] || [ -e /dev/dri/renderD130 ]
}

os_family() {
  if [ -r /etc/os-release ]; then
    . /etc/os-release
    case " ${ID:-} ${ID_LIKE:-} " in
      *fedora*|*rhel*) printf 'fedora\n'; return ;;
      *debian*|*ubuntu*) printf 'ubuntu\n'; return ;;
    esac
  fi
  printf 'ubuntu\n'
}

select_llama_asset() {
  _backend="${1:-cpu}"
  _arch="$(uname -m)"
  _family="$(os_family)"
  LLAMA_ASSET=""
  LLAMA_SHA=""
  LLAMA_ID=""

  case "$_arch" in
    x86_64) _norm_arch="x86_64" ;;
    aarch64|arm64) _norm_arch="aarch64" ;;
    *) die "Unsupported CPU for bundled llama-server: $_arch" ;;
  esac

  if [ "$_backend" = "vulkan" ]; then
    [ "$_family" = "ubuntu" ] || return 1
    if [ "$_norm_arch" = "x86_64" ]; then
      LLAMA_ASSET="$MEERA_LLAMA_UBUNTU_VULKAN_X64_ASSET"
      LLAMA_SHA="$MEERA_SHA_LLAMA_UBUNTU_VULKAN_X64"
      LLAMA_ID="ubuntu-vulkan-x64"
    else
      LLAMA_ASSET="$MEERA_LLAMA_UBUNTU_VULKAN_ARM64_ASSET"
      LLAMA_SHA="$MEERA_SHA_LLAMA_UBUNTU_VULKAN_ARM64"
      LLAMA_ID="ubuntu-vulkan-arm64"
    fi
  else
    # Use the upstream Ubuntu CPU bundles as the portable default. The openEuler
    # llama.cpp assets can require Ascend runtime libraries (for example
    # libascendcl.so), which are not present on normal Fedora/Silverblue GNOME
    # systems. This matches the successful run_meera.sh behavior on Silverblue
    # when no mutable dnf package manager is available.
    if [ "$_norm_arch" = "x86_64" ]; then
      LLAMA_ASSET="$MEERA_LLAMA_UBUNTU_X64_ASSET"
      LLAMA_SHA="$MEERA_SHA_LLAMA_UBUNTU_X64"
      LLAMA_ID="ubuntu-x64"
    else
      LLAMA_ASSET="$MEERA_LLAMA_UBUNTU_ARM64_ASSET"
      LLAMA_SHA="$MEERA_SHA_LLAMA_UBUNTU_ARM64"
      LLAMA_ID="ubuntu-arm64"
    fi
  fi
  return 0
}

ensure_llama_bundle_for() {
  _backend="${1:-cpu}"
  select_llama_asset "$_backend" || return 1
  _root="$MEERA_LLAMA_CACHE/$MEERA_LLAMA_CPP_TAG"
  _archive="$_root/$LLAMA_ASSET"
  _extract="$_root/$LLAMA_ID"
  _bindir="$_extract/$MEERA_LLAMA_DIR_NAME"
  mkdir -p "$_root"

  if [ ! -x "$_bindir/llama-server" ]; then
    section "Downloading llama.cpp $_backend bundle"
    download_file "$MEERA_LLAMA_DL_BASE/$LLAMA_ASSET" "$_archive" "$LLAMA_SHA"
    remove_dir_if_exists "$_extract"
    mkdir -p "$_extract"
    tar xzf "$_archive" -C "$_extract"
  fi

  [ -x "$_bindir/llama-server" ] || die "Downloaded bundle is missing llama-server"
  LLAMA_BIN="$_bindir/llama-server"
  LLAMA_LIB_DIR="$_bindir"
  LLAMA_BACKEND="$_backend"
}

ensure_llama_bundle() {
  if has_render_node && ensure_llama_bundle_for vulkan; then
    return 0
  fi
  ensure_llama_bundle_for cpu
}

can_show_setup_ui() {
  [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && check_gtk
}

download_model_with_setup_ui() {
  _url="$1"; _dest="$2"; _sha="$3"; _name="$4"
  can_show_setup_ui || return 1
  _setup_script="$MEERA_APP_DIR/scripts/first_run_setup.py"
  [ -f "$_setup_script" ] || return 1
  python3 "$_setup_script" "$_url" "$_dest" "$_sha" "$_name"
}

download_model_with_progress_file() {
  _url="$1"; _dest="$2"; _sha="$3"; _progress_file="$4"
  python3 - "$_url" "$_dest" "$_sha" "$_progress_file" <<'PY'
import hashlib
import os
import sys
import urllib.request

url, dest, expected_sha, progress_file = sys.argv[1:5]
part = dest + ".part"


def verify_sha(path: str) -> None:
    if not expected_sha:
        return
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha:
        raise RuntimeError(f"SHA256 mismatch: expected {expected_sha}, got {actual}")


os.makedirs(os.path.dirname(dest), exist_ok=True)
request = urllib.request.Request(url, headers={"User-Agent": "Meera installer"})
with urllib.request.urlopen(request, timeout=60) as response:
    total = int(response.headers.get("Content-Length") or 0)
    downloaded = 0
    with open(part, "wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            with open(progress_file, "w", encoding="utf-8") as progress:
                progress.write(f"{downloaded} {total}")
verify_sha(part)
os.replace(part, dest)
PY
}

run_full_first_setup_ui() {
  can_show_setup_ui || return 1
  _setup_script="$MEERA_APP_DIR/scripts/first_run_setup.py"
  [ -f "$_setup_script" ] || return 1
  python3 "$_setup_script" --full-setup "$MEERA_BIN" first-run-worker
}

ensure_model() {
  _name="$1"; _url="$2"; _sha="$3"
  _path="$MEERA_MODEL_DIR/$_name"
  mkdir -p "$MEERA_MODEL_DIR"
  if [ ! -s "$_path" ]; then
    section "Downloading model $_name"
    if [ "$_name" = "$MEERA_CHAT_MODEL_NAME" ] && [ ! -f "$MEERA_SETUP_COMPLETE_FILE" ] && [ "${MEERA_SUPPRESS_SETUP_UI:-0}" != "1" ]; then
      download_model_with_setup_ui "$_url" "$_path" "$_sha" "$_name" || download_file "$_url" "$_path" "$_sha"
    elif [ "$_name" = "$MEERA_CHAT_MODEL_NAME" ] && [ -n "${MEERA_SETUP_PROGRESS_FILE:-}" ]; then
      download_model_with_progress_file "$_url" "$_path" "$_sha" "$MEERA_SETUP_PROGRESS_FILE"
    else
      download_file "$_url" "$_path" "$_sha"
    fi
  fi
  printf '%s\n' "$_path"
}

port_available() {
  python3 - "$1" <<'PY'
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
sys.exit(0)
PY
}

find_free_port() {
  _preferred="$1"; _start="$2"; _end="$3"; _exclude="${4:-}"
  for _port in "$_preferred" $(seq "$_start" "$_end"); do
    [ "$_port" = "$_exclude" ] && continue
    if port_available "$_port"; then
      printf '%s\n' "$_port"
      return 0
    fi
  done
  return 1
}

server_reachable() {
  _url="${1%/}"
  python3 - "$_url" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

try:
    urllib.request.urlopen(sys.argv[1] + "/v1/models", timeout=2)
except Exception:
    sys.exit(1)
sys.exit(0)
PY
}

pid_alive() {
  _pid_file="$1"
  [ -f "$_pid_file" ] || return 1
  _pid="$(cat "$_pid_file" 2>/dev/null || true)"
  [ -n "$_pid" ] && kill -0 "$_pid" >/dev/null 2>&1
}

wait_for_server() {
  _url="$1"; _log="$2"; _wait=0
  while [ "$_wait" -lt 45 ]; do
    server_reachable "$_url" && return 0
    sleep 1
    _wait=$((_wait + 1))
  done
  if [ -f "$_log" ]; then
    warn "Last lines from $_log:"
    tail -n 80 "$_log" >&2 || true
  fi
  die "Server did not become reachable at $_url. See $_log"
}

stop_pid_file() {
  _pid_file="$1"
  if pid_alive "$_pid_file"; then
    _pid="$(cat "$_pid_file")"
    kill "$_pid" >/dev/null 2>&1 || true
    _wait=0
    while kill -0 "$_pid" >/dev/null 2>&1 && [ "$_wait" -lt 10 ]; do
      sleep 1
      _wait=$((_wait + 1))
    done
    kill -9 "$_pid" >/dev/null 2>&1 || true
  fi
  rm -f "$_pid_file"
}

ensure_servers() {
  mkdir -p "$MEERA_RUNTIME_DIR" "$MEERA_LOG_DIR" "$MEERA_MODEL_DIR" "$MEERA_LLAMA_CACHE"

  _chat_url=""
  _embed_url=""
  if [ -f "$MEERA_STATE_FILE" ]; then
    # shellcheck disable=SC1090
    . "$MEERA_STATE_FILE" || true
    _chat_url="${MEERA_LLAMACPP_URL:-}"
    _embed_url="${MEERA_EMBED_URL:-}"
  fi

  if ! pid_alive "$MEERA_CHAT_PID" || [ -z "$_chat_url" ] || ! server_reachable "$_chat_url"; then
    stop_pid_file "$MEERA_CHAT_PID"
    ensure_llama_bundle
    _chat_model="$(ensure_model "$MEERA_CHAT_MODEL_NAME" "$MEERA_CHAT_MODEL_URL" "$MEERA_CHAT_MODEL_SHA256")"
    _chat_port="$(find_free_port 8080 8082 8089)"
    _chat_url="http://127.0.0.1:$_chat_port"
    _chat_ngl=0
    [ "${LLAMA_BACKEND:-cpu}" = "vulkan" ] && _chat_ngl=99
    section "Starting Meera chat model on $_chat_url"
    env LD_LIBRARY_PATH="${LLAMA_LIB_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
      "$LLAMA_BIN" -m "$_chat_model" --host 127.0.0.1 --port "$_chat_port" \
      -ngl "$_chat_ngl" --parallel 1 >"$MEERA_LOG_DIR/llama-chat.log" 2>&1 &
    echo "$!" >"$MEERA_CHAT_PID"
    wait_for_server "$_chat_url" "$MEERA_LOG_DIR/llama-chat.log"
  fi

  if ! pid_alive "$MEERA_EMBED_PID" || [ -z "$_embed_url" ] || ! server_reachable "$_embed_url"; then
    stop_pid_file "$MEERA_EMBED_PID"
    if [ -z "${LLAMA_BIN:-}" ]; then
      ensure_llama_bundle
    fi
    _embed_model="$(ensure_model "$MEERA_EMBED_MODEL_NAME" "$MEERA_EMBED_MODEL_URL" "$MEERA_EMBED_MODEL_SHA256")"
    _chat_port="${_chat_url##*:}"
    _embed_port="$(find_free_port 8081 8090 8099 "$_chat_port")"
    _embed_url="http://127.0.0.1:$_embed_port"
    section "Starting Meera embedding model on $_embed_url"
    env LD_LIBRARY_PATH="${LLAMA_LIB_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
      "$LLAMA_BIN" -m "$_embed_model" --host 127.0.0.1 --port "$_embed_port" \
      -ngl 0 --embeddings -c 512 >"$MEERA_LOG_DIR/llama-embed.log" 2>&1 &
    echo "$!" >"$MEERA_EMBED_PID"
    wait_for_server "$_embed_url" "$MEERA_LOG_DIR/llama-embed.log"
  fi

  cat >"$MEERA_STATE_FILE" <<EOF
MEERA_LLAMACPP_URL="$_chat_url"
MEERA_EMBED_URL="$_embed_url"
EOF
  mkdir -p "$MEERA_CONFIG_DIR"
  cat >"$MEERA_SETUP_COMPLETE_FILE" <<EOF
version="$MEERA_VERSION"
llama_cpp_tag="$MEERA_LLAMA_CPP_TAG"
chat_model="$MEERA_CHAT_MODEL_NAME"
embed_model="$MEERA_EMBED_MODEL_NAME"
completed_at="$(date -Iseconds 2>/dev/null || date)"
EOF
  export MEERA_BACKEND=llamacpp
  export MEERA_LLAMACPP_URL="$_chat_url"
  export MEERA_EMBED_URL="$_embed_url"
}

cmd_run() {
  check_python || die "python3 not found"
  check_requests || die "Python requests not available"
  check_gtk || die "GTK4/PyGObject runtime not available"
  check_curl || die "curl not found"
  if [ ! -f "$MEERA_SETUP_COMPLETE_FILE" ]; then
    run_full_first_setup_ui || cmd_first_run_worker
  else
    ensure_servers
  fi
  cd "$MEERA_APP_DIR"
  exec python3 meera.py
}

cmd_first_run_worker() {
  export MEERA_SUPPRESS_SETUP_UI=1
  ensure_servers
}

cmd_unload_model() {
  section "Stopping Meera model servers"
  stop_pid_file "$MEERA_CHAT_PID"
  stop_pid_file "$MEERA_EMBED_PID"
  rm -f "$MEERA_STATE_FILE"
}

cmd_restart_model() {
  cmd_unload_model
  ensure_servers
  info "Model servers restarted."
}

cmd_logs() {
  mkdir -p "$MEERA_LOG_DIR"
  info "Log directory: $MEERA_LOG_DIR"
  for _log in "$MEERA_LOG_DIR"/*.log; do
    [ -e "$_log" ] || continue
    printf '\n--- %s ---\n' "$_log"
    tail -n 80 "$_log"
  done
}

cmd_doctor() {
  section "Meera doctor"
  printf 'Version: %s\n' "$MEERA_VERSION"
  printf 'App dir: %s\n' "$MEERA_APP_DIR"
  printf 'Model dir: %s\n' "$MEERA_MODEL_DIR"
  check_python && info "python3: ok" || warn "python3: missing"
  check_requests && info "requests: ok" || warn "requests: missing"
  check_gtk && info "GTK4/PyGObject: ok" || warn "GTK4/PyGObject: missing"
  check_curl && info "curl: ok" || warn "curl: missing"
  if [ -f "$MEERA_STATE_FILE" ]; then
    info "Server state:"
    sed 's/^/  /' "$MEERA_STATE_FILE"
  else
    info "Server state: not running"
  fi
  if [ -f "$MEERA_SETUP_COMPLETE_FILE" ]; then
    info "First-run setup: complete"
  else
    info "First-run setup: pending"
  fi
  pid_alive "$MEERA_CHAT_PID" && info "chat server process: running" || info "chat server process: stopped"
  pid_alive "$MEERA_EMBED_PID" && info "embedding server process: running" || info "embedding server process: stopped"
}

cmd_update() {
  [ -n "$MEERA_INSTALLER_URL" ] || die "Updates are not configured for this build."
  section "Updating Meera"
  curl -fsSL "$MEERA_INSTALLER_URL" | sh
}

cmd_uninstall() {
  if [ -r /dev/tty ]; then
    printf 'Uninstall Meera, including models, config, logs, and history? [y/N] ' >/dev/tty
    IFS= read -r _answer </dev/tty || _answer=""
  else
    _answer=""
  fi
  case "$_answer" in
    [Yy]|[Yy][Ee][Ss]) ;;
    *) info "Uninstall cancelled."; exit 0 ;;
  esac

  cmd_unload_model
  remove_dir_if_exists "$MEERA_APP_DIR"
  remove_dir_if_exists "$MEERA_DATA_DIR"
  remove_dir_if_exists "$MEERA_CONFIG_DIR"
  remove_dir_if_exists "$MEERA_CACHE_DIR"
  rm -f "$MEERA_BIN" "$MEERA_DESKTOP_FILE" "$MEERA_AUTOSTART_FILE" "$MEERA_ICON_FILE"
  info "Meera uninstalled."
}

case "${1:-run}" in
  run) cmd_run ;;
  first-run-worker) cmd_first_run_worker ;;
  update) cmd_update ;;
  uninstall) cmd_uninstall ;;
  doctor) cmd_doctor ;;
  logs) cmd_logs ;;
  restart-model) cmd_restart_model ;;
  unload-model) cmd_unload_model ;;
  *)
    cat <<'EOF'
Usage: meera [command]

Commands:
  run             Start Meera (default)
  update          Update Meera using the configured installer URL
  uninstall       Remove Meera, including downloaded models
  doctor          Check runtime dependencies and server state
  logs            Show recent Meera logs
  restart-model   Restart local llama.cpp model servers
  unload-model    Stop local llama.cpp model servers
EOF
    exit 2
    ;;
esac
