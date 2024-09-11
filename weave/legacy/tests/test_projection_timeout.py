import numpy as np
import pytest

from weave.legacy.weave.ops_primitives import projection_utils

from ... import errors


def test_projection_timeout():
    rng = np.random.RandomState(0)
    embeddings = rng.normal(0, 1, (1000, 50))
    result = projection_utils.perform_2D_projection_with_timeout(
        embeddings, "pca", {}, timeout=1e-6
    )
    assert np.isclose(result, 0).all()


def test_projection_timeout_error_propagation():
    rng = np.random.RandomState(0)
    embeddings = rng.normal(0, 1, (3, 2, 4))
    with pytest.raises(errors.WeaveInternalError):
        projection_utils.perform_2D_projection_with_timeout(
            embeddings, "pca", {}, timeout=1e4
        )
