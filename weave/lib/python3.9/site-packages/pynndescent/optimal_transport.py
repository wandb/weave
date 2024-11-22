#############################################################################
# This code draws from the Python Optimal Transport version of the
# network simplex algorithm, which in turn was adapted from the LEMON
# library. The copyrights/comment blocks for those are preserved below.
# The Python/Numba implementation was adapted by Leland McInnes (2020).
#
#  * This file has been adapted by Nicolas Bonneel (2013),
#  * from network_simplex.h from LEMON, a generic C++ optimization library,
#  * to implement a lightweight network simplex for mass transport, more
#  * memory efficient that the original file. A previous version of this file
#  * is used as part of the Displacement Interpolation project,
#  * Web: http://www.cs.ubc.ca/labs/imager/tr/2011/DisplacementInterpolation/
#  *
#  *
#  **** Original file Copyright Notice :
#  *
#  * Copyright (C) 2003-2010
#  * Egervary Jeno Kombinatorikus Optimalizalasi Kutatocsoport
#  * (Egervary Research Group on Combinatorial Optimization, EGRES).
#  *
#  * Permission to use, modify and distribute this software is granted
#  * provided that this copyright notice appears in all copies. For
#  * precise terms see the accompanying LICENSE file.
#  *
#  * This software is provided "AS IS" with no warranty of any kind,
#  * express or implied, and with no claim as to its suitability for any
#  * purpose.

import numpy as np
import numba
from collections import namedtuple
from enum import Enum, IntEnum

_mock_identity = np.eye(2, dtype=np.float32)
_mock_ones = np.ones(2, dtype=np.float32)
_dummy_cost = np.zeros((2, 2), dtype=np.float64)

# Accuracy tolerance and net supply tolerance
EPSILON = 2.2204460492503131e-15
NET_SUPPLY_ERROR_TOLERANCE = 1e-8

## Defaults to double for everythig in POT
INFINITY = np.finfo(np.float64).max
MAX = np.finfo(np.float64).max

dummy_cost = np.zeros((2, 2), dtype=np.float64)

# Invalid Arc num
INVALID = -1

# Problem Status
class ProblemStatus(Enum):
    OPTIMAL = 0
    MAX_ITER_REACHED = 1
    UNBOUNDED = 2
    INFEASIBLE = 3


# Arc States
class ArcState(IntEnum):
    STATE_UPPER = -1
    STATE_TREE = 0
    STATE_LOWER = 1


SpanningTree = namedtuple(
    "SpanningTree",
    [
        "parent",  # int array
        "pred",  # int array
        "thread",  # int array
        "rev_thread",  # int array
        "succ_num",  # int array
        "last_succ",  # int array
        "forward",  # bool array
        "state",  # state array
        "root",  # int
    ],
)
DiGraph = namedtuple(
    "DiGraph",
    [
        "n_nodes",  # int
        "n_arcs",  # int
        "n",  # int
        "m",  # int
        "use_arc_mixing",  # bool
        "num_total_big_subsequence_numbers",  # int
        "subsequence_length",  # int
        "num_big_subsequences",  # int
        "mixing_coeff",
    ],
)
NodeArcData = namedtuple(
    "NodeArcData",
    [
        "cost",  # double array
        "supply",  # double array
        "flow",  # double array
        "pi",  # double array
        "source",  # unsigned int array
        "target",  # unsigned int array
    ],
)
LeavingArcData = namedtuple(
    "LeavingArcData", ["u_in", "u_out", "v_in", "delta", "change"]
)

# Just reproduce a simpler version of numpy isclose (not numba supported yet)
@numba.njit()
def isclose(a, b, rtol=1.0e-5, atol=EPSILON):
    diff = np.abs(a - b)
    return diff <= (atol + rtol * np.abs(b))


