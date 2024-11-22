# Author: Leland McInnes <leland.mcinnes@gmail.com>
# Enough simple sparse operations in numba to enable sparse UMAP
#
# License: BSD 3 clause
from __future__ import print_function
import locale
import numpy as np
import numba

from pynndescent.utils import norm, tau_rand
from pynndescent.distances import (
    kantorovich,
    jensen_shannon_divergence,
    symmetric_kl_divergence,
)

locale.setlocale(locale.LC_NUMERIC, "C")

FLOAT32_EPS = np.finfo(np.float32).eps
FLOAT32_MAX = np.finfo(np.float32).max

# Just reproduce a simpler version of numpy isclose (not numba supported yet)
@numba.njit(cache=True)
def isclose(a, b, rtol=1.0e-5, atol=1.0e-8):
    diff = np.abs(a - b)
    return diff <= (atol + rtol * np.abs(b))


# Just reproduce a simpler version of numpy unique (not numba supported yet)
@numba.njit(cache=True)
def arr_unique(arr):
    aux = np.sort(arr)
    flag = np.concatenate((np.ones(1, dtype=np.bool_), aux[1:] != aux[:-1]))
    return aux[flag]


# Just reproduce a simpler version of numpy union1d (not numba supported yet)
@numba.njit(cache=True)
def arr_union(ar1, ar2):
    if ar1.shape[0] == 0:
        return ar2
    elif ar2.shape[0] == 0:
        return ar1
    else:
        return arr_unique(np.concatenate((ar1, ar2)))


# Just reproduce a simpler version of numpy intersect1d (not numba supported
# yet)
@numba.njit(cache=True)
def arr_intersect(ar1, ar2):
    aux = np.concatenate((ar1, ar2))
    aux.sort()
    return aux[:-1][aux[1:] == aux[:-1]]


# Some things require size of intersection; do this quickly; assume sorted arrays for speed
@numba.njit(
    [
        "i4(i4[:],i4[:])",
        numba.types.int32(
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
        ),
    ],
    locals={
        "i1": numba.uint16,
        "i2": numba.uint16,
    },
)
def fast_intersection_size(ar1, ar2):
    if ar1.shape[0] == 0 or ar2.shape[0] == 0:
        return 0

    # NOTE: We assume arrays are sorted; if they are not this will break
    i1 = 0
    i2 = 0
    limit1 = ar1.shape[0] - 1
    limit2 = ar2.shape[0] - 1
    j1 = ar1[i1]
    j2 = ar2[i2]

    result = 0

    while True:
        if j1 == j2:
            result += 1
            if i1 < limit1:
                i1 += 1
                j1 = ar1[i1]
            else:
                break

            if i2 < limit2:
                i2 += 1
                j2 = ar2[i2]
            else:
                break

        elif j1 < j2 and i1 < limit1:
            i1 += 1
            j1 = ar1[i1]
        elif j2 < j1 and i2 < limit2:
            i2 += 1
            j2 = ar2[i2]
        else:
            break

    return result


@numba.njit(
    [
        numba.types.Tuple(
            (
                numba.types.Array(numba.types.int32, 1, "C"),
                numba.types.Array(numba.types.float32, 1, "C"),
            )
        )(
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        )
    ],
    fastmath=True,
    locals={
        "result_ind": numba.types.int32[::1],
        "result_data": numba.types.float32[::1],
        "val": numba.types.float32,
        "i1": numba.types.int32,
        "i2": numba.types.int32,
        "j1": numba.types.int32,
        "j2": numba.types.int32,
    },
    cache=True,
)
def sparse_sum(ind1, data1, ind2, data2):
    result_size = ind1.shape[0] + ind2.shape[0]
    result_ind = np.zeros(result_size, dtype=np.int32)
    result_data = np.zeros(result_size, dtype=np.float32)

    i1 = 0
    i2 = 0
    nnz = 0

    # pass through both index lists
    while i1 < ind1.shape[0] and i2 < ind2.shape[0]:
        j1 = ind1[i1]
        j2 = ind2[i2]

        if j1 == j2:
            val = data1[i1] + data2[i2]
            if val != 0:
                result_ind[nnz] = j1
                result_data[nnz] = val
                nnz += 1
            i1 += 1
            i2 += 1
        elif j1 < j2:
            val = data1[i1]
            if val != 0:
                result_ind[nnz] = j1
                result_data[nnz] = val
                nnz += 1
            i1 += 1
        else:
            val = data2[i2]
            if val != 0:
                result_ind[nnz] = j2
                result_data[nnz] = val
                nnz += 1
            i2 += 1

    # pass over the tails
    while i1 < ind1.shape[0]:
        j1 = ind1[i1]
        val = data1[i1]
        if val != 0:
            result_ind[nnz] = j1
            result_data[nnz] = val
            nnz += 1
        i1 += 1

    while i2 < ind2.shape[0]:
        j2 = ind2[i2]
        val = data2[i2]
        if val != 0:
            result_ind[nnz] = j2
            result_data[nnz] = val
            nnz += 1
        i2 += 1

    # truncate to the correct length in case there were zeros created
    result_ind = result_ind[:nnz]
    result_data = result_data[:nnz]

    return result_ind, result_data


