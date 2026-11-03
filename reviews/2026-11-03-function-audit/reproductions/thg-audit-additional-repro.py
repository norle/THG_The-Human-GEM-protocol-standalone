"""Assert two additional audit observations without running project tests."""

import ast
from pathlib import Path

from thg_protocol.gpr.stoichiometry import sgpr_from_dict

node = sgpr_from_dict({"type": "gene", "gene": "A", "coefficient": 2.7})
assert node.coefficient == 2

root = Path(__file__).resolve().parents[3]
path = root / "tests/integration/test_legacy_algorithm_apis.py"
tree = ast.parse(path.read_text())
test = next(
    node
    for node in tree.body
    if isinstance(node, ast.FunctionDef)
    and node.name == "test_small_sbml_reaction_models_use_package_jaccard_workflow"
)
# Evaluate only the two fixture assignments, without executing the test.
assignments = [node for node in test.body if isinstance(node, ast.Assign)][:2]
namespace = {}
exec(compile(ast.Module(body=assignments, type_ignores=[]), str(path), "exec"), namespace)
assert namespace["reverse_template"] == namespace["reaction_template"]

print("Confirmed: fractional subunit count truncation and unchanged reverse fixture.")