# locals: c, min, e, cnt, a
# modifies _in_arc, _next_arc,
@numba.njit(locals={"a": numba.uint32, "e": numba.uint32})
def find_entering_arc(
    pivot_block_size,
    pivot_next_arc,
    search_arc_num,
    state_vector,
    node_arc_data,
    in_arc,
):
    min = 0
    cnt = pivot_block_size

    # Pull from tuple for quick reference
    cost = node_arc_data.cost
    pi = node_arc_data.pi
    source = node_arc_data.source
    target = node_arc_data.target

    for e in range(pivot_next_arc, search_arc_num):
        c = state_vector[e] * (cost[e] + pi[source[e]] - pi[target[e]])
        if c < min:
            min = c
            in_arc = e

        cnt -= 1
        if cnt == 0:
            if np.fabs(pi[source[in_arc]]) > np.fabs(pi[target[in_arc]]):
                a = np.fabs(pi[source[in_arc]])
            else:
                a = np.fabs(pi[target[in_arc]])

            if a <= np.fabs(cost[in_arc]):
                a = np.fabs(cost[in_arc])

            if min < -(EPSILON * a):
                pivot_next_arc = e
                return in_arc, pivot_next_arc
            else:
                cnt = pivot_block_size

    for e in range(pivot_next_arc):
        c = state_vector[e] * (cost[e] + pi[source[e]] - pi[target[e]])
        if c < min:
            min = c
            in_arc = e

        cnt -= 1
        if cnt == 0:
            if np.fabs(pi[source[in_arc]]) > np.fabs(pi[target[in_arc]]):
                a = np.fabs(pi[source[in_arc]])
            else:
                a = np.fabs(pi[target[in_arc]])

            if a <= np.fabs(cost[in_arc]):
                a = np.fabs(cost[in_arc])

            if min < -(EPSILON * a):
                pivot_next_arc = e
                return in_arc, pivot_next_arc
            else:
                cnt = pivot_block_size

    # assert(pivot_block.next_arc[0] == 0 or e == pivot_block.next_arc[0] - 1)

    if np.fabs(pi[source[in_arc]]) > np.fabs(pi[target[in_arc]]):
        a = np.fabs(pi[source[in_arc]])
    else:
        a = np.fabs(pi[target[in_arc]])

    if a <= np.fabs(cost[in_arc]):
        a = np.fabs(cost[in_arc])

    if min >= -(EPSILON * a):
        return -1, 0

    return in_arc, pivot_next_arc


# Find the join node
# Operates with graph (_source, _target) and MST (_succ_num, _parent, in_arc) data
# locals: u, v
# modifies: join
@numba.njit(locals={"u": numba.types.uint16, "v": numba.types.uint16})
def find_join_node(source, target, succ_num, parent, in_arc):
    u = source[in_arc]
    v = target[in_arc]
    while u != v:
        if succ_num[u] < succ_num[v]:
            u = parent[u]
        else:
            v = parent[v]

    join = u

    return join


# Find the leaving arc of the cycle and returns true if the
# leaving arc is not the same as the entering arc
# locals: first, second, result, d, e
# modifies: u_in, v_in, u_out, delta
@numba.njit(
    locals={
        "u": numba.uint16,
        "u_in": numba.uint16,
        "u_out": numba.uint16,
        "v_in": numba.uint16,
        "first": numba.uint16,
        "second": numba.uint16,
        "result": numba.uint8,
        "in_arc": numba.uint32,
    }
)
def find_leaving_arc(join, in_arc, node_arc_data, spanning_tree):
    source = node_arc_data.source
    target = node_arc_data.target
    flow = node_arc_data.flow

    state = spanning_tree.state
    forward = spanning_tree.forward
    pred = spanning_tree.pred
    parent = spanning_tree.parent

    u_out = -1  # May not be set, but we need to return something?

    # Initialize first and second nodes according to the direction
    # of the cycle
    if state[in_arc] == ArcState.STATE_LOWER:
        first = source[in_arc]
        second = target[in_arc]
    else:
        first = target[in_arc]
        second = source[in_arc]

    delta = INFINITY
    result = 0

    # Search the cycle along the path form the first node to the root
    u = first
    while u != join:
        e = pred[u]
        if forward[u]:
            d = flow[e]
        else:
            d = INFINITY

        if d < delta:
            delta = d
            u_out = u
            result = 1

        u = parent[u]

    # Search the cycle along the path form the second node to the root
    u = second
    while u != join:
        e = pred[u]
        if forward[u]:
            d = INFINITY
        else:
            d = flow[e]

        if d <= delta:
            delta = d
            u_out = u
            result = 2

        u = parent[u]

    if result == 1:
        u_in = first
        v_in = second
    else:
        u_in = second
        v_in = first

    return LeavingArcData(u_in, u_out, v_in, delta, result != 0)


