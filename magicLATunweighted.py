"""
--------------------------------------------------------------------------------
MAGIC-LAT implementation with unweighted adjacency matrix.
--------------------------------------------------------------------------------

Description: Implements MAGIC-LAT and associated sub-functions.

Requirements: numpy, math, scipy

File: magicLATunweighted.py

Author: Jennifer Hellar
Email: jenniferhellar@gmail.com
--------------------------------------------------------------------------------
"""

import numpy as np
import math

# nearest-neighbor interpolation
from scipy.interpolate import griddata

# KD-Tree for mapping to nearest point
from scipy.spatial import cKDTree



def edgeMatrix(coordinateMatrix, connectivityMatrix):
	"""
	Computes a list of edges in the graph, based on the triangles in
	connectivityMatrix.  Returns a numpy array of the edges and a list 
	of triangles associated with each edge..
	"""
	edges = []
	triangles = []

	for tri in connectivityMatrix:	# a triangle is a triplet of vertex indices

		idx0 = int(tri[0])	# indices of vertices 0, 1, and 2 in triangle
		idx1 = int(tri[1])
		idx2 = int(tri[2])

		# edges and corresponding deltaLATs
		e1 = set([idx0, idx1])
		e2 = set([idx1, idx2])
		e3 = set([idx0, idx2])

		# check if first edge seen before
		if (e1 not in edges):
			edges.append(e1)
			triangles.append([tri])
		else:
			k = edges.index(e1)
			triangles[k].append(tri)

		# repeat for second edge
		if (e2 not in edges):
			edges.append(e2)
			triangles.append([tri])
		else:
			k = edges.index(e2)
			triangles[k].append(tri)

		# repeat for third edge
		if (e3 not in edges):
			edges.append(e3)
			triangles.append([tri])
		else:
			k = edges.index(e3)
			triangles[k].append(tri)

	return [np.array(edges), triangles]


def updateEdges(V, E, latTiled, knownV, thresh, returnMidpoints=False):
	"""
	Updates the edges in a graph based on known signal values, removing
	edges with a delta > thresh with measured values <15cm away. Optionally 
	returns midpoints of removed edges.

	V: array of vertex coordinates
	E: array of edges
	latTiled: list of all vertex values
	knownV: list of measured signal values
	thresh: threshold to remove edges
	"""
	newE = []

	if returnMidpoints:
		excl_midpt = []

	# KD Tree to find the nearest known mesh vertex
	coordKDtree = cKDTree(knownV)

	for i in range(len(E)):
		e = list(E[i])
		v_i = e[0]	# vertex indices
		v_j = e[1]
		lat_i = latTiled[v_i]	# lat values (tiled manifold)
		lat_j = latTiled[v_j]

		[x1, y1, z1] = V[v_i, :]	# vertex coordinates
		[x2, y2, z2] = V[v_j, :]

		# find distance from nearest known point to vertex i
		[di, ni] = coordKDtree.query([x1, y1, z1], k=2)
		if di[0] > 0:
			di = di[0]
		else:
			di = di[1]	# first point found may be itself
		# find distance from nearest known point to vertex j
		[dj, nj] = coordKDtree.query([x2, y2, z2], k=2)
		if dj[0] > 0:
			dj = dj[0]
		else:
			dj = dj[1]	# first point found may be itself

		if (abs(lat_j - lat_i) < thresh) or (di > 15) or (dj > 15):
		# if (abs(lat_j - lat_i) < thresh):
			newE.append(e)
		elif returnMidpoints:
			[x, y, z] = [float(x1+x2)/2, float(y1+y2)/2, float(z1+z2)/2]
			excl_midpt.append([x, y, z])

	if returnMidpoints:
		return [np.array(newE), np.array(excl_midpt)]
	else:
		return np.array(newE)


def getUnWeightedAdj(n, edges):
	""" Computes the binary adjacency matrix """
	A = np.zeros((n, n))

	for i in range(len(edges)):

		e = list(edges[i])	# list of edges
		v_i = e[0]	# vertices given as indices
		v_j = e[1]

		A[v_i, v_j] = 1
		A[v_j, v_i] = 1

	return A


def magicLATunweighted(V, F, trIdx, trCoord, trLAT, edgeThreshold=50, alpha=1e-5, beta=1e-2):

	N = len(V)	# number of vertices in the graph
	M = len(trIdx)			# number of signal samples

	IDX = [i for i in range(N)]
	COORD = [V[i] for i in IDX]
	lat = np.zeros((N,1))

	trCoord = [V[i] for i in trIdx]

	# (short) lists of sampled vertices, coordinates, and  LAT values
	for i in range(M):
		verIdx = trIdx[i]
		lat[verIdx] = trLAT[i]

	# NN interpolation of unknown vertices
	latNN = [0 for i in range(N)]
	unknownCoord = [COORD[i] for i in range(N) if i not in trIdx]
	unknownCoord = griddata(np.array(trCoord), np.array(trLAT), np.array(unknownCoord), method='nearest')
	currIdx = 0
	for i in range(N):
		if i not in trIdx:
			latNN[i] = unknownCoord[currIdx]
			currIdx += 1
		else:
			latNN[i] = lat[i]

	[E, triangles] = edgeMatrix(V, F)
	edges = updateEdges(V, E, latNN, trCoord, edgeThreshold)

	A = getUnWeightedAdj(N, edges)

	D = np.diag(A.sum(axis=1))

	L = D - A

	latEst = np.zeros((N,1))

	M_l = np.zeros((N,N))
	M_u = np.zeros((N,N))

	for i in range(N):
		if i in trIdx:
			M_l[i,i] = float(1)
		else:
			M_u[i,i] = float(1)


	T = np.linalg.inv(M_l + alpha*M_u + beta*L)

	latEst = np.matmul(T, lat)

	for i in range(N):
		if i in trIdx:
			latEst[i] = lat[i]

	return latEst
