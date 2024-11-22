import numpy as np
import numba

from pynndescent.utils import tau_rand_int, norm

######################################################
# Alternative tree approach; should be the basis
# for a dask-distributed version of the algorithm
######################################################


@numba.njit(fastmath=True, nogil=True)
def apply_hyperplane(
    data,
    hyperplane_vector,
    hyperplane_offset,
    hyperplane_node_num,
    current_num_nodes,
    data_node_loc,
    rng_state,
):

    left_node = current_num_nodes
    right_node = current_num_nodes + 1

    for i in range(data_node_loc.shape[0]):
        if data_node_loc[i] != hyperplane_node_num:
            continue

        margin = hyperplane_offset
        for d in range(hyperplane_vector.shape[0]):
            margin += hyperplane_vector[d] * data[i, d]

        if margin == 0:
            if abs(tau_rand_int(rng_state)) % 2 == 0:
                data_node_loc[i] = left_node
            else:
                data_node_loc[i] = right_node
        elif margin > 0:
            data_node_loc[i] = left_node
        else:
            data_node_loc[i] = right_node

    return


@numba.njit(fastmath=True, nogil=True)
def make_euclidean_hyperplane(data, indices, rng_state):
    left_index = tau_rand_int(rng_state) % indices.shape[0]
    right_index = tau_rand_int(rng_state) % indices.shape[0]
    right_index += left_index == right_index
    right_index = right_index % indices.shape[0]
    left = indices[left_index]
    right = indices[right_index]

    # Compute the normal vector to the hyperplane (the vector between
    # the two points) and the offset from the origin
    hyperplane_offset = 0.0
    hyperplane_vector = np.empty(data.shape[1], dtype=np.float32)

    for d in range(data.shape[1]):
        hyperplane_vector[d] = data[left, d] - data[right, d]
        hyperplane_offset -= (
            hyperplane_vector[d] * (data[left, d] + data[right, d]) / 2.0
        )

    return hyperplane_vector, hyperplane_offset


@numba.njit(fastmath=True, nogil=True)
def make_angular_hyperplane(data, indices, rng_state):
    left_index = tau_rand_int(rng_state) % indices.shape[0]
    right_index = tau_rand_int(rng_state) % indices.shape[0]
    right_index += left_index == right_index
    right_index = right_index % indices.shape[0]
    left = indices[left_index]
    right = indices[right_index]

    left_norm = norm(data[left])
    right_norm = norm(data[right])

    if left_norm == 0.0:
        left_norm = 1.0

    if right_norm == 0.0:
        right_norm = 1.0

    # Compute the normal vector to the hyperplane (the vector between
    # the two points) and the offset from the origin
    hyperplane_offset = 0.0
    hyperplane_vector = np.empty(data.shape[1], dtype=np.float32)

    for d in range(data.shape[1]):
        hyperplane_vector[d] = (data[left, d] / left_norm) - (
            data[right, d] / right_norm
        )

    return hyperplane_vector, hyperplane_offset
