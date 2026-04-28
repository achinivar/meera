#!/bin/sh
set -eu

###############################################################################
# Meera public installer configuration.
# Keep release/model/asset values here so release bumps are easy to review.
###############################################################################

MEERA_VERSION="${MEERA_VERSION:-dev}"
MEERA_RELEASE_URL="${MEERA_RELEASE_URL:-}"
MEERA_RELEASE_SHA256="${MEERA_RELEASE_SHA256:-e2b2d734cec52d3c3f20b1959a9eec5aa9de3bed9c5ee7bafb246908353cf8f7}"
MEERA_INSTALLER_URL="${MEERA_INSTALLER_URL:-}"

MEERA_LLAMA_CPP_TAG="${MEERA_LLAMA_CPP_TAG:-b8672}"
MEERA_LLAMA_DL_BASE="https://github.com/ggml-org/llama.cpp/releases/download/${MEERA_LLAMA_CPP_TAG}"
MEERA_LLAMA_DIR_NAME="llama-${MEERA_LLAMA_CPP_TAG}"

MEERA_LLAMA_UBUNTU_X64_ASSET="llama-${MEERA_LLAMA_CPP_TAG}-bin-ubuntu-x64.tar.gz"
MEERA_LLAMA_UBUNTU_ARM64_ASSET="llama-${MEERA_LLAMA_CPP_TAG}-bin-ubuntu-arm64.tar.gz"
MEERA_LLAMA_OE_X86_ASSET="llama-${MEERA_LLAMA_CPP_TAG}-bin-310p-openEuler-x86.tar.gz"
MEERA_LLAMA_OE_AARCH64_ASSET="llama-${MEERA_LLAMA_CPP_TAG}-bin-310p-openEuler-aarch64.tar.gz"
MEERA_LLAMA_UBUNTU_VULKAN_X64_ASSET="llama-${MEERA_LLAMA_CPP_TAG}-bin-ubuntu-vulkan-x64.tar.gz"
MEERA_LLAMA_UBUNTU_VULKAN_ARM64_ASSET="llama-${MEERA_LLAMA_CPP_TAG}-bin-ubuntu-vulkan-arm64.tar.gz"

MEERA_SHA_LLAMA_UBUNTU_X64="e5274949bd1d94882454abdc9b131cf3e250678026de30fa3b365e4f8f61d824"
MEERA_SHA_LLAMA_UBUNTU_ARM64="2306d31bb232b604fc0478e6c2cf1a673aab8cdcdc782925fed2d7eb51afa825"
MEERA_SHA_LLAMA_OE_X86="cfde7b3bc243a7105a9a9773d78d5635ff446b2a4397d2386d848ff83c637866"
MEERA_SHA_LLAMA_OE_AARCH64="fe75fbdc34214e08ec476430932f6316e46e3d36ed56498628a1a18160537129"
MEERA_SHA_LLAMA_UBUNTU_VULKAN_X64="3832d9fade4aa7b36d4095f5a84fefe7f5849c4bde53f9a60857a029897930b1"
MEERA_SHA_LLAMA_UBUNTU_VULKAN_ARM64="fc7b913426030c49fbb16a44f1e06ed8391eba80a7409fc5107c1472e6838265"

MEERA_CHAT_MODEL_NAME="Qwen3.5-2B-Q4_K_M.gguf"
MEERA_CHAT_MODEL_URL="https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/${MEERA_CHAT_MODEL_NAME}"
MEERA_CHAT_MODEL_SHA256=""

MEERA_EMBED_MODEL_NAME="bge-small-en-v1.5-q8_0.gguf"
MEERA_EMBED_MODEL_URL="https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf/resolve/main/${MEERA_EMBED_MODEL_NAME}"
MEERA_EMBED_MODEL_SHA256=""

###############################################################################

APP_NAME="Meera"
APP_ID="meera"

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"

MEERA_DATA_DIR="$XDG_DATA_HOME/meera"
MEERA_APP_DIR="$MEERA_DATA_DIR/app"
MEERA_HISTORY_DIR="$MEERA_DATA_DIR/history"
MEERA_CONFIG_DIR="$XDG_CONFIG_HOME/meera"
MEERA_CACHE_DIR="$XDG_CACHE_HOME/meera"
MEERA_MODEL_DIR="$MEERA_CACHE_DIR/models"
MEERA_LLAMA_CACHE="$MEERA_CACHE_DIR/llama-cpp"
MEERA_LOG_DIR="$MEERA_CACHE_DIR/logs"
MEERA_BIN_DIR="$HOME/.local/bin"
MEERA_BIN="$MEERA_BIN_DIR/meera"
MEERA_DESKTOP_DIR="$XDG_DATA_HOME/applications"
MEERA_DESKTOP_FILE="$MEERA_DESKTOP_DIR/local.meera.Meera.desktop"
MEERA_AUTOSTART_DIR="$XDG_CONFIG_HOME/autostart"
MEERA_AUTOSTART_FILE="$MEERA_AUTOSTART_DIR/meera.desktop"
MEERA_ICON_DIR="$XDG_DATA_HOME/icons/hicolor/256x256/apps"
MEERA_ICON_FILE="$MEERA_ICON_DIR/meera.png"
MEERA_MANIFEST="$MEERA_CONFIG_DIR/install-manifest"

