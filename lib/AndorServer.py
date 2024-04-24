import yaml
import zmq
import threading
import numpy as np
from enum import Enum
import time

class AndorServer(object):
    # To save sockets, this class doubles as also the feedback server for the sequence. 
    class WorkerRequest(Enum):
        NoRequest = 0
        Stop = 1
        Pending = 2
        Reply = 3

    def recreate_sock(self):
        if self.__sock is not None:
            self.__sock.close()
        self.__sock = self.__ctx.socket(zmq.ROUTER)
        self.__sock.bind(self.__url)

    def __init__(self, config_file):

        with open(config_file, 'r') as fhdl:
            self.config = yaml.load(fhdl, Loader=yaml.FullLoader)
        config = self.config
        self.file_option = False
        if "url" in config:
            url = config["url"]
        else:
            raise Exception("Please specify a url for the server")
        if "file_options" in config:
            if "data_file" in config["file_options"]:
                self.data_fname = config["file_options"]["data_file"]
            else:
                raise Exception("Please specify a data file name")
            self.file_option = True
            # initialize file
            write_dict = dict()
            write_dict["request"] = "None"
            with open(self.data_fname, 'w') as file:
                yaml.dump(write_dict, file)
        

        # lock for worker request
        self.__worker_lock = threading.Lock()

        # data transfer
        self.__data_lock = threading.Lock()
        self.__msg_type = None
        self.__data = None

        self.__req_from_worker_lock = threading.Lock()
        self.__req_from_worker = None
        self.__rep_addr = None # reply address
        self.__req_data = None

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

    def close(self):
        self.stop_worker()
        self.__sock.close()

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
        # Method to handle different requests from external clients. We handle the ones we know. Andor handling will be limited for now.
        if self.file_option:
            write_dict = dict()
        if msg_str == "get_width":
            self.safe_send(addr, [0], [int(512).to_bytes(4, 'little')])
            return True
        elif msg_str == "get_height":
            self.safe_send(addr, [0], [int(512).to_bytes(4, 'little')])
            return True
        elif msg_str == "get_depth":
            self.safe_send(addr, [0], [int(16).to_bytes(4, 'little')])
            return True
        elif msg_str == "get_serial":
            self.safe_send(addr, [1], ["Andor"])
            return True
        elif msg_str == "close":
            self.safe_send(addr, [1], ["Andor doesn't close"])
            return True
        elif msg_str == "info":
            self.safe_send(addr, [1], ["Andor"])
            return True
        elif msg_str == "get_exposure":
            pass
        elif msg_str == "set_exposure":
            exposure = self.safe_recv()
            exposure = np.frombuffer(exposure)
            exposure = exposure[0]
            with self.__req_from_worker_lock:
                self.__req_data = exposure
                if self.file_option:
                    write_dict["data"] = str(exposure)
        elif msg_str == "set_woi":
            woi = self.safe_recv()
            woi = np.frombuffer(woi)
            with self.__req_from_worker_lock:
                self.__req_data = woi
                if self.file_option:
                    write_dict["data"] = str(woi)
        elif msg_str == "get_image":
            pass
        elif msg_str == "flush":
            self.safe_send(addr, [1], ["ok"])
            return True
        elif msg_str == "id":
            self.safe_send(addr, [1], ["MATLAB Experimental Control Server/Andor Server"])
            return True
        elif msg_str == "get_spot_amps":
            scan_fname = self.safe_recv_string()
            scan_name = self.safe_recv_string()
            NumPerParamAvg = int.from_bytes(self.safe_recv(), 'little')
            with self.__req_from_worker_lock:
                self.__req_data = [scan_fname, scan_name, NumPerParamAvg]
                if self.file_option:
                    write_dict["data"] = [scan_fname, scan_name, NumPerParamAvg]
            pass
        else:
            self.safe_send(addr, [1], [f''])
            print("Unknown request " + msg_str)
            return False
        with self.__req_from_worker_lock:
            self.__req_from_worker = msg_str
            self.__rep_addr = addr
            # If files are being used communicate into file.
            if self.file_option:
                write_dict["request"] = msg_str
                with open(self.data_fname, 'w') as file:
                    yaml.dump(write_dict, file)
        with self.__worker_lock:
            self.__worker_req = self.WorkerRequest.Pending
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
            if self.file_option:
                with open(self.data_fname, 'r') as file:
                    data = yaml.load(file, Loader=yaml.FullLoader)
                    if data["request"] == "reply":
                        if data["msg_type"] == "get_spot_amps":
                            data_to_send = np.array(data["data"])
                        self.reply(data["msg_type"], data_to_send)
                        with open(self.data_fname, 'w') as file2:
                            write_dict = dict()
                            write_dict["request"] = "None"
                            yaml.dump(write_dict, file2)
            if self.__check_worker_req() == self.WorkerRequest.NoRequest:
                if self.__sock.poll(self.timeout) == 0: # in milliseconds
                    continue
                addr = self.safe_recv()
                delimit = self.safe_recv_string()
                msg_str = self.safe_recv_string()
                if msg_str is None:
                    self.safe_send(addr, [1], ["Send more"])
                self.handle_msg(addr, msg_str)
            elif self.__check_worker_req() == self.WorkerRequest.Reply:
                with self.__req_from_worker_lock:
                    self.__req_from_worker = None
                    addr = self.__rep_addr
                with self.__data_lock:
                    rep = self.__data
                    msg_type = self.__msg_type
                msg_type, rep = self._reply(msg_type, rep)
                self.safe_send(addr, msg_type, rep)
                with self.__worker_lock:
                    self.__worker_req = self.WorkerRequest.NoRequest
            time.sleep(0.5)
        print("Worker finishing")

    def _reply(self, msg_type, data):
        if msg_type == "get_exposure":
            exposure = np.array(data)
            return [0], [exposure.tobytes()]
        elif msg_type == "set_exposure":
            return [1], ["ok"]
        elif msg_type == "set_woi":
            return [1], ["ok"]
        elif msg_type == "get_image":
            return [0], [data.tobytes()]
        elif msg_type == "get_spot_amps":
            return [0], [data.tobytes()]
        else:
            return [1], ["unknown reply"]
    
    def check_req_from_worker(self):
        if self.__check_worker_req() == self.WorkerRequest.Pending:
            print('Checking for request')
            with self.__req_from_worker_lock:
                return (self.__req_from_worker, self.__req_data)
        else:
            return None, None

    def reply(self, msg_type, rep):
        with self.__data_lock:
            self.__msg_type = msg_type
            self.__data = rep
        with self.__worker_lock:
            self.__worker_req = self.WorkerRequest.Reply