import numba
import numpy as np
import heapq

from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from itertools import combinations

import pynndescent.distances as pynnd_dist
import joblib

from pynndescent.utils import (
    rejection_sample,
    make_heap,
    deheap_sort,
    simple_heap_push,
    has_been_visited,
    mark_visited,
)

FLOAT32_EPS = np.finfo(np.float32).eps


def create_component_search(index):
    alternative_dot = pynnd_dist.alternative_dot
    alternative_cosine = pynnd_dist.alternative_cosine

    data = index._raw_data
    indptr = index._search_graph.indptr
    indices = index._search_graph.indices
    dist = index._distance_func

    @numba.njit(
        fastmath=True,
        nogil=True,
        locals={
            "current_query": numba.types.float32[::1],
            "i": numba.types.uint32,
            "j": numba.types.uint32,
            "heap_priorities": numba.types.float32[::1],
            "heap_indices": numba.types.int32[::1],
            "candidate": numba.types.int32,
            "vertex": numba.types.int32,
            "d": numba.types.float32,
            "d_vertex": numba.types.float32,
            "visited": numba.types.uint8[::1],
            "indices": numba.types.int32[::1],
            "indptr": numba.types.int32[::1],
            "data": numba.types.float32[:, ::1],
            "heap_size": numba.types.int16,
            "distance_scale": numba.types.float32,
            "distance_bound": numba.types.float32,
            "seed_scale": numba.types.float32,
        },
    )
    def custom_search_closure(query_points, candidate_indices, k, epsilon, visited):
        result = make_heap(query_points.shape[0], k)
        distance_scale = 1.0 + epsilon

        for i in range(query_points.shape[0]):
            visited[:] = 0
            if dist == alternative_dot or dist == alternative_cosine:
                norm = np.sqrt((query_points[i] ** 2).sum())
                if norm > 0.0:
                    current_query = query_points[i] / norm
                else:
                    continue
            else:
                current_query = query_points[i]

            heap_priorities = result[1][i]
            heap_indices = result[0][i]
            seed_set = [(np.float32(np.inf), np.int32(-1)) for j in range(0)]

            ############ Init ################
            n_initial_points = candidate_indices.shape[0]

            for j in range(n_initial_points):
                candidate = np.int32(candidate_indices[j])
                d = dist(data[candidate], current_query)
                # indices are guaranteed different
                simple_heap_push(heap_priorities, heap_indices, d, candidate)
                heapq.heappush(seed_set, (d, candidate))
                mark_visited(visited, candidate)

            ############ Search ##############
            distance_bound = distance_scale * heap_priorities[0]

            # Find smallest seed point
            d_vertex, vertex = heapq.heappop(seed_set)

            while d_vertex < distance_bound:

                for j in range(indptr[vertex], indptr[vertex + 1]):

                    candidate = indices[j]

                    if has_been_visited(visited, candidate) == 0:
                        mark_visited(visited, candidate)

                        d = dist(data[candidate], current_query)

                        if d < distance_bound:
                            simple_heap_push(
                                heap_priorities, heap_indices, d, candidate
                            )
                            heapq.heappush(seed_set, (d, candidate))
                            # Update bound
                            distance_bound = distance_scale * heap_priorities[0]

                # find new smallest seed point
                if len(seed_set) == 0:
                    break
                else:
                    d_vertex, vertex = heapq.heappop(seed_set)

        return result

    return custom_search_closure


# @numba.njit(nogil=True)
def find_component_connection_edge(
    component1,
    component2,
    search_closure,
    raw_data,
    visited,
    rng_state,
    search_size=10,
    epsilon=0.0,
):
    indices = [np.zeros(1, dtype=np.int64) for i in range(2)]
    indices[0] = component1[
        rejection_sample(np.int64(search_size), component1.shape[0], rng_state)
    ]
    indices[1] = component2[
        rejection_sample(np.int64(search_size), component2.shape[0], rng_state)
    ]
    query_side = 0
    query_points = raw_data[indices[query_side]]
    candidate_indices = indices[1 - query_side].copy()
    changed = [True, True]
    best_dist = np.inf
    best_edge = (indices[0][0], indices[1][0])

    while changed[0] or changed[1]:
        inds, dists, _ = search_closure(
            query_points, candidate_indices, search_size, epsilon, visited
        )
        inds, dists = deheap_sort(inds, dists)
        for i in range(dists.shape[0]):
            for j in range(dists.shape[1]):
                if dists[i, j] < best_dist:
                    best_dist = dists[i, j]
                    best_edge = (indices[query_side][i], inds[i, j])
        candidate_indices = indices[query_side]
        new_indices = np.unique(inds[:, 0])
        if indices[1 - query_side].shape[0] == new_indices.shape[0]:
            changed[1 - query_side] = np.any(indices[1 - query_side] != new_indices)
        indices[1 - query_side] = new_indices
        query_points = raw_data[indices[1 - query_side]]
        query_side = 1 - query_side

    return best_edge[0], best_edge[1], best_dist


def adjacency_matrix_representation(neighbor_indices, neighbor_distances):
    result = coo_matrix(
        (neighbor_indices.shape[0], neighbor_indices.shape[0]), dtype=np.float32
    )

    # Preserve any distance 0 points
    neighbor_distances[neighbor_distances == 0.0] = FLOAT32_EPS

    result.row = np.repeat(
        np.arange(neighbor_indices.shape[0], dtype=np.int32), neighbor_indices.shape[1]
    )
    result.col = neighbor_indices.ravel()
    result.data = neighbor_distances.ravel()

    # Get rid of any -1 index entries
    result = result.tocsr()
    result.data[result.indices == -1] = 0.0
    result.eliminate_zeros()

    # Symmetrize
    result = result.maximum(result.T)

    return result


def connect_graph(graph, index, search_size=10, n_jobs=None):

    search_closure = create_component_search(index)
    n_components, component_ids = connected_components(graph)
    result = graph.tolil()

    # Translate component ids into internal vertex order
    component_ids = component_ids[index._vertex_order]

    def new_edge(c1, c2):
        component1 = np.where(component_ids == c1)[0]
        component2 = np.where(component_ids == c2)[0]

        i, j, d = find_component_connection_edge(
            component1,
            component2,
            search_closure,
            index._raw_data,
            index._visited,
            index.rng_state,
            search_size=search_size,
        )

        # Correct the distance if required
        if index._distance_correction is not None:
            d = index._distance_correction(d)

        # Convert indices to original data order
        i = index._vertex_order[i]
        j = index._vertex_order[j]

        return i, j, d

    new_edges = joblib.Parallel(n_jobs=n_jobs, prefer="threads")(
        joblib.delayed(new_edge)(c1, c2)
        for c1, c2 in combinations(range(n_components), 2)
    )

    for i, j, d in new_edges:
        result[i, j] = d
        result[j, i] = d

    return result.tocsr()
