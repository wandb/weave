# Author: Leland McInnes <leland.mcinnes@gmail.com>
# Enough simple sparse operations in numba to enable sparse UMAP
#
# License: BSD 3 clause
from __future__ import print_function
import locale
import numpy as np
import numba

from pynndescent.utils import (
    tau_rand_int,
    make_heap,
    new_build_candidates,
    deheap_sort,
    checked_flagged_heap_push,
    apply_graph_updates_high_memory,
    apply_graph_updates_low_memory,
)

from pynndescent.sparse import sparse_euclidean

locale.setlocale(locale.LC_NUMERIC, "C")

EMPTY_GRAPH = make_heap(1, 1)


@numba.njit(parallel=True, cache=False)
def generate_leaf_updates(leaf_block, dist_thresholds, inds, indptr, data, dist):

    updates = [[(-1, -1, np.inf)] for i in range(leaf_block.shape[0])]

    for n in numba.prange(leaf_block.shape[0]):
        for i in range(leaf_block.shape[1]):
            p = leaf_block[n, i]
            if p < 0:
                break

            for j in range(i + 1, leaf_block.shape[1]):
                q = leaf_block[n, j]
                if q < 0:
                    break

                from_inds = inds[indptr[p] : indptr[p + 1]]
                from_data = data[indptr[p] : indptr[p + 1]]

                to_inds = inds[indptr[q] : indptr[q + 1]]
                to_data = data[indptr[q] : indptr[q + 1]]
                d = dist(from_inds, from_data, to_inds, to_data)

                if d < dist_thresholds[p] or d < dist_thresholds[q]:
                    updates[n].append((p, q, d))

    return updates


@numba.njit(locals={"d": numba.float32, "p": numba.int32, "q": numba.int32}, cache=False)
def init_rp_tree(inds, indptr, data, dist, current_graph, leaf_array):

    n_leaves = leaf_array.shape[0]
    block_size = 65536
    n_blocks = n_leaves // block_size

    for i in range(n_blocks + 1):
        block_start = i * block_size
        block_end = min(n_leaves, (i + 1) * block_size)

        leaf_block = leaf_array[block_start:block_end]
        dist_thresholds = current_graph[1][:, 0]

        updates = generate_leaf_updates(
            leaf_block, dist_thresholds, inds, indptr, data, dist
        )

        for j in range(len(updates)):
            for k in range(len(updates[j])):
                p, q, d = updates[j][k]

                if p == -1 or q == -1:
                    continue

                checked_flagged_heap_push(
                    current_graph[1][p],
                    current_graph[0][p],
                    current_graph[2][p],
                    d,
                    q,
                    np.uint8(1),
                )
                checked_flagged_heap_push(
                    current_graph[1][q],
                    current_graph[0][q],
                    current_graph[2][q],
                    d,
                    p,
                    np.uint8(1),
                )


@numba.njit(
    fastmath=True,
    locals={"d": numba.float32, "i": numba.int32, "idx": numba.int32},
    cache=False,
)
def init_random(n_neighbors, inds, indptr, data, heap, dist, rng_state):
    n_samples = indptr.shape[0] - 1
    for i in range(n_samples):
        if heap[0][i, 0] < 0.0:
            for j in range(n_neighbors - np.sum(heap[0][i] >= 0.0)):
                idx = np.abs(tau_rand_int(rng_state)) % n_samples

                from_inds = inds[indptr[idx] : indptr[idx + 1]]
                from_data = data[indptr[idx] : indptr[idx + 1]]

                to_inds = inds[indptr[i] : indptr[i + 1]]
                to_data = data[indptr[i] : indptr[i + 1]]
                d = dist(from_inds, from_data, to_inds, to_data)

                checked_flagged_heap_push(
                    heap[1][i], heap[0][i], heap[2][i], d, idx, np.uint8(1)
                )

    return


@numba.njit(parallel=True, cache=False)
def generate_graph_updates(
    new_candidate_block, old_candidate_block, dist_thresholds, inds, indptr, data, dist
):

    block_size = new_candidate_block.shape[0]
    updates = [[(-1, -1, np.inf)] for i in range(block_size)]
    max_candidates = new_candidate_block.shape[1]

    for i in numba.prange(block_size):
        for j in range(max_candidates):
            p = int(new_candidate_block[i, j])
            if p < 0:
                continue
            for k in range(j, max_candidates):
                q = int(new_candidate_block[i, k])
                if q < 0:
                    continue

                from_inds = inds[indptr[p] : indptr[p + 1]]
                from_data = data[indptr[p] : indptr[p + 1]]

                to_inds = inds[indptr[q] : indptr[q + 1]]
                to_data = data[indptr[q] : indptr[q + 1]]
                d = dist(from_inds, from_data, to_inds, to_data)

                if d <= dist_thresholds[p] or d <= dist_thresholds[q]:
                    updates[i].append((p, q, d))

            for k in range(max_candidates):
                q = int(old_candidate_block[i, k])
                if q < 0:
                    continue

                from_inds = inds[indptr[p] : indptr[p + 1]]
                from_data = data[indptr[p] : indptr[p + 1]]

                to_inds = inds[indptr[q] : indptr[q + 1]]
                to_data = data[indptr[q] : indptr[q + 1]]
                d = dist(from_inds, from_data, to_inds, to_data)

                if d <= dist_thresholds[p] or d <= dist_thresholds[q]:
                    updates[i].append((p, q, d))

    return updates


