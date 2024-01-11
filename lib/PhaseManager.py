import numpy as np
import slmsuite.holography.toolbox.phase
import utils
#from PIL import Image

class PhaseManager(object):
    def __init__(self, slm):
        self.slm = slm
        self.shape = slm.shape
        self.base = np.zeros(self.shape,dtype=np.float32)
        self.base_source = ''
        self.additional = np.zeros(self.shape,dtype=np.float32)
        self.add_log = [] # log for everything that has been added to this additional phase

    def set_base(self, base, source = ''):
        self.base = base
        self.base_source = source

    def get(self):
        return self.base + self.additional

    def reset_base(self):
        self.base = np.zeros(self.shape)
        self.base_source = ''

    def reset_additional(self):
        self.additional = np.zeros(self.shape)
        self.add_log = []

    def add_fresnel_lens(self, focal_length):
        phase= slmsuite.holography.toolbox.phase.lens(self.slm, focal_length)
        self.additional = self.additional + phase
        self.add_log.append(["fresnel_lens", focal_length])
    
    def add_zernike_poly(self, zernike_list):
        phase = slmsuite.holography.toolbox.phase.zernike_sum(self.slm, zernike_list, aperture="cropped")
        self.additional = self.additional + phase
        self.add_log.append(["zernike", zernike_list])

    def save_to_file(self, save_options, extra_info=None):
        full_path, full_path2 = utils.save_add_phase(self, save_options, extra_info)
        return full_path, full_path2

    def add_from_file(self, fname):
        #with Image.open(fname) as image:
        #    image_array = np.array(image)
        _,data = utils.load_add_phase(fname, 0, 1)
        self.additional = self.additional + data["phase"]
        self.add_log.append(["file", fname])






