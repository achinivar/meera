# vim Basics

## What it is

`vim` is a modal terminal text editor. You switch between modes for typing, navigation, and commands.

## When to use it

Use `vim` when editing config files over SSH, making quick terminal edits, or working without a GUI editor.

## Modes

- Normal mode: navigation and commands
- Insert mode: typing text
- Command-line mode: save/quit/search commands (entered with `:` from Normal mode)

## Essential keys

### Enter insert mode

- `i`: insert before cursor
- `a`: append after cursor
- `o`: open a new line below

Press `Esc` to return to Normal mode.

### Save and quit

```vim
:w
:q
:wq
:q!
```

### Navigation

- `h` `j` `k` `l`: left/down/up/right
- `gg`: start of file
- `G`: end of file
- `/pattern`: search forward
- `n`: next search result

## Copy/paste/delete (Normal mode)

- `yy`: yank (copy) line
- `p`: paste after cursor
- `dd`: delete line
- `u`: undo
- `Ctrl+r`: redo

## Beginner workflow

1. Open file: `vim notes.txt`
2. Press `i`, type text.
3. Press `Esc`.
4. Save and quit with `:wq`.

## Common mistakes

- Forgetting which mode you are in.
- Trying to type while still in Normal mode.
- Exiting with unsaved changes by accident.

## Safety notes

- If stuck, press `Esc` a few times, then `:q!` to exit without saving.
- Prefer `:w` often while learning.

## Related commands

- `nano`, `less`, `cat`

## Sources

- Vim documentation: https://www.vim.org/docs.php
- Vim user manual (online): https://vimhelp.org/usr_toc.txt.html

