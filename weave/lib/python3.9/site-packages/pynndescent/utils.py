# Author: Leland McInnes <leland.mcinnes@gmail.com>
#
# License: BSD 2 clause

import time

import numba
from numba.core import types
import numba.experimental.structref as structref
import numpy as np


@numba.njit("void(i8[:], i8)", cache=True)
def seed(rng_state, seed):
    """Seed the random number generator with a given seed."""
    rng_state.fill(seed + 0xFFFF)


@numba.njit("i4(i8[:])", cache=True)
def tau_rand_int(state):
    """A fast (pseudo)-random number generator.

    Parameters
    ----------
    state: array of int64, shape (3,)
        The internal state of the rng

    Returns
    -------
    A (pseudo)-random int32 value
    """
    state[0] = (((state[0] & 4294967294) << 12) & 0xFFFFFFFF) ^ (
        (((state[0] << 13) & 0xFFFFFFFF) ^ state[0]) >> 19
    )
    state[1] = (((state[1] & 4294967288) << 4) & 0xFFFFFFFF) ^ (
        (((state[1] << 2) & 0xFFFFFFFF) ^ state[1]) >> 25
    )
    state[2] = (((state[2] & 4294967280) << 17) & 0xFFFFFFFF) ^ (
        (((state[2] << 3) & 0xFFFFFFFF) ^ state[2]) >> 11
    )

    return state[0] ^ state[1] ^ state[2]


@numba.njit("f4(i8[:])", cache=True)
def tau_rand(state):
    """A fast (pseudo)-random number generator for floats in the range [0,1]

    Parameters
    ----------
    state: array of int64, shape (3,)
        The internal state of the rng

    Returns
    -------
    A (pseudo)-random float32 in the interval [0, 1]
    """
    integer = tau_rand_int(state)
    return abs(float(integer) / 0x7FFFFFFF)


@numba.njit(
    [
        "f4(f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.float32, 1, "C", readonly=True)
        ),
    ],
    locals={
        "dim": numba.types.intp,
        "i": numba.types.uint32,
        # "result": numba.types.float32, # This provides speed, but causes errors in corner cases
    },
    fastmath=True,
    cache=True,
)
def norm(vec):
    """Compute the (standard l2) norm of a vector.

    Parameters
    ----------
    vec: array of shape (dim,)

    Returns
    -------
    The l2 norm of vec.
    """
    result = 0.0
    dim = vec.shape[0]
    for i in range(dim):
        result += vec[i] * vec[i]
    return np.sqrt(result)


@numba.njit(cache=True)
def rejection_sample(n_samples, pool_size, rng_state):
    """Generate n_samples many integers from 0 to pool_size such that no
    integer is selected twice. The duplication constraint is achieved via
    rejection sampling.

    Parameters
    ----------
    n_samples: int
        The number of random samples to select from the pool

    pool_size: int
        The size of the total pool of candidates to sample from

    rng_state: array of int64, shape (3,)
        Internal state of the random number generator

    Returns
    -------
    sample: array of shape(n_samples,)
        The ``n_samples`` randomly selected elements from the pool.
    """
    result = np.empty(n_samples, dtype=np.int64)
    for i in range(n_samples):
        reject_sample = True
        j = 0
        while reject_sample:
            j = tau_rand_int(rng_state) % pool_size
            for k in range(i):
                if j == result[k]:
                    break
            else:
                reject_sample = False
        result[i] = j
    return result


@structref.register
class HeapType(types.StructRef):
    pass


class Heap(structref.StructRefProxy):
    @property
    def indices(self):
        return Heap_get_indices(self)

    @property
    def distances(self):
        return Heap_get_distances(self)

    @property
    def flags(self):
        return Heap_get_flags(self)


@numba.njit(cache=True)
def Heap_get_flags(self):
    return self.flags


@numba.njit(cache=True)
def Heap_get_distances(self):
    return self.distances


@numba.njit(cache=True)
def Heap_get_indices(self):
    return self.indices


structref.define_proxy(Heap, HeapType, ["indices", "distances", "flags"])

# Heap = namedtuple("Heap", ("indices", "distances", "flags"))


@numba.njit(cache=True)
def make_heap(n_points, size):
    """Constructor for the numba enabled heap objects. The heaps are used
    for approximate nearest neighbor search, maintaining a list of potential
    neighbors sorted by their distance. We also flag if potential neighbors
    are newly added to the list or not. Internally this is stored as
    a single ndarray; the first axis determines whether we are looking at the
    array of candidate graph_indices, the array of distances, or the flag array for
    whether elements are new or not. Each of these arrays are of shape
    (``n_points``, ``size``)

    Parameters
    ----------
    n_points: int
        The number of graph_data points to track in the heap.

    size: int
        The number of items to keep on the heap for each graph_data point.

    Returns
    -------
    heap: An ndarray suitable for passing to other numba enabled heap functions.
    """
    indices = np.full((int(n_points), int(size)), -1, dtype=np.int32)
    distances = np.full((int(n_points), int(size)), np.inf, dtype=np.float32)
    flags = np.zeros((int(n_points), int(size)), dtype=np.uint8)
    result = (indices, distances, flags)

    return result


