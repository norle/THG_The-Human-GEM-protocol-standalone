"""Reaction identification and matching helpers."""

from __future__ import annotations

import re
from io import StringIO

import pandas as pd

__all__ = [
    "execute_jaccard",
    "gather_kegg_metabolites",
    "identify_reaction",
    "jaccard",
    "process_jaccard",
    "process_reac",
    "replace_met_id_by_met_kegg",
]


def process_reac(
    input_file: str,
    MetID: str,
    MetIDH: str,
    MetIDH2O: str | None = "",
    take: int = -1,
) -> pd.DataFrame:
    result = ""
    with open(input_file) as handle:
        variable_file = handle.read()

    for n, reaction in enumerate(
        re.findall(r"<reaction.+?</reaction>", variable_file, re.DOTALL)
    ):
        if take < n:
            result += identify_reaction(reaction, n, MetID, MetIDH, MetIDH2O)

    reaction_jaccard_input = StringIO(result)
    out = pd.read_csv(reaction_jaccard_input, sep=" ", header=None)
    out.dropna(subset=[5, 6], inplace=True)
    return out


def gather_kegg_metabolites(Output: str) -> dict[str, str]:
    metabolite = {}
    with open(Output) as handle:
        content = handle.read()

    for species in re.findall(r"<species metaid.+?</species>", content, re.DOTALL):
        compound_id = ""
        met_id = re.findall('about="#(.+?)">', species)[0]
        if re.findall("compound.([A-Z][0-9]+)", species):
            compound_id = re.findall("compound.([A-Z][0-9]+)", species)[0]
        if met_id and compound_id and met_id not in metabolite:
            metabolite[met_id] = compound_id + re.findall("[a-z]+[0-9]*", met_id)[0]
    return metabolite


def replace_met_id_by_met_kegg(infile: pd.DataFrame, dictionary: dict) -> pd.DataFrame:
    infile = infile[infile[5].notna() & infile[6].notna()]
    infile[5].replace(dictionary, regex=True, inplace=True)
    infile[6].replace(dictionary, regex=True, inplace=True)
    return infile


def execute_jaccard(b: pd.DataFrame, c2: pd.DataFrame) -> pd.DataFrame:
    """Match reactions with identical left/right metabolite sets in either direction."""
    b_left_sets = [set(left.split(",")) for left in b[5]]
    b_right_sets = [set(right.split(",")) for right in b[6]]
    c2_left_sets = [set(left.split(",")) for left in c2[5]]
    c2_right_sets = [set(right.split(",")) for right in c2[6]]

    b_ids = [str(reaction_id) for reaction_id in b[0]]
    c2_ids = [str(reaction_id) for reaction_id in c2[1]]

    results = []
    for i, (b_left, b_right, b_id) in enumerate(
        zip(b_left_sets, b_right_sets, b_ids, strict=True)
    ):
        for j, (c2_left, c2_right, c2_id) in enumerate(
            zip(c2_left_sets, c2_right_sets, c2_ids, strict=True)
        ):
            if (b_left == c2_left and b_right == c2_right) or (
                b_left == c2_right and b_right == c2_left
            ):
                results.append(
                    [
                        b_id,
                        b[5].iloc[i],
                        b[6].iloc[i],
                        c2_id,
                        c2[5].iloc[j],
                        c2[6].iloc[j],
                        2.0,
                    ]
                )
                break

    if results:
        return pd.DataFrame(results)
    return pd.DataFrame(columns=range(7))


