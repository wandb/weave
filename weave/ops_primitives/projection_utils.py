import threading
import multiprocessing

import queue
import numpy as np
from .. import errors
from .. import environment
from .. import context_state
import typing
import logging
import warnings

from sklearn.manifold import TSNE
from sklearn.decomposition import PCA

umap_lib = {}

DEFAULT_TIMEOUT_SEC = environment.projection_timeout_sec()

ResultQueueItemType = typing.Union[Exception, np.ndarray]


def _get_umap():
    # Lazily load a cached version of UMAP - umap import
    # time is quite expensive so we want to do it once and
    # only when needed
    if "lib" not in umap_lib:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import umap

            umap_lib["lib"] = umap
    return umap_lib["lib"]


def perform_2D_projection(
    np_array_of_embeddings: np.ndarray,
    projectionAlgorithm: str,
    algorithmOptions: dict,
) -> np.ndarray:
    if len(np_array_of_embeddings.shape) != 2:
        raise errors.WeaveInternalError(
            f"The input to the 2D projection must be a 2D array of embeddings, found {np_array_of_embeddings.shape}"
        )
    if projectionAlgorithm == "pca":
        projection = perform_2D_projection_pca(
            np_array_of_embeddings, algorithmOptions.get("pca", {})
        )
    elif projectionAlgorithm == "tsne":
        projection = perform_2D_projection_tsne(
            np_array_of_embeddings, algorithmOptions.get("tsne", {})
        )
    elif projectionAlgorithm == "umap":
        projection = perform_2D_projection_umap(
            np_array_of_embeddings, algorithmOptions.get("umap", {})
        )
    else:
        raise Exception("Unknown projection algorithm: " + projectionAlgorithm)
    return projection


def perform_2D_projection_async(
    np_array_of_embeddings: np.ndarray,
    projectionAlgorithm: str,
    algorithmOptions: dict,
    result_queue: queue.Queue[ResultQueueItemType],
):
    try:
        projection = perform_2D_projection(
            np_array_of_embeddings, projectionAlgorithm, algorithmOptions
        )
        result_queue.put(projection)
    except Exception as e:
        result_queue.put(e)


def perform_2D_projection_with_timeout(
    np_array_of_embeddings: np.ndarray,
    projectionAlgorithm: str,
    algorithmOptions: dict,
    timeout: typing.Optional[typing.Union[int, float]] = DEFAULT_TIMEOUT_SEC,
) -> np.ndarray:
    if timeout is None:
        return perform_2D_projection(
            np_array_of_embeddings, projectionAlgorithm, algorithmOptions
        )

    # otherwise run it in another process and kill it if it goes over time

    result_queue: queue.Queue[ResultQueueItemType] = multiprocessing.Queue()
    target = multiprocessing.Process(
        target=perform_2D_projection_async,
        args=(
            np_array_of_embeddings,
            projectionAlgorithm,
            algorithmOptions,
            result_queue,
        ),
        name="projection",
    )
    target.start()

    try:
        result = result_queue.get(timeout=timeout)
    except queue.Empty:
        target.kill()
        logging.warning(
            f"Projection timed out after {timeout} seconds, killing process {target.pid}, returning empty projection",
        )

        return np.zeros((len(np_array_of_embeddings), 2))
    if isinstance(result, Exception):
        raise result

    return result


def limit_embedding_dimensions(
    np_array_of_embeddings: np.ndarray, max_dimensions: int = 50
) -> np.ndarray:
    max_dimensions = min(max_dimensions, len(np_array_of_embeddings))
    if np_array_of_embeddings.shape[1] > max_dimensions:
        return PCA(n_components=max_dimensions).fit_transform(np_array_of_embeddings)
    return np_array_of_embeddings


def perform_2D_projection_pca(
    np_array_of_embeddings: np.ndarray, options: dict
) -> np.ndarray:
    model = PCA(n_components=2)
    return model.fit_transform(np_array_of_embeddings)


def perform_2D_projection_tsne(
    np_array_of_embeddings: np.ndarray, options
) -> np.ndarray:
    n_samples = len(np_array_of_embeddings)
    return TSNE(
        n_components=2,
        perplexity=min(n_samples - 1, options.get("perplexity", 30)),
        n_iter=min(1000, max(500, options.get("iterations", 1000))),
        learning_rate=options.get("learningRate", "auto"),
        init="random",
    ).fit_transform(limit_embedding_dimensions(np_array_of_embeddings))


# TODO: we need lock stats in datadog
# UMAP is not thread safe, it crashes the server when called at the same
# time on parallel threads.
umap_lock = threading.Lock()


def perform_2D_projection_umap(
    np_array_of_embeddings: np.ndarray, options: dict
) -> np.ndarray:
    model = _get_umap().UMAP(
        n_components=2,
        # Letting the library choose defaults
        # n_neighbors=min(n_samples - 1, options.get("neighbors", 15)),
        # min_dist=options.get("minDist", 0.1),
        # spread=options.get("spread", 1.0),
        init="random",
    )
    with umap_lock:
        return model.fit_transform(np_array_of_embeddings)
