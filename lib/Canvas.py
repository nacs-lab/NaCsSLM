import numpy as np

class Canvas:
    # Wrapper around an image with some metadata
    def __init__(self, npixels):
        # pixel_size is a unit conversion more or less
        # self.pixel_size = pixel_size
        # two element list of x and y
        # xcoords and ycoords are the x and y coordinates of each pixel. They are 0 indexed and go from 0 to npixels - 1
        # x coords are the rows and y coords are the columns
        self.npixels = npixels
        self.ycoords, self.xcoords = np.meshgrid(np.linspace(0, self.npixels[1] - 1, self.npixels[1]), np.linspace(0, self.npixels[0] - 1, self.npixels[0]))
        #self.img = np.zeros(self.npixels,dtype='uint8')
        self.amp = np.zeros(self.npixels)
        self.phase = np.zeros(self.npixels)

    def get_amp(self, data_type=None):
        if data_type is None:
            return self.amp
        else:
            return self.amp.astype(data_type)

    def get_phase(self, data_type=None):
        if data_type is None:
            return self.phase
        else:
            return self.phase.astype(data_type)

    def _check_shape(func):
        def fn(self, arr, *args):
            if arr.shape != tuple(self.npixels):
                raise Exception("Array shape doesn't match the shape of the array in the current Canvas")
            func(self, arr, *args)
        return fn

    @_check_shape
    def add_amp(self, arr):
        self.amp = self.amp + arr

    def add_fn_to_amp(self, fn):
        self.amp = self.amp + fn(self.xcoords, self.ycoords)

    @_check_shape
    def add_phase(self, arr):
        self.phase = self.phase + arr

    def add_fn_to_phase(self, fn):
        self.phase = self.phase + fn(self.xcoords, self.ycoords)

    @_check_shape
    def replace_amp(self, arr):
        self.amp = arr

    @_check_shape
    def replace_phase(self, arr):
        self.phase = arr

    def shape(self):
        return tuple(self.npixels)
