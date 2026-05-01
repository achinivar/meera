# Processes, jobs, and systemd services

## Overview

**User processes** — inspect with **`ps`**/**`pgrep`**, stop with **`kill`**/**`pkill`**. **systemd** manages **services**; use **`journalctl -u <unit>`** for service logs, not only **`ps`**. A **wrong unit name** or typo in **`systemctl`** makes commands look like “nothing is wrong” while the real service has another name.

**Safety:** confirm PID/name before **`kill -9`** or **`pkill`**—they can match or terminate more than you intend. Service start/stop affects all users.

**Sources:** [ps(1)](https://man7.org/linux/man-pages/man1/ps.1.html), [kill(1)](https://man7.org/linux/man-pages/man1/kill.1.html), [systemctl](https://www.freedesktop.org/software/systemd/man/systemctl.html), [journalctl](https://www.freedesktop.org/software/systemd/man/journalctl.html).

## View processes, filter by name, and shell jobs

**Full listing (BSD-style)** — common on desktops; shows USER, PID, command:

```bash
ps aux
```

**POSIX-style** tree of parent/child PIDs:

```bash
ps -ef
```

**Narrow to one app** — pipe into `grep` (your search also appears as a `grep` line; that is normal):

```bash
ps aux | grep firefox
```

**Cleaner name search** without extra `grep` noise:

```bash
pgrep -a firefox
```

**Live** resource view:

```bash
top
```

**Interactive** monitor if installed:

```bash
htop
```

**Background job** in the current shell — run, list, bring to foreground:

```bash
sleep 100 &
jobs
fg %1
```

## Stop and signal processes

**Polite** stop by PID (SIGTERM):

```bash
kill <pid>
```

**Force** kill when the process ignores SIGTERM:

```bash
kill -9 <pid>
```

**By pattern** — **`pkill`** can match **multiple** processes; use **`pgrep <pattern>`** first to see PIDs:

```bash
pkill firefox
```

Prefer **`kill <pid>`** after identifying the PID; use **`-9`** only when necessary.

## systemd: services, boot, and journal logs

**Status** — replace `sshd` with your unit (`systemctl` usually accepts the short name):

```bash
systemctl status sshd
systemctl status NetworkManager
```

**Start, stop, restart** (typically need root):

```bash
sudo systemctl start <service>
sudo systemctl stop <service>
sudo systemctl restart <service>
```

**Enable or disable** starting at boot:

```bash
sudo systemctl enable <service>
sudo systemctl disable <service>
```

**Logs for one unit** — all messages, or last 100 lines:

```bash
journalctl -u <service>
journalctl -u <service> -n 100
```

**Follow** all logs live, or **this boot only**:

```bash
journalctl -f
journalctl -b
```
