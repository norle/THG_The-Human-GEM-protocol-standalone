"""Configuration helpers for THG protocol workflows."""

from __future__ import annotations

import ast
import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _read_dotenv(path: Path) -> dict[str, str]:
    """Read simple ``KEY=VALUE`` dotenv files without executing them."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[7:].lstrip()
        key, separator, value = text.partition("=")
        key = key.strip()
        if not separator or not _ENV_KEY.fullmatch(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            try:
                value = str(ast.literal_eval(value))
            except (SyntaxError, ValueError):
                continue
        values[key] = value
    return values


def load_environment_files(
    paths: Iterable[str | Path] | None = None,
) -> tuple[Path, ...]:
    """Load trusted dotenv files without overriding existing environment values.

    By default, files are considered in this order: ``THG_ENV_FILE`` when set,
    the current working directory, then the THG package/project directory.
    Earlier files and explicit process environment variables take precedence.
    """
    if paths is None:
        candidates: list[Path] = []
        explicit = os.environ.get("THG_ENV_FILE")
        if explicit:
            candidates.append(Path(explicit).expanduser())
        candidates.extend((Path.cwd() / ".env", get_project_root() / ".env"))
    else:
        candidates = [Path(item).expanduser() for item in paths]

    loaded: list[Path] = []
    for path in candidates:
        path = path.resolve()
        if not path.is_file() or path in loaded:
            continue
        for key, value in _read_dotenv(path).items():
            os.environ.setdefault(key, value)
        loaded.append(path)
    return tuple(loaded)


def get_project_root() -> Path:
    """Return the source checkout root, or the installed package directory.

    A wheel has no repository root.  Source checkouts are detected by the
    packaging marker; installed packages instead return their own directory so
    callers never resolve paths through an unrelated interpreter prefix.
    """
    package_path = Path(__file__).resolve()
    for parent in package_path.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return package_path.parent


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load a JSON configuration file.

    Relative paths are resolved first from the current working directory and
    then from the project root. This preserves the behavior of the original
    ``functions.config`` helper while making it importable from the package.
    """
    if config_path is None:
        resolved_path = get_project_root() / "config.json"
    else:
        resolved_path = Path(config_path)
        if not resolved_path.is_absolute():
            cwd_path = Path.cwd() / resolved_path
            root_path = get_project_root() / resolved_path

            if cwd_path.exists():
                resolved_path = cwd_path
            elif root_path.exists():
                resolved_path = root_path

    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {resolved_path}\n"
            f"  Searched in:\n"
            f"    - {resolved_path.absolute()}\n"
            f"  Please ensure the config file exists."
        )

    try:
        with resolved_path.open() as file_handle:
            config = json.load(file_handle)
    except json.JSONDecodeError as error:
        raise json.JSONDecodeError(
            f"Invalid JSON in config file: {resolved_path}",
            error.doc,
            error.pos,
        ) from error

    print(f"  Configuration file: {resolved_path.absolute()}")
    return config


def get_model_paths(config: dict[str, Any] | None = None) -> tuple[str, str]:
    """Return base and output model paths from a configuration mapping."""
    if config is None:
        config = load_config()

    project_root = get_project_root()
    base_model = config.get("model", {}).get("base")
    output_model = config.get("model", {}).get("output")

    if not base_model:
        raise ValueError("'model.base' not found in config.json")
    if not output_model:
        raise ValueError("'model.output' not found in config.json")

    base_path = (
        project_root / base_model
        if not Path(base_model).is_absolute()
        else Path(base_model)
    )
    output_path = (
        project_root / output_model
        if not Path(output_model).is_absolute()
        else Path(output_model)
    )

    return str(base_path), str(output_path)


def get_compartments(config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Return compartment specifications from a configuration mapping."""
    if config is None:
        config = load_config()

    compartments = config.get("compartments", [])
    if not compartments:
        raise ValueError("'compartments' not found or empty in config.json")

    for compartment in compartments:
        if "name" not in compartment or "abbreviation" not in compartment:
            raise ValueError(
                f"Invalid compartment definition: {compartment}. "
                "Each compartment must have 'name' and 'abbreviation' fields."
            )

    return compartments


def resolve_compartment_abbreviation(
    model: Any,
    compartment_config: dict[str, str],
) -> dict[str, str | bool | None]:
    """Resolve the compartment abbreviation that should be used for a model."""
    desired_name = compartment_config["name"].lower()
    config_abbrev = compartment_config["abbreviation"]

    if hasattr(model, "compartments"):
        compartments = model.compartments
    elif isinstance(model, dict) and "compartments" in model:
        compartments = model["compartments"]
    else:
        raise ValueError("Invalid model format. Expected COBRApy model or JSON dict.")

    for abbrev, name in compartments.items():
        if name.lower() == desired_name or abbrev.lower() == config_abbrev.lower():
            return {
                "abbreviation": abbrev,
                "exists": True,
                "existing_abbrev": abbrev,
                "name": name,
            }

    return {
        "abbreviation": config_abbrev,
        "exists": False,
        "existing_abbrev": None,
        "name": compartment_config["name"],
    }


def resolve_all_compartments(
    model: Any,
    config: dict[str, Any] | None = None,
) -> list[dict[str, str | bool | None]]:
    """Resolve configured compartment abbreviations against a model."""
    if config is None:
        config = load_config()

    return [
        resolve_compartment_abbreviation(model, compartment)
        for compartment in get_compartments(config)
    ]
