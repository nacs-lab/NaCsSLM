%% Tracks access to the scan system to prevent concurrent scan submissions.
%  Provides an interface for submitting scans and recording results.

classdef ScanAccessTracker < handle
    properties
        scan_running = false;
        last_date = '';
        last_time = '';
    end

    methods
        function [this_date, this_time] = run_scan(self, scan)
            % Submit a scan and record its date/time.
            % Raises an error if a scan is already running.
            if self.scan_running
                error('ScanAccessTracker:scanBusy', ...
                      'A scan is already running. Wait for it to complete before submitting another.');
            end
            self.scan_running = true;
            try
                [this_date, this_time] = StartScan2(scan);
                self.last_date = this_date;
                self.last_time = this_time;
            catch e
                self.scan_running = false;
                rethrow(e);
            end
            self.scan_running = false;
        end
    end

    properties(Constant, Access=private)
        cache = containers.Map();
    end
    methods(Static)
        function dropAll()
            k = keys(ScanAccessTracker.cache);
            if ~isempty(k)
                remove(ScanAccessTracker.cache, k);
            end
        end
        function res = get()
            key = 'default';
            cache = ScanAccessTracker.cache;
            if isKey(cache, key)
                res = cache(key);
                if ~isempty(res) && isvalid(res)
                    return;
                end
            end
            res = ScanAccessTracker();
            cache(key) = res;
        end
    end
end
