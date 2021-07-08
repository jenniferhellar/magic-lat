
"""
Requirements: numpy, scipy, matplotlib, scikit-learn
"""

import os

import numpy as np
import math
import random

# plotting packages
from vedo import *

# loading images
import cv2

# Gaussian process regression interpolation
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF

# functions to read the files
from readMesh import readMesh
from readLAT import readLAT


from utils import *
from const import *
from magicLAT import *



"""
p033 = 9
p034 = 14
p035 = 18
p037 = 21
"""
PATIENT_MAP				=		9

NUM_TRAIN_SAMPS 		= 		200
EDGE_THRESHOLD			=		50

outDir				 	=		'results_wip'

""" Read the files """
meshFile = meshNames[PATIENT_MAP]
latFile = latNames[PATIENT_MAP]
nm = meshFile[0:-5]
patient = nm[7:10]

print('Reading files for ' + nm + ' ...\n')
[vertices, faces] = readMesh(os.path.join(dataDir, meshFile))
[OrigLatCoords, OrigLatVals] = readLAT(os.path.join(dataDir, latFile))

n = len(vertices)

mapIdx = [i for i in range(n)]
mapCoord = [vertices[i] for i in mapIdx]

allLatIdx, allLatCoord, allLatVal = mapSamps(mapIdx, mapCoord, OrigLatCoords, OrigLatVals)

M = len(allLatIdx)

mesh = Mesh([vertices, faces])
# mesh.backColor('white').lineColor('black').lineWidth(0.25)
mesh.c('grey')

origLatPoints = Points(OrigLatCoords, r=10).cmap('rainbow_r', OrigLatVals, vmin=np.min(OrigLatVals), vmax=np.max(OrigLatVals)).addScalarBar()
latPoints = Points(allLatCoord, r=10).cmap('rainbow_r', allLatVal, vmin=np.min(allLatVal), vmax=np.max(allLatVal)).addScalarBar()

# KD Tree to find the nearest mesh vertex
k = 6
coordKDtree = cKDTree(allLatCoord)
[dist, nearestVers] = coordKDtree.query(allLatCoord, k=k)

anomalous = np.zeros(M)

for i in range(M):
	verCoord = allLatCoord[i]
	verVal = allLatVal[i]

	neighbors = [nearestVers[i, n] for n in range(1,k) if dist[i,n] < 5]

	adj = len(neighbors)

	cnt = 0
	for neighVer in neighbors:
		neighVal = allLatVal[neighVer]

		if abs(verVal - neighVal) > 50:
			cnt += 1
		else:
			break

	# if (cnt >= (len(neighbors)-1) and len(neighbors) > 1):	# differs from all but 1 neighbor by >50ms and has at least 2 neighbors w/in 5mm
	if cnt > 1 and adj > 1:
		anomalous[i] = 1
		# print(cnt, adj)

		# print(verVal, [allLatVal[neighVer] for neighVer in neighbors])

numPtsIgnored = np.sum(anomalous)

latIdx = [allLatIdx[i] for i in range(M) if anomalous[i] == 0]
latCoords = [allLatCoord[i] for i in range(M) if anomalous[i] == 0]
latVals = [allLatVal[i] for i in range(M) if anomalous[i] == 0]

M = len(latIdx)

print('{:<20}{:g}'.format('n', n))
print('{:<20}{:g}/{:g}'.format('m', NUM_TRAIN_SAMPS, M))
print('{:<20}{:g}'.format('ignored', numPtsIgnored))
# exit()

mapLAT = [0 for i in range(n)]
for i in range(M):
	mapLAT[latIdx[i]] = latVals[i]

edgeFile = 'E_p{}.npy'.format(patient)
if not os.path.isfile(edgeFile):
	[edges, TRI] = edgeMatrix(vertices, faces)

	print('Writing edge matrix to file...')
	with open(edgeFile, 'wb') as fid:
		np.save(fid, edges)
else:
	edges = np.load(edgeFile, allow_pickle=True)

if not os.path.isdir(outDir):
	os.makedirs(outDir)

sampLst = [i for i in range(M)]


tr_i = random.sample(sampLst, NUM_TRAIN_SAMPS)
tst_i = [i for i in sampLst if i not in tr_i]

# get vertex indices of labelled/unlabelled nodes
TrIdx = sorted(np.take(latIdx, tr_i))
TstIdx = sorted(np.take(latIdx, tst_i))

# get vertex coordinates
TrCoord = [vertices[i] for i in TrIdx]
TstCoord = [vertices[i] for i in TstIdx]

# get mapLAT signal values
TrVal = [mapLAT[i] for i in TrIdx]
TstVal = [mapLAT[i] for i in TstIdx]