@numba.njit()
def nn_descent_internal_low_memory_parallel(
    current_graph,
    inds,
    indptr,
    data,
    n_neighbors,
    rng_state,
    max_candidates=50,
    dist=sparse_euclidean,
    n_iters=10,
    delta=0.001,
    verbose=False,
):
    n_vertices = indptr.shape[0] - 1
    block_size = 16384
    n_blocks = n_vertices // block_size
    n_threads = numba.get_num_threads()

    for n in range(n_iters):
        if verbose:
            print("\t", n + 1, " / ", n_iters)

        (new_candidate_neighbors, old_candidate_neighbors) = new_build_candidates(
            current_graph, max_candidates, rng_state, n_threads
        )

        c = 0
        for i in range(n_blocks + 1):
            block_start = i * block_size
            block_end = min(n_vertices, (i + 1) * block_size)

            new_candidate_block = new_candidate_neighbors[block_start:block_end]
            old_candidate_block = old_candidate_neighbors[block_start:block_end]
            dist_thresholds = current_graph[1][:, 0]

            updates = generate_graph_updates(
                new_candidate_block,
                old_candidate_block,
                dist_thresholds,
                inds,
                indptr,
                data,
                dist,
            )

            c += apply_graph_updates_low_memory(current_graph, updates, n_threads)

        if c <= delta * n_neighbors * n_vertices:
            if verbose:
                print("\tStopping threshold met -- exiting after", n + 1, "iterations")
            return


@numba.njit()
def nn_descent_internal_high_memory_parallel(
    current_graph,
    inds,
    indptr,
    data,
    n_neighbors,
    rng_state,
    max_candidates=50,
    dist=sparse_euclidean,
    n_iters=10,
    delta=0.001,
    verbose=False,
):
    n_vertices = indptr.shape[0] - 1
    block_size = 16384
    n_blocks = n_vertices // block_size
    n_threads = numba.get_num_threads()

    in_graph = [
        set(current_graph[0][i].astype(np.int64))
        for i in range(current_graph[0].shape[0])
    ]

    for n in range(n_iters):
        if verbose:
            print("\t", n + 1, " / ", n_iters)

        (new_candidate_neighbors, old_candidate_neighbors) = new_build_candidates(
            current_graph, max_candidates, rng_state, n_threads
        )

        c = 0
        for i in range(n_blocks + 1):
            block_start = i * block_size
            block_end = min(n_vertices, (i + 1) * block_size)

            new_candidate_block = new_candidate_neighbors[block_start:block_end]
            old_candidate_block = old_candidate_neighbors[block_start:block_end]
            dist_thresholds = current_graph[1][:, 0]

            updates = generate_graph_updates(
                new_candidate_block,
                old_candidate_block,
                dist_thresholds,
                inds,
                indptr,
                data,
                dist,
            )

            c += apply_graph_updates_high_memory(current_graph, updates, in_graph)

        if c <= delta * n_neighbors * n_vertices:
            if verbose:
                print("\tStopping threshold met -- exiting after", n + 1, "iterations")
            return


@numba.njit()
def nn_descent(
    inds,
    indptr,
    data,
    n_neighbors,
    rng_state,
    max_candidates=50,
    dist=sparse_euclidean,
    n_iters=10,
    delta=0.001,
    init_graph=EMPTY_GRAPH,
    rp_tree_init=True,
    leaf_array=None,
    low_memory=False,
    verbose=False,
):

    n_samples = indptr.shape[0] - 1

    if init_graph[0].shape[0] == 1:  # EMPTY_GRAPH
        current_graph = make_heap(n_samples, n_neighbors)

        if rp_tree_init:
            init_rp_tree(inds, indptr, data, dist, current_graph, leaf_array)

        init_random(n_neighbors, inds, indptr, data, current_graph, dist, rng_state)
    elif init_graph[0].shape[0] == n_samples and init_graph[0].shape[1] == n_neighbors:
        current_graph = init_graph
    else:
        raise ValueError("Invalid initial graph specified!")

    if low_memory:
        nn_descent_internal_low_memory_parallel(
            current_graph,
            inds,
            indptr,
            data,
            n_neighbors,
            rng_state,
            max_candidates=max_candidates,
            dist=dist,
            n_iters=n_iters,
            delta=delta,
            verbose=verbose,
        )
    else:
        nn_descent_internal_high_memory_parallel(
            current_graph,
            inds,
            indptr,
            data,
            n_neighbors,
            rng_state,
            max_candidates=max_candidates,
            dist=dist,
            n_iters=n_iters,
            delta=delta,
            verbose=verbose,
        )

    return deheap_sort(current_graph[0], current_graph[1])
