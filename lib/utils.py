import yaml
import os
from datetime import datetime
from slmsuite.holography import toolbox
import numpy as np

def save_slm_calculation(hologram, save_options, extra_data = None):
    """

    """
    if not "config" in save_options:
        save_options["config"] = False
    if not "slm_pattern" in save_options:
        save_options["slm_pattern"] = False
    if not "ff_pattern" in save_options:
        save_options["ff_pattern"] = False
    if not "target" in save_options:
        save_options["target"] = False
    if not "path" in save_options:
        save_options["path"] = os.getcwd()
    if not "name" in save_options:
        save_options["name"] = ""
    if not "prefix" in save_options:
        now = datetime.now()
        save_options["prefix"] = now.strftime("%Y%m%d_%H%M%S")
    if not "crop" in save_options:
        save_options["crop"] = True

    full_path = None 
    full_path2 = None
    # Now, we gather all the information to save in the config
    if save_options["config"] is True:
        config_info = dict()
        config_info["method"] = hologram.method
        config_info["iteration"] = hologram.iter
        config_info["alg_settings"] = hologram.flags
        config_info["computational_shape"] = str(list(hologram.shape))
        config_info["slm_shape"] = str(list(hologram.slm_shape))
        config_info["save_options"] = save_options
        if extra_data is not None:
            config_info["extra_data"] = extra_data
        # Now perform the actual save:
        full_path = save_options["path"] + os.sep + save_options["prefix"] + save_options["name"] + "_config.yml"
        fhdl = open(full_path, 'w')
        yaml.dump(config_info, fhdl)
        
    npy_data = dict()
    if save_options["slm_pattern"] is True:
        # Here, we save the amplitude pattern that is assumed, and the phase pattern for the SLM
        # If crop is True, then we resize the amplitude and phase pattern 
        try:
            if isinstance(hologram.amp, float):
                amp = hologram.amp
                npy_data["slm_amp"] = amp
            else:
                amp = hologram.amp.get()
                if save_options["crop"] is True:
                    npy_data["slm_amp"] = toolbox.unpad(amp, hologram.slm_shape)
                else:
                    npy_data["slm_amp"] = amp
        except:
            amp = hologram.amp
            npy_data["slm_amp"] = amp

        if save_options["crop"] is True:
            npy_data["slm_phase"] = toolbox.unpad(hologram.extract_phase(), hologram.slm_shape)
        else:
            npy_data["slm_phase"] = hologram.extract_phase()
            

    if save_options["ff_pattern"] is True:
        # Here, we save the farfield pattern. There is no cropping here.
        npy_data["ff_amp"] = hologram.extract_farfield()

    if save_options["target"] is True:
        # Here, we save the target. The target is in the computational space
        npy_data["target"] = hologram.target

    if (save_options["slm_pattern"] is True) or (save_options["ff_pattern"] is True) or (save_options["target"] is True):
        full_path2 = save_options["path"] + os.sep + save_options["prefix"] + save_options["name"] + "_data"
        np.savez_compressed(full_path2, **npy_data)
        full_path2 = full_path2 + ".npz" # Add file extension

    return full_path, full_path2