# Change _flow and _state vectors
# locals: val, u
# modifies: _state, _flow
@numba.njit(locals={"u": numba.uint16, "in_arc": numba.uint32, "val": numba.float64})
def update_flow(join, leaving_arc_data, node_arc_data, spanning_tree, in_arc):
    source = node_arc_data.source
    target = node_arc_data.target
    flow = node_arc_data.flow

    state = spanning_tree.state
    pred = spanning_tree.pred
    parent = spanning_tree.parent
    forward = spanning_tree.forward

    # Augment along the cycle
    if leaving_arc_data.delta > 0:
        val = state[in_arc] * leaving_arc_data.delta
        flow[in_arc] += val
        u = source[in_arc]
        while u != join:
            if forward[u]:
                flow[pred[u]] -= val
            else:
                flow[pred[u]] += val

            u = parent[u]

        u = target[in_arc]
        while u != join:
            if forward[u]:
                flow[pred[u]] += val
            else:
                flow[pred[u]] -= val

            u = parent[u]

    # Update the state of the entering and leaving arcs
    if leaving_arc_data.change:
        state[in_arc] = ArcState.STATE_TREE
        if flow[pred[leaving_arc_data.u_out]] == 0:
            state[pred[leaving_arc_data.u_out]] = ArcState.STATE_LOWER
        else:
            state[pred[leaving_arc_data.u_out]] = ArcState.STATE_UPPER
    else:
        state[in_arc] = -state[in_arc]


# Update the tree structure
# locals: u, w, old_rev_thread, old_succ_num, old_last_succ, tmp_sc, tmp_ls
# more locals: up_limit_in, up_limit_out, _dirty_revs
# modifies: v_out, _thread, _rev_thread, _parent, _last_succ,
# modifies: _pred, _forward, _succ_num
@numba.njit(
    locals={
        "u": numba.int32,
        "w": numba.int32,
        "u_in": numba.uint16,
        "u_out": numba.uint16,
        "v_in": numba.uint16,
        "right": numba.uint16,
        "stem": numba.uint16,
        "new_stem": numba.uint16,
        "par_stem": numba.uint16,
        "in_arc": numba.uint32,
    }
)
def update_spanning_tree(spanning_tree, leaving_arc_data, join, in_arc, source):

    parent = spanning_tree.parent
    thread = spanning_tree.thread
    rev_thread = spanning_tree.rev_thread
    succ_num = spanning_tree.succ_num
    last_succ = spanning_tree.last_succ
    forward = spanning_tree.forward
    pred = spanning_tree.pred

    u_out = leaving_arc_data.u_out
    u_in = leaving_arc_data.u_in
    v_in = leaving_arc_data.v_in

    old_rev_thread = rev_thread[u_out]
    old_succ_num = succ_num[u_out]
    old_last_succ = last_succ[u_out]
    v_out = parent[u_out]

    u = last_succ[u_in]  # the last successor of u_in
    right = thread[u]  # the node after it

    # Handle the case when old_rev_thread equals to v_in
    # (it also means that join and v_out coincide)
    if old_rev_thread == v_in:
        last = thread[last_succ[u_out]]
    else:
        last = thread[v_in]

    # Update _thread and _parent along the stem nodes (i.e. the nodes
    # between u_in and u_out, whose parent have to be changed)
    thread[v_in] = stem = u_in
    dirty_revs = []
    dirty_revs.append(v_in)
    par_stem = v_in
    while stem != u_out:
        # Insert the next stem node into the thread list
        new_stem = parent[stem]
        thread[u] = new_stem
        dirty_revs.append(u)

        # Remove the subtree of stem from the thread list
        w = rev_thread[stem]
        thread[w] = right
        rev_thread[right] = w

        # Change the parent node and shift stem nodes
        parent[stem] = par_stem
        par_stem = stem
        stem = new_stem

        # Update u and right
        if last_succ[stem] == last_succ[par_stem]:
            u = rev_thread[par_stem]
        else:
            u = last_succ[stem]

        right = thread[u]

    parent[u_out] = par_stem
    thread[u] = last
    rev_thread[last] = u
    last_succ[u_out] = u

    # Remove the subtree of u_out from the thread list except for
    # the case when old_rev_thread equals to v_in
    # (it also means that join and v_out coincide)
    if old_rev_thread != v_in:
        thread[old_rev_thread] = right
        rev_thread[right] = old_rev_thread

    # Update _rev_thread using the new _thread values
    for i in range(len(dirty_revs)):
        u = dirty_revs[i]
        rev_thread[thread[u]] = u

    # Update _pred, _forward, _last_succ and _succ_num for the
    # stem nodes from u_out to u_in
    tmp_sc = 0
    tmp_ls = last_succ[u_out]
    u = u_out
    while u != u_in:
        w = parent[u]
        pred[u] = pred[w]
        forward[u] = not forward[w]
        tmp_sc += succ_num[u] - succ_num[w]
        succ_num[u] = tmp_sc
        last_succ[w] = tmp_ls
        u = w

    pred[u_in] = in_arc
    forward[u_in] = u_in == source[in_arc]
    succ_num[u_in] = old_succ_num

    # Set limits for updating _last_succ form v_in and v_out
    # towards the root
    up_limit_in = -1
    up_limit_out = -1
    if last_succ[join] == v_in:
        up_limit_out = join
    else:
        up_limit_in = join

    # Update _last_succ from v_in towards the root
    u = v_in
    while u != up_limit_in and last_succ[u] == v_in:
        last_succ[u] = last_succ[u_out]
        u = parent[u]

    # Update _last_succ from v_out towards the root
    if join != old_rev_thread and v_in != old_rev_thread:
        u = v_out
        while u != up_limit_out and last_succ[u] == old_last_succ:
            last_succ[u] = old_rev_thread
            u = parent[u]

    else:
        u = v_out
        while u != up_limit_out and last_succ[u] == old_last_succ:
            last_succ[u] = last_succ[u_out]
            u = parent[u]

    # Update _succ_num from v_in to join
    u = v_in
    while u != join:
        succ_num[u] += old_succ_num
        u = parent[u]

    # Update _succ_num from v_out to join
    u = v_out
    while u != join:
        succ_num[u] -= old_succ_num
        u = parent[u]