""" MAGIC-LAT estimate """
latEst = magicLAT(vertices, faces, edges, TrIdx, TrCoord, TrVal, EDGE_THRESHOLD)

""" Create GPR kernel and regressor """
gp_kernel = RBF(length_scale=0.01) + RBF(length_scale=0.1) + RBF(length_scale=1)
gpr = GaussianProcessRegressor(kernel=gp_kernel, normalize_y=True)

""" GPR estimate """
# fit the GPR with training samples
gpr.fit(TrCoord, TrVal)

# predict the entire signal
latEstGPR = gpr.predict(vertices, return_std=False)


# For colorbar ranges
MINLAT = math.floor(min(allLatVal)/10)*10
MAXLAT = math.ceil(max(allLatVal)/10)*10

elev = 0
azimuth = 120
roll = -45

verPoints = Points(latCoords, r=10).cmap('rainbow_r', latVals, vmin=MINLAT, vmax=MAXLAT).addScalarBar()

"""
Figure 0: Ground truth (entire), training points, and MAGIC-LAT (entire)
"""
plt = Plotter(N=3, axes=9, offscreen=True)

# Plot 0: Ground truth
plt.show(mesh, verPoints, 'all known points', azimuth=azimuth, elevation=elev, roll=roll, at=0)

# Plot 1: Training points
trainPoints = Points(TrCoord, r=10).cmap('rainbow_r', TrVal, vmin=MINLAT, vmax=MAXLAT).addScalarBar()
plt.show(mesh, trainPoints, 'training points', at=1)

# Plot 2: MAGIC-LAT output signal
magicPoints = Points(vertices, r=10).cmap('rainbow_r', latEst, vmin=MINLAT, vmax=MAXLAT).addScalarBar()

plt.show(mesh, magicPoints, 'interpolation result', title='MAGIC-LAT', at=2, interactive=True)
plt.screenshot(filename=os.path.join(outDir, 'magic.png'), returnNumpy=False)
plt.close()


"""
Figure 1: Ground truth (entire), training points, and GPR (entire)
"""
plt = Plotter(N=3, axes=9, offscreen=True)

# Plot 0: Ground truth
plt.show(mesh, verPoints, 'all known points', azimuth=azimuth, elevation=elev, roll=roll, at=0)
# Plot 1: Training points
plt.show(mesh, trainPoints, 'training points', at=1)
# Plot 2: GPR output signal
gprPoints = Points(vertices, r=10).cmap('rainbow_r', latEstGPR, vmin=MINLAT, vmax=MAXLAT).addScalarBar()

plt.show(mesh, gprPoints, 'interpolation result', title='GPR', at=2, interactive=True)
plt.screenshot(filename=os.path.join(outDir, 'gpr.png'), returnNumpy=False)
plt.close()

# mesh.interpolateDataFrom(pts, N=1).cmap('rainbow_r').addScalarBar()
elev = 0
azim = [-60, 30, 120, 210]
roll = -45
whitemesh = Mesh([vertices, faces], c='black')
"""
Figure 2: Ground truth (test points only - for ssim)
"""
plt = Plotter(N=1, axes=0, offscreen=True)
testPoints = Points(TstCoord, r=20).cmap('rainbow_r', TstVal, vmin=MINLAT, vmax=MAXLAT)
for a in azim:
	plt.show(whitemesh, testPoints, azimuth=a, elevation=elev, roll=roll, title='true, azimuth={:g}'.format(a), bg='black')
	plt.screenshot(filename=os.path.join(outDir, 'true{:g}.png'.format(a)), returnNumpy=False)

plt.close()

"""
Figure 3: MAGIC-LAT estimate (test points only - for ssim)
"""
plt = Plotter(N=1, axes=0, offscreen=True)
testEst = Points(TstCoord, r=20).cmap('rainbow_r', latEst[TstIdx], vmin=MINLAT, vmax=MAXLAT)

for a in azim:
	plt.show(whitemesh, testEst, azimuth=a, elevation=elev, roll=roll, title='MAGIC-LAT, azimuth={:g}'.format(a), bg='black')
	plt.screenshot(filename=os.path.join(outDir, 'estimate{:g}.png'.format(a)), returnNumpy=False)

plt.close()

"""
Figure 4: GPR estimate (test points only - for ssim)
"""
plt = Plotter(N=1, axes=0, offscreen=True)
testEstGPR = Points(TstCoord, r=20).cmap('rainbow_r', latEstGPR[TstIdx], vmin=MINLAT, vmax=MAXLAT)

