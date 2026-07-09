# Changelog

## 1.20260709.0

### Added

- Added `--latest-version-tag` for Git plugins to install the newest version-sorted tag.
- Added `latest-version-tag = true` support in `bnpm.toml`.
- Added Nix flake and devcontainer development environments.

### Changed

- Simplified CLI command wiring and error handling.
- Hardened runtime plugin verification by checking installed plugin tree checksums against `bnpm.lock`.
- Improved Git source validation, including rejecting insecure `http://` URLs.
- Updated README usage and lockfile behavior documentation.

### Fixed

- Preserved `.git` suffix handling for `github.com/...` plugin sources.
- Included symlink targets in plugin tree checksums.

## 1.20260627.0

### Changed

- Adopted date-based package versioning.
