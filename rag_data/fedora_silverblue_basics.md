# Fedora Silverblue Basics

## What it is

Fedora Silverblue is an Atomic Desktop edition of Fedora with an immutable base OS.

## When to use this guide

Use this guide when learning how software installation works differently on Silverblue compared with traditional Fedora Workstation.

## What "immutable" means in Silverblue

- The core OS image is managed atomically instead of being modified package-by-package in place.
- Updates are transactional: you boot into a new deployment.
- Rollbacks are supported by selecting a previous deployment.
- This model reduces host drift and makes breakage recovery easier.

## Package/app model on Silverblue

Silverblue typically uses three paths:

1. Flatpak for GUI applications.
2. Toolbox for development CLI environments.
3. rpm-ostree layering for host-level RPMs when needed.

## Toolbox (toolbx)

Toolbox gives you a mutable container-like environment integrated with your user session.

Common flow:

```bash
toolbox create
toolbox enter
sudo dnf install <dev-package>
```

Use Toolbox for most CLI/dev workflows so the host remains clean.

## rpm-ostree layering

Layering adds RPMs to the host image.

Example:

```bash
rpm-ostree install <package-name>
systemctl reboot
```

After reboot, the layered package is available on the host.

Useful commands:

```bash
rpm-ostree status
rpm-ostree upgrade
```

## When to use what

- Need a desktop app: prefer Flatpak.
- Need dev tools and shells: prefer Toolbox.
- Need host-level integration: use rpm-ostree layering.

## Common mistakes

- Trying to use host `dnf install` like a mutable distro.
- Layering too many packages instead of using Toolbox or Flatpak.
- Forgetting reboot after rpm-ostree changes.

## Safety notes

- Layering modifies host deployments; validate package choices before applying.
- Keep at least one known-good deployment for rollback confidence.

## Related commands

- `flatpak`, `toolbox`, `rpm-ostree status`, `rpm-ostree rollback`

## Sources

- Fedora Silverblue docs: https://docs.fedoraproject.org/en-US/fedora-silverblue/
- Fedora Silverblue Toolbox docs: https://docs.fedoraproject.org/en-US/fedora-silverblue/toolbox/
- Fedora Atomic Desktops (Silverblue): https://fedoraproject.org/atomic-desktops/silverblue/
- Toolbox docs: https://containertoolbx.org/doc/

