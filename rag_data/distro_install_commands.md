# Distro-Specific Package Installation Commands

## What this guide is for

This guide maps common package-management tasks to Debian/Ubuntu, Fedora/RPM-based systems, and Arch Linux.

## When to use it

Use this when you know what software you want and need the correct install/remove/update command for your distro.

## Detect your distro

```bash
cat /etc/os-release
```

Look at `ID` and `ID_LIKE` values.

## Install a package

### Debian/Ubuntu

```bash
sudo apt update
sudo apt install <package-name>
```

### Fedora (RPM-based)

```bash
sudo dnf install <package-name>
```

### Arch Linux

```bash
sudo pacman -S <package-name>
```

Example installs:

- Debian/Ubuntu: `sudo apt install ripgrep`
- Fedora: `sudo dnf install ripgrep`
- Arch: `sudo pacman -S ripgrep`

## Update system packages

### Debian/Ubuntu

```bash
sudo apt update
sudo apt upgrade
```

### Fedora

```bash
sudo dnf upgrade
```

### Arch Linux

```bash
sudo pacman -Syu
```

## Remove a package

### Debian/Ubuntu

```bash
sudo apt remove <package-name>
```

Use `--purge` to also remove config files:

```bash
sudo apt remove --purge <package-name>
```

### Fedora

```bash
sudo dnf remove <package-name>
```

### Arch Linux

```bash
sudo pacman -R <package-name>
```

## Search for packages

### Debian/Ubuntu

```bash
apt search <term>
```

### Fedora

```bash
dnf search <term>
```

### Arch Linux

```bash
pacman -Ss <term>
```

## Notes

- `apt` is generally preferred for interactive usage on Ubuntu.
- `dnf` is the default package manager on Fedora.
- `pacman` is the native package manager for Arch Linux.

## Common mistakes

- Copying commands from another distro family.
- Forgetting to refresh metadata first (`apt update`, `pacman -Syu`).
- Confusing package names across distros.

## Safety notes

- Package installs/removals modify the system.
- Review prompts before confirming, especially on production machines.

## Related commands

- `flatpak`, `rpm-ostree` (Silverblue host), `toolbox` (Silverblue dev workflows)

## Sources

- Ubuntu package management docs: https://documentation.ubuntu.com/server/how-to/software/package-management/index.html
- DNF command reference: https://dnf.readthedocs.io/en/stable/command_ref.html
- ArchWiki pacman: https://wiki.archlinux.org/title/Pacman

