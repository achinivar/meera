# Downloads Basics

## What it is

`curl` and `wget` download files and make HTTP requests from the command line.

## When to use it

Use these commands for scripted downloads, API checks, and fetching release artifacts.

## Download a file

```bash
curl -L -o file.tar.gz "https://example.com/file.tar.gz"
wget "https://example.com/file.tar.gz"
```

## Resume downloads

```bash
wget -c "https://example.com/large.iso"
```

## Show response headers

```bash
curl -I "https://example.com"
```

## Simple API request

```bash
curl "https://api.github.com/repos/torvalds/linux"
```

## Notes

- Use `-L` with `curl` to follow redirects.
- Verify checksums when downloading binaries/scripts.

## Common mistakes

- Downloading HTML redirect pages instead of real files.
- Running remote scripts without inspecting them.
- Ignoring TLS/URL typos.

## Safety notes

- Verify downloads with checksums/signatures when available.
- Prefer explicit output paths (`-o`) and review files before execution.

## Related commands

- `sha256sum`, `tar`, `unzip`

## Sources

- curl docs: https://curl.se/docs/
- GNU Wget manual: https://www.gnu.org/software/wget/manual/wget.html

