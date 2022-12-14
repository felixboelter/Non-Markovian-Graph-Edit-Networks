"""
Provides an interface to the HEP-Th dataset as pre-processed by the
hep-th/preprocess_graph.py script. HeP-Th is a dataset of all arXiv
abstracts in the category of high energy physics theory between 1992
and 2003, as provided by

J. Leskovec, J. Kleinberg and C. Faloutsos. Graph Evolution: Densification and
Shrinking Diameters. ACM Transactions on Knowledge Discovery from Data
(ACM TKDD), 1(1), 2007.

under the URL https://snap.stanford.edu/data/ca-HepTh.html. Folowing the
scheme of Goyal, Chhetri, and Canedo in their dyngraph2vec paper
( https://doi.org/10.1016/j.knosys.2019.06.024 ), we build a one graph
per month from this dataset which includes all collaborations between authors
up to (and including) this month, i.e. each author is a node and an undirected
edge is drawn between authors who wrote a paper together.

Note that we perform duplicate detection to handle authors who write their
names differently in different papers. Due to that fact, we obtain a lower
node count (8874) compared to the report of Leskovec, Kleinberg, and Faloutsos
(who reported 9877).

"""

# Copyright (C) 2020-2021
# Benjamin Paaßen
# The University of Sydney

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import csv
import numpy as np
import torch
import pandas as pd
import networkx as nx


month_dict = {4:30, 5:31, 6:30, 7:31, 8:31, 9:30, 10:31}
_day_strings = []
for month in range(4, 10+1):
    for day in range(1,month_dict[month]+1):
        _day_strings.append('2004-{:0>2}-{:0>2}'.format(month,day))


def return_adj_nodes(df, date_a, date_b):
    """Pass a date range like '2014-01-01', '2014-02-01'.
    Make sure to parse df dates as index before passing df.
    returns nodes and adjacency matrix."""
    df = df.loc[date_a:date_b]
    G = nx.from_pandas_edgelist(df,"From","To")
    nodes = np.array(G.nodes)
    #A = nx.adjacency_matrix(G)
    A = nx.to_numpy_array(G, dtype=int)
    return A, nodes

def read_graph_from_txt(df, date_a, date_b):
    """ Date format '2004-07-13', '2004-07-13'
    """
    A, N = return_adj_nodes(df, date_a, date_b )
    G1 = nx.convert_matrix.from_numpy_matrix(A)
    idx = []
    for node in G1.degree():
        idx.append(node[0])
    idx_np = np.array(idx, dtype=int)
    return A, idx_np


def _teaching_protocol(A, I, B, J):
    """ Generates a simple teaching protocol transforming the given graph
    (A, I) to the given graph (B, J), with a simplified node insertion
    handling. In particular, the teaching protocol deletes nodes i where
    the ID I[i] does not occur in J, deletes edges (i, k) where the edge
    with ids (I[i], I[k]) is not in B, inserts edges (i, k) where the edge
    with ids (I[i], I[k]) is in B, and lets node i insert a new node whenever
    there is at least one edge with ids (I[i], id) in B where id is not in I.
    This node insertion handling may get things wrong when a single node needs
    to insert multiple other nodes or when multiple nodes need to be connected
    to a single new node. For this simplified setting here, we gloss over this
    difficulty in order to have a single-step protocol.
    Parameters
    ----------
    A: ndarray of size m x m
        An adjacency matrix for the input graph.
    I: list
        A list of node ids for the input graph
    B: ndarray of size n x n
        An adjacency matrix for the output graph.
    J: list
        A list of node ids for the output graph.
    Returns
    -------
    A: ndarray of size m x m
        The adjacency matrix for the current graph, containing 'past' months
        of citation activity.
    delta: ndarray of size m
        The change in nodes to get from the past graph to the current graph.
        Note that only a single insertion is considered 
    Epsilon: ndarray of size m x m
        The change in adjacencies required to get from the past graph to the
        current graph.
    """
    # compute an index mapping for the past and the current graph
    I_map = {}
    for i in range(len(I)):
        I_map[I[i]] = i
    J_map = {}
    for j in range(len(J)):
        J_map[J[j]] = j
    # build an adjacency list for the past and present graph
    Adj = []
    for i in range(len(I)):
        Adj.append(set(np.where(A[i, :] > 0.5)[0].tolist()))
    Bdj = []
    for j in range(len(J)):
        Bdj.append(set(np.where(B[j, :] > 0.5)[0].tolist()))
    # compute the expected node and edge changes
    delta = np.zeros(len(I))
    Epsilon = np.zeros((len(I), len(I)))
    for i in range(len(I)):
        # if i is deleted, set delta[i] to -1
        if I[i] not in J_map:
            delta[i] = -1
            continue
        # otherwise retrieve the matching index j in the current graph
        j = J_map[I[i]]
        # iterate over all adjacent nodes of i and check whether these
        # adjacencies persist
        for k in Adj[i]:
            # if an adjacent node is deleted, we ignore that in Epsilon,
            # because that will be handled via delta
            if I[k] not in J_map:
                continue
            l = J_map[I[k]]
            # if an adjacency vanishes, set Epsilon[i, k] = -1
            if B[j, l] < 0.5:
                Epsilon[i, k] = -1
        # iterate over all adjacent nodes of j and check whether these
        # adjacencies are new
        for l in Bdj[j]:
            # if an adjacent node of j is inserted, set delta[i] = +1.
            # Note that, if multiple nodes are inserted, only one
            # insertion is performed per node in the cluster, which may
            # not accurately reflect the number of authors.
            if J[l] not in I:
                delta[i] = +1
                continue
            k = I_map[J[l]]
            # if an adjacency emerges, set Epsilon[i, k] = +1
            if A[i, k] < 0.5:
                Epsilon[i, k] = +1
    return delta, Epsilon