for a in azim:
	plt.show(whitemesh, testEstGPR, azimuth=a, elevation=elev, roll=roll, title='GPR, azimuth={:g}'.format(a), bg='black')
	plt.screenshot(filename=os.path.join(outDir, 'estimateGPR{:g}.png'.format(a)), returnNumpy=False)

plt.close()


"""
Figure 5: quLATi estimate (test points only for ssim)
"""
# TODO


"""
Error metrics
"""
# bin_edges = np.linspace(start=MINLAT, stop=MAXLAT, num=21, endpoint=True)

# nTst, bins = np.histogram(TstVal, bins=bin_edges)

# n, bins = np.histogram(latEst[TstIdx], bins=bin_edges)

# nGPR, bins = np.histogram(latEstGPR[TstIdx], bins=bin_edges)

# print(calcNMSE(nTst, n))
# print(calcNMSE(nTst, nGPR))

nmse = calcNMSE(TstVal, latEst[TstIdx])
nmseGPR = calcNMSE(TstVal, latEstGPR[TstIdx])

mae = calcMAE(TstVal, latEst[TstIdx])
maeGPR = calcMAE(TstVal, latEstGPR[TstIdx])

from matplotlib import pyplot as plt
b = [0, 0]
g = [0, 0]
r = [0, 0]

b_mean = [0, 0]
g_mean = [0, 0]
r_mean = [0, 0]

bins = 256

for a in azim:
	img = cv2.imread(os.path.join(outDir, 'true{:g}.png'.format(a)), cv2.IMREAD_GRAYSCALE)
	n_black_px = np.sum(img == 0)
	numpx = np.sum(img > 0)

	figTruth = cv2.imread(os.path.join(outDir, 'true{:g}.png'.format(a)))
	figEst = cv2.imread(os.path.join(outDir, 'estimate{:g}.png'.format(a)))
	figEstGPR = cv2.imread(os.path.join(outDir, 'estimateGPR{:g}.png'.format(a)))

	# Calculate histograms
	true_hist = np.zeros((3, bins))
	true_hist[0] = cv2.calcHist([figTruth],[0],None,[bins],[0,256]).ravel()
	true_hist[1] = cv2.calcHist([figTruth],[1],None,[bins],[0,256]).ravel()
	true_hist[2] = cv2.calcHist([figTruth],[2],None,[bins],[0,256]).ravel()
	true_hist[:,0] -= n_black_px

	magic_hist = np.zeros((3, bins))
	magic_hist[0] = cv2.calcHist([figEst],[0],None,[bins],[0,256]).ravel()
	magic_hist[1] = cv2.calcHist([figEst],[1],None,[bins],[0,256]).ravel()
	magic_hist[2] = cv2.calcHist([figEst],[2],None,[bins],[0,256]).ravel()
	magic_hist[:,0] -= n_black_px

	gpr_hist = np.zeros((3, bins))
	gpr_hist[0] = cv2.calcHist([figEstGPR],[0],None,[bins],[0,256]).ravel()
	gpr_hist[1] = cv2.calcHist([figEstGPR],[1],None,[bins],[0,256]).ravel()
	gpr_hist[2] = cv2.calcHist([figEstGPR],[2],None,[bins],[0,256]).ravel()
	gpr_hist[:,0] -= n_black_px

	true_mean = np.zeros((3, bins, 2))
	magic_mean = np.zeros((3, bins, 2))
	gpr_mean = np.zeros((3, bins, 2))

	for colorval in range(bins):
		for ch in range(3):
			pxls = np.column_stack(np.where(figTruth[:, :, ch] == colorval))
			if pxls.shape[0] == 0:
				true_mean[ch, colorval] = np.array([[0, 0]])
			else:
				true_mean[ch, colorval] = np.mean(pxls, axis=0)

			pxls = np.column_stack(np.where(figEst[:, :, ch] == colorval))
			if pxls.shape[0] == 0:
				magic_mean[ch, colorval] = np.array([[0, 0]])
			else:
				magic_mean[ch, colorval] = np.mean(pxls, axis=0)

			pxls = np.column_stack(np.where(figEstGPR[:, :, ch] == colorval))
			if pxls.shape[0] == 0:
				gpr_mean[ch, colorval] = np.array([[0, 0]])
			else:
				gpr_mean[ch, colorval] = np.mean(pxls, axis=0)	

	plt.subplot(321, title='Ground truth image'), plt.imshow(figTruth)
	plt.subplot(322, title='Ground truth histogram'),
	plt.plot(true_hist[0], 'b'), plt.plot(true_hist[1], 'g'), plt.plot(true_hist[2], 'r')
	plt.xlim([0,256])
	plt.subplot(323, title='MAGIC-LAT image'), plt.imshow(figEst)
	plt.subplot(324, title='MAGIC-LAT histogram'),
	plt.plot(magic_hist[0], 'b'), plt.plot(magic_hist[1], 'g'), plt.plot(magic_hist[2], 'r')
	plt.xlim([0,256])
	plt.subplot(325, title='GPR image'), plt.imshow(figEstGPR)
	plt.subplot(326, title='GPR histogram'),
	plt.plot(gpr_hist[0], 'b'), plt.plot(gpr_hist[1], 'g'), plt.plot(gpr_hist[2], 'r')
	plt.xlim([0,256])

	plt.tight_layout()
	plt.show()

	# true_hist = true_hist / numpx
	# magic_hist = magic_hist / numpx
	# gpr_hist = gpr_hist / numpx

	true_mean = true_mean / img.shape[0]
	magic_mean = magic_mean / img.shape[0]
	gpr_mean = gpr_mean / img.shape[0]

	true_spatio = np.zeros((3, bins, 3))
	magic_spatio = np.zeros((3, bins, 3))
	gpr_spatio = np.zeros((3, bins, 3))
	for ch in range(3):
		for bin in range(bins):
			true_spatio[ch, bin] = np.array([true_hist[ch, bin], true_mean[ch, bin, 0], true_mean[ch, bin, 1]])
			magic_spatio[ch, bin] = np.array([magic_hist[ch, bin], magic_mean[ch, bin, 0], magic_mean[ch, bin, 1]])
			gpr_spatio[ch, bin] = np.array([gpr_hist[ch, bin], gpr_mean[ch, bin, 0], gpr_mean[ch, bin, 1]])

	# print(np.sum(np.minimum(true_hist, magic_hist)))
	# print(np.sum(np.minimum(true_hist, gpr_hist)))

	print(cv2.compareHist(true_hist[0], magic_hist[0], cv2.HISTCMP_CORREL))
	print(cv2.compareHist(true_hist[0], gpr_hist[0], cv2.HISTCMP_CORREL))

	magic_hist_mse, magic_mean_mse = calcMSE(true_spatio, magic_spatio, multichannel=True)
	b[0] += magic_hist_mse[0][0]
	g[0] += magic_hist_mse[1][0]
	r[0] += magic_hist_mse[2][0]

	b_mean[0] += magic_mean_mse[0][0]
	g_mean[0] += magic_mean_mse[1][0]
	r_mean[0] += magic_mean_mse[2][0]

	gpr_hist_mse, gpr_mean_mse = calcMSE(true_spatio, gpr_spatio, multichannel=True)
	b[1] += gpr_hist_mse[0][0]
	g[1] += gpr_hist_mse[1][0]
	r[1] += gpr_hist_mse[2][0]

	b_mean[1] += gpr_mean_mse[0][0]
	g_mean[1] += gpr_mean_mse[1][0]
	r_mean[1] += gpr_mean_mse[2][0]

	# with np.printoptions(precision=10, suppress=True):
	# 	print(calcMSE(true_spatio, magic_spatio, multichannel=True))
	# 	print(calcMSE(true_spatio, gpr_spatio, multichannel=True))

