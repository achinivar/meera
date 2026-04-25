# grep Basics

## What it is

`grep` searches line-by-line text for a pattern and prints matching lines.

## When to use it

Use `grep` to find errors in logs, search code, or filter command output in pipelines.

## Common usage

```bash
grep "error" app.log
grep -i "warning" app.log
grep -r "TODO" ./src
grep -n "main" script.py
```

## Useful flags

- `-i`: case-insensitive match
- `-r` or `-R`: recursive search
- `-n`: show line numbers
- `-v`: invert match (show non-matching lines)
- `-E`: extended regular expressions

## Practical regex examples

```bash
grep -E "error|warning" app.log
grep -E "^[0-9]{4}-[0-9]{2}-[0-9]{2}" dates.txt
```

## Pipeline examples

```bash
ps aux | grep python
journalctl -u sshd | grep -i "failed"
```

## Common mistakes

- Forgetting case-insensitivity (`-i`) when needed.
- Matching too broadly and getting noisy results.
- Using `grep` where a fixed-string search (`grep -F`) would be safer and faster.

## Safety notes

- `grep` is read-only.
- Be careful when combining with `xargs rm` style pipelines.

## Related commands

- `sed`, `awk`, `rg`, `find`

## Sources

- GNU grep manual: https://www.gnu.org/software/grep/manual/grep.html
- man7 grep man page mirror: https://www.man7.org/linux/man-pages/man1/grep.1.html