section() {
  printf '\n==> %s\n' "$1"
}

info() {
  printf '%s\n' "$1"
}

warn() {
  printf 'Warning: %s\n' "$1" >&2
}

die() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

remove_dir_if_exists() {
  _dir="$1"
  [ -n "$_dir" ] || die "Refusing to remove an empty path"
  [ "$_dir" != "/" ] || die "Refusing to remove /"
  [ -d "$_dir" ] || return 0
  rm -r "$_dir"
}

prompt_yes_no() {
  _prompt="$1"
  _default="${2:-no}"
  _suffix="[y/N]"
  [ "$_default" = "yes" ] && _suffix="[Y/n]"

  if [ -r /dev/tty ]; then
    printf '%s %s ' "$_prompt" "$_suffix" >/dev/tty
    IFS= read -r _answer </dev/tty || _answer=""
  else
    _answer=""
  fi

  case "$_answer" in
    [Yy]|[Yy][Ee][Ss]) return 0 ;;
    [Nn]|[Nn][Oo]) return 1 ;;
    "") [ "$_default" = "yes" ] ;;
    *) return 1 ;;
  esac
}

is_ostree_host() {
  [ -e /run/ostree-booted ]
}

detect_pkg_manager() {
  if command -v apt-get >/dev/null 2>&1; then
    printf 'apt\n'
  elif command -v dnf >/dev/null 2>&1 && ! is_ostree_host; then
    printf 'dnf\n'
  else
    printf 'none\n'
  fi
}

check_python() {
  command -v python3 >/dev/null 2>&1
}

check_requests() {
  python3 -c 'import requests' >/dev/null 2>&1
}

check_gtk() {
  python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0"); gi.require_version("Gio", "2.0"); from gi.repository import Gtk, Gdk, Gio, Pango' >/dev/null 2>&1
}

check_curl() {
  command -v curl >/dev/null 2>&1
}

missing_dependencies() {
  _missing=""
  check_python || _missing="${_missing} python3"
  if check_python; then
    check_requests || _missing="${_missing} requests"
    check_gtk || _missing="${_missing} gtk"
  fi
  check_curl || _missing="${_missing} curl"
  printf '%s\n' "$_missing"
}

install_dependencies_if_needed() {
  section "Checking runtime dependencies"
  _missing="$(missing_dependencies)"
  if [ -z "$_missing" ]; then
    info "Runtime dependencies found."
    return 0
  fi

  warn "Missing runtime dependencies:$_missing"

  if is_ostree_host; then
    cat >&2 <<'EOF'
This looks like an immutable Fedora/Silverblue-style host.
Meera can run here when the runtime dependencies are already present, but this
installer will not run dnf on an ostree host. Install or layer the missing
runtime packages with rpm-ostree, then run this installer again.
EOF
    exit 1
  fi

  _pkg_manager="$(detect_pkg_manager)"
  case "$_pkg_manager" in
    apt)
      _packages=""
      printf '%s\n' "$_missing" | grep -q 'python3' && _packages="${_packages} python3"
      printf '%s\n' "$_missing" | grep -q 'requests' && _packages="${_packages} python3-requests"
      printf '%s\n' "$_missing" | grep -q 'gtk' && _packages="${_packages} python3-gi gir1.2-gtk-4.0"
      printf '%s\n' "$_missing" | grep -q 'curl' && _packages="${_packages} curl"
      if prompt_yes_no "Install missing packages with apt?" "no"; then
        sudo apt-get update
        # shellcheck disable=SC2086
        sudo apt-get install -y $_packages
      else
        die "Install the missing dependencies and rerun the installer."
      fi
      ;;
    dnf)
      _packages=""
      printf '%s\n' "$_missing" | grep -q 'python3' && _packages="${_packages} python3"
      printf '%s\n' "$_missing" | grep -q 'requests' && _packages="${_packages} python3-requests"
      printf '%s\n' "$_missing" | grep -q 'gtk' && _packages="${_packages} python3-gobject gtk4"
      printf '%s\n' "$_missing" | grep -q 'curl' && _packages="${_packages} curl"
      if prompt_yes_no "Install missing packages with dnf?" "no"; then
        # shellcheck disable=SC2086
        sudo dnf install -y $_packages
      else
        die "Install the missing dependencies and rerun the installer."
      fi
      ;;
    *)
      die "No supported package manager found for missing dependencies. Install them manually and rerun the installer."
      ;;
  esac

  _missing_after="$(missing_dependencies)"
  [ -z "$_missing_after" ] || die "Dependencies are still missing:$_missing_after"
}

