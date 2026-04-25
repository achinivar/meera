# awk Basics

## What it is

`awk` is a text-processing language for selecting lines, splitting fields, and computing values.

## When to use it

Use `awk` when your input is table-like (columns) and you want filtering plus computation in one command.

## Common usage

```bash
awk '{print $1}' file.txt
awk -F: '{print $1}' /etc/passwd
awk '/error/ {print $0}' app.log
awk '{sum += $2} END {print sum}' numbers.txt
```

## Common syntax and ideas

- Pattern + action model: `pattern { action }`
- Default field separator is whitespace (`$1`, `$2`, ...).
- Use `-F` to set a custom separator.

## Practical examples

```bash
awk 'NF > 0' file.txt
awk 'BEGIN {print "start"} {print $0} END {print "end"}' file.txt
awk '$3 > 100 {print $1, $3}' data.txt
```

## Common mistakes

- Forgetting quotes around the awk program.
- Using the wrong field separator and getting empty or shifted columns.
- Expecting numeric comparison when the input is actually text.

## Safety notes

- `awk` is read-only unless you explicitly redirect output or combine with `-i` style tools elsewhere.

## Related commands

- `cut`, `grep`, `sed`, `sort`, `uniq`

## Sources

- GNU Awk User's Guide: https://www.gnu.org/software/gawk/manual/gawk.html

