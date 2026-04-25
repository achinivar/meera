# Linux Help and Discovery

## What it is

This guide covers built-in ways to discover commands and read documentation directly in Linux.

## When to use it

Use these commands whenever you find an unfamiliar command or need authoritative syntax quickly.

## Built-in help

```bash
<command> --help
```

Examples:

```bash
grep --help
tar --help
```

## Manual pages

```bash
man grep
man tar
man 5 passwd
```

`man 5 passwd` means section 5 (file formats), while section 1 is user commands.

## Discover command paths and types

```bash
which python3
type cd
```

`type` is especially useful because it can show shell builtins, aliases, and functions.

## Search man page names/descriptions

```bash
apropos network
```

## Common mistakes

- Reading the wrong man section.
- Assuming online guides match your installed command version.
- Skipping `--help` and missing quick usage hints.

## Safety notes

- Prefer official manuals/man pages when commands affect system state.

## Related commands

- `info`, `whatis`, `which`, `type`, `help`

## Sources

- Linux man-pages project: https://www.kernel.org/doc/man-pages/
- Bash builtin `help` and `type`: https://www.gnu.org/software/bash/manual/bash.html#Bash-Builtins

