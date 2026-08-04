# Core and I/O

These modules provide configuration resolution, glycan/formula helpers,
reaction configuration, and explicit JSON-to-SBML conversion. They do not
choose repository-relative output locations.

## Recommended entry points

Start with [`load_config`][thg_protocol.config.load_config] for configuration,
[`parse_formula`][thg_protocol.glycan.parse_formula] for formulas, and
[`convert_json_to_sbml`][thg_protocol.io.convert_json_to_sbml] for format conversion.

## Configuration

::: thg_protocol.config
    options:
      members:
        - get_project_root
        - load_config
        - get_model_paths
        - get_compartments
        - resolve_compartment_abbreviation
        - resolve_all_compartments

## Glycans

::: thg_protocol.glycan
    options:
      members:
        - glycan_atoms
        - normalize_identifiers
        - parse_formula
        - resolve_glycan_atoms

## Reaction configuration

::: thg_protocol.reaction_config
    options:
      members:
        - DEFAULT_BIOCHEMICAL_SBO
        - DEFAULT_UPPER_BOUND
        - build_reaction_entry
        - default_lower_bound
        - upsert_reaction_entry

## File conversion

::: thg_protocol.io
    options:
      members:
        - convert_json_to_sbml
