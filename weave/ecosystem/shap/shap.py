# Disable warning spew.
import warnings

warnings.filterwarnings("ignore", message=".*The 'nopython' keyword.*")

import shap
import random
import typing
import xgboost
import pickle
import numpy as np

import matplotlib.pyplot as plt
import weave

from .. import huggingface as hf
from .. import xgboost as weave_xgb


@weave.op(
    input_type={
        "df": weave.types.TypedDict({}),
    },
    output_type=weave.types.TypedDict({"X": weave.types.Any(), "y": weave.types.Any()}),
    hidden=True,
)
def split_labels(df, label_col: str):
    X = df.drop(label_col, axis=1)
    y = df[label_col]
    return {"X": X, "y": y}


@weave.type()
class ShapValues:
    values: np.ndarray

    @weave.op(
        output_type=weave.types.FileType(weave.types.Const(weave.types.String(), "png"))  # type: ignore
    )
    def summary_plot(self):
        shap.summary_plot(self.values, show=False)
        path = "/tmp/shap-%s.png" % random.randrange(0, 1000000)
        plt.savefig(path)
        plt.close()
        return weave.ops.LocalFile(path)


class ShapExplanationType(weave.types.Type):
    instance_classes = shap.Explanation

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.pickle", binary=True) as f:
            pickle.dump(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.pickle", binary=True) as f:
            return pickle.load(f)


@weave.op()
def shap_explain_tree(self: xgboost.core.Booster, data: typing.Any) -> ShapValues:
    explainer = shap.TreeExplainer(self)
    shap_values = explainer.shap_values(data)
    return ShapValues(shap_values)


@weave.op()
def shap_explain(
    pipeline_output: hf.FullTextClassificationPipelineOutput,
) -> shap.Explanation:
    # TODO: shap has some options, like computing logits is better in some cases?
    # TODO: does shap work for all task styles?
    pipeline = weave.use(pipeline_output._model.pipeline())
    explainer = shap.Explainer(pipeline)
    return explainer([pipeline_output.model_input])


@weave.op()
def shap_plot_text(shap_values: shap.Explanation) -> weave.ops.Html:
    html = shap.plots.text(shap_values, display=False)
    return weave.ops.Html(html)


@weave.type()
class ShapPlotText(weave.Panel):
    id = "ShapPlotText"
    input_node: weave.Node[shap.Explanation]

    @weave.op()
    def render(self) -> weave.panels.PanelHtml:
        return weave.panels.PanelHtml(shap_plot_text(self.input_node))