@numba.njit(cache=True)
def sparse_diff(ind1, data1, ind2, data2):
    return sparse_sum(ind1, data1, ind2, -data2)


@numba.njit(
    [
        # "Tuple((i4[::1],f4[::1]))(i4[::1],f4[::1],i4[::1],f4[::1])",
        numba.types.Tuple(
            (
                numba.types.ListType(numba.types.int32),
                numba.types.ListType(numba.types.float32),
            )
        )(
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        )
    ],
    fastmath=True,
    locals={
        "val": numba.types.float32,
        "i1": numba.types.int32,
        "i2": numba.types.int32,
        "j1": numba.types.int32,
        "j2": numba.types.int32,
    },
    cache=True,
)
def sparse_mul(ind1, data1, ind2, data2):
    result_ind = numba.typed.List.empty_list(numba.types.int32)
    result_data = numba.typed.List.empty_list(numba.types.float32)

    i1 = 0
    i2 = 0

    # pass through both index lists
    while i1 < ind1.shape[0] and i2 < ind2.shape[0]:
        j1 = ind1[i1]
        j2 = ind2[i2]

        if j1 == j2:
            val = data1[i1] * data2[i2]
            if val != 0:
                result_ind.append(j1)
                result_data.append(val)
            i1 += 1
            i2 += 1
        elif j1 < j2:
            i1 += 1
        else:
            i2 += 1

    return result_ind, result_data


@numba.njit(
    [
        # "Tuple((i4[::1],f4[::1]))(i4[::1],f4[::1],i4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        )
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "val": numba.types.float32,
        "i1": numba.types.uint16,
        "i2": numba.types.uint16,
        "j1": numba.types.int32,
        "j2": numba.types.int32,
    },
    cache=True,
)
def sparse_dot_product(ind1, data1, ind2, data2):
    dim1 = ind1.shape[0]
    dim2 = ind2.shape[0]

    result = 0.0

    i1 = 0
    i2 = 0
    j1 = ind1[i1]
    j2 = ind2[i2]

    # pass through both index lists
    while True:
        if j1 == j2:
            val = data1[i1] * data2[i2]
            result += val
            i1 += 1
            if i1 >= dim1:
                return result
            j1 = ind1[i1]
            i2 += 1
            if i2 >= dim2:
                return result
            j2 = ind2[i2]
        elif j1 < j2:
            i1 += 1
            if i1 >= dim1:
                return result
            j1 = ind1[i1]
        else:
            i2 += 1
            if i2 >= dim2:
                return result
            j2 = ind2[i2]

    return result  # unreachable


