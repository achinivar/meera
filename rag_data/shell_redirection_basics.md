# Shell Redirection Basics

## What it is

Redirection controls where command input comes from and where output/errors go.

## When to use it

Use redirection to save command output, separate errors, and build reusable shell workflows.

## Standard streams

- `stdin` (0): input
- `stdout` (1): normal output
- `stderr` (2): errors

## Common patterns

```bash
echo "hello" > out.txt
echo "again" >> out.txt
command 2> errors.log
command > all.log 2>&1
command | less
```

## Use tee (view + save)

```bash
command | tee output.log
command | tee -a output.log
```

## Read input from file

```bash
sort < names.txt
```

## Common mistakes

- Overwriting files unintentionally with `>`.
- Reversing order in stderr merge (must be `> file 2>&1`).
- Forgetting quotes around paths with spaces.

## Safety notes

- Use `>>` when you need append behavior.
- Consider writing logs into dedicated directories.

## Notes

- `>` overwrites, `>>` appends.
- `2>&1` merges stderr into stdout.

## Related commands

- `tee`, `cat`, `less`, pipelines with `|`

## Sources

- Bash manual (redirections): https://www.gnu.org/software/bash/manual/bash.html#Redirections
- GNU Coreutils `tee`: https://www.gnu.org/software/coreutils/manual/html_node/tee-invocation.html

