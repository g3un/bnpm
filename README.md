# BNPM

A plugin manager for Binary Ninja.

BNPM installs plugins from Git URLs or local paths. It handles plain Python plugins and `pyproject.toml` projects.

## Usage

Install the CLI with `uv`:

```bash
uv tool install git+https://codeberg.org/g3un/bnpm
# Install BNPM into Binary Ninja.
bnpm setup
```

Upgrade BNPM later:

```bash
uv tool upgrade bnpm
# Copy the upgraded BNPM files into Binary Ninja.
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

## Lockfile behavior

`bnpm.lock` pins Git plugins by commit and tree checksum. Local path plugins stay editable, so Binary Ninja will still load them after their checksum changes. `bnpm verify` still reports the mismatch.

Python package entries show what the last sync installed. They are not a resolver lock; each `bnpm sync` resolves dependencies from the current plugin requirements.

Run BNPM without installing it with `uvx`:

```bash
# Install BNPM into Binary Ninja.
uvx --from git+https://codeberg.org/g3un/bnpm bnpm setup
uvx --from git+https://codeberg.org/g3un/bnpm bnpm list
```
