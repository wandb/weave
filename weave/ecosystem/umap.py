import joblib
import os

# import pickle
import random
import shap
import typing
import umap
import weave

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from sklearn.datasets import fetch_openml


@weave.op(
    render_info={"type": "function"},
    output_type=weave.types.TypedDict(
        {
            "digits": weave.types.Any(),
            "labels": weave.ops.DataFrameType(weave.types.TypedDict({})),
        }
    ),
)  # https://scikit-learn.org/stable/datasets/loading_other_datasets.html#openml
def get_mnist(version: int, dataset_name: str = "mnist_784"):
    mnist = fetch_openml(dataset_name, version=version)
    digits = mnist.data
    labels = mnist.target.astype("int").to_frame()
    return {"digits": digits, "labels": labels}


class UMAPReducer(weave.types.Type):
    name = "UMAP-model"
    instance_class = umap.umap_.UMAP
    instance_classes = umap.umap_.UMAP

    """
	You can't serialize UMAP as JSON this will require pkl or joblib
	"""

    # pkl
    # def save_instance(cls, obj, artifact, name):
    # 	os.makedirs(artifact._write_dirname, exist_ok=True)
    # 	f = os.path.join(artifact._write_dirname, f"{name}.pkl")
    # 	pickle.dump(obj, open(f, 'wb'))

    # def load_instance(self, artifact, name, extra=None):
    # 	f = os.path.join(artifact._read_dirname, f"{name}.pkl")
    # 	loaded_reducer = pickle.load((open(f, 'rb')))
    # 	return loaded_reducer

    # joblib
    def save_instance(cls, obj, artifact, name):
        os.makedirs(artifact._write_dirname, exist_ok=True)
        f = os.path.join(artifact._write_dirname, f"{name}.pkl")
        joblib.dump(obj, f)

    def load_instance(self, artifact, name, extra=None):
        f = os.path.join(artifact._read_dirname, f"{name}.pkl")
        loaded_reducer = joblib.load(f)
        return loaded_reducer


@weave.op()
def UMAP_fit(unmapped_data: typing.Any, random_state: int = 42) -> umap.umap_.UMAP:
    return umap.UMAP(random_state=random_state).fit(unmapped_data)


@weave.type()
class MapPlot:
    embedding: np.ndarray
    labels: pd.DataFrame

    @weave.op(
        output_type=weave.types.FileType(weave.types.Const(weave.types.String(), "png"))  # type: ignore
    )
    def summary_plot(self, plot_title: str = "UMAP results"):
        fig, ax = plt.subplots(figsize=(12, 10))
        color = self.labels.to_numpy()
        plt.scatter(
            self.embedding[:, 0], self.embedding[:, 1], c=color, cmap="Spectral", s=0.1
        )
        plt.setp(ax, xticks=[], yticks=[])
        plt.title(plot_title, fontsize=18)
        path = f"/tmp/umap-{random.randrange(0, 1000000)}.png"
        plt.savefig(path)
        plt.close()
        return weave.ops.LocalFile(path)


@weave.weave_class(weave_type=UMAPReducer)
class UMAPOps:
    @weave.op()
    def transform(self: umap.umap_.UMAP, data: typing.Any) -> np.ndarray:
        return self.transform(data)

    @weave.op()
    def transform_plot_2d(
        self: umap.umap_.UMAP, data: typing.Any, labels: pd.DataFrame
    ) -> MapPlot:
        return MapPlot(self.transform(data), labels)
