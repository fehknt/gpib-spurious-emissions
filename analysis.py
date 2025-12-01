import numpy as np
import os
import csv
import datetime

def load_compensation_file(filename):
    """Loads a compensation file with frequency and dB pairs."""
    if not os.path.exists(filename):
        print(f"Warning: Compensation file '{filename}' not found. No compensation will be applied.")
        return None, None
    try:
        data = np.loadtxt(filename, delimiter=',', skiprows=1)
        freqs, dbs = data[:, 0], data[:, 1]
        print(f"Successfully loaded compensation file: {filename}")
        return freqs, dbs
    except Exception as e:
        print(f"Error loading compensation file '{filename}': {e}")
        return None, None

def get_compensation(freq_hz, comp_freqs, comp_dbs):
    """Calculates compensation for a given frequency using linear interpolation."""
    if comp_freqs is None or comp_dbs is None or len(comp_freqs) == 0:
        return 0.0
    return np.interp(freq_hz, comp_freqs, comp_dbs)

def dbm_to_watts_formatted(dbm):
    """Converts dBm to a formatted string in W, mW, or µW."""
    watts = 10**((dbm - 30) / 10)
    if watts >= 1:
        return f"{watts:.2f} W"
    elif watts >= 0.001:
        return f"{watts * 1e3:.2f} mW"
    else:
        return f"{watts * 1e6:.2f} µW"

def format_frequency(freq_hz):
    """
    Formats a frequency in Hz to a string with appropriate units (kHz, MHz, GHz)
    and variable precision to maintain approximately 4 significant figures.
    """
    if freq_hz < 1e6:
        value = freq_hz / 1e3
        unit = "kHz"
    elif freq_hz < 1e9:
        value = freq_hz / 1e6
        unit = "MHz"
    else:
        value = freq_hz / 1e9
        unit = "GHz"

    if value < 10:
        precision = 3
    elif value < 100:
        precision = 2
    else:
        precision = 1
    
    return f"{value:.{precision}f} {unit}"

def parse_frequency(freq_str):
    """Parses a frequency string (e.g., '100mhz', '2.4g') into Hz."""
    freq_str = freq_str.lower().replace(" ", "")
    
    if freq_str.endswith("khz"):
        return float(freq_str[:-3]) * 1e3
    elif freq_str.endswith("k"):
        return float(freq_str[:-1]) * 1e3
    elif freq_str.endswith("mhz"):
        return float(freq_str[:-3]) * 1e6
    elif freq_str.endswith("m"):
        return float(freq_str[:-1]) * 1e6
    elif freq_str.endswith("ghz"):
        return float(freq_str[:-3]) * 1e9
    elif freq_str.endswith("g"):
        return float(freq_str[:-1]) * 1e9
    else:
        return float(freq_str)

def get_search_range(carrier_freq_hz):
    """Determines the spurious emission search range based on carrier frequency."""
    if carrier_freq_hz < 1e6:
        return 10e6
    elif carrier_freq_hz < 10e6:
        return 100e6
    elif carrier_freq_hz < 500e6:
        return 2.5e9
    elif carrier_freq_hz < 3e9:
        return 10e9
    else:
        return 26e9

def get_next_measurement_index(filename='peak_report.csv'):
    """
    Calculates the next measurement index by reading a CSV file.
    If the file doesn't exist, it returns 0. Otherwise, it returns
    the highest index found + 1.
    """
    if not os.path.exists(filename):
        return 0
    
    max_index = -1
    try:
        with open(filename, 'r', newline='') as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
                try:
                    idx_col = header.index('measurement_index')
                except ValueError:
                    print(f"Warning: 'measurement_index' column not found in {filename}. Assuming index 0.")
                    return 0
            except StopIteration:
                return 0 # File is empty

            for row in reader:
                try:
                    if row:
                        current_index = int(row[idx_col])
                        if current_index > max_index:
                            max_index = current_index
                except (ValueError, IndexError):
                    continue
    except IOError:
        print(f"Warning: Could not read {filename}. Assuming index 0.")
        return 0

    return max_index + 1

def append_peaks_to_csv(carrier_peaks, spurious_peaks, comp_freqs, comp_dbs, filename='peak_report.csv', measurement_index=None, timestamp=None):
    """Appends a list of carrier and spurious peaks to a CSV file."""
    if measurement_index is None:
        measurement_index = get_next_measurement_index(filename)
    if timestamp is None:
        timestamp = datetime.datetime.now().isoformat()
    
    fieldnames = [
        'measurement_index', 'timestamp', 'peak_type', 
        'frequency_hz', 'measured_power_dbm', 'compensation_db', 'corrected_power_dbm'
    ]
    
    rows_to_write = []
    
    for freq, power in carrier_peaks:
        comp_db = get_compensation(freq, comp_freqs, comp_dbs)
        corrected_power = power - comp_db
        rows_to_write.append({
            'measurement_index': measurement_index, 'timestamp': timestamp, 'peak_type': 'carrier',
            'frequency_hz': freq, 'measured_power_dbm': power,
            'compensation_db': comp_db, 'corrected_power_dbm': corrected_power
        })

    for freq, power in spurious_peaks:
        comp_db = get_compensation(freq, comp_freqs, comp_dbs)
        corrected_power = power - comp_db
        rows_to_write.append({
            'measurement_index': measurement_index, 'timestamp': timestamp, 'peak_type': 'spurious',
            'frequency_hz': freq, 'measured_power_dbm': power,
            'compensation_db': comp_db, 'corrected_power_dbm': corrected_power
        })

    if not rows_to_write:
        return

    file_exists = os.path.exists(filename)
    try:
        with open(filename, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(rows_to_write)
        print(f"\nAppended {len(rows_to_write)} peaks to {filename} with measurement index {measurement_index}.")
    except IOError as e:
        print(f"\nError writing to {filename}: {e}")

def separate_carrier_and_spurious(peaks, carrier_freq):
    """Separates a list of peaks into carrier and spurious signals."""
    carrier_peaks, spurious_peaks = [], []
    tolerance = max(carrier_freq * 0.01, 100e3)
    for freq, power in peaks:
        if abs(freq - carrier_freq) < tolerance:
            carrier_peaks.append((freq, power))
        else:
            spurious_peaks.append((freq, power))
    return carrier_peaks, spurious_peaks

def parse_peak_data(raw_signals):
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
