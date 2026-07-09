from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform


@dataclass(frozen=True)
class Config:
    bnpm_config_dir: Path
    bnpm_data_dir: Path
    bn_install_dir: Path | None
    bn_user_dir: Path

    @property
    def bnpm_manifest_path(self) -> Path:
        return self.bnpm_config_dir / "bnpm.toml"

    @property
    def bnpm_lock_path(self) -> Path:
        return self.bnpm_config_dir / "bnpm.lock"

    @property
    def bnpm_plugin_dir(self) -> Path:
        return self.bnpm_data_dir / "plugins"

    @property
    def bnpm_package_dir(self) -> Path:
        return self.bnpm_data_dir / "packages"

    @property
    def bnpm_venv_dir(self) -> Path:
        return self.bnpm_data_dir / "venv"

    @property
    def bnpm_venv_python(self) -> Path:
        if platform.system() == "Windows":
            return self.bnpm_venv_dir / "Scripts" / "python.exe"
        return self.bnpm_venv_dir / "bin" / "python"

    @property
    def bn_user_plugin_dir(self) -> Path:
        return self.bn_user_dir / "plugins"


@dataclass(frozen=True)
class SourceSpec:
    name: str
    kind: str
    git: str | None = None
    path: str | None = None
    tag: str | None = None
    branch: str | None = None
    rev: str | None = None
    latest_tag: bool = False

    @property
    def version(self) -> str | None:
        if self.kind == "path":
            return None
        if self.tag:
            return f"tag:{self.tag}"
        if self.rev:
            return f"rev:{self.rev}"
        if self.branch:
            return f"branch:{self.branch}"
        if self.latest_tag:
            return "latest-version-tag"
        return "HEAD"


@dataclass(frozen=True)
class Manifest:
    path: Path
    version: int
    plugins: dict[str, SourceSpec]


@dataclass(frozen=True)
class LockedPlugin:
    name: str
    source: str
    checksum: str
    version: str | None = None
    commit: str | None = None
    dependencies: list[str] | None = None
    requirements: list[str] | None = None


@dataclass(frozen=True)
class LockedPackage:
    name: str
    source: str
    version: str
    checksum: str | None = None
    dependencies: list[str] | None = None


@dataclass(frozen=True)
class Lockfile:
    path: Path
    plugins: list[LockedPlugin]
    packages: list[LockedPackage]


@dataclass(frozen=True)
class InstalledPlugin:
    name: str
    source: str
    checksum: str
    version: str | None = None
    commit: str | None = None


@dataclass(frozen=True)
class ManifestPlugin:
    name: str
    source: str
    version: str | None


@dataclass(frozen=True)
class VerificationResult:
    plugin: LockedPlugin
    path: Path
    expected: str
    actual: str | None
    ok: bool
    message: str
