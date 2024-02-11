import zmq
from datetime import datetime
import numpy as np
import yaml
import ast

class Client(object):
    def recreate_sock(self):
        if self.__sock is not None:
            self.__sock.close()
        self.__sock = self.__ctx.socket(zmq.REQ)
        self.__sock.connect(self.__url)

    def __init__(self, url: str):
        # network
        config_file = False
        self.config = None
        if not url.startswith('tcp'):
            #config file in this case
            config_file = True
            with open(config_file, 'r') as fhdl:
                config = yaml.load(fhdl, Loader=yaml.FullLoader)
            self.config = config
            if "url" in config:
                url = config["url"]
            else:
                raise Exception("Please specify a url for this client")

        if config_file:
            self._load_config()

        self.__url = url
        self.__ctx = zmq.Context()
        self.__sock = None
        self.recreate_sock()
        self.timeout = 500
        rep = self.send_id()
        print(rep)

    # decorators for polling

    # recv_type = 1 is a string receive
    def poll_recv(recv_type = [1], timeout=1000, flag=0):
        def deco(func):
            def f(self, *args): #timeout in milliseconds
                try:
                    func(self, *args)
                except Exception as e:
                    print('Error in client function: ' + str(e))
                    return None
                rep = []
                for i in recv_type:
                    if self.__sock.poll(timeout) == 0:
                        rep.append(None)
                    else:
                        if i == 0:
                            rep.append(self.__sock.recv(flag))
                        else:
                            rep.append(self.__sock.recv_string(flag))
                now = datetime.now()
                print(now.strftime("%Y%m%d_%H%M%S"))
                return rep
            return f
        return deco

    @poll_recv([1])
    def send_id(self):
        self.__sock.send_string("id") # handshake

    @poll_recv([1])
    def send_pattern(self, path_str):
        self.__sock.send_string("use_pattern", zmq.SNDMORE)
        self.__sock.send_string(path_str)

    @poll_recv([1])
    def send_add_phase(self, path_str):
        self.__sock.send_string("use_additional_phase", zmq.SNDMORE)
        self.__sock.send_string(path_str)
    
    @poll_recv([1], timeout=-1)
    def send_calculate(self, targets, amps, iterations):
        self.__sock.send_string("calculate", zmq.SNDMORE)
        self.__sock.send(targets.astype(np.float64).tobytes(), zmq.SNDMORE)
        #self.__sock.send(targets.tobytes(), zmq.SNDMORE)
        self.__sock.send(amps.astype(np.float64).tobytes(), zmq.SNDMORE)
        self.__sock.send(int(iterations).to_bytes(1, 'little'))

    @poll_recv([1, 1], timeout=-1)
    def send_save(self, save_path, save_name):
        self.__sock.send_string("save_calculation", zmq.SNDMORE)
        self.__sock.send_string(save_path, zmq.SNDMORE)
        self.__sock.send_string(save_name)

    @poll_recv([1, 1], timeout=-1)
    def send_save_add_phase(self, save_path, save_name):
        self.__sock.send_string("save_additional_phase", zmq.SNDMORE)
        self.__sock.send_string(save_path, zmq.SNDMORE)
        self.__sock.send_string(save_name)

    @poll_recv([1])
    def send_correction(self, path):
        self.__sock.send_string("use_correction", zmq.SNDMORE)
        self.__sock.send_string(path)

    @poll_recv([1])
    def send_fresnel_lens(self, focal_length):
        # focal length should be one element array
        self.__sock.send_string("add_fresnel_lens", zmq.SNDMORE)
        self.__sock.send(focal_length.astype(np.float64).tobytes())

    @poll_recv([1])
    def send_zernike_poly(self, zernike_arr):
        self.__sock.send_string("add_zernike_poly", zmq.SNDMORE)
        self.__sock.send(zernike_arr.astype(np.float64).tobytes())

    @poll_recv([1])
    def send_reset_add_phase(self):
        self.__sock.send_string("reset_additional_phase")

    @poll_recv([1])
    def send_reset_pattern(self):
        self.__sock.send_string("reset_pattern")

    @poll_recv([1])
    def send_slm_amplitude(self, func_type, param1, param2):
        self.__sock.send_string("use_slm_amp", zmq.SNDMORE)
        self.__sock.send_string(func_type, zmq.SNDMORE)
        self.__sock.send(param1, zmq.SNDMORE)
        self.__sock.send(param2)

    @poll_recv([1])
    def send_project(self):
        self.__sock.send_string("project")

    @poll_recv([1])
    def send_get_current_phase_info(self):
        self.__sock.send_string("get_current_phase_info")

    @poll_recv([1], timeout=-1)
    def send_perform_fourier_calibration(self, shape=np.array([5,5]), pitch=np.array([30,40])):
        self.__sock.send_string("perform_fourier_calibration", zmq.SNDMORE)
        self.__sock.send(shape.astype(np.float64).tobytes(), zmq.SNDMORE)
        self.__sock.send(pitch.astype(np.float64).tobytes())

    @poll_recv([1])
    def send_save_fourier_calibration(self, save_path, save_name):
        self.__sock.send_string("save_fourier_calibration", zmq.SNDMORE)
        self.__sock.send_string(save_path, zmq.SNDMORE)
        self.__sock.send_string(save_name)

    @poll_recv([1])
    def send_load_fourier_calibration(self, path):
        self.__sock.send_string("load_fourier_calibration", zmq.SNDMORE)
        self.__sock.send_string(path)

    @poll_recv([1], timeout=-1)
    def send_perform_camera_feedback(self, niters=20):
        self.__sock.send_string("perform_camera_feedback", zmq.SNDMORE)
        self.__sock.send(int(niters).to_bytes(1, 'little'))

    @poll_recv([1], timeout=-1)
    def send_perform_scan_feedback(self, niters=20, NumPerParamAvg=-1):
        self.__sock.send_string("perform_scan_feedback", zmq.SNDMORE)
        self.__sock.send(int(niters).to_bytes(1, 'little'), zmq.SNDMORE)
        self.__sock.send(int(NumPerParamAvg).to_bytes(4, 'little'))

    @poll_recv([1])
    def send_get_fourier_calibration(self):
        self.__sock.send_string("get_fourier_calibration")

    @poll_recv([1])
    def send_get_base(self):
        self.__sock.send_string("get_base")

    @poll_recv([1])
    def send_get_additional_phase(self):
        self.__sock.send_string("get_additional_phase")

    def calculate_save_and_project(self, targets, amps, iterations, save_path, save_name):
        ret = self.send_calculate(targets, amps, iterations)
        if ret[0] != "ok":
            print("Calculate not successful")
            return ret
        ret2 = self.send_save(save_path, save_name)
        config_path = ret2[0]
        pattern_path = ret2[1]
        pattern_path_to_send = pattern_path[:-9]
        ret3 = self.send_pattern(pattern_path_to_send)
        ret4 = self.send_project()
        return config_path, pattern_path, ret3, ret4

    def load_and_project(self, fname):
        ret = self.send_pattern(fname)
        ret2 = self.send_project()
        return ret, ret2

    def _load_config(self):
        config = self.config
        if config is None:
            return
        else:
            for key in config:
                if key == "pattern":
                    self.send_pattern(config["pattern"])
                elif key == "fourier_calibration":
                    self.send_load_fourier_calibration(config["fourier_calibration"])
                elif key.startswith("correction_pattern"):
                    self.send_correction(config[key])
                elif key.startswith("fresnel_lens"):
                    self.send_fresnel_lens(np.array(ast.literal_eval(config[key])))
                elif key == "zernike":
                    res = ast.literal_eval(config["zernike"])
                    new_list = []
                    for item in res:
                        new_list.append([item[0][0], item[0][1], item[1]])
                    self.send_zernike_poly(np.array(new_list))
            return

    def load_config(self, fname):
        with open(fname, 'r') as fhdl:
            config = yaml.load(fhdl, Loader=yaml.FullLoader)
        self.config = config
        self._load_config()
        
    def save_config(self, fname):
        config_dict = dict()
        base_str = self.send_get_base()
        if base_str != "":
            config_dict["pattern"] = base_str[0]
        add_str = self.send_get_additional_phase()
        corrections = add_str[0].split(';')
        correction_pattern_idx = 0
        file_idx = 0
        fresnel_lens_idx = 0
        zernike_idx = 0
        for i in range(int(np.floor(len(corrections)/2))):
            this_key = corrections[2 * i]
            this_val = corrections[2 * i + 1]
            if this_key == 'file_correction':
                if correction_pattern_idx > 0:
                    config_dict[this_key + str(correction_pattern_idx)] = this_val
                else:
                    config_dict[this_key] = this_val
                correction_pattern_idx += 1
            elif this_key == "file":
                if file_idx > 0:
                    config_dict[this_key + str(file_idx)] = this_val
                else:
                    config_dict[this_key] = this_val
                file_idx += 1
            elif this_key == 'fresnel_lens':
                if fresnel_lens_idx > 0:
                    config_dict[this_key + str(fresnel_lens_idx)] = this_val
                else:
                    config_dict[this_key] = this_val
                fresnel_lens_idx += 1
            elif this_key == "zernike":
                if zernike_idx > 0:
                    config_dict[this_key + str(zernike_idx)] = this_val
                else:
                    config_dict[this_key] = this_val
                zernike_idx += 1
        with open(fname, 'w') as fhdl:
            yaml.dump(config_dict, fhdl)
        return

    def close(self):
        if self.__sock is not None:
            self.__sock.close()

    def __del__(self):
        if self.__sock is not None:
            self.__sock.close()
        self.__ctx.destroy

