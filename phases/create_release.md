# Create a Meera release

Use this when publishing a new **version** of the app tarball (`meera-vX.Y.tar.gz`) plus the **`install.sh`** asset. The standalone installer is **not** inside the tarball; it is uploaded as its own release file so `curl …/install.sh | sh` stays one line for users.

## 1. Choose a version tag

Pick a Git tag such as `v0.2` (must match URLs and filenames below).

Update these in **`install.sh`** at the top (defaults block), but **do not set the tarball SHA yet**—that hash is only known after you build the archive in step 2.

- `MEERA_VERSION` — e.g. `v0.2`
- `MEERA_RELEASE_URL` — full download URL for the tarball once you know it, e.g.  
  `https://github.com/achinivar/meera/releases/download/v0.2/meera-v0.2.tar.gz`
- `MEERA_INSTALLER_URL` — usually leave as latest installer:  
  `https://github.com/achinivar/meera/releases/latest/download/install.sh`

Commit all **application** changes you want in this release. The tarball should reflect that tree.

## 2. Build the tarball (the `tar` command)

**Important:** Write the archive **outside** the repository tree, or exclude the output file. If you run `tar` inside the repo and write `meera-v0.2.tar.gz` into the same directory you are archiving, you can get errors like `tar: …: file changed as we read it`.

From the **parent** directory of your clone (replace paths and version):

```bash
tar --exclude='.git' \
    --exclude='.cache' \
    --exclude='history' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='env' \
    --exclude='install.sh' \
    -czf ~/meera-v0.1.tar.gz .
```

Notes:

- **`--exclude='install.sh'`** — the published installer is attached as a separate GitHub release asset, not bundled inside the app archive.
- **`--exclude='meera-v*.tar.gz'`** — avoids pulling a previous bundle back into a new one.
- Adjust **`--exclude`** if you also want to omit local-only paths (e.g. `phases`, editor folders); keep the archive aligned with what `install.sh` expects to extract into `~/.local/share/meera/app`.

## 3. SHA-256 and `install.sh`

Compute the checksum of the file you will upload:

```bash
sha256sum "$HOME/meera-${VERSION}.tar.gz"
```

Copy the hex digest (first column) into **`install.sh`**:

- `MEERA_RELEASE_SHA256` — the full SHA-256 of **`meera-vX.Y.tar.gz`**

Re-check that **`MEERA_VERSION`** and **`MEERA_RELEASE_URL`** match the tag and filename you will use on GitHub.

Commit the updated **`install.sh`** (and **`README.md`** if the install line must change) on your release branch, then merge or fast-forward as you prefer before tagging.

## 4. Create the release in the GitHub UI

1. Open the repository on GitHub: `https://github.com/achinivar/meera`
2. Go to **Releases** → **Draft a new release** (or **Create a new release**).
3. **Choose a tag**: Create the tag from the UI.
4. **Release title**: e.g. `v0.2`.
5. Add **release notes** (changelog) as needed.
6. **Attach binaries** (upload assets):
   - `meera-v0.2.tar.gz` — the tarball from step 2 (checksum must match `MEERA_RELEASE_SHA256` in `install.sh`).
   - `install.sh` — the current script from the repo so **Attach binary** gives users `…/releases/latest/download/install.sh` with the right defaults.
7. Publish the release.

After publishing, spot-check:

- Tarball URL returns the same bytes you hashed.
- `curl -fsSL https://github.com/achinivar/meera/releases/latest/download/install.sh | sh` runs against a test user or VM if possible.

## Checklist

- [ ] Tarball built from the intended commit, not including itself or stale `*.tar.gz` files in-tree
- [ ] `MEERA_VERSION`, `MEERA_RELEASE_URL`, `MEERA_RELEASE_SHA256` updated in `install.sh` and committed
- [ ] Tag created and pushed
- [ ] GitHub release created with **`meera-vX.Y.tar.gz`** + **`install.sh`** attached
