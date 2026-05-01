# Package installation by distro (and Fedora Atomic)

## Overview

This guide maps **install**, **upgrade**, **remove**, and **search** to **Debian/Ubuntu** (`apt`), **Fedora-class** (`dnf`), **Arch** (`pacman`), and **Fedora Atomic / Silverblue** (Flatpak, Toolbox, `rpm-ostree`). **Pick commands that match `ID` / `ID_LIKE` in `/etc/os-release`**—running `apt` on Fedora or `dnf` on Ubuntu will not work.

**Safety:** read install/remove prompts. On Atomic hosts prefer **Flatpak** and **Toolbox**; many **`rpm-ostree install`** layers mean more reboots and harder rollbacks.

**Sources:** [Ubuntu package management](https://documentation.ubuntu.com/server/how-to/software/package-management/index.html), [DNF reference](https://dnf.readthedocs.io/en/stable/command_ref.html), [ArchWiki pacman](https://wiki.archlinux.org/title/Pacman), [Silverblue docs](https://docs.fedoraproject.org/en-US/fedora-silverblue/), [Toolbox](https://containertoolbx.org/doc/).

## Detect your distro

Print OS metadata; read **`ID`** and **`ID_LIKE`**:

```bash
cat /etc/os-release
```

## Install a package

**Debian/Ubuntu** — metadata must be current before new packages show up:

```bash
sudo apt update
sudo apt install <package-name>
```

**Fedora / RPM family:**

```bash
sudo dnf install <package-name>
```

**Arch Linux:**

```bash
sudo pacman -S <package-name>
```

Example same app on all three: `ripgrep` — `apt install ripgrep`, `dnf install ripgrep`, `pacman -S ripgrep` (exact package names can differ slightly by distro).

## Upgrade installed packages

**Debian/Ubuntu:**

```bash
sudo apt update
sudo apt upgrade
```

**Fedora:**

```bash
sudo dnf upgrade
```

**Arch** — **`Syu`** refreshes databases then upgrades (expect new packages only after a successful sync):

```bash
sudo pacman -Syu
```

## Remove a package

**Debian/Ubuntu** — remove; add **`--purge`** to drop config files:

```bash
sudo apt remove <package-name>
sudo apt remove --purge <package-name>
```

**Fedora:**

```bash
sudo dnf remove <package-name>
```

**Arch:**

```bash
sudo pacman -R <package-name>
```

## Search package indexes

**Debian/Ubuntu:**

```bash
apt search <term>
```

**Fedora:**

```bash
dnf search <term>
```

**Arch:**

```bash
pacman -Ss <term>
```

## Fedora Atomic / Silverblue: what is different

**Silverblue** (and related Atomic Desktops) use an **immutable** base image: the host is updated as a **whole image**, not endlessly mutated in place. Rollbacks switch boot entries. Typical software paths:

1. **Flatpak** — desktop apps.
2. **Toolbox (`toolbox`)** — mutable CLI/dev environments (DNF inside the container).
3. **`rpm-ostree` layering** — extra RPMs fused into the host image when you truly need them on the base.

Do **not** rely on **`sudo dnf install`** on the host the way you would on classic Fedora Workstation.

## Toolbox workflow (CLI and dev packages)

Create and enter a toolbox; use **DNF inside** for compilers, language stacks, etc.:

```bash
toolbox create
toolbox enter
sudo dnf install <dev-package>
```

Prefer this for development so the host image stays minimal.

## rpm-ostree: layer packages on the host

Install an RPM into the **pending** deployment, then **reboot** so you boot into the new image:

```bash
rpm-ostree install <package-name>
systemctl reboot
```

Check status and upgrade the image:

```bash
rpm-ostree status
rpm-ostree upgrade
```

**When to use what:** desktop app → **Flatpak**; dev shell → **Toolbox**; driver/kernel/module that must live on host → consider **layering** sparingly.
