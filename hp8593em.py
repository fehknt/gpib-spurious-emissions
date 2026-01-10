import pyvisa as visa
import time

class HP8593EM:
    def __init__(self, resource_or_address):
        if isinstance(resource_or_address, str):
            rm = visa.ResourceManager()
            self.instrument = rm.open_resource(resource_or_address)
        else:
            self.instrument = resource_or_address
        
        self.instrument.timeout = 10000

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def write(self, command):
        print(f"GPIB WRITE: {command}")
        self.instrument.write(command)

    def read(self):
        response = self.instrument.read()
        print(f"GPIB READ: {response.strip()}")
        return response

    def query(self, command):
        response = self.instrument.query(command)
        print(f"GPIB QUERY '{command}': {response.strip()}")
        return response

    def close(self):
        self.instrument.close()

    def get_id(self):
        return self.query("ID?")

    def reset(self):
        """Resets the instrument and configures it for EMC peak measurements."""
        self.write("*RST")
        time.sleep(1)
        self.write("MODE EMC")
        time.sleep(1)
        self.write("AT AUTO")
        self.write("ARNG ON")
        self.write("AUNITS DBM")
        self.write("SIGLIST ON")
        self.write("SIGDEL ALL")
        self.write("AUTOQPD OFF")
        self.write("AUTOAVG OFF")

    def set_center_frequency(self, freq_hz):
        self.write(f"CF {freq_hz}Hz")

    def set_span(self, span_hz):
        self.write(f"SP {span_hz}Hz")

    def set_start_frequency(self, freq_hz):
        self.write(f"FA {freq_hz}Hz")

    def set_end_frequency(self, freq_hz):
        self.write(f"FB {freq_hz}Hz")

    def get_start_frequency(self):
        return float(self.query("FA?"))

    def get_end_frequency(self):
        return float(self.query("FB?"))

    def set_resolution_bandwidth(self, rbw_hz):
        self.write(f"RB {rbw_hz}Hz")

    def set_video_bandwidth(self, vbw_hz):
        self.write(f"VB {vbw_hz}Hz")

    def set_attenuation(self, att_db):
        self.write(f"AT {att_db}dB")

    def set_reference_level(self, level_dbm):
        self.write(f"RL {level_dbm}DBM")

    def turn_off_tracking_generator(self):
        """Turns off the tracking generator."""
        self.write("SRCPWR OFF")

    def set_tracking_generator_power(self, power_dbm):
        self.write(f"SRCPWR {power_dbm}DB")

    def set_trace_data_format(self, format_char):
        self.write(f"TDF {format_char}")

    def take_sweep_and_wait(self):
        """Queries sweep time, initiates a sweep, and waits for it to complete."""
        sweep_time_s = self.get_sweep_time()
        self.write("TS")
        # Wait for sweep to complete, with a small buffer
        time.sleep(sweep_time_s * 1.1 + 0.1)

    def get_sweep_time(self):
        """Queries the instrument for its sweep time."""
        return float(self.query("SWPT?"))

    def get_trace_data(self, trace_num):
        return self.query(f"TA?")

    def _wait_for_measurement(self, timeout=600):
        """Waits for a measurement to complete, returning the number of signals found."""
        print("Measurement in progress...")
        start_time = time.time()
        wait_interval = 2
        while time.time() - start_time < timeout:
            try:
                num_signals = int(self.query("SIGLEN?"))
                if num_signals > 0:
                    print(f"Measurement complete. Found {num_signals} signals.")
                    return num_signals
                else:
                    print("Waiting for signals...")
                    time.sleep(wait_interval * 5)
            except visa.errors.VisaIOError:
                time.sleep(wait_interval)
            except ValueError:
                 print("Warning: Could not parse number of signals. Retrying...")
                 time.sleep(wait_interval)

        print("Error: Timed out waiting for measurement to complete.")
        return 0

    def _fetch_signal_data(self, num_signals, timeout=600):
        """Fetches the data for each signal from the instrument."""
        signals = {}
        i = 1
        start_time = time.time()
        wait_interval = 2
        
        while i <= num_signals and time.time() - start_time < timeout:
            try:
                self.write(f"SIGPOS {i}")
                print(f"Fetching signal {i} of {num_signals}...")
                signals[i] = self.query("SIGRESULT?")
                i += 1
            except visa.errors.VisaIOError:
                print(f"Warning: VISA error fetching signal {i}. Retrying...")
                time.sleep(wait_interval)

        if len(signals) < num_signals:
            print(f"Warning: Timed out getting all signals. Only got {len(signals)} of {num_signals}.")

        return signals

    def find_peaks_emc(self):
        """Finds peaks using the EMC analyzer's auto-measure function."""
        self.write("MEASALLSIGS")
        time.sleep(1)
        
        num_signals = self._wait_for_measurement()
        if num_signals == 0:
            print("No signals found.")
            return []
        
        raw_signals = self._fetch_signal_data(num_signals)
        peaks = self._parse_peak_data(raw_signals)
        return peaks

    def _parse_peak_data(self, raw_signals):
        """Parses raw signal strings into a list of (frequency, power) tuples."""
        peaks = []
        for signal_str in raw_signals.values():
            try:
                parts = signal_str.strip().split(',')
                freq_mhz = float(parts[1])
                amp_dbm = float(parts[2])
                peaks.append((freq_mhz * 1e6, amp_dbm))
            except (ValueError, IndexError):
                print(f"Warning: Could not parse peak data point: '{signal_str}'")
        return peaks
