# BNPM

A modern plugin manager for Binary Ninja:
- Install plugins directly from trusted Git URLs or local paths.
- Support common Python plugin layouts, including `pyproject.toml`.

## Usage

Install the CLI with `uv`:

```bash
uv tool install git+https://codeberg.org/g3un/bnpm
# Install BNPM itself as a Binary Ninja plugin.
bnpm setup
```

Upgrade BNPM later:

```bash
uv tool upgrade bnpm
# Reinstall BNPM into Binary Ninja after upgrading the CLI.
bnpm setup
```

```bash
bnpm add plugin --git github.com/owner/plugin --tag v1.2.3
bnpm add devtools --git github.com/owner/devtools --branch main
bnpm add local --path ../local-plugin
bnpm remove plugin [plugin ...]
bnpm update [plugin]
bnpm sync
bnpm list
```

Run BNPM without installing it with `uvx`:

```bash
# Install BNPM itself as a Binary Ninja plugin.
uvx --from git+https://codeberg.org/g3un/bnpm bnpm setup
uvx --from git+https://codeberg.org/g3un/bnpm bnpm list
```