@numba.njit(cache=True)
def siftdown(heap1, heap2, elt):
    """Restore the heap property for a heap with an out of place element
    at position ``elt``. This works with a heap pair where heap1 carries
    the weights and heap2 holds the corresponding elements."""
    while elt * 2 + 1 < heap1.shape[0]:
        left_child = elt * 2 + 1
        right_child = left_child + 1
        swap = elt

        if heap1[swap] < heap1[left_child]:
            swap = left_child

        if right_child < heap1.shape[0] and heap1[swap] < heap1[right_child]:
            swap = right_child

        if swap == elt:
            break
        else:
            heap1[elt], heap1[swap] = heap1[swap], heap1[elt]
            heap2[elt], heap2[swap] = heap2[swap], heap2[elt]
            elt = swap


@numba.njit(parallel=True, cache=False)
def deheap_sort(indices, distances):
    """Given two arrays representing a heap (indices and distances), reorder the
     arrays by increasing distance. This is effectively just the second half of
     heap sort (the first half not being required since we already have the
     graph_data in a heap).

     Note that this is done in-place.

    Parameters
    ----------
    indices : array of shape (n_samples, n_neighbors)
        The graph indices to sort by distance.
    distances : array of shape (n_samples, n_neighbors)
        The corresponding edge distance.

    Returns
    -------
    indices, distances: arrays of shape (n_samples, n_neighbors)
        The indices and distances sorted by increasing distance.
    """
    for i in numba.prange(indices.shape[0]):
        # starting from the end of the array and moving back
        for j in range(indices.shape[1] - 1, 0, -1):
            indices[i, 0], indices[i, j] = indices[i, j], indices[i, 0]
            distances[i, 0], distances[i, j] = distances[i, j], distances[i, 0]

            siftdown(distances[i, :j], indices[i, :j], 0)

    return indices, distances


# @numba.njit()
# def smallest_flagged(heap, row):
#     """Search the heap for the smallest element that is
#     still flagged.
#
#     Parameters
#     ----------
#     heap: array of shape (3, n_samples, n_neighbors)
#         The heaps to search
#
#     row: int
#         Which of the heaps to search
#
#     Returns
#     -------
#     index: int
#         The index of the smallest flagged element
#         of the ``row``th heap, or -1 if no flagged
#         elements remain in the heap.
#     """
#     ind = heap[0][row]
#     dist = heap[1][row]
#     flag = heap[2][row]
#
#     min_dist = np.inf
#     result_index = -1
#
#     for i in range(ind.shape[0]):
#         if flag[i] == 1 and dist[i] < min_dist:
#             min_dist = dist[i]
#             result_index = i
#
#     if result_index >= 0:
#         flag[result_index] = 0.0
#         return int(ind[result_index])
#     else:
#         return -1


@numba.njit(parallel=True, locals={"idx": numba.types.int64}, cache=False)
def new_build_candidates(current_graph, max_candidates, rng_state, n_threads):
    """Build a heap of candidate neighbors for nearest neighbor descent. For
    each vertex the candidate neighbors are any current neighbors, and any
    vertices that have the vertex as one of their nearest neighbors.

    Parameters
    ----------
    current_graph: heap
        The current state of the graph for nearest neighbor descent.

    max_candidates: int
        The maximum number of new candidate neighbors.

    rng_state: array of int64, shape (3,)
        The internal state of the rng

    Returns
    -------
    candidate_neighbors: A heap with an array of (randomly sorted) candidate
    neighbors for each vertex in the graph.
    """
    current_indices = current_graph[0]
    current_flags = current_graph[2]

    n_vertices = current_indices.shape[0]
    n_neighbors = current_indices.shape[1]

    new_candidate_indices = np.full((n_vertices, max_candidates), -1, dtype=np.int32)
    new_candidate_priority = np.full(
        (n_vertices, max_candidates), np.inf, dtype=np.float32
    )

    old_candidate_indices = np.full((n_vertices, max_candidates), -1, dtype=np.int32)
    old_candidate_priority = np.full(
        (n_vertices, max_candidates), np.inf, dtype=np.float32
    )

    for n in numba.prange(n_threads):
        local_rng_state = rng_state + n
        for i in range(n_vertices):
            for j in range(n_neighbors):
                idx = current_indices[i, j]
                isn = current_flags[i, j]

                if idx < 0:
                    continue

                d = tau_rand(local_rng_state)

                if isn:
                    if i % n_threads == n:
                        checked_heap_push(
                            new_candidate_priority[i], new_candidate_indices[i], d, idx
                        )
                    if idx % n_threads == n:
                        checked_heap_push(
                            new_candidate_priority[idx],
                            new_candidate_indices[idx],
                            d,
                            i,
                        )
                else:
                    if i % n_threads == n:
                        checked_heap_push(
                            old_candidate_priority[i], old_candidate_indices[i], d, idx
                        )
                    if idx % n_threads == n:
                        checked_heap_push(
                            old_candidate_priority[idx],
                            old_candidate_indices[idx],
                            d,
                            i,
                        )

    indices = current_graph[0]
    flags = current_graph[2]

    for i in numba.prange(n_vertices):
        for j in range(n_neighbors):
            idx = indices[i, j]

            for k in range(max_candidates):
                if new_candidate_indices[i, k] == idx:
                    flags[i, j] = 0
                    break

    return new_candidate_indices, old_candidate_indices


