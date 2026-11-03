"""Reproduce notebook logic bugs without executing any notebook cells."""
import ast
from pathlib import Path
from types import SimpleNamespace

import json
import pandas as pd
from cobra import Metabolite, Model, Reaction

ROOT = Path(__file__).resolve().parents[3]

def extract(path, cell_index, name):
    cell = json.loads((ROOT / path).read_text())['cells'][cell_index]
    tree = ast.parse(''.join(cell['source']))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {}
    exec(compile(module, f'{path} cell {cell_index}', 'exec'), namespace)
    return namespace[name]

# F7: reverse-only FVA intervals are falsely marked blocked by maximum <= 0.
test_and_remove_rxns = extract('supplementary_material/crucial_exchange_rs.ipynb', 29, 'test_and_remove_rxns')
class ModelStub:
    def __init__(self): self.restored = False
    def remove_reactions(self, rxns): pass
    def add_reactions(self, rxns): self.restored = True
model = ModelStub()
rxn = SimpleNamespace(id='SINK_A')
namespace = test_and_remove_rxns.__globals__
namespace['flux_variability_analysis'] = lambda *a, **k: pd.DataFrame({'minimum': [-10.0], 'maximum': [0.0]})
removed = test_and_remove_rxns(model, [rxn], [SimpleNamespace(id='R_REVERSE')])
assert removed == [] and model.restored

# F8: stoichiometric sign alone mistakes an exchange-capable reversible reaction for a final substrate.
classify = extract('supplementary_material/extra.ipynb', 4, 'classify_deadend_in_final_model')
model = Model('reversible_case')
a, b = Metabolite('A_c', compartment='c'), Metabolite('B_c', compartment='c')
r = Reaction('A_to_B', lower_bound=-10, upper_bound=10)
r.add_metabolites({a: -1, b: 1})
model.add_reactions([r])
substrates, products, both, missing = classify(model, ['A_c'])
assert substrates == ['A_c'] and products == [] and both == [] and missing == []
print('F7 reproduced: reverse-only interval marked blocked, so sink is restored.')
print(f'F8 reproduced: reversible A_c is classified as final substrate: {substrates}.')