# Return dense vectors supported on the union of the non-zero valued indices
@numba.njit()
def dense_union(ind1, data1, ind2, data2):
    result_ind = arr_union(ind1, ind2)
    result_data1 = np.zeros(result_ind.shape[0], dtype=np.float32)
    result_data2 = np.zeros(result_ind.shape[0], dtype=np.float32)

    i1 = 0
    i2 = 0
    nnz = 0

    # pass through both index lists
    while i1 < ind1.shape[0] and i2 < ind2.shape[0]:
        j1 = ind1[i1]
        j2 = ind2[i2]

        if j1 == j2:
            val = data1[i1] + data2[i2]
            if val != 0:
                result_data1[nnz] = data1[i1]
                result_data2[nnz] = data2[i2]
                nnz += 1
            i1 += 1
            i2 += 1
        elif j1 < j2:
            val = data1[i1]
            if val != 0:
                result_data1[nnz] = data1[i1]
                nnz += 1
            i1 += 1
        else:
            val = data2[i2]
            if val != 0:
                result_data2[nnz] = data2[i2]
                nnz += 1
            i2 += 1

    # pass over the tails
    while i1 < ind1.shape[0]:
        val = data1[i1]
        if val != 0:
            result_data1[nnz] = data1[i1]
            nnz += 1
        i1 += 1

    while i2 < ind2.shape[0]:
        val = data2[i2]
        if val != 0:
            result_data2[nnz] = data2[i2]
            nnz += 1
        i2 += 1

    # truncate to the correct length in case there were zeros
    result_data1 = result_data1[:nnz]
    result_data2 = result_data2[:nnz]

    return result_data1, result_data2


@numba.njit(fastmath=True)
def sparse_euclidean(ind1, data1, ind2, data2):
    _, aux_data = sparse_diff(ind1, data1, ind2, data2)
    result = 0.0
    for i in range(aux_data.shape[0]):
        result += aux_data[i] ** 2
    return np.sqrt(result)