sha256_verify() {
  _file="$1"
  _expected="$2"
  [ -n "$_expected" ] || return 0
  printf '%s  %s\n' "$_expected" "$_file" | sha256sum -c - >/dev/null
}

download_file() {
  _url="$1"
  _dest="$2"
  _sha="${3:-}"
  _part="${_dest}.part"
  curl -fL --retry 3 -C - --proto '=https' -o "$_part" "$_url"
  if [ -n "$_sha" ]; then
    sha256_verify "$_part" "$_sha" || {
      rm -f "$_part"
      die "SHA256 mismatch for $_url"
    }
  fi
  mv -f "$_part" "$_dest"
}

copy_checkout_source() {
  _src="$1"
  _dest="$2"
  mkdir -p "$_dest"
  (
    cd "$_src"
    tar \
      --exclude='.git' \
      --exclude='.cache' \
      --exclude='history' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='.venv' \
      --exclude='venv' \
      --exclude='env' \
      -cf - .
  ) | tar -xf - -C "$_dest"
}

install_release_source() {
  section "Installing Meera app files"
  _tmp="$(mktemp -d)"
  trap 'remove_dir_if_exists "$_tmp"' EXIT

  _script_path="${MEERA_INSTALLER_SOURCE:-$0}"
  _script_dir="$(cd "$(dirname "$_script_path")" 2>/dev/null && pwd || printf '.')"
  if [ -f "$_script_dir/meera.py" ] && [ -d "$_script_dir/ui" ]; then
    info "Installing from local checkout: $_script_dir"
    copy_checkout_source "$_script_dir" "$_tmp/app"
  else
    [ -n "$MEERA_RELEASE_URL" ] || die "MEERA_RELEASE_URL is not set and this is not a checkout install."
    _archive="$_tmp/meera.tar.gz"
    info "Downloading Meera release: $MEERA_RELEASE_URL"
    download_file "$MEERA_RELEASE_URL" "$_archive" "$MEERA_RELEASE_SHA256"
    mkdir -p "$_tmp/extract"
    tar -xzf "$_archive" -C "$_tmp/extract"
    if [ -f "$_tmp/extract/meera.py" ]; then
      copy_checkout_source "$_tmp/extract" "$_tmp/app"
    else
      _src="$(find "$_tmp/extract" -mindepth 1 -maxdepth 2 -type f -name meera.py -print -quit)"
      [ -n "$_src" ] || die "Release archive does not contain meera.py"
      copy_checkout_source "$(dirname "$_src")" "$_tmp/app"
    fi
  fi

  remove_dir_if_exists "$MEERA_APP_DIR"
  mkdir -p "$MEERA_DATA_DIR"
  mv "$_tmp/app" "$MEERA_APP_DIR"
  mkdir -p "$MEERA_HISTORY_DIR" "$MEERA_CONFIG_DIR" "$MEERA_MODEL_DIR" "$MEERA_LLAMA_CACHE" "$MEERA_LOG_DIR"
  remove_dir_if_exists "$MEERA_LLAMA_CACHE/$MEERA_LLAMA_CPP_TAG/openEuler-x86"
  remove_dir_if_exists "$MEERA_LLAMA_CACHE/$MEERA_LLAMA_CPP_TAG/openEuler-aarch64"
  trap - EXIT
  remove_dir_if_exists "$_tmp"
}

