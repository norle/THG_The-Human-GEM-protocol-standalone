"""Generate the RAVEN task mapping ``name[comp]`` -> ID from a Human-GEM YAML.

Usage:
    python make_name_mapping.py Human-GEM.yml <commit> > human_gem_names.json

The mapping lets the Human-GEM task tables resolve on models that keep the
Human-GEM ``MAM...`` metabolite IDs but renamed metabolites (THG, endoC, ...).
"""

import json
import sys

import yaml


def metabolites(path):
    """Yield (id, name, compartment) from the YAML ``metabolites`` section."""
    current, section = {}, None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("- "):
                section = line[2:].split(":")[0]
                continue
            if section != "metabolites":
                continue
            stripped = line.strip()
            if stripped == "- !!omap":
                if current:
                    yield current["id"], current["name"], current["compartment"]
                current = {}
            elif stripped.startswith("- ") and ":" in stripped:
                key, value = stripped[2:].split(":", 1)
                if key in ("id", "name", "compartment"):
                    current[key] = str(yaml.safe_load(value.strip() or '""'))
    if current:
        yield current["id"], current["name"], current["compartment"]


def main():
    path, commit = sys.argv[1], sys.argv[2]
    mapping, seen = {}, {}
    for met_id, name, compartment in metabolites(path):
        key = f"{name}[{compartment}]"
        folded = key.upper()
        if folded in seen and seen[folded] != met_id:
            raise SystemExit(f"ambiguous name {key!r}: {seen[folded]} and {met_id}")
        seen[folded] = met_id
        mapping[key] = met_id
    json.dump(
        {
            "metabolites": mapping,
            "metadata": {
                "source": "Human-GEM model/Human-GEM.yml",
                "human_gem_commit": commit,
                "description": "Human-GEM metabolite names (name[comp]) to MAM IDs",
            },
        },
        sys.stdout,
        indent=1,
        sort_keys=True,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
