import typing
import weave


@weave.op()
def confusion_matrix(
    inp: typing.Any, guess_col: str, truth_col: str, compare_col: str
) -> weave.panels.Facet:
    return weave.panels.Facet(
        input_node=inp,
        x=lambda i: i[guess_col],
        y=lambda i: i[truth_col],
        select=lambda cell: cell.count(),
    )