class FeedbackClient(object):
    def recreate_sock(self):
        if self.__sock is not None:
            self.__sock.close()
        self.__sock = self.__ctx.socket(zmq.REQ)
        self.__sock.connect(self.__url)

    def __init__(self, url: str, scan_fname, scan_name, NumPerParamAvg = -1):
        # network
        self.__url = url
        self.__ctx = zmq.Context()
        self.__sock = None
        self.recreate_sock()
        self.timeout = 500
        self.connected = True
        rep = self.send_id()
        print(rep)
        
        self.scan_fname = scan_fname
        self.scan_name = scan_name
        self.NumPerParamAvg = NumPerParamAvg

    # decorators for polling

    # recv_type = 1 is a string receive
    def poll_recv(recv_type = [1], timeout=1000, flag=0, default_val=None):
        def deco(func):
            def f(self, *args): #timeout in milliseconds
                try:
                    if self.connected:
                        func(self, *args)
                    else:
                        return default_val
                except Exception as e:
                    print('Error in client function: ' + str(e))
                    return None
                rep = []
                for i in recv_type:
                    if self.__sock.poll(timeout) == 0:
                        self.connected=False
                        print("Warning: FeedbackClient is not connected")
                        rep.append(default_val[i])
                    else:
                        if i == 0:
                            rep.append(self.__sock.recv(flag))
                        else:
                            rep.append(self.__sock.recv_string(flag))
                return rep
            return f
        return deco

    def recv1arr(reshape_dims=None, dtype=float):
        def deco(func):
            def f(*args, **kwargs):
                rep = func(*args, **kwargs)
                data = None
                if rep is not None:
                    data = np.frombuffer(rep[0], dtype=dtype)
                    if reshape_dims is not None:
                        data = np.reshape(data, reshape_dims)
                return data
            return f
        return deco

    @poll_recv([1], default_val=["Not connected"])
    def send_id(self):
        self.__sock.send_string("id") # handshake

    @recv1arr
    @poll_recv([0], default_val=np.array([-1.0]))
    def get_spot_amps(self):
        self.__sock.send_string("get_spot_amps", zmq.SNDMORE)
        self.__sock.send_string(self.scan_fname, zmq.SNDMORE)
        self.__sock.send_string(self.scan_name, zmq.SNDMORE)
        self.__sock.send(int(self.NumPerParamAvg).to_bytes(4, 'little'))