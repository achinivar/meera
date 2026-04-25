# Archives Basics

## What it is

Archives bundle files into one artifact, and compression reduces storage or transfer size.

## When to use it

Use archives for backups, releases, and moving many files between systems.

## Create tar archives

```bash
tar -cvf archive.tar my_folder
tar -czvf archive.tar.gz my_folder
tar -cJvf archive.tar.xz my_folder
```

## Extract archives

```bash
tar -xvf archive.tar
tar -xzvf archive.tar.gz
tar -xJvf archive.tar.xz
```

## List archive contents

```bash
tar -tvf archive.tar.gz
```

## Zip and unzip

```bash
zip -r files.zip my_folder
unzip files.zip
```

## Common mistakes

- Extracting archives in the wrong directory.
- Forgetting compression flags (`z` for gzip, `J` for xz).
- Assuming `.zip` and `.tar.gz` use the same command.

## Safety notes

- Inspect archive contents before extraction (`tar -tvf`, `unzip -l`).
- Be cautious with untrusted archives.

## Related commands

- `gzip`, `xz`, `sha256sum`

## Sources

- GNU tar manual: https://www.gnu.org/software/tar/manual/tar.html
- Info-ZIP `zip`/`unzip` reference: https://infozip.sourceforge.net/

