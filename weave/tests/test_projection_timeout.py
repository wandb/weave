import numpy as np
import pytest

from ..ops_primitives import projection_utils


def test_projection_timeout():
    rng = np.random.RandomState(0)
    embeddings = rng.normal(0, 1, (1000, 50))
    result = projection_utils.perform_2D_projection_with_timeout(
        embeddings, "pca", {}, timeout=1e-6
    )
    assert np.isclose(result, 0).all()


def test_projection_timeout_error_propagation(raise_error_in_projection):
    rng = np.random.RandomState(0)
    embeddings = rng.normal(0, 1, (1000, 50))
    with pytest.raises(Exception):
        projection_utils.perform_2D_projection_with_timeout(
            embeddings, "pca", {}, timeout=None
        )