def process_jaccard(
    left_model: pd.DataFrame, right_model: pd.DataFrame, jaccard_result: pd.DataFrame
) -> dict:
    """Postprocess dataframe from reaction Jaccard matching."""
    right_model.columns = [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
    jaccard_result.columns = [0, 5, 6, 14, 18, 19, 12]

    for df, cols in (
        (jaccard_result, [0, 5, 6, 14, 18, 19]),
        (right_model, [14, 18, 19]),
        (left_model, [0, 5, 6]),
    ):
        for col in cols:
            if col in df.columns:
                df[col] = df[col].astype("string")

    jaccard_result = pd.merge(
        pd.merge(jaccard_result, right_model, on=[18, 19, 14]), left_model, on=[0, 5, 6]
    ).drop(columns=[11])
    jaccard_result = jaccard_result.sort_index(axis=1)
    jaccard_result = jaccard_result.sort_values(by=[0, 1])
    jaccard_result[100] = jaccard_result[1] + jaccard_result[2]
    mm = jaccard_result[
        (
            jaccard_result[100].isin(
                jaccard_result[100][jaccard_result[100].duplicated()]
            )
        )
    ]
    mm = mm[(mm[8] == mm[21])]
    mm = mm[(mm[100].isin(mm[100][mm[100].duplicated()]))]
    mm = mm.drop_duplicates(100).reset_index(drop=True)
    jaccard_result = jaccard_result.loc[~jaccard_result[100].isin(mm[100])]
    jaccard_result = jaccard_result[(jaccard_result[8] == jaccard_result[21])]
    jaccard_result = jaccard_result[jaccard_result[1] != jaccard_result[14]]
    jaccard_result = jaccard_result.rename(columns={1: "kegg.reaction"})
    jaccard_result = jaccard_result[["kegg.reaction", 14, 24]]

    result = {}
    for _, row in jaccard_result.iterrows():
        result[row[24]] = row.drop([14, 24]).to_dict()
    return result


def identify_reaction(
    reaction: str,
    n: int,
    MetID: str,
    MetIDH: str,
    MetIDH2O: str | None = "",
) -> str:
    mar_id = "MAR[0-9]+"
    met_id_pattern = "([A-Z0-9]+)"
    reactants_pattern = "<listOfReactants>(.+?)<.listOfReactants>"
    products_pattern = "<listOfProducts>(.+?)<.listOfProducts>"
    products, product_compartments = [], []
    rxn_id, mar = "", ""

    if re.findall("/(R[0-9]+)", reaction):
        rxn_id = re.findall("/(R[0-9]+)", reaction)[0]
    if re.findall(mar_id, reaction):
        mar = re.findall(mar_id, reaction)[0]

    reactants = re.findall(reactants_pattern, reaction, re.DOTALL)[0]
    reactants = re.findall(MetID, reactants)
    reactant_compartments = list(
        {re.findall("[a-z]+[0-9]*", reactant)[0] for reactant in reactants}
    )
    reactants = [
        reactant
        for reactant in reactants
        if re.findall(met_id_pattern, reactant)[0] not in MetIDH
        and re.findall(met_id_pattern, reactant)[0] not in MetIDH2O
    ]

    if re.findall(products_pattern, reaction, re.DOTALL):
        products = re.findall(products_pattern, reaction, re.DOTALL)[0]
        products = re.findall(MetID, products)
        product_compartments = list(
            {re.findall("[a-z]+[0-9]*", product)[0] for product in products}
        )
        products = [
            product
            for product in products
            if re.findall(met_id_pattern, product)[0] not in MetIDH
            and re.findall(met_id_pattern, product)[0] not in MetIDH2O
        ]

    species_pairs = (
        ",".join(map(str, reactants)) + " " + ",".join(map(str, products))
    ).replace("_", "")
    compartments = ",".join(set(re.findall("[a-z]+[0-9]*", species_pairs)))
    all_compartments = ",".join(set(reactant_compartments + product_compartments))
    stoichiometry = [
        str(round(float(re.findall(species + '" stoichiometry="(.+?)"', reaction)[0])))
        for species in reactants + products
    ]
    stoichiometry = ",".join(stoichiometry)
    all_stoichiometry = [
        str(round(float(value)))
        for value in re.findall('stoichiometry="(.+?)"', reaction)
    ]
    all_stoichiometry = ",".join(all_stoichiometry)
    reversible = re.findall('reversible="(.+?)"', reaction)[0]
    ec_numbers = ",".join(re.findall(r'\/[a-z]+-[a-z]+\/\+?([\.0-9]+)"/>', reaction))
    genes = ",".join(re.findall('geneProduct="(.+?)"/>', reaction))

    return (
        str(n)
        + " "
        + rxn_id
        + " "
        + compartments
        + " "
        + all_compartments
        + " "
        + reversible
        + " "
        + species_pairs
        + " "
        + stoichiometry
        + " "
        + all_stoichiometry
        + " "
        + ec_numbers
        + " "
        + genes
        + " "
        + mar
        + "\n"
    )


def jaccard(list1: list, list2: list) -> float:
    intersection = len(set(list1).intersection(list2))
    union = (len(list1) + len(list2)) - intersection
    return float(intersection) / union
