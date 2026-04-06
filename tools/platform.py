"""Detect Linux distribution family for Ubuntu vs Fedora-style tooling."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

Distro = Literal["ubuntu", "fedora"]

_OS_RELEASE = Path("/etc/os-release")

# Map to "ubuntu" (apt) or "fedora" (dnf/rpm) per Phase2_plan.md §4.4
_APT_IDS = frozenset({"ubuntu", "debian", "pop", "linuxmint"})
_RPM_IDS = frozenset({"fedora", "rhel", "centos", "rocky", "almalinux"})


class DistroUnknownError(RuntimeError):
    """Host OS is not mapped to ubuntu|fedora."""


def _parse_os_release(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        out[k.strip()] = v
    return out


def detect_distro() -> Distro:
    if not _OS_RELEASE.is_file():
        raise DistroUnknownError("/etc/os-release not found")
    raw = _OS_RELEASE.read_text(encoding="utf-8", errors="replace")
    data = _parse_os_release(raw)
    id_ = data.get("ID", "").lower()
    id_like = data.get("ID_LIKE", "").lower().split()

    if id_ in _APT_IDS or "ubuntu" in id_like or "debian" in id_like:
        return "ubuntu"
    if id_ in _RPM_IDS or any(x in id_like for x in ("fedora", "rhel", "centos")):
        return "fedora"
    raise DistroUnknownError(
        f"Unsupported ID={id_!r} ID_LIKE={id_like!r}; expected Ubuntu/apt or Fedora/rpm family"
    )
