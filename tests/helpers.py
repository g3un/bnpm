from __future__ import annotations

from bnpm.config import get_config
from bnpm.helpers import bn as bn_helpers
from bnpm.utils.python_env import resolve_bn_python_version


def clear_bnpm_caches() -> None:
    get_config.cache_clear()
    bn_helpers.find_bn_install_path.cache_clear()
    bn_helpers.get_bn_python_version.cache_clear()
    resolve_bn_python_version.cache_clear()

