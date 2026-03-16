from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from scenarios.base import BaseScenario


def load_all_scenarios(enabled: list[str] | None = None) -> list[BaseScenario]:
    instances: list[BaseScenario] = []
    pkg_path = Path(__file__).parent

    for _, module_name, _ in pkgutil.iter_modules([str(pkg_path)]):
        if module_name == "base":
            continue
        if enabled is not None and module_name not in enabled:
            continue

        module = importlib.import_module(f"scenarios.{module_name}")
        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, BaseScenario) and attr is not BaseScenario:
                instances.append(attr())

    return sorted(instances, key=lambda x: x.name)