@numba.njit(
    [
        "f4(i4[::1],f4[::1],i4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "aux_data": numba.types.float32[::1],
        "result": numba.types.float32,
        "diff": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def sparse_squared_euclidean(ind1, data1, ind2, data2):
    _, aux_data = sparse_diff(ind1, data1, ind2, data2)
    result = 0.0
    dim = len(aux_data)
    for i in range(dim):
        result += aux_data[i] * aux_data[i]
    return result


@numba.njit()
def sparse_manhattan(ind1, data1, ind2, data2):
    _, aux_data = sparse_diff(ind1, data1, ind2, data2)
    result = 0.0
    for i in range(aux_data.shape[0]):
        result += np.abs(aux_data[i])
    return result


@numba.njit()
def sparse_chebyshev(ind1, data1, ind2, data2):
    _, aux_data = sparse_diff(ind1, data1, ind2, data2)
    result = 0.0
    for i in range(aux_data.shape[0]):
        result = max(result, np.abs(aux_data[i]))
    return result


@numba.njit()
def sparse_minkowski(ind1, data1, ind2, data2, p=2.0):
    _, aux_data = sparse_diff(ind1, data1, ind2, data2)
    result = 0.0
    for i in range(aux_data.shape[0]):
        result += np.abs(aux_data[i]) ** p
    return result ** (1.0 / p)


@numba.njit()
def sparse_hamming(ind1, data1, ind2, data2, n_features):
    num_not_equal = sparse_diff(ind1, data1, ind2, data2)[0].shape[0]
    return float(num_not_equal) / n_features


@numba.njit()
def sparse_canberra(ind1, data1, ind2, data2):
    abs_data1 = np.abs(data1)
    abs_data2 = np.abs(data2)
    denom_inds, denom_data = sparse_sum(ind1, abs_data1, ind2, abs_data2)
    denom_data = (1.0 / denom_data).astype(np.float32)
    numer_inds, numer_data = sparse_diff(ind1, data1, ind2, data2)
    numer_data = np.abs(numer_data)

    _, val_data = sparse_mul(numer_inds, numer_data, denom_inds, denom_data)
    result = 0.0
    for val in val_data:
        result += val

    return result


@numba.njit(
    [
        "f4(i4[::1],f4[::1],i4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
)
def sparse_bray_curtis(ind1, data1, ind2, data2):  # pragma: no cover
    _, denom_data = sparse_sum(ind1, data1, ind2, data2)
    denom_data = np.abs(denom_data)

    if denom_data.shape[0] == 0:
        return 0.0

    denominator = np.sum(denom_data)

    if denominator == 0.0:
        return 0.0

    _, numer_data = sparse_diff(ind1, data1, ind2, data2)
    numer_data = np.abs(numer_data)

    numerator = np.sum(numer_data)

    return float(numerator) / denominator


@numba.njit()
def sparse_jaccard(ind1, data1, ind2, data2):
    num_equal = fast_intersection_size(ind1, ind2)
    num_non_zero = ind1.shape[0] + ind2.shape[0] - num_equal

    if num_non_zero == 0:
        return 0.0
    else:
        return float(num_non_zero - num_equal) / num_non_zero


@numba.njit(
    [
        "f4(i4[::1],f4[::1],i4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.int32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={"num_non_zero": numba.types.intp, "num_equal": numba.types.intp},
)
def sparse_alternative_jaccard(ind1, data1, ind2, data2):
    num_equal = fast_intersection_size(ind1, ind2)
    num_non_zero = ind1.shape[0] + ind2.shape[0] - num_equal

    if num_non_zero == 0:
        return 0.0
    elif num_equal == 0:
        return FLOAT32_MAX
    else:
        return -np.log2(num_equal / num_non_zero)
        # return (num_non_zero - num_equal) / num_equal


@numba.vectorize(fastmath=True)
def correct_alternative_jaccard(v):
    return 1.0 - pow(2.0, -v)
    # return v / (v + 1)


@numba.njit()
def sparse_matching(ind1, data1, ind2, data2, n_features):
    num_true_true = fast_intersection_size(ind1, ind2)
    num_non_zero = ind1.shape[0] + ind2.shape[0] - num_true_true
    num_not_equal = num_non_zero - num_true_true

    return float(num_not_equal) / n_features


@numba.njit()
def sparse_dice(ind1, data1, ind2, data2):
    num_true_true = fast_intersection_size(ind1, ind2)
    num_non_zero = ind1.shape[0] + ind2.shape[0] - num_true_true
    num_not_equal = num_non_zero - num_true_true

    if num_not_equal == 0.0:
        return 0.0
    else:
        return num_not_equal / (2.0 * num_true_true + num_not_equal)


@numba.njit()
def sparse_kulsinski(ind1, data1, ind2, data2, n_features):
    num_true_true = fast_intersection_size(ind1, ind2)
    num_non_zero = ind1.shape[0] + ind2.shape[0] - num_true_true
    num_not_equal = num_non_zero - num_true_true

    if num_not_equal == 0:
        return 0.0
    else:
        return float(num_not_equal - num_true_true + n_features) / (
            num_not_equal + n_features
        )


@numba.njit()
def sparse_rogers_tanimoto(ind1, data1, ind2, data2, n_features):
    num_true_true = fast_intersection_size(ind1, ind2)
    num_non_zero = ind1.shape[0] + ind2.shape[0] - num_true_true
    num_not_equal = num_non_zero - num_true_true

    return (2.0 * num_not_equal) / (n_features + num_not_equal)


@numba.njit()
def sparse_russellrao(ind1, data1, ind2, data2, n_features):
    if ind1.shape[0] == ind2.shape[0] and np.all(ind1 == ind2):
        return 0.0

    num_true_true = fast_intersection_size(ind1, ind2)

    if num_true_true == np.sum(data1 != 0) and num_true_true == np.sum(data2 != 0):
        return 0.0
    else:
        return float(n_features - num_true_true) / (n_features)


@numba.njit()
def sparse_sokal_michener(ind1, data1, ind2, data2, n_features):
    num_true_true = fast_intersection_size(ind1, ind2)
    num_non_zero = ind1.shape[0] + ind2.shape[0] - num_true_true
    num_not_equal = num_non_zero - num_true_true

    return (2.0 * num_not_equal) / (n_features + num_not_equal)


@numba.njit()
def sparse_sokal_sneath(ind1, data1, ind2, data2):
    num_true_true = fast_intersection_size(ind1, ind2)
    num_non_zero = ind1.shape[0] + ind2.shape[0] - num_true_true
    num_not_equal = num_non_zero - num_true_true

    if num_not_equal == 0.0:
        return 0.0
    else:
        return num_not_equal / (0.5 * num_true_true + num_not_equal)


@numba.njit()
def sparse_cosine(ind1, data1, ind2, data2):
    _, aux_data = sparse_mul(ind1, data1, ind2, data2)
    result = 0.0
    norm1 = norm(data1)
    norm2 = norm(data2)

    for val in aux_data:
        result += val

    if norm1 == 0.0 and norm2 == 0.0:
        return 0.0
    elif norm1 == 0.0 or norm2 == 0.0:
        return 1.0
    else:
        return 1.0 - (result / (norm1 * norm2))


@numba.njit(
    #    "f4(i4[::1],f4[::1],i4[::1],f4[::1])",
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "norm_x": numba.types.float32,
        "norm_y": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def sparse_alternative_cosine(ind1, data1, ind2, data2):
    _, aux_data = sparse_mul(ind1, data1, ind2, data2)
    result = 0.0
    norm_x = norm(data1)
    norm_y = norm(data2)
    dim = len(aux_data)
    for i in range(dim):
        result += aux_data[i]
    if norm_x == 0.0 and norm_y == 0.0:
        return 0.0
    elif norm_x == 0.0 or norm_y == 0.0:
        return FLOAT32_MAX
    elif result <= 0.0:
        return FLOAT32_MAX
    else:
        result = (norm_x * norm_y) / result
        return np.log2(result)


@numba.vectorize(fastmath=True, cache=True)
def sparse_correct_alternative_cosine(d):
    if isclose(0.0, abs(d), atol=1e-7) or d < 0.0:
        return 0.0
    else:
        return 1.0 - pow(2.0, -d)


@numba.njit()
def sparse_dot(ind1, data1, ind2, data2):
    result = sparse_dot_product(ind1, data1, ind2, data2)

    return 1.0 - result


@numba.njit(
    #    "f4(i4[::1],f4[::1],i4[::1],f4[::1])",
    fastmath=True,
    locals={
        "result": numba.types.float32,
    },
)
def sparse_alternative_dot(ind1, data1, ind2, data2):
    result = sparse_dot_product(ind1, data1, ind2, data2)

    if result <= 0.0:
        return FLOAT32_MAX
    else:
        return -np.log2(result)


@numba.njit()
def sparse_correlation(ind1, data1, ind2, data2, n_features):

    mu_x = 0.0
    mu_y = 0.0
    dot_product = 0.0

    if ind1.shape[0] == 0 and ind2.shape[0] == 0:
        return 0.0
    elif ind1.shape[0] == 0 or ind2.shape[0] == 0:
        return 1.0

    for i in range(data1.shape[0]):
        mu_x += data1[i]
    for i in range(data2.shape[0]):
        mu_y += data2[i]

    mu_x /= n_features
    mu_y /= n_features

    shifted_data1 = np.empty(data1.shape[0], dtype=np.float32)
    shifted_data2 = np.empty(data2.shape[0], dtype=np.float32)

    for i in range(data1.shape[0]):
        shifted_data1[i] = data1[i] - mu_x
    for i in range(data2.shape[0]):
        shifted_data2[i] = data2[i] - mu_y

    norm1 = np.sqrt(
        (norm(shifted_data1) ** 2) + (n_features - ind1.shape[0]) * (mu_x**2)
    )
    norm2 = np.sqrt(
        (norm(shifted_data2) ** 2) + (n_features - ind2.shape[0]) * (mu_y**2)
    )

    dot_prod_inds, dot_prod_data = sparse_mul(ind1, shifted_data1, ind2, shifted_data2)

    common_indices = set(dot_prod_inds)

    for val in dot_prod_data:
        dot_product += val

    for i in range(ind1.shape[0]):
        if ind1[i] not in common_indices:
            dot_product -= shifted_data1[i] * (mu_y)

    for i in range(ind2.shape[0]):
        if ind2[i] not in common_indices:
            dot_product -= shifted_data2[i] * (mu_x)

    all_indices = arr_union(ind1, ind2)
    dot_product += mu_x * mu_y * (n_features - all_indices.shape[0])

    if norm1 == 0.0 and norm2 == 0.0:
        return 0.0
    elif dot_product == 0.0:
        return 1.0
    else:
        return 1.0 - (dot_product / (norm1 * norm2))


@numba.njit()
def sparse_hellinger(ind1, data1, ind2, data2):
    aux_inds, aux_data = sparse_mul(ind1, data1, ind2, data2)
    result = 0.0
    norm1 = np.sum(data1)
    norm2 = np.sum(data2)
    sqrt_norm_prod = np.sqrt(norm1 * norm2)

    for val in aux_data:
        result += np.sqrt(val)

    if norm1 == 0.0 and norm2 == 0.0:
        return 0.0
    elif norm1 == 0.0 or norm2 == 0.0:
        return 1.0
    elif result > sqrt_norm_prod:
        return 0.0
    else:
        return np.sqrt(1.0 - (result / sqrt_norm_prod))


@numba.njit(
    #   "f4(i4[::1],f4[::1],i4[::1],f4[::1])",
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "l1_norm_x": numba.types.float32,
        "l1_norm_y": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def sparse_alternative_hellinger(ind1, data1, ind2, data2):
    aux_inds, aux_data = sparse_mul(ind1, data1, ind2, data2)
    result = 0.0
    l1_norm_x = np.sum(data1)
    l1_norm_y = np.sum(data2)
    dim = len(aux_data)

    for i in range(dim):
        result += np.sqrt(aux_data[i])

    if l1_norm_x == 0 and l1_norm_y == 0:
        return 0.0
    elif l1_norm_x == 0 or l1_norm_y == 0:
        return FLOAT32_MAX
    elif result <= 0:
        return FLOAT32_MAX
    else:
        result = np.sqrt(l1_norm_x * l1_norm_y) / result
        return np.log2(result)


@numba.vectorize(fastmath=True, cache=True)
def sparse_correct_alternative_hellinger(d):
    if isclose(0.0, abs(d), atol=1e-7) or d < 0.0:
        return 0.0
    else:
        return np.sqrt(1.0 - pow(2.0, -d))


@numba.njit()
def dummy_ground_metric(x, y):
    return np.float32(not x == y)


def create_ground_metric(ground_vectors, metric):
    """Generate a "ground_metric" suitable for passing to a ``sparse_kantorovich``
    distance function. This should be a metric that, given indices of the data,
    should produce the ground distance between the corresponding vectors. This
    allows the construction of a cost_matrix or ground_distance_matrix between
    sparse samples on the fly -- without having to compute an all pairs distance.
    This is particularly useful for things like word-mover-distance.

    For example, to create a suitable ground_metric for word-mover distance one
    would use:

    ``wmd_ground_metric = create_ground_metric(word_vectors, cosine)``

    Parameters
    ----------
    ground_vectors: array of shape (n_features, d)
        The set of vectors between which ground_distances are measured. That is,
        there should be a vector for each feature of the space one wishes to compute
        Kantorovich distance over.

    metric: callable (numba jitted)
        The underlying metric used to cpmpute distances between feature vectors.

    Returns
    -------
    ground_metric: callable (numba jitted)
        A ground metric suitable for passing to ``sparse_kantorovich``.
    """

    @numba.njit()
    def ground_metric(index1, index2):
        return metric(ground_vectors[index1], ground_vectors[index2])

    return ground_metric


@numba.njit()
def sparse_kantorovich(ind1, data1, ind2, data2, ground_metric=dummy_ground_metric):

    cost_matrix = np.empty((ind1.shape[0], ind2.shape[0]))
    for i in range(ind1.shape[0]):
        for j in range(ind2.shape[0]):
            cost_matrix[i, j] = ground_metric(ind1[i], ind2[j])

    return kantorovich(data1, data2, cost_matrix)


@numba.njit()
def sparse_wasserstein_1d(ind1, data1, ind2, data2, p=1):
    result = 0.0
    old_ind = 0
    delta = 0.0
    i1 = 0
    i2 = 0
    cdf1 = 0.0
    cdf2 = 0.0
    l1_norm_x = np.sum(data1)
    l1_norm_y = np.sum(data2)

    norm = lambda x, p: np.power(np.abs(x), p)

    # pass through both index lists
    while i1 < ind1.shape[0] and i2 < ind2.shape[0]:
        j1 = ind1[i1]
        j2 = ind2[i2]

        if j1 == j2:
            result += delta * (j1 - old_ind)
            cdf1 += data1[i1] / l1_norm_x
            cdf2 += data2[i2] / l1_norm_y
            delta = norm(cdf1 - cdf2, p)
            old_ind = j1
            i1 += 1
            i2 += 1
        elif j1 < j2:
            result += delta * (j1 - old_ind)
            cdf1 += data1[i1] / l1_norm_x
            delta = norm(cdf1 - cdf2, p)
            old_ind = j1
            i1 += 1
        else:
            result += delta * (j2 - old_ind)
            cdf2 += data2[i2] / l1_norm_y
            delta = norm(cdf1 - cdf2, p)
            old_ind = j2
            i2 += 1
            # pass over the tails
    while i1 < ind1.shape[0]:
        j1 = ind1[i1]
        result += delta * (j1 - old_ind)
        cdf1 += data1[i1] / l1_norm_x
        delta = norm(cdf1 - cdf2, p)
        old_ind = j1
        i1 += 1

    while i2 < ind2.shape[0]:
        j2 = ind2[i2]
        result += delta * (j2 - old_ind)
        cdf2 += data2[i2] / l1_norm_y
        delta = norm(cdf1 - cdf2, p)
        old_ind = j2
        i2 += 1

    return np.power(result, 1.0 / p)


# Because of the EPS values and the need to normalize after adding them (and then average those for jensen_shannon)
# it seems like we might as well just take the dense union (dense vectors supported on the union of indices)
# and call the dense distance functions


@numba.njit()
def sparse_jensen_shannon_divergence(ind1, data1, ind2, data2):
    dense_data1, dense_data2 = dense_union(ind1, data1, ind2, data2)
    return jensen_shannon_divergence(dense_data1, dense_data2)


@numba.njit()
def sparse_symmetric_kl_divergence(ind1, data1, ind2, data2):
    dense_data1, dense_data2 = dense_union(ind1, data1, ind2, data2)
    return symmetric_kl_divergence(dense_data1, dense_data2)


@numba.njit(parallel=True, cache=False)
def diversify(
    indices,
    distances,
    data_indices,
    data_indptr,
    data_data,
    dist,
    rng_state,
    prune_probability=1.0,
):

    for i in numba.prange(indices.shape[0]):

        new_indices = [indices[i, 0]]
        new_distances = [distances[i, 0]]
        for j in range(1, indices.shape[1]):
            if indices[i, j] < 0:
                break

            flag = True
            for k in range(len(new_indices)):
                c = new_indices[k]

                from_ind = data_indices[
                    data_indptr[indices[i, j]] : data_indptr[indices[i, j] + 1]
                ]
                from_data = data_data[
                    data_indptr[indices[i, j]] : data_indptr[indices[i, j] + 1]
                ]

                to_ind = data_indices[data_indptr[c] : data_indptr[c + 1]]
                to_data = data_data[data_indptr[c] : data_indptr[c + 1]]

                d = dist(from_ind, from_data, to_ind, to_data)
                if new_distances[k] > FLOAT32_EPS and d < distances[i, j]:
                    if tau_rand(rng_state) < prune_probability:
                        flag = False
                        break

            if flag:
                new_indices.append(indices[i, j])
                new_distances.append(distances[i, j])

        for j in range(indices.shape[1]):
            if j < len(new_indices):
                indices[i, j] = new_indices[j]
                distances[i, j] = new_distances[j]
            else:
                indices[i, j] = -1
                distances[i, j] = np.inf

    return indices, distances


@numba.njit(parallel=True, cache=False)
def diversify_csr(
    graph_indptr,
    graph_indices,
    graph_data,
    data_indptr,
    data_indices,
    data_data,
    dist,
    rng_state,
    prune_probability=1.0,
):

    n_nodes = graph_indptr.shape[0] - 1

    for i in numba.prange(n_nodes):

        current_indices = graph_indices[graph_indptr[i] : graph_indptr[i + 1]]
        current_data = graph_data[graph_indptr[i] : graph_indptr[i + 1]]

        order = np.argsort(current_data)
        retained = np.ones(order.shape[0], dtype=np.int8)

        for idx in range(1, order.shape[0]):

            j = order[idx]

            for k in range(idx):

                l = order[k]

                if retained[l] == 1:
                    p = current_indices[j]
                    q = current_indices[l]

                    from_inds = data_indices[data_indptr[p] : data_indptr[p + 1]]
                    from_data = data_data[data_indptr[p] : data_indptr[p + 1]]

                    to_inds = data_indices[data_indptr[q] : data_indptr[q + 1]]
                    to_data = data_data[data_indptr[q] : data_indptr[q + 1]]
                    d = dist(from_inds, from_data, to_inds, to_data)

                    if current_data[l] > FLOAT32_EPS and d < current_data[j]:
                        if tau_rand(rng_state) < prune_probability:
                            retained[j] = 0
                            break

        for idx in range(order.shape[0]):
            j = order[idx]
            if retained[j] == 0:
                graph_data[graph_indptr[i] + j] = 0

    return


sparse_named_distances = {
    # general minkowski distances
    "euclidean": sparse_euclidean,
    "l2": sparse_euclidean,
    "sqeuclidean": sparse_squared_euclidean,
    "manhattan": sparse_manhattan,
    "l1": sparse_manhattan,
    "taxicab": sparse_manhattan,
    "chebyshev": sparse_chebyshev,
    "linf": sparse_chebyshev,
    "linfty": sparse_chebyshev,
    "linfinity": sparse_chebyshev,
    "minkowski": sparse_minkowski,
    # Other distances
    "canberra": sparse_canberra,
    "braycurtis": sparse_bray_curtis,
    # Binary distances
    "hamming": sparse_hamming,
    "jaccard": sparse_jaccard,
    "dice": sparse_dice,
    "matching": sparse_matching,
    "kulsinski": sparse_kulsinski,
    "rogerstanimoto": sparse_rogers_tanimoto,
    "russellrao": sparse_russellrao,
    "sokalmichener": sparse_sokal_michener,
    "sokalsneath": sparse_sokal_sneath,
    # Angular distances
    "cosine": sparse_cosine,
    "correlation": sparse_correlation,
    # Distribution distances
    "kantorovich": sparse_kantorovich,
    "wasserstein": sparse_kantorovich,
    "wasserstein_1d": sparse_wasserstein_1d,
    "wasserstein-1d": sparse_wasserstein_1d,
    "kantorovich-1d": sparse_wasserstein_1d,
    "kantorovich-1d": sparse_wasserstein_1d,
    "hellinger": sparse_hellinger,
    "jensen-shannon": sparse_jensen_shannon_divergence,
    "jensen_shannon": sparse_jensen_shannon_divergence,
    "symmetric-kl": sparse_symmetric_kl_divergence,
    "symmetric_kl": sparse_symmetric_kl_divergence,
    "symmetric_kullback_liebler": sparse_symmetric_kl_divergence,
}

sparse_need_n_features = (
    "hamming",
    "matching",
    "kulsinski",
    "rogerstanimoto",
    "russellrao",
    "sokalmichener",
    "correlation",
)


# Some distances have a faster to compute alternative that
# retains the same ordering of distances. We can compute with
# this instead, and then correct the final distances when complete.
# This provides a list of distances that have such an alternative
# along with the alternative distance function and the correction
# function to be applied.
sparse_fast_distance_alternatives = {
    "euclidean": {"dist": sparse_squared_euclidean, "correction": np.sqrt},
    "l2": {"dist": sparse_squared_euclidean, "correction": np.sqrt},
    "cosine": {
        "dist": sparse_alternative_cosine,
        "correction": sparse_correct_alternative_cosine,
    },
    "dot": {
        "dist": sparse_alternative_dot,
        "correction": sparse_correct_alternative_cosine,
    },
    "hellinger": {
        "dist": sparse_alternative_hellinger,
        "correction": sparse_correct_alternative_hellinger,
    },
    "jaccard": {
        "dist": sparse_alternative_jaccard,
        "correction": correct_alternative_jaccard,
    },
}
