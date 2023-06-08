import numpy as np
import yaml

class AlgConfig:
    def __init__(self, name, grid_sz, loop_count, phase_fixed_threshold):
        self.name = name
        self.grid_sz = grid_sz
        self.loop_count = loop_count
        self.phase_fixed_threshold = phase_fixed_threshold # 0 for a constantly evolving phase

    @staticmethod
    def from_npy_file(self, fname):
        # compatibility with old format
        settings = np.load(fname).item()
        grid_sz = [settings['FFT grid size (bit)'], settings['FFT grid size (bit)']]
        loop_count = settings['Loop']
        phase_fixed_threshold = settings['WGS threshold']
        return AlgConfig(None, grid_sz, loop_count, phase_fixed_threshold)

    @staticmethod
    def from_yml_file(self, fname, dev_name):
        fhdl = open(fname, 'r')
        res = yaml.load(fhdl, Loader=yaml.FullLoader)
        fhdl.close()
        devs = res["devices"]
        if dev_name in devs:
            settings = devs[dev_name]
            name = dev_name
            grid_sz = settings["grid_sz"]
            loop_count = settings["loop_count"]
            phase_fixed_threshold = settings["phase_fixed_threshold"]
        else:
            raise Exception('Device config not found')
        return AlgConfig(name, grid_sz, loop_count, phase_fixed_threshold)
