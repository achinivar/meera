# Meera `tools/` package (Phase 2)

Typed, allowlisted actions the assistant may run later (Phase 3). **No raw shell** — commands use fixed `argv` lists and timeouts.

## Public API

- `tools.run_tool(name, params)` — validate parameters, resolve/check `distro` against `/etc/os-release`, dispatch handler.
- `tools.tools_manifest_json()` — compact JSON catalog (no Python `handler` field) for prompts.
- `tools.TOOLS`, `tools.get_tool(name)` — in-process registry.

## `distro` parameter

Every tool schema includes required `distro`: `"ubuntu"` or `"fedora"`. The runner **injects** it from `detect_distro()` when omitted. If the model sends a value that **does not match** the host, the runner returns `DISTRO_MISMATCH` and runs **no** subprocess.

## Adding a tool

1. Implement a handler `def _foo(params: Mapping[str, Any]) -> ToolResult` in the right module (`system.py`, `files.py`, …).
2. Append a `ToolSpec` to that module’s `TOOLS` list (include `distro` in `parameters`).
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