write_launcher_config() {
  mkdir -p "$MEERA_CONFIG_DIR"
  cat >"$MEERA_CONFIG_DIR/launcher.env" <<EOF
MEERA_VERSION="$MEERA_VERSION"
MEERA_INSTALLER_URL="$MEERA_INSTALLER_URL"
MEERA_LLAMA_CPP_TAG="$MEERA_LLAMA_CPP_TAG"
MEERA_LLAMA_DL_BASE="$MEERA_LLAMA_DL_BASE"
MEERA_LLAMA_DIR_NAME="$MEERA_LLAMA_DIR_NAME"
MEERA_LLAMA_UBUNTU_X64_ASSET="$MEERA_LLAMA_UBUNTU_X64_ASSET"
MEERA_LLAMA_UBUNTU_ARM64_ASSET="$MEERA_LLAMA_UBUNTU_ARM64_ASSET"
MEERA_LLAMA_OE_X86_ASSET="$MEERA_LLAMA_OE_X86_ASSET"
MEERA_LLAMA_OE_AARCH64_ASSET="$MEERA_LLAMA_OE_AARCH64_ASSET"
MEERA_LLAMA_UBUNTU_VULKAN_X64_ASSET="$MEERA_LLAMA_UBUNTU_VULKAN_X64_ASSET"
MEERA_LLAMA_UBUNTU_VULKAN_ARM64_ASSET="$MEERA_LLAMA_UBUNTU_VULKAN_ARM64_ASSET"
MEERA_SHA_LLAMA_UBUNTU_X64="$MEERA_SHA_LLAMA_UBUNTU_X64"
MEERA_SHA_LLAMA_UBUNTU_ARM64="$MEERA_SHA_LLAMA_UBUNTU_ARM64"
MEERA_SHA_LLAMA_OE_X86="$MEERA_SHA_LLAMA_OE_X86"
MEERA_SHA_LLAMA_OE_AARCH64="$MEERA_SHA_LLAMA_OE_AARCH64"
MEERA_SHA_LLAMA_UBUNTU_VULKAN_X64="$MEERA_SHA_LLAMA_UBUNTU_VULKAN_X64"
MEERA_SHA_LLAMA_UBUNTU_VULKAN_ARM64="$MEERA_SHA_LLAMA_UBUNTU_VULKAN_ARM64"
MEERA_CHAT_MODEL_NAME="$MEERA_CHAT_MODEL_NAME"
MEERA_CHAT_MODEL_URL="$MEERA_CHAT_MODEL_URL"
MEERA_CHAT_MODEL_SHA256="$MEERA_CHAT_MODEL_SHA256"
MEERA_EMBED_MODEL_NAME="$MEERA_EMBED_MODEL_NAME"
MEERA_EMBED_MODEL_URL="$MEERA_EMBED_MODEL_URL"
MEERA_EMBED_MODEL_SHA256="$MEERA_EMBED_MODEL_SHA256"
EOF
}

write_launcher() {
  section "Installing meera launcher"
  mkdir -p "$MEERA_BIN_DIR"
  write_launcher_config

  _launcher_src="$MEERA_APP_DIR/scripts/meera-launcher.sh"
  [ -f "$_launcher_src" ] || die "Missing launcher template: $_launcher_src"
  cp "$_launcher_src" "$MEERA_BIN"
  chmod +x "$MEERA_BIN"
}

install_icon_if_present() {
  _src=""
  for _candidate in "$MEERA_APP_DIR/assets/meera.png" "$MEERA_APP_DIR/assets/icon.png" "$MEERA_APP_DIR/meera.png"; do
    if [ -f "$_candidate" ]; then
      _src="$_candidate"
      break
    fi
  done
  [ -n "$_src" ] || return 0
  mkdir -p "$MEERA_ICON_DIR"
  cp "$_src" "$MEERA_ICON_FILE"
}

write_desktop_file() {
  section "Installing GNOME desktop launcher"
  mkdir -p "$MEERA_DESKTOP_DIR"
  install_icon_if_present

  _icon="meera"
  [ -f "$MEERA_ICON_FILE" ] || _icon="applications-system"

  cat >"$MEERA_DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Meera
Comment=Local GNOME AI Assistant
Exec=$MEERA_BIN
Icon=$_icon
Terminal=false
Categories=Utility;GTK;
StartupNotify=true
EOF

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$MEERA_DESKTOP_DIR" >/dev/null 2>&1 || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "$XDG_DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
  fi
}

write_manifest() {
  mkdir -p "$MEERA_CONFIG_DIR"
  cat >"$MEERA_MANIFEST" <<EOF
version=$MEERA_VERSION
app_dir=$MEERA_APP_DIR
bin=$MEERA_BIN
desktop_file=$MEERA_DESKTOP_FILE
autostart_file=$MEERA_AUTOSTART_FILE
icon_file=$MEERA_ICON_FILE
model_dir=$MEERA_MODEL_DIR
llama_cache=$MEERA_LLAMA_CACHE
log_dir=$MEERA_LOG_DIR
EOF
}

main() {
  section "Meera installer"
  install_dependencies_if_needed
  install_release_source
  write_launcher
  write_desktop_file
  write_manifest

  section "Installation complete"
  info "Launch Meera from GNOME app search, or run:"
  info "  meera"
  info ""
  info "Useful commands:"
  info "  meera doctor"
  info "  meera logs"
  info "  meera unload-model"
  info "  meera uninstall"
}

main "$@"
