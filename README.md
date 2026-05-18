# BNPM

A modern plugin manager for Binary Ninja:
- Install plugins directly from trusted Git URLs or local paths.
- Support more plugin project shapes over time, including Rust-based plugins
  and `uv`-managed Python projects.

## Usage

```bash
uv run bnpm add plugin --git github.com/owner/plugin --tag v1.2.3
uv run bnpm add devtools --git github.com/owner/devtools --branch main
uv run bnpm add local --path ../local-plugin
uv run bnpm remove plugin
uv run bnpm update [plugin]
uv run bnpm sync
uv run bnpm list
```

Run BNPM directly from a Git checkout with `uvx`:

```bash
uvx --from git+https://github.com/g3un/bnpm bnpm list
```
