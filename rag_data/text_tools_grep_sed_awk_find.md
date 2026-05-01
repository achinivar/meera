# Text tools: grep, sed, awk, and find

## Overview

**grep** prints lines matching a pattern (logs, code, pipes). **sed** edits text in a stream (substitutions, deletes). **awk** selects rows, splits **fields**, and computes sums or filters. **find** walks directories and lists paths matching tests. Use **grep** for “which lines match?”; **awk** when input is **columnar**; **sed** for scripted rewrites; **find** before **`xargs`** or **`-exec`**.

**Safety:** Quote **`awk`**/**`sed`** scripts so the shell does not expand **`$`** or break on spaces. **`sed -i`** overwrites—run without **`-i`** first to verify output. **`find`** actions like **`-delete`** are destructive; list matches before acting.

**Nearby:** `rg` (ripgrep), `cut`, `sort`, `xargs`. **Sources:** [GNU grep](https://www.gnu.org/software/grep/manual/grep.html), [GNU sed](https://www.gnu.org/software/sed/manual/sed.html), [Gawk manual](https://www.gnu.org/software/gawk/manual/gawk.html), [GNU findutils](https://www.gnu.org/software/findutils/manual/findutils.html).

## Find files by name or type

`find` walks a tree and prints paths that pass **tests**. Start path is often `.` (current directory).

List everything under current dir (can be huge):

```bash
find .
```

Names ending in `.log` (quote the pattern so the shell does not expand `*`):

```bash
find . -name '*.log'
```

Case-insensitive name match:

```bash
find . -iname '*.png'
```

Only regular files:

```bash
find . -type f -name '*.md'
```

Max depth (avoid scanning whole disk):

```bash
find . -maxdepth 2 -type d
```

**Safer pairing with xargs** (weird filenames): `find ... -print0 | xargs -0 wc -l`

## Grep: print matching lines

**Basic search** — lines containing `error` in a file:

```bash
grep 'error' app.log
```

**Case-insensitive** — matches `Error`, `ERROR`:

```bash
grep -i 'warning' app.log
```

**Recursive** — all files under `./src`:

```bash
grep -r 'TODO' ./src
```

**Line numbers** — for editors or debugging:

```bash
grep -n 'main' script.py
```

**Invert** — lines that do **not** match:

```bash
grep -v '^#' config.txt
```

**Extended regex** — alternation and repetition:

```bash
grep -E 'error|warning' app.log
```

**Fixed string** (no regex—use for literals like version numbers so `.` is not “any character”):

```bash
grep -F '1.2.3' changelog.txt
```

**Pipeline** — filter another command’s output:

```bash
journalctl -u sshd --no-pager | grep -i 'failed'
```

## Grep flags quick reference

| Flag | Meaning |
|------|---------|
| `-i` | Ignore case |
| `-r` | Recursive (directories) |
| `-n` | Show line numbers |
| `-v` | Invert match |
| `-E` | Extended regex |
| `-F` | Fixed string, not regex |
| `-w` | Whole word |

## Sed: substitutions and line edits

**First** `foo` → `bar` per line (still prints whole file):

```bash
sed 's/foo/bar/' input.txt
```

**Global** replace on each line:

```bash
sed 's/foo/bar/g' input.txt
```

**Print only lines 5–10**:

```bash
sed -n '5,10p' input.txt
```

**Delete** lines starting with `#`:

```bash
sed '/^#/d' input.txt
```

**Delete** first / last line:

```bash
sed '1d' input.txt
sed '$d' input.txt
```

**GNU in-place** edit (overwrites file):

```bash
sed -i 's/old/new/g' file.txt
```

BSD/macOS often needs a backup suffix: `sed -i.bak 's/old/new/g' file.txt`

**Extended regex** example (digits → placeholder):

```bash
sed -E 's/[0-9]+/<num>/g' input.txt
```

## Awk: fields, filters, and totals

**Model:** `pattern { action }`. Default field separator is whitespace; `$1`, `$2` are columns; `$0` is whole line. If columns look wrong, check **`-F`** against a few lines (**`head`**) before relying on **`$n`**.

**Print first column** of each line:

```bash
awk '{print $1}' file.txt
```

**Colon-separated** (e.g. usernames from `/etc/passwd`):

```bash
awk -F: '{print $1}' /etc/passwd
```

**Only lines matching** a regex:

```bash
awk '/error/ {print $0}' app.log
```

**Sum** second column (numbers):

```bash
awk '{sum += $2} END {print sum}' numbers.txt
```

**Skip blank lines** (`NF` = number of fields):

```bash
awk 'NF > 0' file.txt
```

**Numeric filter** — print col1 and col3 where col3 > 100:

```bash
awk '$3 > 100 {print $1, $3}' data.txt
```

**BEGIN/END** blocks run once before/after all lines:

```bash
awk 'BEGIN {print "start"} {print $0} END {print "end"}' file.txt
```
