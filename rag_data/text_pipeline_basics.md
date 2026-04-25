# Text Pipeline Basics

## What it is

Linux text pipelines chain small commands so output from one becomes input to the next.

## When to use it

Use pipelines for log analysis, quick reports, and command-line data cleanup.

## Common pipeline tools

```bash
cat file.txt
head -n 20 file.txt
tail -n 50 file.txt
wc -l file.txt
sort file.txt
uniq file.txt
cut -d: -f1 /etc/passwd
tr '[:upper:]' '[:lower:]' < file.txt
```

## Example pipelines

Count unique error lines:

```bash
grep -i "error" app.log | sort | uniq -c | sort -nr
```

Extract usernames:

```bash
cut -d: -f1 /etc/passwd | sort
```

Use `xargs` to pass results as arguments:

```bash
find . -name "*.log" | xargs wc -l
```

## Common mistakes

- Losing expected order after `sort`.
- Forgetting `uniq` needs adjacent duplicates (often requires `sort` first).
- Breaking on spaces/newlines when using `xargs` with unsafe input.

## Safety notes

- Prefer null-delimited flows for arbitrary filenames (`-print0` + `xargs -0`).

## Related commands

- `grep`, `sed`, `awk`, `paste`, `join`

## Sources

- GNU Coreutils manual: https://www.gnu.org/software/coreutils/manual/coreutils.html
- GNU findutils (`xargs`): https://www.gnu.org/software/findutils/manual/html_node/find_html/xargs-options.html

