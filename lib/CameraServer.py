import yaml
import zmq
import threading
import numpy as np
import slmsuite.hardware.cameras.camera
from enum import Enum
import time
from matplotlib import pyplot as plt

class CameraServer(object):

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
        if "url" in config:
            url = config["url"]
        else:
            raise Exception("Please specify a url for the server")
        if "camera" in config:
            camera_dict = config["camera"]
            camera_type = camera_dict["type"]
            if camera_type == "virtual":
                self.cam = slmsuite.hardware.cameras.camera.Camera(1024, 1024)
                self.cam_type = "virtual"
            elif camera_type == "thorcam_scientific_camera":
                import slmsuite.hardware.cameras.thorlabs
                if "sn" in camera_dict:
                    serial = str(camera_dict["sn"])
                else:
                    serial = ""
                self.cam = slmsuite.hardware.cameras.thorlabs.ThorCam(serial)
                self.cam_type = "thorcam_scientific_camera"
            elif camera_type == "the_imaging_source":
                import tis_camera as ts
                if "sn" in camera_dict:
                    serial = str(camera_dict["sn"])
                else:
                    serial = ""
                if "vid_format" in camera_dict:
                    vid_format = str(camera_dict["vid_format"])
                else:
                    vid_format = None
                self.cam = ts.TISCamera(serial,vid_format)
                self.cam_type = "the_imaging_source"
            elif camera_type == "network":
                camera_url = camera_dict["url"]
                import CameraClient
                self.cam = CameraClient.CameraClient(camera_url)
                self.cam_type = "network"
            else:
                raise Exception("Camera type not recognized")
        else:
            raise Exception("Please specify a camera with the camera field")

        # lock for worker request
        self.__worker_lock = threading.Lock()

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
        if msg_str == "get_width":
            msg_type, rep = self.get_width()
        elif msg_str == "get_height":
            msg_type, rep = self.get_height()
        elif msg_str == "get_depth":
            msg_type, rep = self.get_depth()
        elif msg_str == "get_serial":
            msg_type, rep = self.get_serial()
        elif msg_str == "close":
            msg_type, rep = self.close()
        elif msg_str == "info":
            msg_type, rep = self.info()
        elif msg_str == "get_exposure":
            msg_type, rep = self.get_exposure()
        elif msg_str == "set_exposure":
            msg_type, rep = self.set_exposure()
        elif msg_str == "set_woi":
            msg_type, rep = self.set_woi()
        elif msg_str == "get_image":
            msg_type, rep = self.get_image()
        elif msg_str == "flush":
            msg_type, rep = self.flush()
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

    def __check_worker_req(self):
        with self.__worker_lock:
            return self.__worker_req

    def __worker_func(self):
        # worker function
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

    def get_width(self):
        if self.cam_type == "virtual":
            width = int(1024)
        else:
            width = int(self.cam.shape[1])
        return [0], [width.to_bytes(4, 'little')]

    def get_height(self):
        if self.cam_type == "virtual":
            height = int(1024)
        else:
            height = int(self.cam.shape[0])
        return [0], [height.to_bytes(4, 'little')]

    def get_depth(self):
        if self.cam_type == "virtual":
            depth = int(8)
        else:
            depth = int(self.cam.bitdepth)
        return [0], [depth.to_bytes(4, 'little')]

    def get_serial(self):
        if self.cam_type == "virtual":
            name = "virtual_camera"
        else:
            name = self.cam.name
        return [1], [name]

    def close(self):
        print("closing the camera")
        if self.cam_type != "virtual":
            self.cam.close()
        return [1], ["ok"]

    def info(self):
        print("info request")
        return [1], ["some_info"]

    def get_exposure(self):
        if self.cam_type == "virtual":
            exposure = np.array([0.1])
        else:
            exposure = np.array(self.cam.get_exposure())
        return [0], [exposure.tobytes()]

    def set_exposure(self):
        exposure = self.safe_recv()
        exposure = np.frombuffer(exposure)
        exposure = exposure[0]
        print("Exposure set to " + str(exposure))
        if self.cam_type != "virtual":
            self.cam.set_exposure(exposure)
        return [1], ["set"]

    def set_woi(self):
        woi = self.safe_recv()
        woi = np.frombuffer(woi)
        print("woi set to " + str(woi))
        if self.cam_type != "virtual":
            self.cam.set_woi(woi)
        return [1], ["woi set"]

    def get_image(self):
        if self.cam_type == "virtual":
            img = np.random.rand(1024, 1024)
        else:
            retry_count = 10
            idx = 0
            while idx < retry_count:
                img = self.cam.get_image()
                idx = idx + 1
                if img is not None:
                    break
                time.sleep(1)
                print("Retry image grabbing " + str(idx))
            if self.cam_type == "the_imaging_source":
                img = img.astype(np.int32)
            if self.cam_type == "thorcam_scientific_camera":
                img = img.astype(np.int32)
            plt.imshow(img)
            plt.show()
        return [0], [img.tobytes()]

    def flush(self):
        print("flushing")
        if self.cam_type != "virtual":
            self.cam.flush()
        return [1], ["flushed"]