def add_graph(A_left, idxs_left, A_right, idxs_right):
    """ Adds the right graph to the left graph.

    In particular, any entry of idxs_right not contained in idxs_left becomes
    a new node in the result graph, and any edge not existing in A_left but in
    A_right gets inserted as well. Note that the resulting index list gets
    sorted such that add_graph is a symmetric function.

    Parameters
    ----------
    A_left: class numpy.array_like
        An adjacency matrix for the left graph.
    idxs_left: class numpy.array_like
        An array of unique identifiers for each node in the left graph.
    A_right: class numpy.array_like
        An adjacency matrix for the right graph.
    idxs_right: class numpy.array_like
        An array of unique identifiers for each node in the right graph.

    Returns
    -------
    A: class numpy.array_like
        The sorted union of both adjacency matrices.
    idxs: class numpy.array_like
        The sorted union of both index arrays.

    """
    # construct the union of idxs_left and idxs_right
    idxs = np.union1d(idxs_left, idxs_right)
    # construct a map from idxs to indices in the new graph
    idxs_map = {}
    for i in range(len(idxs)):
        idxs_map[idxs[i]] = i
    # construct the new adjacency matrix
    A = np.zeros((len(idxs), len(idxs)), dtype=int)
    for i in range(len(idxs_left)):
        i2 = idxs_map[idxs_left[i]]
        for j in np.where(A_left[i][i+1:] > 0.5)[0]:
            j2 = idxs_map[idxs_left[i+1+j]]
            A[i2, j2] = 1
            A[j2, i2] = 1
    for i in range(len(idxs_right)):
        i2 = idxs_map[idxs_right[i]]
        for j in np.where(A_right[i][i+1:] > 0.5)[0]:
            j2 = idxs_map[idxs_right[i+1+j]]
            A[i2, j2] = 1
            A[j2, i2] = 1
    return A, idxs


