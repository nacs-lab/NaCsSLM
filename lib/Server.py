import Interface
import yaml
import zmq
import threading
import numpy as np
import utils
import PhaseManager
import re
import CorrectedSLM
import Client
from enum import Enum

bDebugMode = 1

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

        self.feedback_client = None

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
        if "feedback" in config:
            feedback_config = config["feedback"]
            if "url" in feedback_config:
                url = feedback_config["url"]
            else:
                raise Exception("Please specify a url for the feedback client")
            if "NumPerParamAvg" in feedback_config:
                NumPerParamAvg = feedback_config["NumPerParamAvg"]
            else:
                NumPerParamAvg = -1
            if "scan_fname" in feedback_config:
                scan_fname = feedback_config["scan_fname"]
            else:
                raise Exception("Please specify a fname for the scan")
            if "scan_name" in feedback_config:
                scan_name = feedback_config["scan_name"]
            else:
                raise Exception("Please specify a scan name")
        self.feedback_client = Client.FeedbackClient(url, scan_fname, scan_name, NumPerParamAvg=NumPerParamAvg)

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
        if msg_str == "id":
            msg_type, rep = self.reply_id()
        elif msg_str == "use_pattern":
            msg_type, rep = self.use_pattern()
        elif msg_str == "calculate":
            msg_type, rep = self.calculate()
        elif msg_str == "save_calculation":
            msg_type, rep = self.save_calculation()
        elif msg_str == "add_fresnel_lens":
            msg_type, rep = self.add_fresnel_lens()
        elif msg_str == "add_offset":
            msg_type, rep = self.add_offset()
        elif msg_str == "add_zernike_poly":
            msg_type, rep = self.add_zernike_poly()
        elif msg_str == "reset_additional_phase":
            msg_type, rep = self.reset_additional_phase()
        elif msg_str == "reset_pattern":
            msg_type, rep = self.reset_pattern()
        elif msg_str == "save_additional_phase":
            msg_type, rep = self.save_add_phase()
        elif msg_str == "use_additional_phase":
            msg_type, rep = self.use_add_phase()
        elif msg_str == "use_correction":
            msg_type, rep = self.use_correction()
        elif msg_str == "use_slm_amp":
            msg_type, rep = self.use_slm_amp()
        elif msg_str == "project":
            msg_type, rep = self.project()
        elif msg_str == "get_current_phase_info":
            msg_type, rep = self.get_current_phase_info()
        elif msg_str == "perform_fourier_calibration":
            msg_type, rep = self.perform_fourier_calibration()
        elif msg_str == "save_fourier_calibration":
            msg_type, rep = self.save_fourier_calibration()
        elif msg_str == "load_fourier_calibration":
            msg_type, rep = self.load_fourier_calibration()
        elif msg_str == "get_fourier_calibration":
            msg_type, rep = self.get_fourier_calibration()
            
        elif msg_str == "perform_wavefront_calibration":
            msg_type, rep = self.perform_wavefront_calibration()
        elif msg_str == "save_wavefront_calibration":
            msg_type, rep = self.save_wavefront_calibration()
        elif msg_str == "load_wavefront_calibration":
            msg_type, rep = self.load_wavefront_calibration()
        elif msg_str == "get_wavefront_calibration":
            msg_type, rep = self.get_wavefront_calibration()
            
        elif msg_str == "perform_camera_feedback":
            msg_type, rep = self.perform_camera_feedback()
        elif msg_str == "perform_scan_feedback":
            msg_type, rep = self.perform_scan_feedback()
        elif msg_str == "get_base":
            msg_type, rep = self.get_base()
        elif msg_str == "get_additional_phase":
            msg_type, rep = self.get_additional_phase()
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

    def safe_process(func):
        def f(self):
            try:
                msg_type, data = func(self)
            except Exception as e:
                msg_type = [1]
                data = ['error: ' + str(e)]
            return msg_type, data
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
        try:
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
                else:
                    raise Exception("SLM type not recognized")
            else:
                raise Exception("Please specify an SLM with the slm field")
            self.phase_mgr = PhaseManager.PhaseManager(slm)
            wrapped_slm = CorrectedSLM.CorrectedSLM(slm, self.phase_mgr)
            iface.set_SLM(wrapped_slm)
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
                elif camera_type == "thorcam_scientific_camera":
                    import slmsuite.hardware.cameras.thorlabs
                    if "sn" in camera_dict:
                        serial = str(camera_dict["sn"])
                    else:
                        serial = ""
                    camera = slmsuite.hardware.cameras.thorlabs.ThorCam(serial)
                    iface.set_camera(camera)
                else:
                    raise Exception("Camera type not recognized")
            else:
                raise Exception("Please specify a camera with the camera field")
            self.iface = iface
            # additional phase. For instance, Fresnel lens or zernike polynomial. 
            #self.phase_mgr = PhaseManager.PhaseManager(self.iface.slm)
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
        except Exception as e:
            print("Worker errored: " + str(e))
            if bDebugMode:
                raise

    @safe_process
    def reply_id(self):
        slm_config_str = "slm: " + self.config["slm"]["type"]
        camera_config_str = "camera: " + self.config["camera"]["type"]
        if self.config["slm"]["type"] == "hamamatsu":
            slm_config_str = slm_config_str + " display " + str(self.config["slm"]["display_num"])
        return [1], [slm_config_str + " / " + camera_config_str]

    @safe_process
    def use_pattern(self):
        fname = self.safe_recv_string()
        print("Received " + fname)
        phase = self.load_pattern(fname)
        self.phase_mgr.set_base(phase, fname)
        return [1], ["ok"]

    @safe_process
    def use_add_phase(self):
        fname = self.safe_recv_string()
        print("Received for add phase: " + fname)
        if re.match(r'[A-Z]:', fname) is None:
            # check to see if it's an absolute path
            fname = self.pattern_path + fname
        self.phase_mgr.add_from_file(fname)
        return [1], ["ok"]

    @safe_process
    def use_correction(self):
        fname = self.safe_recv_string()
        print("Received correction pattern: " + fname)
        if self.config["slm"]["type"] == "hamamatsu":
            self.phase_mgr.add_correction(fname, self.config["slm"]["bitdepth"], 1)
        else:
            self.phase_mgr.add_correction(fname, self.config["slm"]["bitdepth"], 1) #TODO, in case you need to scale.
        return [1], ["ok"]

    @safe_process
    def use_slm_amp(self):
        func = self.safe_recv_string()
        if func == "gaussian":
            waist_x = self.safe_recv()
            waist_x = np.frombuffer(waist_x)
            waist_y = self.safe_recv()
            waist_y = np.frombuffer(waist_y)

            shape = self.iface.slm.shape
            xpix = (shape[1] - 1) *  np.linspace(-.5, .5, shape[1])
            ypix = (shape[0] - 1) * np.linspace(-.5, .5, shape[0])

            x_grid, y_grid = np.meshgrid(xpix, ypix)

            gaussian_amp = np.exp(-np.square(x_grid) * (1 / waist_x**2)) * np.exp(-np.square(y_grid) * (1 / waist_y**2))

            self.iface.set_slm_amplitude(gaussian_amp)
        else:
            print("Unknown amp type")
        return [1], ["ok"]

    @safe_process
    def project(self):
        self.iface.write_to_SLM(self.phase_mgr.base, self.phase_mgr.base_source)
        return [1], ["ok"]

    @safe_process
    def calculate(self):
        target_data = self.safe_recv()
        target_data = np.frombuffer(target_data)
        target_data = np.copy(target_data)
        amp_data = self.safe_recv()
        amp_data = np.frombuffer(amp_data)
        amp_data = np.copy(amp_data)
        iteration_data = self.safe_recv()
        #print(iteration_data)
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
            self.iface.plot_stats()
            return [1], ["ok"]
        else:
            print("Not integer number of targets")
            return [1], ["error: not integer number of targets"]

    @safe_process
    def save_calculation(self):
        save_path = self.safe_recv_string()
        save_name = self.safe_recv_string()
        if re.match(r'[A-Z]:', save_path) is None:
            # check to see if it's an absolute path
            save_path = self.pattern_path + save_path
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

    @safe_process
    def save_add_phase(self):
        save_path = self.safe_recv_string()
        save_name = self.safe_recv_string()
        if re.match(r'[A-Z]:', save_path) is None:
            # check to see if it's an absolute path
            save_path = self.pattern_path + save_path
        save_options = dict()
        save_options["config"] = True # This option saves the information about how this additional phase was created
        save_options["phase"] = True # saves the actual phase
        save_options["path"] = save_path # Enable this to save to a desired path. By default it is the current working directory
        save_options["name"] = save_name # This name will be used in the path.
        config_path, pattern_path = self.phase_mgr.save_to_file(save_options)
        return [1,1], [config_path, pattern_path]

    def load_pattern(self, path):
        if re.match(r'[A-Z]:', path) is None:
            # check to see if it's an absolute path
            path = self.pattern_path + path
        _,data = utils.load_slm_calculation(path, 0, 1)
        return data["slm_phase"]

    @safe_process
    def add_fresnel_lens(self):
        focal_length = self.safe_recv()
        focal_length = np.frombuffer(focal_length)
        #phase, _ = self.iface.get_lens_phase(focal_length[0])
        #if self.additional_phase is None:
        #    self.additional_phase = phase
        #else:
        #    self.additional_phase = self.additional_phase + phase
        if len(focal_length) == 1:
            self.phase_mgr.add_fresnel_lens(focal_length[0])
        else:
            self.phase_mgr.add_fresnel_lens(focal_length)
        return [1], ["ok"]
    
    
    @safe_process
    def add_offset(self):
        offset = self.safe_recv()
        offset_data = np.frombuffer(offset)
        offset_data = np.copy(offset_data)
        self.phase_mgr.add_offset(offset_data)
        return [1], ["ok"]


    @safe_process
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

    @safe_process
    def reset_additional_phase(self):
        self.phase_mgr.reset_additional()
        return [1], ["ok"]

    @safe_process
    def reset_pattern(self):
        self.phase_mgr.reset_base()
        return [1], ["ok"]

    @safe_process
    def get_current_phase_info(self):
        base_str = "base: " + self.phase_mgr.base_source
        add_str = " additional: "
        log = self.phase_mgr.add_log
        for item in log:
            add_str = add_str + str(item[0]) + ":" + str(item[1]) + ","
        return [1], [base_str + add_str]

    @safe_process
    def get_base(self):
        return [1], [self.phase_mgr.base_source]

    @safe_process
    def get_additional_phase(self):
        rep = ""
        log = self.phase_mgr.add_log
        for item in log:
            rep = rep + str(item[0]) + ";" + str(item[1]) + ";"
        return [1], [rep]
        
    @safe_process
    def perform_fourier_calibration(self):
        shape = self.safe_recv()
        shape_data = np.frombuffer(shape)
        shape_data= np.copy(shape_data)
        pitch = self.safe_recv()
        pitch_data = np.frombuffer(pitch)
        pitch_data = np.copy(pitch_data)
        self.iface.perform_fourier_calibration(shape_data, pitch_data)
        return [1], ["ok"]

    @safe_process
    def save_fourier_calibration(self):
        save_path = self.safe_recv_string()
        save_name = self.safe_recv_string()
        _, path = self.iface.save_fourier_calibration(save_path, save_name)
        return [1], [path]

    @safe_process
    def load_fourier_calibration(self):
        path = self.safe_recv_string()
        self.iface.load_fourier_calibration(path)
        return [1], ["ok"]

    @safe_process
    def get_fourier_calibration(self):
        return [1], [self.iface.fourier_calibration_source]
    
    
    
    @safe_process
    def perform_wavefront_calibration(self):
        interference_point = self.safe_recv()
        interference_point_data = np.frombuffer(interference_point)
        interference_point_data= np.copy(interference_point_data)
        field_point = self.safe_recv()
        field_point_data = np.frombuffer(field_point)
        field_point_data = np.copy(field_point_data)
        test_super_pixel = self.safe_recv()
        test_super_pixel_data = np.frombuffer(test_super_pixel_data)
        test_super_pixel_data = np.copy(test_super_pixel_data)
        if test_super_pixel_data[0] == -1:
            test_super_pixel_data = None
        self.iface.perform_wavefront_calibration(interference_point_data, field_point_data,test_super_pixel_data)
        return [1], ["ok"]

    @safe_process
    def save_wavefront_calibration(self):
        save_path = self.safe_recv_string()
        save_name = self.safe_recv_string()
        _, path = self.iface.save_wavefront_calibration(save_path, save_name)
        return [1], [path]

    @safe_process
    def load_wavefront_calibration(self):
        path = self.safe_recv_string()
        self.iface.load_wavefront_calibration(path)
        return [1], ["ok"]
    @safe_process
    def get_wavefront_calibration(self):
        return [1], [self.iface.wavefront_calibration_source]


    @safe_process
    def perform_camera_feedback(self):
        niters = self.safe_recv()
        niters = int.from_bytes(niters, 'little')
        _, msg = self.iface.perform_camera_feedback(niters)
        return [1], [msg]

    @safe_process
    def perform_scan_feedback(self):
        if self.feedback_client is None:
            return [1], ["No feedback client on server."]
        else:
            niters = self.safe_recv()
            niters = int.from_bytes(niters, 'little')
            NumPerParamAvg = self.safe_recv()
            NumPerParamAvg = int.from_bytes(NumPerParamAvg, 'little')
            if NumPerParamAvg != -1:
                self.feedback_client.NumPerParamAvg = NumPerParamAvg
            _, msg = self.iface.perform_scan_feedback(niters, self.feedback_client)
            return [1], [msg]

