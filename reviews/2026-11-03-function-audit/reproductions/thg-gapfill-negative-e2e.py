from pathlib import Path
from tempfile import TemporaryDirectory
from cobra import Metabolite, Model, Reaction
from cobra.io import write_sbml_model
from thg_protocol.gapfill.core import gapfill_model

x = Metabolite('x_c', compartment='c')
base = Model('blocked_base')
biomass = Reaction('BIOMASS', lower_bound=0, upper_bound=1000)
biomass.add_metabolites({x: -1})
base.add_reactions([biomass])
base.objective = 'BIOMASS'
assert base.optimize().objective_value == 0
universal = Model('universal')
make = Reaction('MAKE_X', lower_bound=0, upper_bound=1000)
make.add_metabolites({x: 1})
universal.add_reactions([make])
with TemporaryDirectory() as td:
    universal_path = Path(td) / 'universal.xml'
    write_sbml_model(universal, str(universal_path))
    result = gapfill_model(base, method='milp', parameters={
        'universal_model': str(universal_path),
        'objective': 'BIOMASS',
        'minimum_flux': -1,
    })
    print({'status': result.status, 'selected': result.selected_reactions,
           'objective': result.model.slim_optimize(error_value=None),
           'failure': result.failure})
    assert result.status == 'solved'
    assert result.selected_reactions == []
    assert result.model.slim_optimize(error_value=None) == 0