def compute_loss(gen, df, year, month, day, past=7):
    """ Computes the teaching-protocol specific loss of the given graph edit
    network on a graph from the HEP-Th dataset.

    In particular, we expect that edge insertions are predicted whenever two
    existing authors would submit a new paper in the current month, and that
    a node insertion is predicted whenever an author submits a new paper with
    a co-author that is not yet part of the collaboration graph.

    The current collaboration graph is constructed from the past 12 month per
    default.

    Parameters
    ----------
    gen: class pytorch_graph_edit_network.GEN
        A graph edit network.
    year: int
        A year in the range 1992-2003
    month: int
        A month in the range 1-12
    past: int (default = 12)
        The number of days in the past we consider to construct the initial
        collaboration graph that is fed into the GEN.

    Returns
    -------
    loss: torch.Tensor
        a scalar value containing the GEN loss for the expectations above.

    """
    if past < 1:
        raise ValueError('Expected a strictly positive integer for past')
    # construct the current collaboration graph from the past
    t = _day_strings.index('2004-{:0>2}-{:0>2}'.format(month,day))
    if t <= 0:
        raise ValueError('Expected input time in the range 1992-2 until 2003-4')
    if t < past:
        past_days = _day_strings[:t]
    else:
        past_days = _day_strings[(t-past):t]
    # Read the first graph
    A, I = read_graph_from_txt(df, past_days[0], past_days[0])
    for tau in range(1, len(past_days)-1):
        # Update the EvolveGCN weights
        _, _ = gen(torch.tensor(A, dtype=torch.float))
        # parse the current graph from TXT data
        A, I = read_graph_from_txt(df, past_days[tau], past_days[tau])
    # parse the next graph from txt data
    B, J = read_graph_from_txt(df, _day_strings[t], _day_strings[t])


    if gen._filter_edge_edits is False:
        # compute the output of the GEN for the current graph
        deltaX, deltaA = gen(torch.tensor(A, dtype=torch.float))
        # compute an index map for the current graph
        idx_map = {}
        for i in range(len(I)):
            idx_map[I[i]] = i

        # compute the expected deltaX and filters
        deltaX_expected = torch.zeros(len(I))
        for i in range(len(J)):
            if J[i] not in idx_map:
                continue
            i2 = idx_map[J[i]]
            for j in np.where(B[i+1:] > 0.5)[0]:
                if J[j+i+1] not in idx_map:
                    # if i makes a connection to a node that does not exist
                    # in A, we expect a node insertion
                    deltaX_expected[i2] = 1.
        # add a loss of N * ReLU(-deltaX[i] + 1.)^2 if deltaX[i] should be
        # positive
        mask = deltaX_expected > 0.5
        loss = len(I) * torch.sum(torch.pow(torch.nn.functional.relu(-deltaX[mask]+1.), 2))
        # add a loss of N * ReLU(deltaX[i])^2 if deltaX[i] should be
        # zero
        mask = deltaX_expected < 0.5
        loss = loss + len(I) * torch.sum(torch.pow(torch.nn.functional.relu(deltaX[mask]), 2))

        # compute an index map for the next graph
        idx_map_next = {}
        for i in range(len(J)):
            idx_map_next[J[i]] = i

        for i in range(len(I)):
            if I[i] not in idx_map_next:
                # add a loss of ReLU(+deltaA[i, j])^2 if there should
                # be no edge
                loss = loss + torch.sum(torch.pow(torch.nn.functional.relu(deltaA[i, :]), 2))
                continue
            i2 = idx_map_next[I[i]]
            for j in range(len(I)):
                if I[j] not in idx_map_next:
                    continue
                j2 = idx_map_next[I[j]]
                if B[i2, j2] < 0.5:
                    # add a loss of ReLU(+deltaA[i, j])^2 if there should
                    # be no edge
                    loss = loss + torch.sum(torch.pow(torch.nn.functional.relu(deltaA[i, j]), 2))
                else:
                    # add a loss of ReLU(-deltaA[i, j]+1)^2 if there should
                    # be an edge
                    loss = loss + torch.pow(torch.nn.functional.relu(-deltaA[i, j]+1.), 2)
    else:
        # compute the output of the GEN for the current graph
        deltaX, deltaA, edge_filters = gen(torch.tensor(A, dtype=torch.float))
        # compute an index map for the current graph
        idx_map = {}
        for i in range(len(I)):
            idx_map[I[i]] = i
        # compute the expected deltaX and filters
        deltaX_expected = torch.zeros(len(I))
        filter_expected = -torch.ones(len(I))
        for i in range(len(J)):
            if J[i] not in idx_map:
                continue
            i2 = idx_map[J[i]]
            for j in np.where(B[i+1:] > 0.5)[0]:
                if J[j+i+1] not in idx_map:
                    # if i makes a connection to a node that does not exist
                    # in A, we expect a node insertion
                    deltaX_expected[i2] = 1.
                else:
                    j2 = idx_map[J[j+i+1]]
                    # otherwise we expect that out_filter[i] and
                    # in_filter[j] are positive
                    filter_expected[i2] = 1.
                    filter_expected[j2] = 1.
        # add a loss of N * ReLU(-deltaX[i] + 1.)^2 if deltaX[i] should be
        # positive
        mask = deltaX_expected > 0.5
        loss = len(I) * torch.sum(torch.pow(torch.nn.functional.relu(-deltaX[mask]+1.), 2))
        # add a loss of N * ReLU(deltaX[i])^2 if deltaX[i] should be
        # zero
        mask = deltaX_expected < 0.5
        loss = loss + len(I) * torch.sum(torch.pow(torch.nn.functional.relu(deltaX[mask]), 2))
        # add a loss of N * ReLU(-edge_filters[i, :] + .5)^2 if
        # edge_filters[i] should be positive.
        mask = filter_expected > 0.
        loss = loss + len(I) * torch.sum(torch.pow(torch.nn.functional.relu(-edge_filters[mask, 0] + .5), 2))
        loss = loss + len(I) * torch.sum(torch.pow(torch.nn.functional.relu(-edge_filters[mask, 1] + .5), 2))
        # add a loss of N * ReLU(+edge_filters[i, :] + .5)^2 if
        # edge_filters[i] should be negative.
        mask = filter_expected <= 0.
        loss = loss + len(I) * torch.sum(torch.pow(torch.nn.functional.relu(edge_filters[mask, 0], 1 + .5), 2))
        loss = loss + len(I) * torch.sum(torch.pow(torch.nn.functional.relu(edge_filters[mask, 1], 1 + .5), 2))

        # compute an index map for the next graph
        idx_map_next = {}
        for i in range(len(J)):
            idx_map_next[J[i]] = i

        # now add the edge loss only for those edges where we have an
        # edge prediction
        if isinstance(gen._filter_edge_edits, int):
            if torch.sum(edge_filters[:, 0] > 0.) > gen._filter_edge_edits:
                # if there are too many filtered nodes, limit to the top K
                out_filtered = torch.argsort(edge_filters[:, 0], descending = True)[:gen._filter_edge_edits]
            else:
                out_filtered = torch.where(edge_filters[:, 0] > 0.)[0]
            if torch.sum(edge_filters[:, 1] > 0.) > gen._filter_edge_edits:
                in_filtered  = torch.argsort(edge_filters[:, 1], descending = True)[:gen._filter_edge_edits]
            else:
                in_filtered = torch.where(edge_filters[:, 1] > 0.)[0]
        else:
            out_filtered = torch.where(edge_filters[:, 0] > 0.)[0]
            in_filtered  = torch.where(edge_filters[:, 1] > 0.)[0]
        for i in range(len(out_filtered)):
            if I[out_filtered[i]] not in idx_map_next:
                continue
            i2 = idx_map_next[I[out_filtered[i]]]
            for j in range(len(in_filtered)):
                if I[in_filtered[j]] not in idx_map_next:
                    continue
                j2 = idx_map_next[I[in_filtered[j]]]
                if B[i2, j2] < 0.5:
                    # add a loss of ReLU(+deltaA[i, j])^2 if there should
                    # be no edge
                    loss = loss + torch.pow(torch.nn.functional.relu(deltaA[i, j]), 2)
                else:
                    # add a loss of ReLU(-deltaA[i, j]+1)^2 if there should
                    # be an edge
                    loss = loss + torch.pow(torch.nn.functional.relu(-deltaA[i, j]+1.), 2)
    # return the loss
    return loss


