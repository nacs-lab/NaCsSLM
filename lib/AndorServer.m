%% uses AndorServer.py as the server

classdef AndorServer < handle
    properties
        serv;
        op; % Andor operations struct
        file_option = 1; % communicate via file 
        fname = '';
    end

    methods%(Access = private)
        function self = AndorServer(url)
            if self.file_option
                self.fname = url;
            else
                [path, ~, ~] = fileparts(mfilename('fullpath'));
                pyglob = py.dict(pyargs('mat_srcpath', path, 'url', url));
                try
                    py.exec('from AndorServer import AndorServer', pyglob);
                catch
                    py.exec('import sys; sys.path.append(mat_srcpath)', pyglob);
                    py.exec('from AndorServer import AndorServer', pyglob);
                end
                self.serv = py.eval('AndorServer(url)', pyglob);
            end

            %self.op = AndorConfigure(); % Used with default settings
        end
        function res = check_req_from_worker(self)
            if self.file_option
                contents = yaml.loadFile(self.fname);
                res = contents;
            else
                res = cell(self.serv.check_req_from_worker());
                res{1} = char(res{1});
            end
        end
        function reply(self, msg_type, rep)
            if self.file_option
                reply_struct = struct();
                reply_struct.request = 'reply';
                reply_struct.msg_type = msg_type;
                reply_struct.data = rep;
                yaml.dumpFile(self.fname, reply_struct);
            else
                self.serv.reply(msg_type, rep)
            end
        end
        function out = handle_msg(self)
            msg_tot = self.check_req_from_worker();
            if self.file_option
                msg = msg_tot.request;
                out.request = msg;
                if strcmp(msg, "None")
                    return
                else
                    msg_data = msg_tot.data;
                end
            else
                msg = msg_tot{1};
                msg_data = msg_tot{2};
            end
            if strcmp(msg, "get_image")
                %img = AndorTakePicture(self.op);
                img = int32(reshape(img,[1, 512 * 512]));
                self.reply(msg, img);
            elseif strcmp(msg, "get_exposure")
                %t = self.op.ExposureTime;
                t = 0.1;
                self.reply(msg, t);
            elseif strcmp(msg, "set_exposure")
                self.reply(msg, -1);
            elseif strcmp(msg, "set_woi")
                self.reply(msg, -1);
            elseif strcmp(msg, "get_spot_amps")
                scan_fn = msg_data{1};
                fn_hdl = str2func(scan_fn);
                scan_name = msg_data{2};
                num_tot_seq = msg_data{3};
                scan = fn_hdl(scan_name);
                scan.runp().NumTotSeq = num_tot_seq;
                disp(['Running ', scan_fn, '(', scan_name, ')', ' for ', num2str(num_tot_seq), ' sequences'])
                [this_date, this_time] = StartScan2(scan);
                res = run_analysis(this_date, this_time);
                disp(['Replying ' num2str(res.feedback)])
                self.reply(msg, res.feedback);
                out.date = this_date;
                out.time = this_time;
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
        function delete(self)
            self.serv.close()
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