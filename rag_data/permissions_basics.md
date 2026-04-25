# Permissions Basics

## What it is

Linux permissions control who can read, write, or execute files and directories.

## When to use it

Use these commands when scripts are not executable, files are inaccessible, or ownership is wrong after copy/extract operations.

## See permissions

```bash
ls -l
```

You will see entries like `-rwxr-xr--` and owner/group fields.

## Change permissions with chmod

```bash
chmod u+x script.sh
chmod go-r secret.txt
chmod 644 file.txt
chmod 755 runme.sh
```

## Change owner/group with chown

```bash
sudo chown user:group file.txt
sudo chown -R user:group project_dir
```

## Common numeric modes

- `644`: owner read/write, group read, others read
- `755`: owner read/write/execute, group read/execute, others read/execute

## Common mistakes

- Using overly permissive modes like `777`.
- Changing ownership recursively in the wrong path.
- Confusing file and directory permission behavior.

## Safety notes

- Use least privilege; grant only what is required.
- Double-check path targets before `sudo chown -R`.

## Related commands

- `ls -l`, `umask`, `sudo`

## Sources

- GNU Coreutils `chmod`: https://www.gnu.org/software/coreutils/manual/html_node/chmod-invocation.html
- GNU Coreutils `chown`: https://www.gnu.org/software/coreutils/manual/html_node/chown-invocation.html