# Update potentials
# locals: sigma, end
# modifies: _pi
@numba.njit(
    fastmath=True,
    inline="always",
    locals={"u": numba.uint16, "u_in": numba.uint16, "v_in": numba.uint16},
)
def update_potential(leaving_arc_data, pi, cost, spanning_tree):

    thread = spanning_tree.thread
    pred = spanning_tree.pred
    forward = spanning_tree.forward
    last_succ = spanning_tree.last_succ

    u_in = leaving_arc_data.u_in
    v_in = leaving_arc_data.v_in

    if forward[u_in]:
        sigma = pi[v_in] - pi[u_in] - cost[pred[u_in]]
    else:
        sigma = pi[v_in] - pi[u_in] + cost[pred[u_in]]

    # Update potentials in the subtree, which has been moved
    end = thread[last_succ[u_in]]
    u = u_in
    while u != end:
        pi[u] += sigma
        u = thread[u]


# If we have mixed arcs (for better random access)
# we need a more complicated function to get the ID of a given arc
@numba.njit()
def arc_id(arc, graph):
    k = graph.n_arcs - arc - 1
    if graph.use_arc_mixing:
        smallv = (k > graph.num_total_big_subsequence_numbers) & 1
        k -= graph.num_total_big_subsequence_numbers * smallv
        subsequence_length2 = graph.subsequence_length - smallv
        subsequence_num = (
            k // subsequence_length2
        ) + graph.num_big_subsequences * smallv
        subsequence_offset = (k % subsequence_length2) * graph.mixing_coeff

        return subsequence_offset + subsequence_num
    else:
        return k


# Heuristic initial pivots
# locals: curr, total, supply_nodes, demand_nodes, u
# modifies:
@numba.njit(locals={"i": numba.uint16})
def construct_initial_pivots(graph, node_arc_data, spanning_tree):

    cost = node_arc_data.cost
    pi = node_arc_data.pi
    source = node_arc_data.source
    target = node_arc_data.target
    supply = node_arc_data.supply

    n1 = graph.n
    n2 = graph.m
    n_nodes = graph.n_nodes
    n_arcs = graph.n_arcs

    state = spanning_tree.state

    total = 0
    supply_nodes = []
    demand_nodes = []

    for u in range(n_nodes):
        curr = supply[n_nodes - u - 1]  # _node_id(u)
        if curr > 0:
            total += curr
            supply_nodes.append(u)
        elif curr < 0:
            demand_nodes.append(u)

    arc_vector = []
    if len(supply_nodes) == 1 and len(demand_nodes) == 1:
        # Perform a reverse graph search from the sink to the source
        reached = np.zeros(n_nodes, dtype=np.bool_)
        s = supply_nodes[0]
        t = demand_nodes[0]
        stack = []
        reached[t] = True
        stack.append(t)
        while len(stack) > 0:
            u = stack[-1]
            v = stack[-1]
            stack.pop(-1)
            if v == s:
                break

            first_arc = n_arcs + v - n_nodes if v >= n1 else -1
            for a in range(first_arc, -1, -n2):
                u = a // n2
                if reached[u]:
                    continue

                j = arc_id(a, graph)
                if INFINITY >= total:
                    arc_vector.append(j)
                    reached[u] = True
                    stack.append(u)

    else:
        # Find the min. cost incomming arc for each demand node
        for i in range(len(demand_nodes)):
            v = demand_nodes[i]
            c = MAX
            min_cost = MAX
            min_arc = INVALID
            first_arc = n_arcs + v - n_nodes if v >= n1 else -1
            for a in range(first_arc, -1, -n2):
                c = cost[arc_id(a, graph)]
                if c < min_cost:
                    min_cost = c
                    min_arc = a

            if min_arc != INVALID:
                arc_vector.append(arc_id(min_arc, graph))

    # Perform heuristic initial pivots
    in_arc = -1
    for i in range(len(arc_vector)):
        in_arc = arc_vector[i]
        # Bad arcs
        if (
            state[in_arc] * (cost[in_arc] + pi[source[in_arc]] - pi[target[in_arc]])
            >= 0
        ):
            continue

        join = find_join_node(
            source, target, spanning_tree.succ_num, spanning_tree.parent, in_arc
        )
        leaving_arc_data = find_leaving_arc(join, in_arc, node_arc_data, spanning_tree)
        if leaving_arc_data.delta >= MAX:
            return False, in_arc

        update_flow(join, leaving_arc_data, node_arc_data, spanning_tree, in_arc)
        if leaving_arc_data.change:
            update_spanning_tree(spanning_tree, leaving_arc_data, join, in_arc, source)
            update_potential(leaving_arc_data, pi, cost, spanning_tree)

    return True, in_arc


