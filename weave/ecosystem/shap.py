import os
import shap
import random
import typing
import xgboost
import numpy as np

import matplotlib.pyplot as plt
from sklearn.datasets import fetch_california_housing
import weave


@weave.op(
    render_info={"type": "function"},
    output_type=weave.ops.DataFrameType(weave.types.TypedDict({})),
)
def ca_housing_dataset(seed: int):
    housing = fetch_california_housing(as_frame=True)
    housingdf = housing.frame
    return housingdf


@weave.op(
    output_type=weave.types.TypedDict({"X": weave.types.Any(), "y": weave.types.Any()})
)
def split_labels(df: typing.Any, label_col: str):
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


class XGBoostModelType(weave.types.Type):
    name = "xgboost-model"
    instance_class = xgboost.core.Booster
    instance_classes = xgboost.core.Booster

    def save_instance(cls, obj, artifact, name):
        os.makedirs(artifact._write_dirname, exist_ok=True)
        f = os.path.join(artifact._write_dirname, f"{name}.json")
        obj.save_model(f)

    def load_instance(self, artifact, name, extra=None):
        f = os.path.join(artifact._read_dirname, f"{name}.json")
        model_xgb = xgboost.Booster()
        model_xgb.load_model(f)
        return model_xgb


@weave.weave_class(weave_type=XGBoostModelType)
class XGBoostMdelOps:
    @weave.op()
    def shap_explain(self: xgboost.core.Booster, data: typing.Any) -> ShapValues:
        explainer = shap.TreeExplainer(self)
        shap_values = explainer.shap_values(data)
        return ShapValues(shap_values)


class XGBoostHyperparams(typing.TypedDict):
    learning_rate: float


@weave.op()
def xgboost_train(
    xy: typing.Any, hyperparams: XGBoostHyperparams
) -> xgboost.core.Booster:
    return xgboost.train(
        hyperparams, xgboost.DMatrix(xy["X"], label=xy["y"].to_numpy()), 100
    )
