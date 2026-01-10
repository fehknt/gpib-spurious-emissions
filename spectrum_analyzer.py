from hp8593em import HP8593EM
import pyvisa as visa
import time
import analysis
from visa_utils import discover_and_connect

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



def main():
    """Main execution function."""
    comp_freqs, comp_dbs = analysis.load_compensation_file(COMPENSATION_FILE)
    sa = None

    try:
        device_map = {'8593EM': HP8593EM}
        found_devices = discover_and_connect(device_map)
        sa = found_devices['8593EM']
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
        
        note = input("Enter a note for this measurement: ")
        analysis.append_peaks_to_csv(carrier_peaks, spurious_peaks, comp_freqs, comp_dbs, note)

    except (visa.errors.VisaIOError, ConnectionError) as e:
        print(f"Error communicating with instrument: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if sa:
            sa.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()