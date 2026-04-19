# Meera `tools/` package (Phase 2)

Typed, allowlisted actions the assistant may run later (Phase 3). **No raw shell** — commands use fixed `argv` lists and timeouts.

## Public API

- `tools.run_tool(name, params)` — validate parameters, inject host `distro` from `detect_distro()`, dispatch handler.
- `tools.tools_prompt_catalog_json()` — JSON tool catalog for system prompts (names, descriptions, parameters only).
- `tools.TOOLS`, `tools.get_tool(name)` — in-process registry.

## Host distribution (`distro`)

Do **not** declare `distro` in tool parameter lists. The runner always sets `params["distro"]` from `detect_distro()` before calling handlers (any model-supplied `distro` key is ignored). Handlers may read `params["distro"]` when behavior differs between Ubuntu and Fedora.

## Adding a tool

1. Implement a handler `def _foo(params: Mapping[str, Any]) -> ToolResult` in the right module (`system.py`, `files.py`, …).
2. Append a `ToolSpec` to that module’s `TOOLS` list (only real arguments — not `distro`).
3. Import the module from `registry.py` so specs are merged (names must stay unique).
4. Add a unit test (mock `subprocess.run` via `tools._cmd.run_argv` patches when needed).

## Tests

From the repo root:

```bash
python3 -m unittest discover -s tests -v
```

## Security rules (summary)

- No `shell=True`; user strings never concatenated into shell one-liners.
- Paths: stay under `$HOME` where tools accept paths; reject `..` where enforced.
- Bounded output (truncation) and subprocess timeouts in `_cmd.run_argv`.
- Elevation: tools with `requires_elevation=True` are denied unless `run_tool(..., allow_elevation=True)` (Phase 3 may wire policy).
