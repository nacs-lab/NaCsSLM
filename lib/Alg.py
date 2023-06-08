import numpy as np
import scipy as sp

class Alg:
    def __init__(self, config, init_canvas, target_amp):
        #self.grid_sz = config.grid_sz
        self.loop_count = config.loop_count
        self.phase_fixed_threshold = config.phase_fixed_threshold # 0 for a constantly evolving phase
        self.canvas = init_canvas
        self.target = target_amp
        # find locations of target > 0
        idxs = np.where(target_amp > 0)
        target_locs = np.zeros(np.shape(target_amp))
        target_locs[idxs] = 1
        self.n_targets = len(idxs[0])
        self.target_locs = target_locs;
        self.incident_amp = self.canvas.get_amp()
        self.g_corr = np.ones_like(target_amp);

    def iterate(self, g_corr, fix_phase=0):
        # iteration of WGS. g_corr carries information from previous iterations
        init_field = np.multiply(self.canvas.get_amp(), np.exp(1j * self.canvas.get_phase()))
        fft_field = sp.fft.fftshift(sp.fft.fft2(init_field))
        fft_norm = np.sqrt(np.sum(np.square(np.abs(fft_field))))
        fft_field = fft_field / fft_norm
        fft_amp = np.abs(fft_field)
        mean_B = np.sum(np.multiply(fft_amp, self.target_locs)) / self.n_targets
        factor = np.divide(mean_B, fft_field, where=self.target_locs, out=np.ones_like(fft_field))