def evaluate_model(gen,df, year, month,day, past = 7):
    """ Evaluates the given graph edit network on the given year and month
    of the HEP-Th dataset. The resulting score is the mean average precision
    as computed by Goyal et al.

    Parameters
    ----------
    gen: class pytorch_graph_edit_network.GEN
        A graph edit network.
    year: int
        A year in the range 1992-2003
    month: int
        A month in the range 1-12
    past: int (default = 12)
        The number of month in the past we consider to construct the initial
        collaboration graph that is fed into the GEN.

    Returns
    -------
    map: double
        The mean average precision of the input GEN in predicting edges for
        the input graph.

    """
    if past < 1:
        raise ValueError('Expected a strictly positive integer for past')
    # construct the current collaboration graph from the past
    t = _day_strings.index('2004-{:0>2}-{:0>2}'.format(month,day))
    if t <= 0:
        raise ValueError('Expected input time in the range 1992-2 until 2003-4')
    if t < past:
        past_days = _day_strings[:t]
    else:
        past_days = _day_strings[(t-past):t]
    A, I = read_graph_from_txt(df, past_days[0], past_days[0])
    # A, I = read_graph_from_csv('hep-th/graphs/%s.csv' % past_days[0])
    for tau in range(1, len(past_days)-1):
        # parse the current graph from txt data
        B, J = read_graph_from_txt(df, past_days[tau], past_days[tau])
        # add B, J to A, I
        A, I = add_graph(A, I, B, J)
    # parse the next graph from txt data
    B, J = read_graph_from_txt(df, _day_strings[t], _day_strings[t])
    # build an index map from global node indices to I and J
    idx_map_I = {}
    for i in range(len(I)):
        idx_map_I[I[i]] = i
    idx_map_J = {}
    for j in range(len(J)):
        idx_map_J[J[j]] = j

    # build the actual adjacency list
    actual_adj = []
    for i in range(len(I)):
        adj_i = []
        actual_adj.append(adj_i)
        if I[i] not in idx_map_J:
            continue
        i2 = idx_map_J[I[i]]
        for j2 in np.where(B[i2, :] > 0.5)[0]:
            if J[j2] not in idx_map_I:
                if len(I)+1 not in adj_i:
                    adj_i.append(len(I)+1)
            else:
                adj_i.append(idx_map_I[J[j2]])

    # compute the output of the GEN for the current graph
    deltaX, deltaA = gen(torch.tensor(A, dtype=torch.float))
    #
    # compute the filtered edges
    # if isinstance(gen._filter_edge_edits, int):
    #     if torch.sum(edge_filters[:, 0] > 0.) > gen._filter_edge_edits:
    #         # if there are too many filtered nodes, limit to the top K
    #         out_filtered = torch.argsort(edge_filters[:, 0], descending = True)[:gen._filter_edge_edits]
    #     else:
    #         out_filtered = torch.where(edge_filters[:, 0] > 0.)[0]
    #     if torch.sum(edge_filters[:, 1] > 0.) > gen._filter_edge_edits:
    #         in_filtered  = torch.argsort(edge_filters[:, 1], descending = True)[:gen._filter_edge_edits]
    #     else: 
    #         in_filtered = torch.where(edge_filters[:, 1] > 0.)[0]
    # else:
    #     out_filtered = torch.where(edge_filters[:, 0] > 0.)[0]
    #     in_filtered  = torch.where(edge_filters[:, 1] > 0.)[0]

    # build the predicted adjacency list
    predicted_adj = []
    for i in range(len(I)):
        predicted_adj.append([])
    # for i in range(len(out_filtered)):
    #     for j in range(len(in_filtered)):
    #         if deltaA[i, j] > 0.5:
    #             predicted_adj[out_filtered[i]].append((in_filtered[j].item(), deltaA[i, j].item()))
    for i in range(len(I)):
        if deltaX[i] > 0.5:
            predicted_adj[i].append((len(I)+1, deltaX[i].item()))

    # then return the MAP
    return computeMAP(predicted_adj, actual_adj)