@numba.njit("b1(u1[::1],i4)", cache=True)
def has_been_visited(table, candidate):
    loc = candidate >> 3
    mask = 1 << (candidate & 7)
    return table[loc] & mask


@numba.njit("void(u1[::1],i4)", cache=True)
def mark_visited(table, candidate):
    loc = candidate >> 3
    mask = 1 << (candidate & 7)
    table[loc] |= mask
    return


@numba.njit(
    "i4(f4[::1],i4[::1],f4,i4)",
    fastmath=True,
    locals={
        "size": numba.types.intp,
        "i": numba.types.uint16,
        "ic1": numba.types.uint16,
        "ic2": numba.types.uint16,
        "i_swap": numba.types.uint16,
    },
    cache=True,
)
def simple_heap_push(priorities, indices, p, n):
    if p >= priorities[0]:
        return 0

    size = priorities.shape[0]

    # insert val at position zero
    priorities[0] = p
    indices[0] = n

    # descend the heap, swapping values until the max heap criterion is met
    i = 0
    while True:
        ic1 = 2 * i + 1
        ic2 = ic1 + 1

        if ic1 >= size:
            break
        elif ic2 >= size:
            if priorities[ic1] > p:
                i_swap = ic1
            else:
                break
        elif priorities[ic1] >= priorities[ic2]:
            if p < priorities[ic1]:
                i_swap = ic1
            else:
                break
        else:
            if p < priorities[ic2]:
                i_swap = ic2
            else:
                break

        priorities[i] = priorities[i_swap]
        indices[i] = indices[i_swap]

        i = i_swap

    priorities[i] = p
    indices[i] = n

    return 1


@numba.njit(
    "i4(f4[::1],i4[::1],f4,i4)",
    fastmath=True,
    locals={
        "size": numba.types.intp,
        "i": numba.types.uint16,
        "ic1": numba.types.uint16,
        "ic2": numba.types.uint16,
        "i_swap": numba.types.uint16,
    },
    cache=True,
)
def checked_heap_push(priorities, indices, p, n):
    if p >= priorities[0]:
        return 0

    size = priorities.shape[0]

    # break if we already have this element.
    for i in range(size):
        if n == indices[i]:
            return 0

    # insert val at position zero
    priorities[0] = p
    indices[0] = n

    # descend the heap, swapping values until the max heap criterion is met
    i = 0
    while True:
        ic1 = 2 * i + 1
        ic2 = ic1 + 1

        if ic1 >= size:
            break
        elif ic2 >= size:
            if priorities[ic1] > p:
                i_swap = ic1
            else:
                break
        elif priorities[ic1] >= priorities[ic2]:
            if p < priorities[ic1]:
                i_swap = ic1
            else:
                break
        else:
            if p < priorities[ic2]:
                i_swap = ic2
            else:
                break

        priorities[i] = priorities[i_swap]
        indices[i] = indices[i_swap]

        i = i_swap

    priorities[i] = p
    indices[i] = n

    return 1


