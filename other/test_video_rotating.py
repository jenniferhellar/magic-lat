
"""

DATA INDICES:
	Too large for my laptop:
		p031 = 0 (4-SINUS LVFAM)
		p032 = 1 (1-LVFAM LAT HYB), 2 (2-LVFAM INITIAL PVC), 3 (4-LVFAM SINUS)
		p037 = 10 (12-LV-SINUS)

	Testable:
		p033 = 4 (3-RV-FAM-PVC-A-NORMAL), 5 (4-RV-FAM-PVC-A-LAT-HYBRID)
		p034 = 6 (4-RVFAM-LAT-HYBRID), 7 (5-RVFAM-PVC), 8 (6-RVFAM-SINUS-VOLTAGE)
		p035 = 9 (8-SINUS)
		p037 = 11 (9-RV-SINUS-VOLTAGE)

Requirements: numpy, scipy, matplotlib, scikit-learn
"""

import os

import argparse

import numpy as np
import math
import random

from vedo import Plotter, Video, Points, Mesh
from vedo.pyplot import plot

# functions to read the files
from readMesh import readMesh
from readLAT import readLAT


import utils
import metrics
from const import DATADIR, DATAFILES
from magicLAT import magicLAT



EDGE_THRESHOLD			=		50

OUTDIR				 	=		'test_video_rotating_results'

""" Parse the input for data index argument. """
parser = argparse.ArgumentParser(
    description='Processes a single mesh file for comparison of MAGIC-LAT, GPR, and quLATi performance.')

parser.add_argument('-i', '--idx', required=True, default='11',
                    help='Data index to process. \
                    Default: 11')

parser.add_argument('-a', '--anomalies_removed', required=True, default=1,
                    help='Remove anomalous points (disable: 0, enable: 1). \
                    Default: 1')

parser.add_argument('-v', '--verbose', required=False, default=1,
                    help='Verbose output (disable: 0, enable: 1). \
                    Default: 1')

args = parser.parse_args()

PATIENT_IDX				=		int(vars(args)['idx'])
verbose					=		int(vars(args)['verbose'])
remove_anomalies		=		int(vars(args)['anomalies_removed'])

""" Obtain file names, patient number, mesh id, etc. """
(meshFile, latFile, ablFile) = DATAFILES[PATIENT_IDX]
nm = meshFile[0:-5]
patient = nm[7:10]
id = latFile.split('_')[3]

""" Create output directory for this script and subdir for this mesh. """
outSubDir = os.path.join(OUTDIR, 'p' + patient + '_' + id)
if not os.path.isdir(OUTDIR):
	os.makedirs(OUTDIR)
if not os.path.isdir(outSubDir):
	os.makedirs(outSubDir)

""" Read the files """
print('\nProcessing ' + nm + ' ...\n')
[vertices, faces] = readMesh(os.path.join(DATADIR, meshFile))
[OrigLatCoords, OrigLatVals] = readLAT(os.path.join(DATADIR, latFile))

if ablFile != '':
	ablFile = os.path.join(DATADIR, ablFile)
else:
	ablFile = None
	print('No ablation file available for this mesh... continuing...\n')

""" Pre-process the mesh and LAT samples. """
mesh = Mesh([vertices, faces])
mesh.c('grey')

n = len(vertices)

mapIdx = [i for i in range(n)]
mapCoord = [vertices[i] for i in mapIdx]

# Map the LAT samples to nearest mesh vertices
allLatIdx, allLatCoord, allLatVal = utils.mapSamps(mapIdx, mapCoord, OrigLatCoords, OrigLatVals)

M = len(allLatIdx)

# Identify and exclude anomalous LAT samples
anomalous = np.zeros(M)
if remove_anomalies:
	anomIdx = []	
	if PATIENT_IDX == 4:
		anomIdx = [25, 112, 159, 218, 240, 242, 264]
	elif PATIENT_IDX == 5:
		anomIdx = [119, 150, 166, 179, 188, 191, 209, 238]
	elif PATIENT_IDX == 6:
		anomIdx = [11, 12, 59, 63, 91, 120, 156]
	elif PATIENT_IDX ==7:
		anomIdx = [79, 98, 137, 205]
	elif PATIENT_IDX == 8:
		anomIdx = [10, 11, 51, 56, 85, 105, 125, 143, 156, 158, 169, 181, 210, 269, 284, 329, 336, 357, 365, 369, 400, 405]
	elif PATIENT_IDX == 9:
		anomIdx = [0, 48, 255, 322]
	else:
		anomalous = utils.isAnomalous(allLatCoord, allLatVal)
	anomalous[anomIdx] = 1
