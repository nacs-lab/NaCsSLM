"""
Contains several clients to talk with various servers related to the SLM

- Client communicates with a Server in Server.py which contains a slm and camera
- FeedbackClient communicates with a Server connected to the Experiment Control MATLAB, for instance, AndorServer.py

For future: Implement parent client class, and subclients, so that common features can be shared without copying code.
"""

import zmq
from datetime import datetime
import numpy as np
import yaml
import ast

class Client(object):
    """
    This client communicates with a server with a slm and camera.
    """
    def recreate_sock(self):
        """
        Creates a socket for communication with the server. Recreates it if it is already created.

        Args:
            None

        Returns:
            None

        Raises:
            None

        """
        if self.__sock is not None:
            self.__sock.close()
        self.__sock = self.__ctx.socket(zmq.REQ)
        self.__sock.connect(self.__url)

    def __init__(self, url: str):
        """
        Creates a Client object. Prints an "id" for the server.

        Args:
            url: The url for the server to connect to. If it starts with 'tcp', it assumes it is a url. Otherwise, it can also be a path to a config file.

        Returns:
            Object upon creation

        Raises:
            Exception when a url is not specified.

        """
        # network
        config_file = False
        self.config = None
        """ Config file for this client. If None, no config loaded. """
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
        """
        Decorator. Decorates a function to safely receive without throwing an error. The types of receives are also specified,
        along with a timeout parameter and any flag to pass onto zmq. Prints an error if an error occurs.

        Args:
            recv_type: list of 0s and 1s specifying the types of receives to use. 0 corresponds to a pure recv (for binary information) and 1 corresponds to a recv_string.
            timeout: Timeout in ms for the polling function.
            flag: Any zmq flag which is passed to both recv and recv_string.

        Returns:
            The decorated function. The actual decorated function returns a list of responses, where None is a placeholder if no response is received.

        Raises:
            None

        """
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
        """
        Send a "id" request to the server. Can act as a "handshake"

        Args:
            None

        Returns:
            List containing a string with the response.

        Raises:
            None

        """
        self.__sock.send_string("id") # handshake

    @poll_recv([1])
    def send_pattern(self, path_str):
        """
        Request the Server to use a pattern at a particular path

        Args:
            path_str: String for the path where the pattern is located

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("use_pattern", zmq.SNDMORE)
        self.__sock.send_string(path_str)

    @poll_recv([1])
    def send_add_phase(self, path_str):
        """
        Request the Server to use an additional phase at a particular path

        Args:
            path_str: String for the path where the additional phase is located

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("use_additional_phase", zmq.SNDMORE)
        self.__sock.send_string(path_str)

    @poll_recv([1])
    def send_init_hologram(self, path_str):
        self.__sock.send_string("init_hologram", zmq.SNDMORE)
        self.__sock.send_string(path_str)
    
    @poll_recv([1], timeout=-1)
    def send_calculate(self, targets, amps, iterations):
        """
        Request the Server to calculate a pattern with targets, amps and number of iterations. This request has no timeout.

        Args:
            targets: A 2 x ntargets numpy array where the x-coordinates are the first row and y-coordinates are the second row.
            amps: A 1 x ntargets numpy array specifying the amplitudes for each target
            iterations: Number of iterations 

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("calculate", zmq.SNDMORE)
        self.__sock.send(targets.astype(np.float64).tobytes(), zmq.SNDMORE)
        #self.__sock.send(targets.tobytes(), zmq.SNDMORE)
        self.__sock.send(amps.astype(np.float64).tobytes(), zmq.SNDMORE)
        self.__sock.send(int(iterations).to_bytes(1, 'little'))

    @poll_recv([1, 1], timeout=-1)
    def send_save(self, save_path, save_name):
        """
        Request the Server to save a pattern at a particular path. The request has no timeout.

        Args:
            save_path: String for the path where the pattern is saved
            save_name: String for the name of the pattern

        Returns:
            List containing a string with the response. The paths where the file is saved is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("save_calculation", zmq.SNDMORE)
        self.__sock.send_string(save_path, zmq.SNDMORE)
        self.__sock.send_string(save_name)

    @poll_recv([1, 1], timeout=-1)
    def send_save_add_phase(self, save_path, save_name):
        """
        Request the Server to save an additional phase at a particular path. The request has no timeout.

        Args:
            save_path: String for the path where the additional phase is saved
            save_name: String for the name of the pattern

        Returns:
            List containing a string with the response. The paths where the file is saved is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("save_additional_phase", zmq.SNDMORE)
        self.__sock.send_string(save_path, zmq.SNDMORE)
        self.__sock.send_string(save_name)

    @poll_recv([1])
    def send_correction(self, path):
        """
        Request the Server to use a correction pattern at a particular path.

        Args:
            path: String for the path where the correction pattern is located

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("use_correction", zmq.SNDMORE)
        self.__sock.send_string(path)

    @poll_recv([1])
    def send_add_pattern_to_add_phase(self, path):
        self.__sock.send_string("add_pattern_to_add_phase", zmq.SNDMORE)
        self.__sock.send_string(path)

    @poll_recv([1])
    def send_fresnel_lens(self, focal_length):
        """
        Request the Server to use a fresnel lens with a specified focal length.

        Args:
            focal_length: A numpy array specifying the focal length in normalized units. If a single element, an isotropic lens is created.
                If two elements, a cylindrical lens is used. In particular, the following form is used:

                $ \\phi(x, y) = \\pi \\left[\\frac{x^2}{f_x} + \\frac{y^2}{f_y} \\right] $

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        # focal length should be one element array
        self.__sock.send_string("add_fresnel_lens", zmq.SNDMORE)
        self.__sock.send(focal_length.astype(np.float64).tobytes())
        
    @poll_recv([1])
    def send_offset(self, offset = np.array([0.0,0.0])):
        # offset should be two element array
        self.__sock.send_string("add_offset", zmq.SNDMORE)
        self.__sock.send(offset.astype(np.float64).tobytes())

    @poll_recv([1])
    def send_zernike_poly(self, zernike_arr):
        """
        Request the Server to use a zernike polynomial specified by Cartesian Zernike indices.

        Args:
            zernike_arr: nzernikes x 3 numpy array. The first two columns are the indices n,m of the polynomial,
            and the last column is the weight of the polynomial. The convention is in this paper:
            https://doi.org/10.1117/12.294412 

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("add_zernike_poly", zmq.SNDMORE)
        self.__sock.send(zernike_arr.astype(np.float64).tobytes())

    @poll_recv([1])
    def send_reset_add_phase(self):
        """
        Request the Server to reset the additional phase.

        Args:
            None

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("reset_additional_phase")

    @poll_recv([1])
    def send_reset_pattern(self):
        """
        Request the Server to reset the base pattern.

        Args:
            None

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("reset_pattern")

    @poll_recv([1])
    def send_slm_amplitude(self, func_type, param1, param2):
        """
        Request the SLM to use a slm amplitude with func_type and parameters. For future: send a list of arguments.

        Args:
            func_type: Function type for the slm amplitude. The only supported option for now is "gaussian".
            param1: For gaussian, waist for x direction.
            param2: For gaussian, waist for y direction.

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("use_slm_amp", zmq.SNDMORE)
        self.__sock.send_string(func_type, zmq.SNDMORE)
        self.__sock.send(param1, zmq.SNDMORE)
        self.__sock.send(param2)

    @poll_recv([1])
    def send_project(self):
        """
        Request the Server to project the current pattern onto the SLM

        Args:
            None

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("project")

    @poll_recv([1])
    def send_get_current_phase_info(self):
        """
        Request the Server for the current phase configuration.

        Args:
            None

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("get_current_phase_info")

    @poll_recv([1], timeout=-1)
    def send_perform_fourier_calibration(self, shape=np.array([5,5]), pitch=np.array([30,40])):
        """
        Request the Server to perform a fourier calibration with a test array of a given shape and pitch. This request has no timeout.

        Args:
            shape: numpy array with the number of spots in each direction.
            pitch: numpy array with the distance between spots in each direction.

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("perform_fourier_calibration", zmq.SNDMORE)
        self.__sock.send(shape.astype(np.float64).tobytes(), zmq.SNDMORE)
        self.__sock.send(pitch.astype(np.float64).tobytes())

    @poll_recv([1])
    def send_save_fourier_calibration(self, save_path, save_name):
        """
        Request the Server to save the fourier calibration at a particular path with a name.

        Args:
            save_path: String for the path where the calibration should be saved.
            save_name: String for the name of the calibration.

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("save_fourier_calibration", zmq.SNDMORE)
        self.__sock.send_string(save_path, zmq.SNDMORE)
        self.__sock.send_string(save_name)
     
    @poll_recv([1])
    def send_load_fourier_calibration(self, path):
        """
        Request the Server to load a fourier calibration at a particular path.

        Args:
            path: String for the path where the fourier calibration is located

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("load_fourier_calibration", zmq.SNDMORE)
        self.__sock.send_string(path)
        
        
    @poll_recv([1], timeout=-1)
    def send_perform_wavefront_calibration(self, interference_point=np.array([900,400]), field_point=np.array([0.25,0]), test_super_pixel = np.array([-1,-1])):  
        self.__sock.send_string("perform_wavefront_calibration", zmq.SNDMORE)
        self.__sock.send(interference_point.astype(np.float64).tobytes(), zmq.SNDMORE)
        self.__sock.send(field_point.astype(np.float64).tobytes(), zmq.SNDMORE)
        self.__sock.send(test_super_pixel.astype(np.float64).tobytes())


    @poll_recv([1])
    def send_save_wavefront_calibration(self, save_path, save_name):
        self.__sock.send_string("save_wavefront_calibration", zmq.SNDMORE)
        self.__sock.send_string(save_path, zmq.SNDMORE)
        self.__sock.send_string(save_name)

    @poll_recv([1])
    def send_load_wavefront_calibration(self, path):
        self.__sock.send_string("load_wavefront_calibration", zmq.SNDMORE)
        self.__sock.send_string(path)      
        
    @poll_recv([1])
    def send_get_wavefront_calibration(self):
        self.__sock.send_string("get_wavefront_calibration")        

    @poll_recv([1], timeout=-1)
    def send_perform_camera_feedback(self, niters=20):
        """
        Request the Server to perform camera based feedback. This request has no timeout.

        Args:
            niters: Number of iterations of feedback to perform.

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("perform_camera_feedback", zmq.SNDMORE)
        self.__sock.send(int(niters).to_bytes(1, 'little'))

    @poll_recv([1], timeout=-1)
    def send_perform_scan_feedback(self, niters=20, NumPerParamAvg=-1):
        """
        Request the Server to peform scan based feedback. This request has no timeout.

        Args:
            niters: Number of iterations of feedback to perform.
            NumPerParamAvg: Number of averages in scan before performing analysis.

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("perform_scan_feedback", zmq.SNDMORE)
        self.__sock.send(int(niters).to_bytes(1, 'little'), zmq.SNDMORE)
        self.__sock.send(int(NumPerParamAvg).to_bytes(4, 'little'))

    @poll_recv([1])
    def send_get_fourier_calibration(self):
        """
        Request the Server to get the current fourier calibration

        Args:
            None

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("get_fourier_calibration")

    @poll_recv([1])
    def send_get_base(self):
        """
        Request the Server to get the current base pattern.

        Args:
            None

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.

        Raises:
            None

        """
        self.__sock.send_string("get_base")

    @poll_recv([1])
    def send_get_additional_phase(self):
        """
        Request the Server to get the current additional phase configuration.

        Args:
            None

        Returns:
            List containing a string with the response. An "ok" is expected, but an error can also be returned.
            The response has entries split with a semicolon.

        Raises:
            None

        """
        self.__sock.send_string("get_additional_phase")

    def calculate_save_and_project(self, targets, amps, iterations, save_path, save_name):
        """
        Request the Server to calculate, save and project a pattern. See send_calculate, send_save and send_project.

        Args:
            targets, amps, iterations: Arguments to send_calculate
            save_path, save_name: Arguments to send_project

        Returns:
            Save paths and results of sending pattern and project.

        Raises:
            None

        """

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
        """
        Request the Server to load and project a pattern. See send_pattern and send_project.

        Args:
            fname: path to the file name of the pattern

        Returns:
            Responses to send_pattern and send_project.

        Raises:
            None

        """
        ret = self.send_pattern(fname)
        ret2 = self.send_project()
        return ret, ret2

    def _load_config(self):
        """
        Load a config which is in self.config. Sends the correct requests to the server.

        Args:
            None

        Returns:
            None

        Raises:
            None

        """
        config = self.config
        if config is None:
            return
        else:
            for key in config:
                if key == "pattern":
                    self.send_pattern(config["pattern"])
                elif key == "fourier_calibration":
                    self.send_load_fourier_calibration(config["fourier_calibration"])
                elif key.startswith("file_correction"):
                    self.send_correction(config[key])
                elif key.startswith("fresnel_lens"):
                    self.send_fresnel_lens(np.array(ast.literal_eval(config[key])))
                elif key == "zernike":
                    res = ast.literal_eval(config["zernike"])
                    new_list = []
                    for item in res:
                        new_list.append([item[0][0], item[0][1], item[1]])
                    self.send_zernike_poly(np.array(new_list))
                elif key == "offset":
                    self.send_offset(np.array(ast.literal_eval(config[key])))
            return

    def load_config(self, fname):
        """
        Request a particular configuration from a file.

        Args:
            fname: path to the file of the configuration.

        Returns:
            None

        Raises:
            None

        """
        with open(fname, 'r') as fhdl:
            config = yaml.load(fhdl, Loader=yaml.FullLoader)
        self.config = config
        self._load_config()
        
    def save_config(self, fname):
        """
        Save the current configuration. Queries the server for information about this configuration. This configuration can be then loaded with load_config

        Args:
            fname: path of the save location

        Returns:
            None

        Raises:
            None

        """
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
        offset_idx = 0
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
            elif this_key == "offset":
                if offset_idx > 0:
                    config_dict[this_key + str(offset_idx)] = this_val
                else:
                    config_dict[this_key] = this_val
                offset_idx += 1
        with open(fname, 'x') as fhdl:
            yaml.dump(config_dict, fhdl)
        return

    def close(self):
        """
        Closes the socket. Called upon deletion.

        Args:
            None

        Returns:
            None.

        Raises:
            None

        """
        if self.__sock is not None:
            self.__sock.close()

    def __del__(self):
        """
        Destructor which ensures the socket is closed.

        Args:
            None

        Returns:
            None

        Raises:
            None

        """
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