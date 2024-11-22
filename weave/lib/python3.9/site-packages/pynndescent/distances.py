# Author: Leland McInnes <leland.mcinnes@gmail.com>
#
# License: BSD 3 clause
import numpy as np
import numba

from pynndescent.optimal_transport import (
    allocate_graph_structures,
    initialize_graph_structures,
    initialize_supply,
    initialize_cost,
    network_simplex_core,
    total_cost,
    ProblemStatus,
    sinkhorn_transport_plan,
)

_mock_identity = np.eye(2, dtype=np.float32)
_mock_ones = np.ones(2, dtype=np.float32)
_dummy_cost = np.zeros((2, 2), dtype=np.float64)

FLOAT32_EPS = np.finfo(np.float32).eps
FLOAT32_MAX = np.finfo(np.float32).max

popcnt = np.array(
    [bin(i).count('1') for i in range(256)],
    dtype=np.float32
)


@numba.njit(fastmath=True)
def euclidean(x, y):
    r"""Standard euclidean distance.

    .. math::
        D(x, y) = \\sqrt{\sum_i (x_i - y_i)^2}
    """
    result = 0.0
    for i in range(x.shape[0]):
        result += (x[i] - y[i]) ** 2
    return np.sqrt(result)


@numba.njit(
    [
        "f4(f4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "diff": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def squared_euclidean(x, y):
    r"""Squared euclidean distance.

    .. math::
        D(x, y) = \sum_i (x_i - y_i)^2
    """
    result = 0.0
    dim = x.shape[0]
    for i in range(dim):
        diff = x[i] - y[i]
        result += diff * diff

    return result


@numba.njit(fastmath=True)
def standardised_euclidean(x, y, sigma=_mock_ones):
    r"""Euclidean distance standardised against a vector of standard
    deviations per coordinate.

    .. math::
        D(x, y) = \sqrt{\sum_i \frac{(x_i - y_i)**2}{v_i}}
    """
    result = 0.0
    for i in range(x.shape[0]):
        result += ((x[i] - y[i]) ** 2) / sigma[i]

    return np.sqrt(result)


@numba.njit(fastmath=True)
def manhattan(x, y):
    r"""Manhattan, taxicab, or l1 distance.

    .. math::
        D(x, y) = \sum_i |x_i - y_i|
    """
    result = 0.0
    for i in range(x.shape[0]):
        result += np.abs(x[i] - y[i])

    return result


@numba.njit(fastmath=True)
def chebyshev(x, y):
    r"""Chebyshev or l-infinity distance.

    .. math::
        D(x, y) = \max_i |x_i - y_i|
    """
    result = 0.0
    for i in range(x.shape[0]):
        result = max(result, np.abs(x[i] - y[i]))

    return result


@numba.njit(fastmath=True)
def minkowski(x, y, p=2):
    r"""Minkowski distance.

    .. math::
        D(x, y) = \left(\sum_i |x_i - y_i|^p\right)^{\frac{1}{p}}

    This is a general distance. For p=1 it is equivalent to
    manhattan distance, for p=2 it is Euclidean distance, and
    for p=infinity it is Chebyshev distance. In general it is better
    to use the more specialised functions for those distances.
    """
    result = 0.0
    for i in range(x.shape[0]):
        result += (np.abs(x[i] - y[i])) ** p

    return result ** (1.0 / p)


@numba.njit(fastmath=True)
def weighted_minkowski(x, y, w=_mock_ones, p=2):
    r"""A weighted version of Minkowski distance.

    .. math::
        D(x, y) = \left(\sum_i w_i |x_i - y_i|^p\right)^{\frac{1}{p}}

    If weights w_i are inverse standard deviations of graph_data in each dimension
    then this represented a standardised Minkowski distance (and is
    equivalent to standardised Euclidean distance for p=1).
    """
    result = 0.0
    for i in range(x.shape[0]):
        result += w[i] * np.abs(x[i] - y[i]) ** p

    return result ** (1.0 / p)


@numba.njit(fastmath=True)
def mahalanobis(x, y, vinv=_mock_identity):
    result = 0.0

    diff = np.empty(x.shape[0], dtype=np.float32)

    for i in range(x.shape[0]):
        diff[i] = x[i] - y[i]

    for i in range(x.shape[0]):
        tmp = 0.0
        for j in range(x.shape[0]):
            tmp += vinv[i, j] * diff[j]
        result += tmp * diff[i]

    return np.sqrt(result)


@numba.njit(fastmath=True)
def hamming(x, y):
    result = 0.0
    for i in range(x.shape[0]):
        if x[i] != y[i]:
            result += 1.0

    return float(result) / x.shape[0]


@numba.njit(fastmath=True)
def canberra(x, y):
    result = 0.0
    for i in range(x.shape[0]):
        denominator = np.abs(x[i]) + np.abs(y[i])
        if denominator > 0:
            result += np.abs(x[i] - y[i]) / denominator

    return result


@numba.njit(fastmath=True)
def bray_curtis(x, y):
    numerator = 0.0
    denominator = 0.0
    for i in range(x.shape[0]):
        numerator += np.abs(x[i] - y[i])
        denominator += np.abs(x[i] + y[i])

    if denominator > 0.0:
        return float(numerator) / denominator
    else:
        return 0.0


@numba.njit(fastmath=True)
def jaccard(x, y):
    num_non_zero = 0.0
    num_equal = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_non_zero += x_true or y_true
        num_equal += x_true and y_true

    if num_non_zero == 0.0:
        return 0.0
    else:
        return float(num_non_zero - num_equal) / num_non_zero


@numba.njit(
    [
        "f4(f4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "num_non_zero": numba.types.float32,
        "num_equal": numba.types.float32,
        "x_true": numba.types.uint8,
        "y_true": numba.types.uint8,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def alternative_jaccard(x, y):
    num_non_zero = 0.0
    num_equal = 0.0
    dim = x.shape[0]
    for i in range(dim):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_non_zero += x_true or y_true
        num_equal += x_true and y_true

    if num_non_zero == 0.0:
        return 0.0
    else:
        return -np.log2(num_equal / num_non_zero)


@numba.vectorize(fastmath=True)
def correct_alternative_jaccard(v):
    return 1.0 - pow(2.0, -v)


@numba.njit(fastmath=True)
def matching(x, y):
    num_not_equal = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_not_equal += x_true != y_true

    return float(num_not_equal) / x.shape[0]


@numba.njit(fastmath=True)
def dice(x, y):
    num_true_true = 0.0
    num_not_equal = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_true_true += x_true and y_true
        num_not_equal += x_true != y_true

    if num_not_equal == 0.0:
        return 0.0
    else:
        return num_not_equal / (2.0 * num_true_true + num_not_equal)


@numba.njit(fastmath=True)
def kulsinski(x, y):
    num_true_true = 0.0
    num_not_equal = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_true_true += x_true and y_true
        num_not_equal += x_true != y_true

    if num_not_equal == 0:
        return 0.0
    else:
        return float(num_not_equal - num_true_true + x.shape[0]) / (
            num_not_equal + x.shape[0]
        )


@numba.njit(fastmath=True)
def rogers_tanimoto(x, y):
    num_not_equal = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_not_equal += x_true != y_true

    return (2.0 * num_not_equal) / (x.shape[0] + num_not_equal)


@numba.njit(fastmath=True)
def russellrao(x, y):
    num_true_true = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_true_true += x_true and y_true

    if num_true_true == np.sum(x != 0) and num_true_true == np.sum(y != 0):
        return 0.0
    else:
        return float(x.shape[0] - num_true_true) / (x.shape[0])


@numba.njit(fastmath=True)
def sokal_michener(x, y):
    num_not_equal = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_not_equal += x_true != y_true

    return (2.0 * num_not_equal) / (x.shape[0] + num_not_equal)


@numba.njit(fastmath=True)
def sokal_sneath(x, y):
    num_true_true = 0.0
    num_not_equal = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_true_true += x_true and y_true
        num_not_equal += x_true != y_true

    if num_not_equal == 0.0:
        return 0.0
    else:
        return num_not_equal / (0.5 * num_true_true + num_not_equal)


@numba.njit(fastmath=True)
def haversine(x, y):
    if x.shape[0] != 2:
        raise ValueError("haversine is only defined for 2 dimensional graph_data")
    sin_lat = np.sin(0.5 * (x[0] - y[0]))
    sin_long = np.sin(0.5 * (x[1] - y[1]))
    result = np.sqrt(sin_lat**2 + np.cos(x[0]) * np.cos(y[0]) * sin_long**2)
    return 2.0 * np.arcsin(result)


@numba.njit(fastmath=True)
def yule(x, y):
    num_true_true = 0.0
    num_true_false = 0.0
    num_false_true = 0.0
    for i in range(x.shape[0]):
        x_true = x[i] != 0
        y_true = y[i] != 0
        num_true_true += x_true and y_true
        num_true_false += x_true and (not y_true)
        num_false_true += (not x_true) and y_true

    num_false_false = x.shape[0] - num_true_true - num_true_false - num_false_true

    if num_true_false == 0.0 or num_false_true == 0.0:
        return 0.0
    else:
        return (2.0 * num_true_false * num_false_true) / (
            num_true_true * num_false_false + num_true_false * num_false_true
        )


@numba.njit(fastmath=True)
def cosine(x, y):
    result = 0.0
    norm_x = 0.0
    norm_y = 0.0
    for i in range(x.shape[0]):
        result += x[i] * y[i]
        norm_x += x[i] ** 2
        norm_y += y[i] ** 2

    if norm_x == 0.0 and norm_y == 0.0:
        return 0.0
    elif norm_x == 0.0 or norm_y == 0.0:
        return 1.0
    else:
        return 1.0 - (result / np.sqrt(norm_x * norm_y))


@numba.njit(
    [
        "f4(f4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "norm_x": numba.types.float32,
        "norm_y": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def alternative_cosine(x, y):
    result = 0.0
    norm_x = 0.0
    norm_y = 0.0
    dim = x.shape[0]
    for i in range(dim):
        result += x[i] * y[i]
        norm_x += x[i] * x[i]
        norm_y += y[i] * y[i]

    if norm_x == 0.0 and norm_y == 0.0:
        return 0.0
    elif norm_x == 0.0 or norm_y == 0.0:
        return FLOAT32_MAX
    elif result <= 0.0:
        return FLOAT32_MAX
    else:
        result = np.sqrt(norm_x * norm_y) / result
        return np.log2(result)


@numba.njit(
    "f4(f4[::1],f4[::1])",
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def dot(x, y):
    result = 0.0
    dim = x.shape[0]
    for i in range(dim):
        result += x[i] * y[i]

    if result <= 0.0:
        return 1.0
    else:
        return 1.0 - result


@numba.njit(
    [
        "f4(f4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def alternative_dot(x, y):
    result = 0.0
    dim = x.shape[0]
    for i in range(dim):
        result += x[i] * y[i]

    if result <= 0.0:
        return FLOAT32_MAX
    else:
        return -np.log2(result)


@numba.vectorize(fastmath=True)
def correct_alternative_cosine(d):
    return 1.0 - pow(2.0, -d)


@numba.njit(fastmath=True)
def tsss(x, y):
    d_euc_squared = 0.0
    d_cos = 0.0
    norm_x = 0.0
    norm_y = 0.0
    dim = x.shape[0]

    for i in range(dim):
        diff = x[i] - y[i]
        d_euc_squared += diff * diff
        d_cos += x[i] * y[i]
        norm_x += x[i] * x[i]
        norm_y += y[i] * y[i]

    norm_x = np.sqrt(norm_x)
    norm_y = np.sqrt(norm_y)
    magnitude_difference = np.abs(norm_x - norm_y)
    d_cos /= norm_x * norm_y
    theta = np.arccos(d_cos) + np.radians(10)  # Add 10 degrees as an "epsilon" to
    # avoid problems
    sector = ((np.sqrt(d_euc_squared) + magnitude_difference) ** 2) * theta
    triangle = norm_x * norm_y * np.sin(theta) / 2.0
    return triangle * sector


@numba.njit(fastmath=True)
def true_angular(x, y):
    result = 0.0
    norm_x = 0.0
    norm_y = 0.0
    dim = x.shape[0]
    for i in range(dim):
        result += x[i] * y[i]
        norm_x += x[i] * x[i]
        norm_y += y[i] * y[i]

    if norm_x == 0.0 and norm_y == 0.0:
        return 0.0
    elif norm_x == 0.0 or norm_y == 0.0:
        return FLOAT32_MAX
    elif result <= 0.0:
        return FLOAT32_MAX
    else:
        result = result / np.sqrt(norm_x * norm_y)
        return 1.0 - (np.arccos(result) / np.pi)


@numba.vectorize(fastmath=True)
def true_angular_from_alt_cosine(d):
    return 1.0 - (np.arccos(pow(2.0, -d)) / np.pi)


@numba.njit(fastmath=True)
def correlation(x, y):
    mu_x = 0.0
    mu_y = 0.0
    norm_x = 0.0
    norm_y = 0.0
    dot_product = 0.0

    for i in range(x.shape[0]):
        mu_x += x[i]
        mu_y += y[i]

    mu_x /= x.shape[0]
    mu_y /= x.shape[0]

    for i in range(x.shape[0]):
        shifted_x = x[i] - mu_x
        shifted_y = y[i] - mu_y
        norm_x += shifted_x**2
        norm_y += shifted_y**2
        dot_product += shifted_x * shifted_y

    if norm_x == 0.0 and norm_y == 0.0:
        return 0.0
    elif dot_product == 0.0:
        return 1.0
    else:
        return 1.0 - (dot_product / np.sqrt(norm_x * norm_y))


@numba.njit(
    [
        "f4(f4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "l1_norm_x": numba.types.float32,
        "l1_norm_y": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def hellinger(x, y):
    result = 0.0
    l1_norm_x = 0.0
    l1_norm_y = 0.0
    dim = x.shape[0]

    for i in range(dim):
        result += np.sqrt(x[i] * y[i])
        l1_norm_x += x[i]
        l1_norm_y += y[i]

    if l1_norm_x == 0 and l1_norm_y == 0:
        return 0.0
    elif l1_norm_x == 0 or l1_norm_y == 0:
        return 1.0
    else:
        return np.sqrt(1 - result / np.sqrt(l1_norm_x * l1_norm_y))


@numba.njit(
    [
        "f4(f4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "l1_norm_x": numba.types.float32,
        "l1_norm_y": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def alternative_hellinger(x, y):
    result = 0.0
    l1_norm_x = 0.0
    l1_norm_y = 0.0
    dim = x.shape[0]

    for i in range(dim):
        result += np.sqrt(x[i] * y[i])
        l1_norm_x += x[i]
        l1_norm_y += y[i]

    if l1_norm_x == 0 and l1_norm_y == 0:
        return 0.0
    elif l1_norm_x == 0 or l1_norm_y == 0:
        return FLOAT32_MAX
    elif result <= 0:
        return FLOAT32_MAX
    else:
        result = np.sqrt(l1_norm_x * l1_norm_y) / result
        return np.log2(result)


@numba.vectorize(fastmath=True)
def correct_alternative_hellinger(d):
    return np.sqrt(1.0 - pow(2.0, -d))


@numba.njit()
def rankdata(a, method="average"):
    arr = np.ravel(np.asarray(a))
    if method == "ordinal":
        sorter = arr.argsort(kind="mergesort")
    else:
        sorter = arr.argsort(kind="quicksort")

    inv = np.empty(sorter.size, dtype=np.intp)
    inv[sorter] = np.arange(sorter.size)

    if method == "ordinal":
        return (inv + 1).astype(np.float64)

    arr = arr[sorter]
    obs = np.ones(arr.size, np.bool_)
    obs[1:] = arr[1:] != arr[:-1]
    dense = obs.cumsum()[inv]

    if method == "dense":
        return dense.astype(np.float64)

    # cumulative counts of each unique value
    nonzero = np.nonzero(obs)[0]
    count = np.concatenate((nonzero, np.array([len(obs)], nonzero.dtype)))

    if method == "max":
        return count[dense].astype(np.float64)

    if method == "min":
        return (count[dense - 1] + 1).astype(np.float64)

    # average method
    return 0.5 * (count[dense] + count[dense - 1] + 1)


@numba.njit(fastmath=True)
def spearmanr(x, y):
    x_rank = rankdata(x)
    y_rank = rankdata(y)

    return correlation(x_rank, y_rank)


@numba.njit(nogil=True)
def kantorovich(x, y, cost=_dummy_cost, max_iter=100000):

    row_mask = x != 0
    col_mask = y != 0

    a = x[row_mask].astype(np.float64)
    b = y[col_mask].astype(np.float64)

    a_sum = a.sum()
    b_sum = b.sum()

    # if not isclose(a_sum, b_sum):
    #     raise ValueError(
    #         "Kantorovich distance inputs must be valid probability distributions."
    #     )

    a /= a_sum
    b /= b_sum

    sub_cost = cost[row_mask, :][:, col_mask]

    node_arc_data, spanning_tree, graph = allocate_graph_structures(
        a.shape[0], b.shape[0], False
    )
    initialize_supply(a, -b, graph, node_arc_data.supply)
    initialize_cost(sub_cost, graph, node_arc_data.cost)
    # initialize_cost(cost, graph, node_arc_data.cost)
    init_status = initialize_graph_structures(graph, node_arc_data, spanning_tree)
    if init_status == False:
        raise ValueError(
            "Kantorovich distance inputs must be valid probability distributions."
        )
    solve_status = network_simplex_core(node_arc_data, spanning_tree, graph, max_iter)
    # if solve_status == ProblemStatus.MAX_ITER_REACHED:
    #     print("WARNING: RESULT MIGHT BE INACCURATE\nMax number of iteration reached!")
    if solve_status == ProblemStatus.INFEASIBLE:
        raise ValueError(
            "Optimal transport problem was INFEASIBLE. Please check inputs."
        )
    elif solve_status == ProblemStatus.UNBOUNDED:
        raise ValueError(
            "Optimal transport problem was UNBOUNDED. Please check inputs."
        )
    result = total_cost(node_arc_data.flow, node_arc_data.cost)

    return result


@numba.njit(fastmath=True)
def sinkhorn(x, y, cost=_dummy_cost, regularization=1.0):
    row_mask = x != 0
    col_mask = y != 0

    a = x[row_mask].astype(np.float64)
    b = y[col_mask].astype(np.float64)

    a_sum = a.sum()
    b_sum = b.sum()

    a /= a_sum
    b /= b_sum

    sub_cost = cost[row_mask, :][:, col_mask]

    transport_plan = sinkhorn_transport_plan(
        x, y, cost=sub_cost, regularization=regularization
    )
    dim_i = transport_plan.shape[0]
    dim_j = transport_plan.shape[1]
    result = 0.0
    for i in range(dim_i):
        for j in range(dim_j):
            result += transport_plan[i, j] * cost[i, j]

    return result


@numba.njit()
def jensen_shannon_divergence(x, y):
    result = 0.0
    l1_norm_x = 0.0
    l1_norm_y = 0.0
    dim = x.shape[0]

    for i in range(dim):
        l1_norm_x += x[i]
        l1_norm_y += y[i]

    l1_norm_x += FLOAT32_EPS * dim
    l1_norm_y += FLOAT32_EPS * dim

    pdf_x = (x + FLOAT32_EPS) / l1_norm_x
    pdf_y = (y + FLOAT32_EPS) / l1_norm_y
    m = 0.5 * (pdf_x + pdf_y)

    for i in range(dim):
        result += 0.5 * (
            pdf_x[i] * np.log(pdf_x[i] / m[i]) + pdf_y[i] * np.log(pdf_y[i] / m[i])
        )

    return result


@numba.njit()
def wasserstein_1d(x, y, p=1):
    x_sum = 0.0
    y_sum = 0.0
    for i in range(x.shape[0]):
        x_sum += x[i]
        y_sum += y[i]

    x_cdf = x / x_sum
    y_cdf = y / y_sum

    for i in range(1, x_cdf.shape[0]):
        x_cdf[i] += x_cdf[i - 1]
        y_cdf[i] += y_cdf[i - 1]

    return minkowski(x_cdf, y_cdf, p)


@numba.njit()
def circular_kantorovich(x, y, p=1):
    x_sum = 0.0
    y_sum = 0.0
    for i in range(x.shape[0]):
        x_sum += x[i]
        y_sum += y[i]

    x_cdf = x / x_sum
    y_cdf = y / y_sum

    for i in range(1, x_cdf.shape[0]):
        x_cdf[i] += x_cdf[i - 1]
        y_cdf[i] += y_cdf[i - 1]

    mu = np.median((x_cdf - y_cdf) ** p)

    # Now we just want minkowski distance on the CDFs shifted by mu
    result = 0.0
    if p > 2:
        for i in range(x_cdf.shape[0]):
            result += np.abs(x_cdf[i] - y_cdf[i] - mu) ** p

        return result ** (1.0 / p)

    elif p == 2:
        for i in range(x_cdf.shape[0]):
            val = x_cdf[i] - y_cdf[i] - mu
            result += val * val

        return np.sqrt(result)

    elif p == 1:
        for i in range(x_cdf.shape[0]):
            result += np.abs(x_cdf[i] - y_cdf[i] - mu)

        return result

    else:
        raise ValueError("Invalid p supplied to Kantorvich distance")


@numba.njit()
def symmetric_kl_divergence(x, y):
    result = 0.0
    l1_norm_x = 0.0
    l1_norm_y = 0.0
    dim = x.shape[0]

    for i in range(dim):
        l1_norm_x += x[i]
        l1_norm_y += y[i]

    l1_norm_x += FLOAT32_EPS * dim
    l1_norm_y += FLOAT32_EPS * dim

    pdf_x = (x + FLOAT32_EPS) / l1_norm_x
    pdf_y = (y + FLOAT32_EPS) / l1_norm_y

    for i in range(dim):
        result += pdf_x[i] * np.log(pdf_x[i] / pdf_y[i]) + pdf_y[i] * np.log(
            pdf_y[i] / pdf_x[i]
        )

    return result


@numba.njit(
    [
        "f4(u1[::1],u1[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.uint8, 1, "C", readonly=True),
            numba.types.Array(numba.types.uint8, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "intersection": numba.types.uint8,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def bit_hamming(x, y):
    result = 0.0
    dim = x.shape[0]

    for i in range(dim):
        intersection = x[i] ^ y[i]
        result += popcnt[intersection]

    return result


@numba.njit(
    [
        "f4(u1[::1],u1[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.uint8, 1, "C", readonly=True),
            numba.types.Array(numba.types.uint8, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "denom": numba.types.float32,
        "and_": numba.types.uint8,
        "or_": numba.types.uint8,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def bit_jaccard(x, y):
    result = 0.0
    denom = 0.0
    dim = x.shape[0]

    for i in range(dim):
        and_ = x[i] & y[i]
        or_ = x[i] | y[i]
        result += popcnt[and_]
        denom += popcnt[or_]

    return -np.log(result / denom)


named_distances = {
    # general minkowski distances
    "euclidean": euclidean,
    "l2": euclidean,
    "sqeuclidean": squared_euclidean,
    "manhattan": manhattan,
    "taxicab": manhattan,
    "l1": manhattan,
    "chebyshev": chebyshev,
    "linfinity": chebyshev,
    "linfty": chebyshev,
    "linf": chebyshev,
    "minkowski": minkowski,
    # Standardised/weighted distances
    "seuclidean": standardised_euclidean,
    "standardised_euclidean": standardised_euclidean,
    "wminkowski": weighted_minkowski,
    "weighted_minkowski": weighted_minkowski,
    "mahalanobis": mahalanobis,
    # Other distances
    "canberra": canberra,
    "cosine": cosine,
    "dot": dot,
    "correlation": correlation,
    "haversine": haversine,
    "braycurtis": bray_curtis,
    "spearmanr": spearmanr,
    "tsss": tsss,
    "true_angular": true_angular,
    # Distribution distances
    "hellinger": hellinger,
    "kantorovich": kantorovich,
    "wasserstein": kantorovich,
    "wasserstein_1d": wasserstein_1d,
    "wasserstein-1d": wasserstein_1d,
    "kantorovich-1d": wasserstein_1d,
    "kantorovich_1d": wasserstein_1d,
    "circular_kantorovich": circular_kantorovich,
    "circular_wasserstein": circular_kantorovich,
    "sinkhorn": sinkhorn,
    "jensen-shannon": jensen_shannon_divergence,
    "jensen_shannon": jensen_shannon_divergence,
    "symmetric-kl": symmetric_kl_divergence,
    "symmetric_kl": symmetric_kl_divergence,
    "symmetric_kullback_liebler": symmetric_kl_divergence,
    # Binary distances
    "hamming": hamming,
    "jaccard": jaccard,
    "dice": dice,
    "matching": matching,
    "kulsinski": kulsinski,
    "rogerstanimoto": rogers_tanimoto,
    "russellrao": russellrao,
    "sokalsneath": sokal_sneath,
    "sokalmichener": sokal_michener,
    "yule": yule,
    "bit_hamming": bit_hamming,
    "bit_jaccard": bit_jaccard,
}

# Some distances have a faster to compute alternative that
# retains the same ordering of distances. We can compute with
# this instead, and then correct the final distances when complete.
# This provides a list of distances that have such an alternative
# along with the alternative distance function and the correction
# function to be applied.
fast_distance_alternatives = {
    "euclidean": {"dist": squared_euclidean, "correction": np.sqrt},
    "l2": {"dist": squared_euclidean, "correction": np.sqrt},
    "cosine": {"dist": alternative_cosine, "correction": correct_alternative_cosine},
    "dot": {"dist": alternative_dot, "correction": correct_alternative_cosine},
    "true_angular": {
        "dist": alternative_cosine,
        "correction": true_angular_from_alt_cosine,
    },
    "hellinger": {
        "dist": alternative_hellinger,
        "correction": correct_alternative_hellinger,
    },
    "jaccard": {"dist": alternative_jaccard, "correction": correct_alternative_jaccard},
}
