import numpy as np
import yaml

class SLMConfig:
    def __init__(self, name, monitor_num, pixel_pitch, npixels):
        self.name = name
        self.monitor = monitor_num
        self.pixel_pitch = pixel_pitch
        self.npixels = npixels # 1 x 2 list with x then y

    @staticmethod
    def from_npy_file(self, fname):
        # compatibility with old format
        settings = np.load(fname).item()
        pixel_pitch = settings['pixel pitch']
        npixels = [settings['SLM resX'], settings['SLM resY']]
        return SLMConfig(None, None, pixel_pitch, npixels)

    @staticmethod
    def from_yml_file(self, fname, dev_name):
        fhdl = open(fname, 'r')
        res = yaml.load(fhdl, Loader=yaml.FullLoader)
        fhdl.close()
        devs = res["devices"]
        if dev_name in devs:
            settings = devs[dev_name]
            name = dev_name
            monitor = settings["monitor"]
            pixel_pitch = settings["pixel_pitch"]
            npixels = settings["npixels"]
        else:
            raise Exception('Device config not found')
        return SLMConfig(name, monitor, pixel_pitch, npixels)
