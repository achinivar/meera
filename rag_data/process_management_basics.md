# Process Management Basics

## What it is

Process management commands let you inspect, prioritize, and stop running programs.

## When to use it

Use these commands when apps freeze, consume too much CPU/RAM, or need to run in background.

## View processes

```bash
ps aux
ps -ef
top
```

If installed, `htop` provides a friendlier interactive view:

```bash
htop
```

## Stop processes

```bash
kill <pid>
kill -9 <pid>
pkill <name>
```

Guideline:

- Try normal termination (`kill`) first.
- Use `-9` only when a process does not respond.

## Background jobs in shell

```bash
sleep 100 &
jobs
fg %1
```

## Common mistakes

- Killing the wrong PID.
- Using `kill -9` too early.
- Forgetting that `pkill` may match multiple processes.

## Safety notes

- Prefer graceful termination first (`kill` / SIGTERM).
- Confirm command target with `ps` before sending signals.

## Related commands

- `nice`, `renice`, `systemctl`, `journalctl`

## Sources

- `ps` man page: https://man7.org/linux/man-pages/man1/ps.1.html
- `kill` man page: https://man7.org/linux/man-pages/man1/kill.1.html
- `top` man page: https://man7.org/linux/man-pages/man1/top.1.html

