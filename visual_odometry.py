"""
* This file is part of PYSLAM 
*
* Copyright (C) 2016-present Luigi Freda <luigi dot freda at gmail dot com> 
*
* PYSLAM is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* PYSLAM is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with PYVO. If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np 
import cv2
from enum import Enum

from feature_tracker import TrackerTypes, TrackResult
from geom_helpers import poseRt
from timer import TimerFps

class VoStage(Enum):
    NO_IMAGES_YET   = 0     # no image received 
    GOT_FIRST_IMAGE = 1     # got first image, we can proceed in a normal way (match current image with previous image)
    
kVerbose=True     
kMinNumFeature = 2000
kRansacThresholdNormalized = 0.0003  # metric threshold used for normalized image coordinates 
kRansacThresholdPixels = 0.1         # pixel threshold used for image coordinates 
kAbsoluteScaleThreshold = 0.1        # absolute translation scale; it is also the minimum translation norm for an accepted motion 
kUseEssentialMatrixEstimation = True # using the essential matrix fitting algorithm is more robust RANSAC given five-point algorithm solver 
kRansacProb = 0.999
kUseGroundTruthScale = True 


class VisualOdometry(object):
    def __init__(self, cam, grountruth, feature_tracker):
        self.stage = VoStage.NO_IMAGES_YET
        self.cam = cam
        self.cur_image = None   # current image
        self.prev_image = None  # previous/reference image

        self.kp_ref = None  # reference keypoints 
        self.des_ref = None # refeference descriptors 
        self.kp_cur = None  # current keypoints 
        self.des_cur = None # current descriptors 

        self.cur_R = np.eye(3,3) # current rotation 
        self.cur_t = np.zeros((3,1))        # current translation 

        self.trueX, self.trueY, self.trueZ = None, None, None
        self.grountruth = grountruth
        
        self.feature_tracker = feature_tracker
        self.track_result = None 

        self.mask_match = None # mask of matched keypoints used for drawing 
        self.draw_img = None 

        self.init_history = True 
        self.poses = []       # history of poses
        self.t0_est = None    # history of estimated translations      
        self.t0_gt = None     # history of ground truth translations (if available)
        self.traj3d_est = []  # history of estimated translations centered w.r.t. first one
        self.traj3d_gt = []   # history of estimated ground truth translations centered w.r.t. first one     

        self.timer_verbose = False # set this to True if you want to print timings 
        self.timer_main = TimerFps('VO', is_verbose = self.timer_verbose)
        self.timer_pose_est = TimerFps('PoseEst', is_verbose = self.timer_verbose)
        self.timer_feat = TimerFps('Feature', is_verbose = self.timer_verbose)

    # get current translation scale from ground-truth if grountruth is not None 
    def getAbsoluteScale(self, frame_id):  
        if self.grountruth is not None and kUseGroundTruthScale:
            self.trueX, self.trueY, self.trueZ, scale = self.grountruth.getPoseAndAbsoluteScale(frame_id)
            return scale
        else:
            self.trueX = 0 
            self.trueY = 0 
            self.trueZ = 0
            return 1

    def computeFundamentalMatrix(self, kp_ref, kp_cur):
            F, mask = cv2.findFundamentalMat(kp_ref, kp_cur, cv2.FM_RANSAC, param1=kRansacThresholdPixels, param2=kRansacProb)
            if F is None or F.shape == (1, 1):
                # no fundamental matrix found
                raise Exception('No fundamental matrix found')
            elif F.shape[0] > 3:
                # more than one matrix found, just pick the first
                F = F[0:3, 0:3]
            return np.matrix(F), mask 	

    def removeOutliersFromMask(self, mask): 
        if mask is not None:    
            n = self.kpn_cur.shape[0]     
            mask_index = [ i for i,v in enumerate(mask) if v > 0]    
            self.kpn_cur = self.kpn_cur[mask_index]           
            self.kpn_ref = self.kpn_ref[mask_index]           
            if self.des_cur is not None: 
                self.des_cur = self.des_cur[mask_index]        
            if self.des_ref is not None: 
                self.des_ref = self.des_ref[mask_index]  
            if kVerbose:
                print('removed ', n-self.kpn_cur.shape[0],' outliers')                

    # fit essential matrix E with RANSAC such that:  p2.T * E * p1 = 0  where  E = [t21]x * R21
    # out: [Rrc, trc]   (with respect to 'ref' frame) 
    # N.B.1: trc is estimated up to scale (i.e. the algorithm always returns ||trc||=1, we need a scale in order to recover a translation which is coherent with the previous estimated ones)
    # N.B.2: this function have problems in the following cases: [see Hartley/Zisserman Book]
    # - 'geometrical degenerate correspondences', e.g. all the observed features lie on a plane (the correct model for the correspondences is an homography) or lie a ruled quadric 
    # - degenerate motions such a pure rotation (a sufficient parallax is required) or an infinitesimal viewpoint change (where the translation is almost zero)
    # N.B.3: the five-point algorithm (used for estimating the Essential Matrix) seems to work well even in the degenerate planar case
    def estimatePose(self, kp_ref, kp_cur):	
        kp_ref_u = self.cam.undistortPoints(kp_ref)	
        kp_cur_u = self.cam.undistortPoints(kp_cur)	        
        self.kpn_ref = self.cam.unprojectPoints(kp_ref_u)
        self.kpn_cur = self.cam.unprojectPoints(kp_cur_u)
        if kUseEssentialMatrixEstimation:
            # the essential matrix algorithm is more robust since it uses the five-point algorithm solver by D. Nister
            E, self.mask_match = cv2.findEssentialMat(self.kpn_cur, self.kpn_ref, focal=1, pp=(0., 0.), method=cv2.RANSAC, prob=kRansacProb, threshold=kRansacThresholdNormalized)
        else:
            # just for the hell of testing it
            F, self.mask_match = self.computeFundamentalMatrix(kp_cur_u, kp_ref_u)
            E = self.cam.K.T @ F @ self.cam.K    # E = K.T * F * K 
        #self.removeOutliersFromMask(self.mask)  # do not remove outliers, the last features can be matched and recognized as inliers in subsequent frames                          
        _, R, t, mask = cv2.recoverPose(E, self.kpn_cur, self.kpn_ref, focal=1, pp=(0., 0.))   
        return R,t  # Rrc, trc (with respect to 'ref' frame) 		

    def processFirstFrame(self):
        # only detect on the current image 
        self.kp_ref, self.des_ref = self.feature_tracker.detect(self.cur_image)
        # convert from list of keypoints to an array of points 
        self.kp_ref = np.array([x.pt for x in self.kp_ref], dtype=np.float32) 
        self.draw_img = self.drawFeatureTracks(self.cur_image)

    def processFrame(self, frame_id):
        # track features 
        self.timer_feat.start()
        self.track_result = self.feature_tracker.track(self.prev_image, self.cur_image, self.kp_ref, self.des_ref)
        self.timer_feat.refresh()
        # estimate pose 
        self.timer_pose_est.start()
        R, t = self.estimatePose(self.track_result.kp_ref_matched, self.track_result.kp_cur_matched)     
        self.timer_pose_est.refresh()
        # update keypoints history  
        self.kp_ref = self.track_result.kp_ref
        self.kp_cur = self.track_result.kp_cur
        self.des_cur = self.track_result.des_cur                   
        if kVerbose:        
            print('# matched points: ', self.kpn_ref.shape[0])      
        # t is estimated up to scale (i.e. the algorithm always returns ||trc||=1, we need a scale in order to recover a translation which is coherent with the previous estimated ones)
        absolute_scale = self.getAbsoluteScale(frame_id)
        if(absolute_scale > kAbsoluteScaleThreshold):
            # compose absolute motion [Rwa,twa] with estimated relative motion [Rab,s*tab] (s is the scale extracted from the ground truth)
            # [Rwb,twb] = [Rwa,twa]*[Rab,tab] = [Rwa*Rab|twa + Rwa*tab]
            print('estimated t with norm |t|: ', np.linalg.norm(t))
            self.cur_t = self.cur_t + absolute_scale*self.cur_R.dot(t) 
            self.cur_R = self.cur_R.dot(R)       
        # draw image         
        self.draw_img = self.drawFeatureTracks(self.cur_image) 
        # check if we have enough features to track otherwise detect new ones and start tracking from them (used for LK tracker) 
        if (self.feature_tracker.tracker_type == TrackerTypes.LK) and (self.kp_ref.shape[0] < self.feature_tracker.min_num_features): 
            self.kp_cur, self.des_cur = self.feature_tracker.detect(self.cur_image)           
            self.kp_cur = np.array([x.pt for x in self.kp_cur], dtype=np.float32) # convert from list of keypoints to an array of points   
            if kVerbose:     
                print('# detected points: ', self.kp_cur.shape[0])                  
        self.kp_ref = self.kp_cur
        self.des_ref = self.des_cur
        self.updateHistory()           
        

    def track(self, img, frame_id):
        if kVerbose:
            print('..................................')
            print('frame: ', frame_id) 
        # convert image to gray if needed    
        if img.ndim>2:
            img = cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)             
        # check coherence of image size with camera settings 
        assert(img.ndim==2 and img.shape[0]==self.cam.height and img.shape[1]==self.cam.width), "Frame: provided image has not the same size as the camera model or image is not grayscale"
        self.cur_image = img
        # manage and check stage 
        if(self.stage == VoStage.GOT_FIRST_IMAGE):
            self.processFrame(frame_id)
        elif(self.stage == VoStage.NO_IMAGES_YET):
            self.processFirstFrame()
            self.stage = VoStage.GOT_FIRST_IMAGE            
        self.prev_image = self.cur_image    
        # update main timer (for profiling)
        self.timer_main.refresh()  
  

    def drawFeatureTracks(self, img, reinit = False):
        draw_img = cv2.cvtColor(img,cv2.COLOR_GRAY2RGB)
        num_outliers = 0        
        if(self.stage == VoStage.GOT_FIRST_IMAGE):            
            if reinit:
                for p1 in self.kp_cur:
                    a,b = p1.ravel()
                    cv2.circle(draw_img,(a,b),1, (0,255,0),-1)                    
            else:    
                for i,pts in enumerate(zip(self.track_result.kp_ref_matched, self.track_result.kp_cur_matched)):
                    drawAll = False # set this to true if you want to draw outliers 
                    if self.mask_match[i] or drawAll:
                        p1, p2 = pts 
                        a,b = p1.ravel()
                        c,d = p2.ravel()
                        cv2.line(draw_img, (a,b),(c,d), (0,255,0), 1)
                        cv2.circle(draw_img,(a,b),1, (0,0,255),-1)   
                    else:
                        num_outliers+=1
            if kVerbose:
                print('# outliers: ', num_outliers)     
        return draw_img            

    def updateHistory(self):
        if (self.init_history is True) and (self.trueX is not None):
            self.t0_est = np.array([self.cur_t[0], self.cur_t[1], self.cur_t[2]])  # starting translation 
            self.t0_gt  = np.array([self.trueX, self.trueY, self.trueZ])           # starting translation 
            self.init_history = False 
        if (self.t0_est is not None) and (self.t0_gt is not None):             
            p = [self.cur_t[0]-self.t0_est[0], self.cur_t[1]-self.t0_est[1], self.cur_t[2]-self.t0_est[2]]   # the estimated traj starts at 0
            self.traj3d_est.append(p)
            self.traj3d_gt.append([self.trueX-self.t0_gt[0], self.trueY-self.t0_gt[1], self.trueZ-self.t0_gt[2]])        
            self.poses.append(poseRt(self.cur_R, p))   
