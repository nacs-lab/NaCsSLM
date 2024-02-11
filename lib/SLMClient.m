%% uses Client.py as the client

classdef SLMClient < handle
    properties
        client;
    end

    methods%(Access = private)
        function self = SLMClient(url)
            [path, ~, ~] = fileparts(mfilename('fullpath'));
            pyglob = py.dict(pyargs('mat_srcpath', path, 'url', url));
            try
                py.exec('from Client import Client', pyglob);
            catch
                py.exec('import sys; sys.path.append(mat_srcpath)', pyglob);
                py.exec('from Client import Client', pyglob);
            end
            self.client = py.eval('Client(url)', pyglob);
        end
    end
    methods
        function delete(self)
            self.client.close()
        end
    end

    properties(Constant, Access=private)
        cache = containers.Map();
    end
    methods(Static)
        function dropAll()
            remove(SLMClient.cache, keys(SLMClient.cache));
        end
        function res = get(url)
            cache = SLMClient.cache;
            if isKey(cache, url)
                res = cache(url);
                if ~isempty(res) && isvalid(res)
                    return;
                end
            end
            res = SLMClient(url);
            cache(url) = res;
        end
    end
end