else:
	anomalous = [0 for i in range(M)]

numPtsIgnored = np.sum(anomalous)

latIdx = [allLatIdx[i] for i in range(M) if anomalous[i] == 0]
latCoords = [allLatCoord[i] for i in range(M) if anomalous[i] == 0]
latVals = [allLatVal[i] for i in range(M) if anomalous[i] == 0]

M = len(latIdx)

# For colorbar ranges
MINLAT = math.floor(min(latVals)/10)*10
MAXLAT = math.ceil(max(latVals)/10)*10
if PATIENT_IDX == 4 or PATIENT_IDX == 5 or PATIENT_IDX == 8 or PATIENT_IDX == 9:
	MAXLAT = MINLAT + math.ceil((3/4 * (max(latVals) - MINLAT)) / 10)*10
elif PATIENT_IDX == 6 or PATIENT_IDX == 7 or PATIENT_IDX == 11:
	MAXLAT = MINLAT + math.ceil((7/8 * (max(latVals) - MINLAT)) / 10)*10

# Create partially-sampled signal vector
mapLAT = [0 for i in range(n)]
for i in range(M):
	mapLAT[latIdx[i]] = latVals[i]


infoFile = os.path.join(outSubDir, 'p{}_info.txt'.format(patient))

with open(infoFile, 'w') as fid:
	fid.write('{:<30}{}\n'.format('file', nm))
	fid.write('{:<30}{:g}\n'.format('n', n))
	fid.write('{:<30}{:g}\n'.format('M', M))
	fid.write('{:<30}{:g}\n'.format('ignored', np.sum(anomalous)))

	fid.write('{:<30}{:g}\n'.format('EDGE_THRESHOLD', EDGE_THRESHOLD))


videoFile0 = os.path.join(outSubDir, 'p{}.mp4'.format(patient))
video0 = Video(videoFile0, duration=12, backend='opencv')


# patient 033
# cam0 = {'pos': (-157, 128, 123),
#            'focalPoint': (14.1, 75.8, 115),
#            'viewup': (0.0728, 0.0926, 0.993),
#            'distance': 179,
#            'clippingRange': (110, 267)}
# cam1 = {'pos': (181, 13.0, 130),
#            'focalPoint': (14.1, 75.8, 115),
#            'viewup': (-0.0213, 0.172, 0.985),
#            'distance': 179,
#            'clippingRange': (106, 273)}

# patient 037
cam0 = {'pos': (183, 166, 4.95),
           'focalPoint': (-0.954, 31.3, 163),
           'viewup': (0.333, -0.873, -0.356),
           'distance': 277,
           'clippingRange': (136, 456)}

cam1 = {'pos': (-157, -63.4, 372),
           'focalPoint': (-0.954, 31.3, 163),
           'viewup': (0.154, -0.938, -0.310),
           'distance': 277,
           'clippingRange': (145, 444)}


tr_i = []
sampLst = utils.getModifiedSampList(latVals)

# for m in range(1, M-1):
tr_i = random.sample(sampLst, 250)
tst_i = [i for i in range(M) if i not in tr_i]

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
latEst = magicLAT(vertices, faces, TrIdx, TrCoord, TrVal, EDGE_THRESHOLD)

magicDE = metrics.deltaE(TstVal, latEst[TstIdx], MINLAT, MAXLAT)

verPoints = Points(TrCoord, r=5).cmap('gist_rainbow', TrVal, vmin=MINLAT, vmax=MAXLAT).addScalarBar()
estPoints = Points(vertices, r=5).cmap('gist_rainbow', latEst, vmin=MINLAT, vmax=MAXLAT).addScalarBar()
coloredMesh = Mesh([vertices, faces])
coloredMesh.interpolateDataFrom(estPoints, N=1).cmap('gist_rainbow', vmin=MINLAT, vmax=MAXLAT).addScalarBar()


vplt0 = Plotter(N=1, bg='black', resetcam=True, sharecam=False, offscreen=True)
vplt0.show(coloredMesh, verPoints, title='Patient{}, Front View'.format(patient), camera=cam0)

# video0.action(cam1=cam0, cam2=cam1)
video0.action(azimuth_range=(0, 359))
video0.close()
vplt0.close()

