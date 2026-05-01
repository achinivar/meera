# Linux help, man pages, and discovery

## Overview

Linux ships with **inline help**: **`--help`** for quick flags, **`man`** for structured manuals, **`apropos`** to search names/descriptions. **`which`** and **`type`** show where a command comes from (binary vs shell builtin). For **flag syntax that matches your install**, prefer **`man`** / **`--help`** on **this machine** over random web articles (versions differ).

**Safety:** for destructive commands, read **`man`** / **`--help`** before running with **`sudo`**.

**Sources:** [man-pages project](https://www.kernel.org/doc/man-pages/), [Bash builtins](https://www.gnu.org/software/bash/manual/bash.html#Bash-Builtins).

## --help and man pages

**`--help`** — many binaries print a short usage summary to the terminal (good for a quick flag reminder):

```bash
grep --help
tar --help
```

**`man`** — full manual; **section 1** is the default for user programs:

```bash
man grep
man tar
```

**Other sections** — config and file formats live elsewhere; if the page is the wrong topic, you may need another section number:

```bash
man 5 passwd
```

**Section 1** = programs, **5** = config/file formats.

## Locate the executable and builtins

**Path** to a binary (if on `PATH`):

```bash
which python3
```

**How the shell resolves** a name (alias, function, builtin, file):

```bash
type cd
```

`type` is especially useful because **`cd`** is often a **shell builtin**, not `/usr/bin/cd`.

## apropos: search manual summaries

Keyword search over what `man` knows:

```bash
apropos network
```