@numba.njit(
    "i4(f4[::1],i4[::1],u1[::1],f4,i4,u1)",
    fastmath=True,
    locals={
        "size": numba.types.intp,
        "i": numba.types.uint16,
        "ic1": numba.types.uint16,
        "ic2": numba.types.uint16,
        "i_swap": numba.types.uint16,
    },
    cache=True,
)
def checked_flagged_heap_push(priorities, indices, flags, p, n, f):
    if p >= priorities[0]:
        return 0

    size = priorities.shape[0]

    # break if we already have this element.
    for i in range(size):
        if n == indices[i]:
            return 0

    # insert val at position zero
    priorities[0] = p
    indices[0] = n
    flags[0] = f

    # descend the heap, swapping values until the max heap criterion is met
    i = 0
    while True:
        ic1 = 2 * i + 1
        ic2 = ic1 + 1

        if ic1 >= size:
            break
        elif ic2 >= size:
            if priorities[ic1] > p:
                i_swap = ic1
            else:
                break
        elif priorities[ic1] >= priorities[ic2]:
            if p < priorities[ic1]:
                i_swap = ic1
            else:
                break
        else:
            if p < priorities[ic2]:
                i_swap = ic2
            else:
                break

        priorities[i] = priorities[i_swap]
        indices[i] = indices[i_swap]
        flags[i] = flags[i_swap]

        i = i_swap

    priorities[i] = p
    indices[i] = n
    flags[i] = f

    return 1


@numba.njit(
    parallel=True,
    locals={
        "p": numba.int32,
        "q": numba.int32,
        "d": numba.float32,
        "added": numba.uint8,
        "n": numba.uint32,
        "i": numba.uint32,
        "j": numba.uint32,
    },
    cache=False,
)
def apply_graph_updates_low_memory(current_graph, updates, n_threads):

    n_changes = 0
    priorities = current_graph[1]
    indices = current_graph[0]
    flags = current_graph[2]
    # n_threads = numba.get_num_threads()

    for n in numba.prange(n_threads):
        for i in range(len(updates)):
            for j in range(len(updates[i])):
                p, q, d = updates[i][j]

                if p == -1 or q == -1:
                    continue

                if p % n_threads == n:
                    added = checked_flagged_heap_push(
                        priorities[p], indices[p], flags[p], d, q, 1
                    )
                    n_changes += added

                if q % n_threads == n:
                    added = checked_flagged_heap_push(
                        priorities[q], indices[q], flags[q], d, p, 1
                    )
                    n_changes += added

    return n_changes


@numba.njit(locals={"p": numba.types.int64, "q": numba.types.int64}, cache=True)
def apply_graph_updates_high_memory(current_graph, updates, in_graph):

    n_changes = 0

    for i in range(len(updates)):
        for j in range(len(updates[i])):
            p, q, d = updates[i][j]

            if p == -1 or q == -1:
                continue

            if q in in_graph[p] and p in in_graph[q]:
                continue
            elif q in in_graph[p]:
                pass
            else:
                added = checked_flagged_heap_push(
                    current_graph[1][p],
                    current_graph[0][p],
                    current_graph[2][p],
                    d,
                    q,
                    1,
                )

                if added > 0:
                    in_graph[p].add(q)
                    n_changes += added

            if p == q or p in in_graph[q]:
                pass
            else:
                added = checked_flagged_heap_push(
                    current_graph[1][p],
                    current_graph[0][p],
                    current_graph[2][p],
                    d,
                    q,
                    1,
                )

                if added > 0:
                    in_graph[q].add(p)
                    n_changes += added

    return n_changes


@numba.njit(cache=False)
def initalize_heap_from_graph_indices(heap, graph_indices, data, metric):

    for i in range(graph_indices.shape[0]):
        for idx in range(graph_indices.shape[1]):
            j = graph_indices[i, idx]
            if j >= 0:
                d = metric(data[i], data[j])
                checked_flagged_heap_push(heap[1][i], heap[0][i], heap[2][i], d, j, 1)

    return heap


@numba.njit(cache=True)
def initalize_heap_from_graph_indices_and_distances(
    heap, graph_indices, graph_distances
):
    for i in range(graph_indices.shape[0]):
        for idx in range(graph_indices.shape[1]):
            j = graph_indices[i, idx]
            if j >= 0:
                d = graph_distances[i, idx]
                checked_flagged_heap_push(heap[1][i], heap[0][i], heap[2][i], d, j, 1)

    return heap


@numba.njit(parallel=True, cache=False)
def sparse_initalize_heap_from_graph_indices(
    heap, graph_indices, data_indptr, data_indices, data_vals, metric
):

    for i in numba.prange(graph_indices.shape[0]):
        for idx in range(graph_indices.shape[1]):
            j = graph_indices[i, idx]
            ind1 = data_indices[data_indptr[i] : data_indptr[i + 1]]
            data1 = data_vals[data_indptr[i] : data_indptr[i + 1]]
            ind2 = data_indices[data_indptr[j] : data_indptr[j + 1]]
            data2 = data_vals[data_indptr[j] : data_indptr[j + 1]]
            d = metric(ind1, data1, ind2, data2)
            checked_flagged_heap_push(heap[1][i], heap[0][i], heap[2][i], d, j, 1)

    return heap


# Generates a timestamp for use in logging messages when verbose=True
def ts():
    return time.ctime(time.time())
