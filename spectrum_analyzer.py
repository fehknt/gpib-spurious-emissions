import pyvisa as visa
import time
import analysis

COMPENSATION_FILE = 'ext_att_compensation.csv'

def get_carrier_frequency():
    """Prompts user for carrier frequency and parses it."""
    while True:
        try:
            freq_str = input("Enter carrier frequency (e.g., 100kHz, 2.4GHz, 11GHz): ")
            freq_hz = analysis.parse_frequency(freq_str)

            if 100e3 <= freq_hz <= 11e9:
                return freq_hz
            else:
                print("Frequency must be between 100kHz and 11GHz.")
        except (ValueError, IndexError):
            print("Invalid input. Please enter a valid frequency (e.g., '100mhz', '2.4g').")

def print_peak_details(freq, power, comp_freqs, comp_dbs):
    """Prints the details of a single signal peak, including compensation."""
    compensation_db = analysis.get_compensation(freq, comp_freqs, comp_dbs)
    corrected_power = power - compensation_db
    print(f"  Frequency: {analysis.format_frequency(freq)}, Measured Power: {power:.2f} dBm")
    if compensation_db != 0.0:
        print(f"  Compensation: {compensation_db:.2f} dB")
        print(f"  Corrected Power: {corrected_power:.2f} dBm = {analysis.dbm_to_watts_formatted(corrected_power)}")

def print_peak_report(carrier_peaks, spurious_peaks, comp_freqs, comp_dbs):
    """Prints a formatted report of carrier and spurious peaks."""
    if carrier_peaks:
        print("\n--- Carrier Signal Detected ---")
        for freq, power in carrier_peaks:
            print_peak_details(freq, power, comp_freqs, comp_dbs)

    if spurious_peaks:
        print("\n--- Spurious Emissions Detected ---")
        for freq, power in spurious_peaks:
            print_peak_details(freq, power, comp_freqs, comp_dbs)
    
    if not spurious_peaks and carrier_peaks:
        print("\nNo significant spurious emissions found.")

class SpectrumAnalyzer:
    def __init__(self, address):
        self.rm = visa.ResourceManager()
        self.instrument = self.rm.open_resource(address)
        self.instrument.timeout = 10000

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
        return self.query("*IDN?")

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

    def set_resolution_bandwidth(self, rbw_hz):
        self.write(f"RB {rbw_hz}Hz")

    def set_video_bandwidth(self, vbw_hz):
        self.write(f"VB {vbw_hz}Hz")

    def set_attenuation(self, att_db):
        self.write(f"AT {att_db}dB")

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
        peaks = analysis.parse_peak_data(raw_signals)
        return peaks

def main():
    """Main execution function."""
    comp_freqs, comp_dbs = analysis.load_compensation_file(COMPENSATION_FILE)
    GPIB_ADDRESS = "GPIB0::18::INSTR"
    sa = None

    try:
        sa = SpectrumAnalyzer(GPIB_ADDRESS)
        print(f"Connected to: {sa.get_id()}")
        sa.reset()

        carrier_freq = get_carrier_frequency()
        stop_freq = analysis.get_search_range(carrier_freq)
        
        print(f"\nCarrier Frequency: {analysis.format_frequency(carrier_freq)}")
        print(f"Searching for spurious emissions up to {stop_freq/1e9} GHz")

        sa.set_center_frequency((stop_freq + 100e3) / 2)
        sa.set_span(stop_freq - 100e3)
        time.sleep(2)
        
        peaks = sa.find_peaks_emc()

        if not peaks:
            print("No emissions of any sort in the search range were found.")
            return
            
        carrier_peaks, spurious_peaks = analysis.separate_carrier_and_spurious(peaks, carrier_freq)
        print_peak_report(carrier_peaks, spurious_peaks, comp_freqs, comp_dbs)
        analysis.append_peaks_to_csv(carrier_peaks, spurious_peaks, comp_freqs, comp_dbs)

    except visa.errors.VisaIOError as e:
        print(f"Error communicating with instrument: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if sa:
            sa.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()