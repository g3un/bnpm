# BNPM

A modern plugin manager for Binary Ninja.

BNPM installs Binary Ninja plugins from Git URLs or local paths, records the
resolved state in `bnpm.lock`, verifies checksums at startup, and loads locked
plugins without relying on Binary Ninja's central plugin index.

BNPM targets Python 3.10+.

## Usage

```bash
PYTHONPATH=src python -m bnpm.cli add plugin github.com/owner/plugin@v1.2.3
PYTHONPATH=src python -m bnpm.cli add local --path ../local-plugin
PYTHONPATH=src python -m bnpm.cli remove plugin
PYTHONPATH=src python -m bnpm.cli sync
PYTHONPATH=src python -m bnpm.cli list
```

```powershell
$env:PYTHONPATH = "src"
python -m bnpm.cli add plugin github.com/owner/plugin@v1.2.3
python -m bnpm.cli add local --path ..\local-plugin
python -m bnpm.cli remove plugin
python -m bnpm.cli sync
python -m bnpm.cli list
```

Inside Binary Ninja, run `BNPM\Sync` from the command palette to sync
`bnpm.toml`, write `bnpm.lock`, and load the synced plugins.

On startup, BNPM compares `bnpm.toml` and `bnpm.lock`. If they differ, it asks
whether to sync now. Choosing later, or a sync failure, keeps using the existing
lock file.

## Manifest

`bnpm.toml` keeps the requested plugin set:

```toml
version = 1

[plugins]
plugin = "github.com/owner/plugin@v1.2.3"
local = { path = "../local-plugin" }
```

## Paths

- Unix/macOS config: `~/.config/bnpm`
- Unix/macOS plugins: `~/.local/share/bnpm/plugins`
- Windows config: `%APPDATA%\bnpm`
- Windows plugins: `%LOCALAPPDATA%\bnpm\plugins`
