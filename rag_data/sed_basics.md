# sed Basics

## What it is

`sed` is a stream editor used to transform text with scripted commands.

## When to use it

Use `sed` for quick substitutions, line deletion, and non-interactive text cleanup in scripts.

## Common usage

```bash
sed 's/foo/bar/' input.txt
sed 's/foo/bar/g' input.txt
sed -n '5,10p' input.txt
sed '/^#/d' input.txt
```

## In-place editing

```bash
sed -i 's/old/new/g' file.txt
```

On some systems (notably BSD/macOS), `-i` may require a backup suffix:

```bash
sed -i.bak 's/old/new/g' file.txt
```

## Practical patterns

```bash
sed -E 's/[0-9]+/<num>/g' input.txt
sed '1d' input.txt
sed '$d' input.txt
```

## Common mistakes

- Running `sed -i` before validating output.
- Forgetting to escape regex metacharacters.
- Mixing GNU and BSD `sed` syntax in cross-platform scripts.

## Safety notes

- Prefer testing without `-i` first: `sed '...' file`.
- Create backups when editing in place (`-i.bak`).

## Related commands

- `grep`, `awk`, `tr`, `cut`

## Sources

- GNU sed manual: https://www.gnu.org/software/sed/manual/sed.html
- GNU sed regex section: https://www.gnu.org/software/sed/manual/html_node/Regular-Expressions.html