# This evaluation code emulates the code of Goyal and colleagues, just with a
# slightly different data format. In particular, the original code can be
# found at
# https://github.com/palash1992/DynamicGEM/blob/master/dynamicgem/evaluation/metrics.py
def computeMAP(predicted_adj, actual_adj, max_k=-1):
    """ Compares a predicted adjacency list with an actual adjacency list,
    taking ranks into account, and returns the mean average precision.

    Parameters
    ----------
    predicted_adj: list
        An adjacency list, i.e. a list of tuples for each node in the graph,
        where the first entry in each list is a target index
        and the second entry is a score, where higher scores mean that this
        entry is predicted with higher likelihood.
    actual_adj: list
        The actual adjacency list of the target graph.
    max_k: int (default = -1)
        The maximum rank considered. If set to -1, all len(predicted_adj)
        entries are considered.

    Returns
    -------
    precision_scores: list
        A list of precision scores of length min(max_k, len(predicted_adj)).
        Every entry precision_scores[k] contains the number of correctly
        predicted edges divided in predicted_adj[:k] divided by k+1.
    delta_factors: list
        A list of numeric scores, indicating whether the prediction at rank k
        was correct (1.0) or incorrect (0.0).

    """
    node_num = len(actual_adj)
    node_AP = [0.0] * node_num
    count = 0
    for i in range(node_num):
        if len(actual_adj[i]) == 0:
            continue
        count += 1
        precision_scores, delta_factors = computePrecisionCurve(predicted_adj[i], actual_adj[i], max_k)
        precision_rectified = [p * d for p, d in zip(precision_scores, delta_factors)]
        if (sum(delta_factors) < 1E-3):
            node_AP[i] = 0
        else:
            node_AP[i] = float(sum(precision_rectified) / sum(delta_factors))
    return sum(node_AP) / count

