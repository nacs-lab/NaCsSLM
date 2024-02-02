%% uses AndorServer.py as the server

classdef AndorServer < handle
    properties
        serv;
        op; % Andor operations struct
    end

    methods(Access = private)
        function self = AndorServer(url)
            [path, ~, ~] = fileparts(mfilename('fullpath'));
            pyglob = py.dict(pyargs('mat_srcpath', path, 'url', url));
            try
                py.exec('from AndorServer import AndorServer', pyglob);
            catch
                py.exec('import sys; sys.path.append(mat_srcpath)', pyglob);
                py.exec('from AndorServer import AndorServer', pyglob);
            end
            self.serv = py.eval('AndorServer(url)', pyglob);
            
            self.op = AndorConfigure(); % Used with default settings
        end
        function res = check_req_from_worker(self)
            res = self.serv.check_req_from_worker();
        end
        function reply(self, msg_type, rep)
            self.serv.reply(msg_type, rep)
        end
        function handle_msg(self)
            msg = self.check_req_from_worker();
            if strcmp(msg, "get_image")
                img = AndorTakePicture(self.op);
                self.reply([0], img);
            elseif strcmp(msg, "get_exposure")
                t = self.op.ExposureTime;
                self.reply([0], t);
            end
            
        end
    end
    methods
        function run(self)
            while true
                self.handle_msg();
                pause(0.5);
            end
        end
        function recreate_sock(self)
            self.serv.recreate_sock();
        end
        function cleanup = register_cleanup(self)
            cleanup = FacyOnCleanup(@recreate_sock, self);
        end
    end

    properties(Constant, Access=private)
        cache = containers.Map();
    end
    methods(Static)
        function dropAll()
            remove(AndorServer.cache, keys(AndorServer.cache));
        end
        function res = get(url)
            cache = AndorServer.cache;
            if isKey(cache, url)
                res = cache(url);
                if ~isempty(res) && isvalid(res)
                    return;
                end
            end
            res = AndorServer(url);
            cache(url) = res;
        end
    end
end