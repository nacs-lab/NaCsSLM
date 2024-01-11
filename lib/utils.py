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

def load_slm_calculation(base_path, bConfig, bPhase):
    config = None
    data = None
    if bConfig:
        config_path = base_path + "_config.yml"
        with open(config_path, 'r') as fhdl:
            config = yaml.load(fhdl, Loader=yaml.FullLoader)
    if bPhase:
        data_path = base_path + "_data.npz"
        data = np.load(data_path)
    return config,data

def save_add_phase(phase_mgr, save_options, extra_data=None):
    """

    """
    if not "config" in save_options:
        save_options["config"] = False
    if not "phase" in save_options:
        save_options["phase"] = False
    if not "path" in save_options:
        save_options["path"] = os.getcwd()
    if not "name" in save_options:
        save_options["name"] = ""
    if not "prefix" in save_options:
        now = datetime.now()
        save_options["prefix"] = now.strftime("%Y%m%d_%H%M%S")
    full_path = None 
    full_path2 = None
    # Now, we gather all the information to save in the config
    if save_options["config"] is True:
        config_info = dict()
        config_info["shape"] = str(list(phase_mgr.shape))
        config_info["log"] = str(phase_mgr.add_log)
        if extra_data is not None:
            config_info["extra_data"] = extra_data
        # Now perform the actual save:
        full_path = save_options["path"] + os.sep + save_options["prefix"] + save_options["name"] + "_add_phase_config.yml"
        fhdl = open(full_path, 'w')
        yaml.dump(config_info, fhdl)

    npy_data = dict()
    if save_options["phase"] is True:
        npy_data["phase"] = phase_mgr.additional
        full_path2 = save_options["path"] + os.sep + save_options["prefix"] + save_options["name"] + "_add_phase_data"
        np.savez_compressed(full_path2, **npy_data)
        full_path2 = full_path2 + ".npz" # Add file extension
    return full_path, full_path2

def load_add_phase(base_path, bConfig, bPhase):
    config = None
    data = None
    if bConfig:
        config_path = base_path + "_add_phase_config.yml"
        with open(config_path, 'r') as fhdl:
            config = yaml.load(fhdl, Loader=yaml.FullLoader)
    if bPhase:
        data_path = base_path + "_add_phase_data.npz"
        data = np.load(data_path)
    return config,data