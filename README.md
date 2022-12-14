# PySLAM
This a revised version of PySLAM for our mission. The original README file is [here](README_PySLAM.md).

## 1. Motivation
Kapture-localization can provide a trajectory for all poses with high absolute accuracy. ORB-SLAM2 (VO) can provide a trajectory with high relative accuracy but without a scale. When we perform the posegraph using both of the trajectories, it's hard for us to recover the right scale and let the scale not absorb the error at the same time because the trajectory generated by Kapture-localization has a bad smooth consistency.

Our basic idea is that we give VO a good initialization with a good scale using good 3D points generated by Kapture-localization. In this case, the output trajectory of VO would have a good scale by itself so that we don't need to put scale as a parameter needing to be optimized in the later posegraph.

## 2. Pipeline
After Kapture-localization generated all the results (make sure your Kapture-localization code is using my [r2d2 repository](https://github.com/ZiyunGe1999/r2d2) to generate the r2d2 features),
- Revise [config.ini](config.ini). The main setting would be:
```
[FOLDER_DATASET]
type=folder 
base_path=/data/MUTC_resized_informative_features/query1/sensors/records_data/images
kapture_dataset_path=/data/MUTC_resized_informative_features/query1
colmap_dataset_path=/data/working_dir_MUTC_resized/MUTC_resized/colmap-localize-query1/r2d2_WASF_N8_big/Resnet101-AP-GeM-LM18/colmap_localized/reconstruction
cam_settings=settings/MUTC.yaml
groundtruth_file=groundtruth.txt
fps=30
```
I add two new parameters which are `kapture_data_path` and `colmap_dataset_path`. `kapture_data_path` is the path to the query images' R2D2 features including descriptors, positions and so on. `colmap_dataset_path` is the path to the reconstruction results including images.txt and points3D.txt.
- Build the docker image (Skip if you already have had one)
```
make docker_build
```
- Revise the loaded data path in [Makefile](Makefile)
```
-v <LOCAL/DATA/PATH>:/data
```
- Enter docker environment and run the python command
```
make enter_docker_env
python3 -O main_slam.py
```
## 3. Output
The output is a trajectory in the `output/` subfolder named `trajectory.txt`. The format for one line is pretty simple.
```
image_name Twc[0][0] Twc[0][1] Twc[0][2] Twc[0][3] Twc[1][0] Twc[1][1] Twc[1][2] Twc[1][3] Twc[2][0] Twc[2][1] Twc[2][2] Twc[2][3] Twc[3][0] Twc[3][1] Twc[3][2] Twc[3][3]
```
`Twc` is the homogeneous transformation from camera to world.