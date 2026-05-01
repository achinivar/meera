# Shell pipelines, redirection, and text tools

## Overview

**Redirection** sends a command’s **stdin/stdout/stderr** to files or other streams. **Pipelines** (`|`) connect one process’s **stdout** to the next process’s **stdin**. Use **`>`** to overwrite a file (truncates), **`>>`** to append, **`2>`** for stderr alone. To merge stderr into the same file as stdout, redirect stdout **first**, then merge: **`>file 2>&1`**.

**Safety:** confirm paths before **`>`**—it clobbers. For arbitrary filenames from **`find`**, use **`find -print0 | xargs -0`** so spaces/newlines in names do not break **`xargs`**.

**Sources:** [Bash redirections](https://www.gnu.org/software/bash/manual/bash.html#Redirections), [GNU coreutils](https://www.gnu.org/software/coreutils/manual/coreutils.html), [findutils xargs](https://www.gnu.org/software/findutils/manual/html_node/find_html/xargs-options.html), [tee](https://www.gnu.org/software/coreutils/manual/html_node/tee-invocation.html).

## Standard streams and file redirection

| Stream | FD | Role |
|--------|----|------|
| stdin | 0 | Input |
| stdout | 1 | Normal output |
| stderr | 2 | Errors/diagnostics |

**Overwrite** stdout to a file:

```bash
echo 'hello' > out.txt
```

**Append** without truncating:

```bash
echo 'again' >> out.txt
```

**Send stderr** to a file (stdout still terminal):

```bash
command 2> errors.log
```

**Merge stderr into stdout** then both go to one file (order matters—set stdout target first, then `2>&1`):

```bash
command > all.log 2>&1
```

**Feed a file** as stdin:

```bash
sort < names.txt
```

## Pipes and tee

**Pipe** stdout of left command into stdin of right:

```bash
command | less
```

**tee** copies stdin to stdout **and** a file (see output while saving):

```bash
command | tee output.log
```

Append mode:

```bash
command | tee -a output.log
```

## Core text utilities (single files or stdin)

Each line below: read a file (or replace with stdin) for quick inspection.

**Dump or concatenate:**

```bash
cat file.txt
```

**First / last lines:**

```bash
head -n 20 file.txt
tail -n 50 file.txt
```

**Line / word / byte counts:**

```bash
wc -l file.txt
```

**Sort lines** (often paired with `uniq`):

```bash
sort file.txt
```

**Collapse adjacent duplicate lines** — **`uniq`** only removes *consecutive* duplicates; **`sort`** first if dupes may be far apart:

```bash
sort file.txt | uniq
```

**Cut a delimiter-separated field** (here field 1 of `:`-separated):

```bash
cut -d: -f1 /etc/passwd
```

**Translate characters** (here lowercasing via class):

```bash
tr '[:upper:]' '[:lower:]' < file.txt
```

## Example pipelines

**Count** how many times each distinct “error” line appears, most common first:

```bash
grep -i 'error' app.log | sort | uniq -c | sort -nr
```

**Sorted list** of usernames from passwd:

```bash
cut -d: -f1 /etc/passwd | sort
```

## xargs: turn lines into command arguments

**Basic** — word-count every `.log` under here (breaks on spaces in names):

```bash
find . -name '*.log' | xargs wc -l
```

**Safer** — null-terminated paths from `find` (use this when names may contain spaces):

```bash
find . -name '*.log' -print0 | xargs -0 wc -l
```
