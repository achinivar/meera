# Files, directories, and permissions

## Overview

Navigate with **`pwd`/`cd`/`ls`**, create and move data with **`mkdir`/`touch`/`cp`/`mv`/`rm`**. **Permissions** (`chmod`, `chown`) control who can read/write/execute; **`ls -l`** shows the mode string and owners. **Relative paths** (no leading `/`) start from the **current working directory**—`rm -r my_folder` deletes **`my_folder` here**, not “somewhere else” unless you **`cd`** first.

**Safety:** **`rm -r`** is irreversible—confirm **`pwd`** and the path. **`chown -R`** on the wrong tree is painful; verify the directory. Prefer **`cp -i`/`mv -i`/`rm -i`** when learning.

**Sources:** [GNU coreutils](https://www.gnu.org/software/coreutils/manual/coreutils.html), [Bash builtins](https://www.gnu.org/software/bash/manual/bash.html#Bourne-Shell-Builtins), [chmod](https://www.gnu.org/software/coreutils/manual/html_node/chmod-invocation.html), [chown](https://www.gnu.org/software/coreutils/manual/html_node/chown-invocation.html).

## Navigate and list

**Print** working directory:

```bash
pwd
```

**List** files; **`-a`** includes hidden; **`-l`** long format (shows permissions):

```bash
ls
ls -la
```

**Change** directory (absolute or relative); home and parent:

```bash
cd /path/to/dir
cd ~
cd ..
```

## Create, copy, move, remove

**Directory** and empty file:

```bash
mkdir my_folder
touch notes.txt
```

**Copy** / **rename** / **remove** file:

```bash
cp source.txt backup.txt
mv oldname.txt newname.txt
rm file.txt
```

**Remove** empty directory:

```bash
rmdir empty_dir
```

**Tree delete** (dangerous—confirm path first):

```bash
rm -r my_folder
```

## Encrypt and decrypt a file with gpg

**Symmetric** mode (you pick a passphrase; ciphertext is a single file). **Encrypt** with defaults — GnuPG picks a strong cipher; creates **`filename.gpg`** beside the original:

```bash
gpg -c filename
# same intent:
gpg --symmetric filename
```

**Decrypt** to a new file (prompts for the passphrase):

```bash
gpg --output filename --decrypt filename.gpg
```

Prefer **`--output`** for binaries; avoid redirecting binary **`gpg -d`** to a tty.

**Specific options** (only when you need them):

- **Pin the cipher** — e.g. **`gpg -c --cipher-algo AES256 filename`** (defaults are usually fine).
- **ASCII armor** — **`gpg -c --armor filename`** writes **`filename.asc`** (text, easier to paste); decrypt with **`gpg --output filename --decrypt filename.asc`**.

**Safety:** Without the passphrase the data is not recoverable. If the plaintext must stay secret, remove or **shred** the original after you have verified the **`.gpg`** decrypts; backups of the ciphertext are useless without the passphrase.

## Permissions: read with ls -l, chmod, and chown

**Inspect** mode and owner columns — e.g. `-rwxr-xr--` is type + rwx for user/group/others:

```bash
ls -l
```

**chmod** — **symbolic** (add user execute; strip group/other read):

```bash
chmod u+x script.sh
chmod go-r secret.txt
```

**Numeric** modes — **`644`** owner rw, group/others r; **`755`** owner rwx, group/others rx. **`777`** gives everyone read/write/exec—avoid unless you understand the exposure:

```bash
chmod 644 file.txt
chmod 755 runme.sh
```

**chown** — needs **root** for someone else’s files; **`-R`** is recursive (verify path—never aim at **`/`** by mistake):

```bash
sudo chown user:group file.txt
sudo chown -R user:group project_dir
```
