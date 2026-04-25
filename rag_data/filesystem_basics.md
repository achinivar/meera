# Filesystem Basics

## What it is

These commands help you navigate directories and manage files in Linux.

## When to use it

Use these commands for daily shell work: moving around, creating files, and copying or deleting data.

## Core navigation

```bash
pwd
ls
ls -la
cd /path/to/dir
cd ~
cd ..
```

## Create and manage files/directories

```bash
mkdir my_folder
touch notes.txt
cp source.txt backup.txt
mv oldname.txt newname.txt
rm file.txt
rmdir empty_dir
```

Remove non-empty directories carefully:

```bash
rm -r my_folder
```

## Safety notes

- Prefer `cp -i`, `mv -i`, and `rm -i` if you want confirmation prompts.
- Be very careful with recursive removal commands.

## Common mistakes

- Running `rm -r` in the wrong directory.
- Forgetting whether a path is relative or absolute.
- Overwriting files accidentally with `cp` or `mv`.

## Related commands

- `find`, `ls`, `tree`, `pwd`

## Sources

- GNU Coreutils manuals: https://www.gnu.org/software/coreutils/manual/coreutils.html
- Linux `cd` (Bash builtin) docs: https://www.gnu.org/software/bash/manual/bash.html#Bourne-Shell-Builtins

