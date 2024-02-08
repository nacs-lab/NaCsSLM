import zmq
from datetime import datetime
import numpy as np

class Client(object):
    def recreate_sock(self):
        if self.__sock is not None:
            self.__sock.close()
        self.__sock = self.__ctx.socket(zmq.REQ)
        self.__sock.connect(self.__url)

    def __init__(self, url: str):
        # network
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
        self.__sock.send(targets.tobytes(), zmq.SNDMORE)
        #self.__sock.send(targets.tobytes(), zmq.SNDMORE)
        self.__sock.send(amps.tobytes(), zmq.SNDMORE)
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
        self.__sock.send(focal_length.tobytes())

    @poll_recv([1])
    def send_zernike_poly(self, zernike_arr):
        self.__sock.send_string("add_zernike_poly", zmq.SNDMORE)
        self.__sock.send(zernike_arr.tobytes())

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
    def send_perform_fourier_calibration(self):
        self.__sock.send_string("perform_fourier_calibration")

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

    @poll_recv([1])
    def send_get_fourier_calibration(self):
        self.__sock.send_string("get_fourier_calibration")

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

class FeedbackClient(object):
    def recreate_sock(self):
        if self.__sock is not None:
            self.__sock.close()
        self.__sock = self.__ctx.socket(zmq.REQ)
        self.__sock.connect(self.__url)

    def __init__(self, url: str):
        # network
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

    @poll_recv([1])
    def send_id(self):
        self.__sock.send_string("id") # handshake

    @recv1arr
    @poll_recv([0])
    def get_spot_amps(self):
        self.__sock.send_string("get_spot_amps")