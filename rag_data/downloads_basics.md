# Downloads and archives

## Overview

**curl** and **wget** fetch URLs from the shell. **tar** bundles directories (`.tar.gz`, `.tar.xz`); **zip/unzip** handle `.zip`. Typical flow: download → optional **checksum** → **list** archive contents → **extract** into a directory you chose (e.g. `mkdir out && cd out` so files do not scatter in the wrong place).

**Safety:** preview with **`tar -tvf`** / **`unzip -l`** before extracting; do not **`curl | bash`** untrusted scripts.

**Sources:** [curl](https://curl.se/docs/), [Wget](https://www.gnu.org/software/wget/manual/wget.html), [GNU tar](https://www.gnu.org/software/tar/manual/tar.html), [Info-ZIP](https://infozip.sourceforge.net/).

## Download with curl and wget

**Save a file** — **`curl`** needs **`-L`** to follow redirects; without it you may save an HTML redirect page instead of the real artifact. Use **`-o`** for the local name. **`wget`** uses the URL basename by default.

```bash
curl -L -o file.tar.gz 'https://example.com/file.tar.gz'
wget 'https://example.com/file.tar.gz'
```

**Resume** a partial **`wget`** download:

```bash
wget -c 'https://example.com/large.iso'
```

**Response headers only** — **`curl -I`** prints the HTTP status line and response headers **only**; the body is omitted. Useful for **`Location:`** redirects, **`Content-Type`**, or a quick “does this URL respond?” check without downloading the full page.

```bash
curl -I 'https://example.com'
```

**GET returning JSON** — a normal GET to a URL whose **response body** is JSON (not a separate `curl` “JSON mode”). This example hits GitHub’s public HTTP API, which returns repository metadata as JSON:

```bash
curl 'https://api.github.com/repos/torvalds/linux'
```

**Checksums** — **`sha256sum`** hashes **any** downloaded file (not tar-specific). Compare to the publisher’s listed hash **before** extract or execute:

```bash
sha256sum file.tar.gz
```

## Tar: create, list, and extract

**Create** — **`-c`** create; **`v`** verbose; **`f`** archive path. Compression: **`-z`** gzip (`.tar.gz`), **`-J`** xz (`.tar.xz`); omit **`z`/`J`** for plain `.tar`.

```bash
tar -cvf archive.tar my_folder
tar -czvf archive.tar.gz my_folder
tar -cJvf archive.tar.xz my_folder
```

**List** before extracting (see paths that would land on disk):

```bash
tar -tvf archive.tar.gz
```

**Extract** — **`-x`** extract; compression flags must **match** how the archive was made (**`z`** vs **`J`** — wrong flag yields errors or garbage):

```bash
tar -xvf archive.tar
tar -xzvf archive.tar.gz
tar -xJvf archive.tar.xz
```

## Zip and unzip

**Create** a zip of a directory:

```bash
zip -r files.zip my_folder
```

**Extract**:

```bash
unzip files.zip
```

**List** contents:

```bash
unzip -l files.zip
```