@numba.njit()
def allocate_graph_structures(n, m, use_arc_mixing=True):

    # Size bipartite graph
    n_nodes = n + m
    n_arcs = n * m

    # Resize vectors
    all_node_num = n_nodes + 1
    max_arc_num = n_arcs + 2 * n_nodes
    root = n_nodes

    source = np.zeros(max_arc_num, dtype=np.uint16)
    target = np.zeros(max_arc_num, dtype=np.uint16)
    cost = np.ones(max_arc_num, dtype=np.float64)
    supply = np.zeros(all_node_num, dtype=np.float64)
    flow = np.zeros(max_arc_num, dtype=np.float64)
    pi = np.zeros(all_node_num, dtype=np.float64)

    parent = np.zeros(all_node_num, dtype=np.int32)
    pred = np.zeros(all_node_num, dtype=np.int32)
    forward = np.zeros(all_node_num, dtype=np.bool_)
    thread = np.zeros(all_node_num, dtype=np.int32)
    rev_thread = np.zeros(all_node_num, dtype=np.int32)
    succ_num = np.zeros(all_node_num, dtype=np.int32)
    last_succ = np.zeros(all_node_num, dtype=np.int32)
    state = np.zeros(max_arc_num, dtype=np.int8)

    if use_arc_mixing:
        # Store the arcs in a mixed order
        k = max(np.int32(np.sqrt(n_arcs)), 10)
        mixing_coeff = k
        subsequence_length = (n_arcs // mixing_coeff) + 1
        num_big_subsequences = n_arcs % mixing_coeff
        num_total_big_subsequence_numbers = subsequence_length * num_big_subsequences

        i = 0
        j = 0
        for a in range(n_arcs - 1, -1, -1):
            source[i] = n_nodes - (a // m) - 1
            target[i] = n_nodes - ((a % m) + n) - 1
            i += k
            if i >= n_arcs:
                j += 1
                i = j

    else:
        # dummy values
        subsequence_length = 0
        mixing_coeff = 0
        num_big_subsequences = 0
        num_total_big_subsequence_numbers = 0
        # Store the arcs in the original order
        i = 0
        for a in range(n_arcs - 1, -1, -1):
            source[i] = n_nodes - (a // m) - 1
            target[i] = n_nodes - ((a % m) + n) - 1
            i += 1

    node_arc_data = NodeArcData(cost, supply, flow, pi, source, target)
    spanning_tree = SpanningTree(
        parent, pred, thread, rev_thread, succ_num, last_succ, forward, state, root
    )
    graph = DiGraph(
        n_nodes,
        n_arcs,
        n,
        m,
        use_arc_mixing,
        num_total_big_subsequence_numbers,
        subsequence_length,
        num_big_subsequences,
        mixing_coeff,
    )

    return node_arc_data, spanning_tree, graph


@numba.njit(locals={"u": numba.uint16, "e": numba.uint32})
def initialize_graph_structures(graph, node_arc_data, spanning_tree):

    n_nodes = graph.n_nodes
    n_arcs = graph.n_arcs

    # unpack arrays
    cost = node_arc_data.cost
    supply = node_arc_data.supply
    flow = node_arc_data.flow
    pi = node_arc_data.pi
    source = node_arc_data.source
    target = node_arc_data.target

    parent = spanning_tree.parent
    pred = spanning_tree.pred
    thread = spanning_tree.thread
    rev_thread = spanning_tree.rev_thread
    succ_num = spanning_tree.succ_num
    last_succ = spanning_tree.last_succ
    forward = spanning_tree.forward
    state = spanning_tree.state

    if n_nodes == 0:
        return False

    # Check the sum of supply values
    net_supply = 0
    for i in range(n_nodes):
        net_supply += supply[i]

    if np.fabs(net_supply) > NET_SUPPLY_ERROR_TOLERANCE:
        return False

    # Fix using doubles
    # Initialize artifical cost
    artificial_cost = 0.0
    for i in range(n_arcs):
        if cost[i] > artificial_cost:
            artificial_cost = cost[i]
        # reset flow and state vectors
        if flow[i] != 0:
            flow[i] = 0
        state[i] = ArcState.STATE_LOWER

    artificial_cost = (artificial_cost + 1) * n_nodes

    # Set data for the artificial root node
    root = n_nodes
    parent[root] = -1
    pred[root] = -1
    thread[root] = 0
    rev_thread[0] = root
    succ_num[root] = n_nodes + 1
    last_succ[root] = root - 1
    supply[root] = -net_supply
    pi[root] = 0

    # Add artificial arcs and initialize the spanning tree data structure
    # EQ supply constraints
    e = n_arcs
    for u in range(n_nodes):
        parent[u] = root
        pred[u] = e
        thread[u] = u + 1
        rev_thread[u + 1] = u
        succ_num[u] = 1
        last_succ[u] = u
        state[e] = ArcState.STATE_TREE
        if supply[u] >= 0:
            forward[u] = True
            pi[u] = 0
            source[e] = u
            target[e] = root
            flow[e] = supply[u]
            cost[e] = 0
        else:
            forward[u] = False
            pi[u] = artificial_cost
            source[e] = root
            target[e] = u
            flow[e] = -supply[u]
            cost[e] = artificial_cost
        e += 1

    return True


@numba.njit()
def initialize_supply(left_node_supply, right_node_supply, graph, supply):
    for n in range(graph.n_nodes):
        if n < graph.n:
            supply[graph.n_nodes - n - 1] = left_node_supply[n]
        else:
            supply[graph.n_nodes - n - 1] = right_node_supply[n - graph.n]


@numba.njit(inline="always")
def set_cost(arc, cost_val, cost, graph):
    cost[arc_id(arc, graph)] = cost_val


@numba.njit(locals={"i": numba.uint16, "j": numba.uint16})
def initialize_cost(cost_matrix, graph, cost):
    for i in range(cost_matrix.shape[0]):
        for j in range(cost_matrix.shape[1]):
            set_cost(i * cost_matrix.shape[1] + j, cost_matrix[i, j], cost, graph)


@numba.njit(fastmath=True, locals={"i": numba.uint32})
def total_cost(flow, cost):
    c = 0.0
    for i in range(flow.shape[0]):
        c += flow[i] * cost[i]
    return c


@numba.njit(nogil=True)
def network_simplex_core(node_arc_data, spanning_tree, graph, max_iter):

    # pivot_block = PivotBlock(
    #     max(np.int32(np.sqrt(graph.n_arcs)), 10),
    #     np.zeros(1, dtype=np.int32),
    #     graph.n_arcs,
    # )
    pivot_block_size = max(np.int32(np.sqrt(graph.n_arcs)), 10)
    search_arc_num = graph.n_arcs
    solution_status = ProblemStatus.OPTIMAL

    # Perform heuristic initial pivots
    bounded, in_arc = construct_initial_pivots(graph, node_arc_data, spanning_tree)
    if not bounded:
        return ProblemStatus.UNBOUNDED

    iter_number = 0
    # pivot.setDantzig(true);
    # Execute the Network Simplex algorithm
    in_arc, pivot_next_arc = find_entering_arc(
        pivot_block_size, 0, search_arc_num, spanning_tree.state, node_arc_data, in_arc
    )
    while in_arc >= 0:
        iter_number += 1
        if max_iter > 0 and iter_number >= max_iter:
            solution_status = ProblemStatus.MAX_ITER_REACHED
            break

        join = find_join_node(
            node_arc_data.source,
            node_arc_data.target,
            spanning_tree.succ_num,
            spanning_tree.parent,
            in_arc,
        )
        leaving_arc_data = find_leaving_arc(join, in_arc, node_arc_data, spanning_tree)
        if leaving_arc_data.delta >= MAX:
            return ProblemStatus.UNBOUNDED

        update_flow(join, leaving_arc_data, node_arc_data, spanning_tree, in_arc)

        if leaving_arc_data.change:
            update_spanning_tree(
                spanning_tree, leaving_arc_data, join, in_arc, node_arc_data.source
            )
            update_potential(
                leaving_arc_data, node_arc_data.pi, node_arc_data.cost, spanning_tree
            )

        in_arc, pivot_next_arc = find_entering_arc(
            pivot_block_size,
            pivot_next_arc,
            search_arc_num,
            spanning_tree.state,
            node_arc_data,
            in_arc,
        )

    flow = node_arc_data.flow
    pi = node_arc_data.pi

    # Check feasibility
    if solution_status == ProblemStatus.OPTIMAL:
        for e in range(graph.n_arcs, graph.n_arcs + graph.n_nodes):
            if flow[e] != 0:
                if np.abs(flow[e]) > EPSILON:
                    return ProblemStatus.INFEASIBLE
                else:
                    flow[e] = 0

    # Shift potentials to meet the requirements of the GEQ/LEQ type
    # optimality conditions
    max_pot = -INFINITY
    for i in range(graph.n_nodes):
        if pi[i] > max_pot:
            max_pot = pi[i]
    if max_pot > 0:
        for i in range(graph.n_nodes):
            pi[i] -= max_pot

    return solution_status


#######################################################
# SINKHORN distances in various variations
#######################################################


@numba.njit(
    fastmath=True,
    parallel=True,
    locals={"diff": numba.float32, "result": numba.float32},
    cache=False,
)
def right_marginal_error(u, K, v, y):
    uK = u @ K
    result = 0.0
    for i in numba.prange(uK.shape[0]):
        diff = y[i] - uK[i] * v[i]
        result += diff * diff
    return np.sqrt(result)


@numba.njit(
    fastmath=True,
    parallel=True,
    locals={"diff": numba.float32, "result": numba.float32},
    cache=False,
)
def right_marginal_error_batch(u, K, v, y):
    uK = K.T @ u
    result = 0.0
    for i in numba.prange(uK.shape[0]):
        for j in range(uK.shape[1]):
            diff = y[j, i] - uK[i, j] * v[i, j]
            result += diff * diff
    return np.sqrt(result)


@numba.njit(fastmath=True, parallel=True, cache=False)
def transport_plan(K, u, v):
    i_dim = K.shape[0]
    j_dim = K.shape[1]
    result = np.empty_like(K)
    for i in numba.prange(i_dim):
        for j in range(j_dim):
            result[i, j] = u[i] * K[i, j] * v[j]

    return result


@numba.njit(fastmath=True, parallel=True, locals={"result": numba.float32}, cache=False)
def relative_change_in_plan(old_u, old_v, new_u, new_v):
    i_dim = old_u.shape[0]
    j_dim = old_v.shape[0]
    result = 0.0
    for i in numba.prange(i_dim):
        for j in range(j_dim):
            old_uv = old_u[i] * old_v[j]
            result += np.float32(np.abs(old_uv - new_u[i] * new_v[j]) / old_uv)

    return result / (i_dim * j_dim)


@numba.njit(fastmath=True, parallel=True, cache=False)
def precompute_K_prime(K, x):
    i_dim = K.shape[0]
    j_dim = K.shape[1]
    result = np.empty_like(K)
    for i in numba.prange(i_dim):
        if x[i] > 0.0:
            x_i_inverse = 1.0 / x[i]
        else:
            x_i_inverse = INFINITY
        for j in range(j_dim):
            result[i, j] = x_i_inverse * K[i, j]

    return result


@numba.njit(fastmath=True, parallel=True, cache=False)
def K_from_cost(cost, regularization):
    i_dim = cost.shape[0]
    j_dim = cost.shape[1]
    result = np.empty_like(cost)
    for i in numba.prange(i_dim):
        for j in range(j_dim):
            scaled_cost = cost[i, j] / regularization
            result[i, j] = np.exp(-scaled_cost)

    return result


@numba.njit(fastmath=True, cache=True)
def sinkhorn_iterations(
    x, y, u, v, K, max_iter=1000, error_tolerance=1e-9, change_tolerance=1e-9
):
    K_prime = precompute_K_prime(K, x)

    prev_u = u
    prev_v = v

    for iteration in range(max_iter):

        next_v = y / (K.T @ u)

        if np.any(~np.isfinite(next_v)):
            break

        next_u = 1.0 / (K_prime @ next_v)

        if np.any(~np.isfinite(next_u)):
            break

        u = next_u
        v = next_v

        if iteration % 20 == 0:
            # Check if values in plan have changed significantly since last 20 iterations
            relative_change = relative_change_in_plan(prev_u, prev_v, next_u, next_v)
            if relative_change <= change_tolerance:
                break

            prev_u = u
            prev_v = v

        if iteration % 10 == 0:
            # Check if right marginal error is less than tolerance every 10 iterations
            err = right_marginal_error(u, K, v, y)
            if err <= error_tolerance:
                break

    return u, v


@numba.njit(fastmath=True, cache=True)
def sinkhorn_iterations_batch(x, y, u, v, K, max_iter=1000, error_tolerance=1e-9):
    K_prime = precompute_K_prime(K, x)

    for iteration in range(max_iter):

        next_v = y.T / (K.T @ u)

        if np.any(~np.isfinite(next_v)):
            break

        next_u = 1.0 / (K_prime @ next_v)

        if np.any(~np.isfinite(next_u)):
            break

        u = next_u
        v = next_v

        if iteration % 10 == 0:
            # Check if right marginal error is less than tolerance every 10 iterations
            err = right_marginal_error_batch(u, K, v, y)
            if err <= error_tolerance:
                break

    return u, v


@numba.njit(fastmath=True, cache=True)
def sinkhorn_transport_plan(
    x,
    y,
    cost=_dummy_cost,
    regularization=1.0,
    max_iter=1000,
    error_tolerance=1e-9,
    change_tolerance=1e-9,
):
    dim_x = x.shape[0]
    dim_y = y.shape[0]
    u = np.full(dim_x, 1.0 / dim_x, dtype=cost.dtype)
    v = np.full(dim_y, 1.0 / dim_y, dtype=cost.dtype)

    K = K_from_cost(cost, regularization)
    u, v = sinkhorn_iterations(
        x,
        y,
        u,
        v,
        K,
        max_iter=max_iter,
        error_tolerance=error_tolerance,
        change_tolerance=change_tolerance,
    )

    return transport_plan(K, u, v)


@numba.njit(fastmath=True, cache=True)
def sinkhorn_distance(x, y, cost=_dummy_cost, regularization=1.0):
    transport_plan = sinkhorn_transport_plan(
        x, y, cost=cost, regularization=regularization
    )
    dim_i = transport_plan.shape[0]
    dim_j = transport_plan.shape[1]
    result = 0.0
    for i in range(dim_i):
        for j in range(dim_j):
            result += transport_plan[i, j] * cost[i, j]

    return result


@numba.njit(fastmath=True, parallel=True, cache=False)
def sinkhorn_distance_batch(x, y, cost=_dummy_cost, regularization=1.0):
    dim_x = x.shape[0]
    dim_y = y.shape[0]

    batch_size = y.shape[1]

    u = np.full((dim_x, batch_size), 1.0 / dim_x, dtype=cost.dtype)
    v = np.full((dim_y, batch_size), 1.0 / dim_y, dtype=cost.dtype)

    K = K_from_cost(cost, regularization)
    u, v = sinkhorn_iterations_batch(
        x,
        y,
        u,
        v,
        K,
    )

    i_dim = K.shape[0]
    j_dim = K.shape[1]
    result = np.zeros(batch_size)
    for i in range(i_dim):
        for j in range(j_dim):
            K_times_cost = K[i, j] * cost[i, j]
            for batch in range(batch_size):
                result[batch] += u[i, batch] * K_times_cost * v[j, batch]

    return result


def make_fixed_cost_sinkhorn_distance(cost, regularization=1.0):

    K = K_from_cost(cost, regularization)
    dim_x = K.shape[0]
    dim_y = K.shape[1]

    @numba.njit(fastmath=True)
    def closure(x, y):
        u = np.full(dim_x, 1.0 / dim_x, dtype=cost.dtype)
        v = np.full(dim_y, 1.0 / dim_y, dtype=cost.dtype)

        K = K_from_cost(cost, regularization)
        u, v = sinkhorn_iterations(
            x,
            y,
            u,
            v,
            K,
        )

        current_plan = transport_plan(K, u, v)

        result = 0.0
        for i in range(dim_x):
            for j in range(dim_y):
                result += current_plan[i, j] * cost[i, j]

        return result

    return closure
