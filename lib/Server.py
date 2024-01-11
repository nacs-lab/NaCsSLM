import Interface
import yaml
import zmq
import threading
import numpy as np
import utils
import PhaseManager
from enum import Enum

class Server(object):

    class WorkerRequest(Enum):
        NoRequest = 0
        Stop = 1

    def recreate_sock(self):
        if self.__sock is not None:
            self.__sock.close()
        self.__sock = self.__ctx.socket(zmq.ROUTER)
        self.__sock.bind(self.__url)

    def __init__(self, config_file):
        with open(config_file, 'r') as fhdl:
            self.config = yaml.load(fhdl, Loader=yaml.FullLoader)
        config = self.config
        # lock for worker request
        self.__worker_lock = threading.Lock()

        if "url" in config:
            url = config["url"]
        else:
            raise Exception("Please specify a url for the server")
        if "pattern_path" in config:
            self.pattern_path = config["pattern_path"]
        else:
            self.pattern_path = ""
        if "alg" in config:
            alg_dict = config["alg"]
            if "computational_space" in alg_dict:
                self.computational_space = tuple(alg_dict["computational_space"])
            else:
                self.computational_space = (2048, 2048)
            if "n_iterations" in alg_dict:
                self.n_iterations = alg_dict["n_iterations"]
            else:
                self.n_iterations = 20
        # network
        self.__url = url
        self.__ctx = zmq.Context()
        self.__sock = None
        self.recreate_sock()
        self.timeout = 500

        # worker. This worker will handle network requests
        with self.__worker_lock:
            self.__worker_req = self.WorkerRequest.NoRequest
        self.__worker = threading.Thread(target = self.__worker_func)
        self.__worker.start()

        # additional phase. For instance, Fresnel lens or zernike polynomial. 
        self.phase_mgr = PhaseManager.PhaseManager(self.slm)

    def __del__(self):
        self.stop_worker()
        self.__sock.close()
        self.__ctx.destroy

    def stop_worker(self):
        if hasattr(self, '__worker'):
            with self.__worker_lock:
                self.__worker_req = self.WorkerRequest.Stop
            self.__worker.join()
        else:
            return

    def start_worker(self):
        if hasattr(self, '__worker'):
            if self.__worker.is_active():
                return
        with self.__worker_lock:
            self.__worker_req = self.WorkerRequest.NoRequest
        self.__worker = threading.Thread(target = self.__worker_func)
        self.__worker.start()

    def handle_msg(self, addr,  msg_str: str) -> bool:
        # Method to handle different requests from external clients
        if msg_str == "use_pattern":
            msg_type, rep = self.use_pattern()
        elif msg_str == "calculate":
            msg_type, rep = self.calculate()
        elif msg_str == "save_calculation":
            msg_type, rep = self.save_calculation()
        elif msg_str == "add_fresnel_lens":
            msg_type, rep = self.add_fresnel_lens()
        elif msg_str == "add_zernike_poly":
            msg_type, rep = self.add_zernike_poly()
        elif msg_str == "reset_additional_phase":
            msg_type, rep = self.reset_additional_phase()
        else:
            self.safe_send(addr, [1], [f''])
            print("Unknown request " + msg_str)
            return False
        self.safe_send(addr, msg_type, rep)
        return True

    def safe_receive(func):
        def f(self):
            try:
                msg = func(self)
            except:
                msg = None
            return  msg
        return f

    @safe_receive
    def safe_recv(self):
        return self.__sock.recv(zmq.NOBLOCK)

    @safe_receive
    def safe_recv_string(self):
        return self.__sock.recv_string(zmq.NOBLOCK)

    def finish_recv(func):
        def f(self, *args, **kwargs):
            # finish receiving messages
            msg = self.safe_recv()
            while msg is not None:
                msg = self.safe_recv()
            func(self, *args, **kwargs)
        return f

    @finish_recv
    def safe_send(self, addr, msg_type, msg_list):
        # send reply
        self.__sock.send(addr, zmq.SNDMORE)
        self.__sock.send(b'', zmq.SNDMORE)
        for idx, item in enumerate(msg_list):
            if idx == len(msg_list) - 1:
                flag = 0 
            else:
                flag = zmq.SNDMORE
            if msg_type[idx] == 1:
                self.__sock.send_string(item, flag)
            else:
                self.__sock.send(item, flag)
        #print("Done sending")

    #@finish_recv
    #def safe_send(self, addr, msg, flag=0):
    #    # send reply
    #    self.__sock.send(addr, zmq.SNDMORE)
    #    self.__sock.send(b'', zmq.SNDMORE)
    #    self.__sock.send(msg, flag)

    def __check_worker_req(self):
        with self.__worker_lock:
            return self.__worker_req

    def __worker_func(self):
        # worker function
        config = self.config
        iface = Interface.SLMSuiteInterface()
        if "slm" in config:
            slm_dict = config["slm"]
            slm_type = slm_dict["type"]
            if slm_type == "virtual":
                slm = iface.set_SLM()
            elif slm_type == "hamamatsu":
                display_num = slm_dict["display_num"]
                bitdepth = slm_dict["bitdepth"]
                wav_design_um = slm_dict["wav_design_um"] # This is the design wavelenth of the SLM. Namely, it's the wavelength at which 2 pi phase modulation is achieved at max value 255
                wav_um = slm_dict["wav_um"] # Actual wavelength
                from slmsuite.hardware.slms.screenmirrored import ScreenMirrored
                slm = ScreenMirrored(display_num, bitdepth, wav_design_um=wav_design_um, wav_um=wav_um)
                iface.set_SLM(slm)
            else:
                raise Exception("SLM type not recognized")
        else:
            raise Exception("Please specify an SLM with the slm field")
        if "camera" in config:
            camera_dict = config["camera"]
            camera_type = camera_dict["type"]
            if camera_type == "virtual":
                camera = iface.set_camera()
            elif camera_type == "network":
                url = camera_dict["url"]
                import CameraClient
                camera = CameraClient.CameraClient(url)
                iface.set_camera(camera)
            else:
                raise Exception("Camera type not recognized")
        else:
            raise Exception("Please specify a camera with the camera field")
        self.iface = iface
        while self.__check_worker_req() != self.WorkerRequest.Stop:
            if self.__sock.poll(self.timeout) == 0: # in milliseconds
                continue
            addr = self.safe_recv()
            delimit = self.safe_recv_string()
            msg_str = self.safe_recv_string()
            if msg_str is None:
                self.safe_send(addr, [1], ["Send more"])
            self.handle_msg(addr, msg_str)
        print("Worker finishing")

    def use_pattern(self):
        fname = self.safe_recv_string()
        print("Received " + fname)
        phase = self.load_phase(fname)
        self.phase_mgr.set_base(phase, fname)
        self.iface.write_to_SLM(self.phase_mgr.get())
        return [1], ["ok"]

    def calculate(self):
        target_data = self.safe_recv()
        target_data = np.frombuffer(target_data)
        amp_data = self.safe_recv()
        #print(amp_data)
        amp_data = np.frombuffer(amp_data)
        iteration_data = self.safe_recv()
        print(iteration_data)
        iteration_number = int.from_bytes(iteration_data, 'little')
        if iteration_number == 0:
            iteration_number = self.n_iterations
        ntargets = len(target_data) / 2
        if ntargets.is_integer():
            targets = np.reshape(target_data, (2, int(ntargets)))
            self.iface.calculate(self.computational_space, targets, amp_data, n_iters=iteration_number)
            #self.iface.calculate(self.computational_space, targets, amp_data, n_iters=self.n_iterations)
            # for debug
            self.iface.plot_slmplane()
            self.iface.plot_farfield()
            return [1], ["ok"]
        else:
            print("Not integer number of targets")
            return [1], ["error: not integer number of targets"]

    def save_calculation(self):
        save_path = self.safe_recv_string()
        save_name = self.safe_recv_string()
        save_options = dict()
        save_options["config"] = True # This option saves the configuration of this run of the algorithm
        save_options["slm_pattern"] = True # This option saves the slm phase pattern and amplitude pattern (the amplitude pattern is not calculated. So far, the above have assumed a constant amplitude and we have not described functionality to change this)
        save_options["ff_pattern"] = True # This option saves the far field amplitude pattern
        save_options["target"] = True # This option saves the desired target
        save_options["path"] = save_path # Enable this to save to a desired path. By default it is the current working directory
        save_options["name"] = save_name # This name will be used in the path.
        save_options["crop"] = True # This option crops the slm pattern to the slm, instead of an array the shape of the computational space size.
        config_path, pattern_path, err = self.iface.save_calculation(save_options)
        return [1,1], [config_path, pattern_path]

    def load_phase(self, path):
        tot_path = self.pattern_path + path
        _,data = utils.load_slm_calculation(tot_path, 0, 1)
        return data["slm_phase"]


    def add_fresnel_lens(self):
        focal_length = self.safe_recv()
        focal_length = np.frombuffer(focal_length)
        #phase, _ = self.iface.get_lens_phase(focal_length[0])
        #if self.additional_phase is None:
        #    self.additional_phase = phase
        #else:
        #    self.additional_phase = self.additional_phase + phase
        self.phase_mgr.add_fresnel_lens(focal_length)
        return [1], ["ok"]

    def add_zernike_poly(self):
        poly_arr = self.safe_recv()
        poly_arr = np.frombuffer(poly_arr)
        npolys = len(poly_arr) / 3
        poly_arr = np.reshape(poly_arr, (int(npolys), 3))
        poly_list = []
        for i in range(int(npolys)):
            poly_list.append(((int(poly_arr[i, 0]), int(poly_arr[i, 1])), poly_arr[i, 2]))
        self.phase_mgr.add_zernike_poly(poly_list)
        #phase, _ = self.iface.get_zernike_sum_phase(poly_list)
        #if self.additional_phase is None:
        #    self.additional_phase = phase
        #else:
        #    self.additional_phase = self.additional_phase + phase
        return [1], ["ok"]

    def reset_additional_phase(self):
        self.phase_mgr.reset_additional()
        return [1], ["ok"]
