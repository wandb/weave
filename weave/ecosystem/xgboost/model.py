import os
import xgboost
import typing

import weave


class XGBoostModelType(weave.types.Type):
    name = "xgboost_model"
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
class XGBoostModelOps:
    @weave.op()
    def predict(self, data: typing.Any) -> typing.Any:
        return self.predict(xgboost.DMatrix(data))


class XGBoostHyperparams(typing.TypedDict):
    learning_rate: float


@weave.op()
def xgboost_train(
    xy: typing.Any, hyperparams: XGBoostHyperparams
) -> xgboost.core.Booster:
    return xgboost.train(
        hyperparams, xgboost.DMatrix(xy["X"], label=xy["y"].to_numpy()), 100
    )
