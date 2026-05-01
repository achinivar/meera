# Vim essentials

## Overview

**Vim** is **modal**: **Normal** mode runs navigation/commands; **Insert** types text; **`:`** opens **Command-line** mode (save/quit/search). If keys **move the cursor** or **delete** instead of typing letters, you are in **Normal** mode—press **`Esc`**, then **`i`** to insert.

**Safety:** if stuck, **`Esc`** a few times then **`:q!`** exits without saving. Use **`:w`** often while learning.

**Sources:** [Vim docs](https://www.vim.org/docs.php), [Vim user manual](https://vimhelp.org/usr_toc.txt.html).

## Modes at a glance

- **Normal** — navigation, delete/yank, run **`:`** commands.
- **Insert** — typing (`i`, `a`, `o` from Normal).
- **Command-line** — after **`:`** (save, quit, substitute).

Press **`Esc`** to return to Normal.

## Enter Insert mode

| Key | Effect |
|-----|--------|
| `i` | Insert before cursor |
| `a` | Append after cursor |
| `o` | Open new line below |

## Save and quit (Command-line)

Type **`:`** from Normal, then:

```vim
:w          " write (save)
:q          " quit only if no unsaved changes (Vim errors if buffer modified)
:wq         " save and quit
:q!         " quit, discard unsaved changes
```

## Move in Normal mode

| Keys | Effect |
|------|--------|
| `h` `j` `k` `l` | Left / down / up / right |
| `gg` | First line |
| `G` | End of file |
| `/pattern` | Search forward |
| `n` | Next match |

## Copy, delete, undo

| Keys | Effect |
|------|--------|
| `yy` | Yank (copy) line |
| `p` | Paste after cursor |
| `dd` | Delete line |
| `u` | Undo |
| `Ctrl+r` | Redo |

## Beginner workflow

1. **`vim notes.txt`**
2. **`i`**, type, **`Esc`**
3. **`:wq`** to save and exit.