t = len(azim)

with open(os.path.join(outDir, 'metrics_ex.txt'), 'w') as fid:
	fid.write('{:<20}{:<20}{:<20}\n\n'.format('Metric', 'MAGIC-LAT', 'GPR'))
	fid.write('{:<20}{:<20.6f}{:<20.6f}\n'.format('NMSE', nmse, nmseGPR))
	fid.write('{:<20}{:<20.6f}{:<20.6f}\n'.format('MAE', mae, maeGPR))

	fid.write('\n')
	fid.write('Color-Histogram\n')
	fid.write('{:<20}{:<20.6f}{:<20.6f}\n'.format('Avg. MSE, Blue', b[0]/t, b[1]/t))
	fid.write('{:<20}{:<20.6f}{:<20.6f}\n'.format('Avg. MSE, Green', g[0]/t, g[1]/t))
	fid.write('{:<20}{:<20.6f}{:<20.6f}\n'.format('Avg. MSE, Red', r[0]/t, r[1]/t))

	fid.write('\n')
	fid.write('Color-Mean-Locations\n')
	fid.write('{:<20}{:<20.6f}{:<20.6f}\n'.format('Avg. MSE, Blue', b_mean[0]/t, b_mean[1]/t))
	fid.write('{:<20}{:<20.6f}{:<20.6f}\n'.format('Avg. MSE, Green', g_mean[0]/t, g_mean[1]/t))
	fid.write('{:<20}{:<20.6f}{:<20.6f}\n'.format('Avg. MSE, Red', r_mean[0]/t, r_mean[1]/t))

