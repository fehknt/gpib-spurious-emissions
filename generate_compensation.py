import numpy as np
import pyvisa as visa
import time
import analysis
from hp8593em import HP8593EM
import pandas as pd
import os

COMPENSATION_FILE = 'ext_att_compensation.csv'

def get_frequency_range():
    """Prompts user for start and end frequencies."""
    while True:
        try:
            start_freq_str = input("Enter start frequency (e.g., 100kHz, 1.5GHz): ")
            start_freq_hz = analysis.parse_frequency(start_freq_str)
            
            end_freq_str = input("Enter end frequency (e.g., 2.4GHz, 11GHz): ")
            end_freq_hz = analysis.parse_frequency(end_freq_str)

            if 100e3 <= start_freq_hz < end_freq_hz <= 11e9:
                return start_freq_hz, end_freq_hz
            else:
                print("Frequency must be between 100kHz and 11GHz, and start frequency must be less than end frequency.")
        except (ValueError, IndexError):
            print("Invalid input. Please enter a valid frequency (e.g., '100mhz', '2.4g').")

def update_compensation_file(new_points, filename):
    """
    Adds new points to the compensation file, removing any existing points
    within a 10% frequency tolerance.
    """
    if os.path.exists(filename):
        df = pd.read_csv(filename, header=0, names=['frequency', 'attenuation'], comment='#')
    else:
        df = pd.DataFrame(columns=['frequency', 'attenuation'])

    for freq, att in new_points:
        # Remove existing points within 10% of the new frequency
        df = df[~((df['frequency'] >= freq * 0.9) & (df['frequency'] <= freq * 1.1))]
    
    new_df = pd.DataFrame(new_points, columns=['frequency', 'attenuation'])
    df = pd.concat([df, new_df], ignore_index=True)
    df = df.sort_values(by='frequency').reset_index(drop=True)

    with open(filename, 'w') as f:
        f.write("# Frequency (Hz), Attenuation (dB)\n")
        df.to_csv(f, index=False, header=False)
    print(f"\nUpdated {filename} with {len(new_points)} new points.")

def generate_frequency_ranges(start_freq, end_freq):
    """Splits a frequency range into sub-ranges with a max 10x span ratio."""
    if start_freq >= end_freq:
        return []

    ranges = []
    current_freq = start_freq
    while current_freq < end_freq:
        span_start = current_freq
        span_end = min(span_start * 10, end_freq)
        ranges.append((span_start, span_end))
        current_freq = span_end
    return ranges

def main():
    """Main execution function."""
    GPIB_ADDRESS = "GPIB0::18::INSTR"
    sa = None

    try:
        sa = HP8593EM(GPIB_ADDRESS)
        print(f"Connected to: {sa.get_id()}")
        
        start_freq, end_freq = get_frequency_range()
        
        frequency_ranges = generate_frequency_ranges(start_freq, end_freq)
        all_compensation_points = []
        
        min_atten_overall = (float('inf'), 0)
        max_atten_overall = (float('-inf'), 0)

        for i, (sub_start_freq, sub_end_freq) in enumerate(frequency_ranges):
            print(f"\n--- Measuring sub-range {i+1}/{len(frequency_ranges)}: {analysis.format_frequency(sub_start_freq)} to {analysis.format_frequency(sub_end_freq)} ---")

            # Configure spectrum analyzer for a single sweep using center and span
            center_freq = (sub_start_freq + sub_end_freq) / 2
            span_freq = sub_end_freq - sub_start_freq
            sa.set_center_frequency(center_freq)
            sa.set_span(span_freq)
            
            # Verify the actual frequencies set on the analyzer
            actual_start_freq = sa.get_start_frequency()
            actual_end_freq = sa.get_end_frequency()

            print(f"  Actual measurement range: {analysis.format_frequency(actual_start_freq)} to {analysis.format_frequency(actual_end_freq)}")
            
            sa.set_reference_level(0) # RL 0DBM
            sa.set_tracking_generator_power(0) # SRCPWR 0DB
            sa.set_trace_data_format('M') # TDF M
            time.sleep(0.5) # Wait for settings to apply

            # Take a sweep and wait for it to complete
            sa.take_sweep_and_wait()

            # Get trace data
            try:
                raw_data = sa.get_trace_data(1)
                raw_points = [float(p) for p in raw_data.strip().split('\r')]
                
                attenuations = [80 - (p / 100) for p in raw_points]
                
                num_points = len(attenuations)
                frequencies = np.linspace(actual_start_freq, actual_end_freq, num_points)
                
                new_compensation_points = list(zip(frequencies, attenuations))
                all_compensation_points.extend(new_compensation_points)

                min_atten_segment = min(attenuations)
                max_atten_segment = max(attenuations)
                if min_atten_segment < min_atten_overall[0]:
                    min_atten_overall = (min_atten_segment, frequencies[attenuations.index(min_atten_segment)])
                if max_atten_segment > max_atten_overall[0]:
                    max_atten_overall = (max_atten_segment, frequencies[attenuations.index(max_atten_segment)])

            except (ValueError, IndexError) as e:
                print(f"  Could not parse attenuation data: {e}")
            except visa.errors.VisaIOError as e:
                print(f"  VISA error during measurement: {e}")

        if all_compensation_points:
            update_compensation_file(all_compensation_points, COMPENSATION_FILE)

            print("\n--- Overall Attenuation Summary ---")
            print(f"Minimum Attenuation: {min_atten_overall[0]:.2f} dB at {analysis.format_frequency(min_atten_overall[1])}")
            print(f"Maximum Attenuation: {max_atten_overall[0]:.2f} dB at {analysis.format_frequency(max_atten_overall[1])}")

    except visa.errors.VisaIOError as e:
        print(f"\nError communicating with instrument: {e}")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if sa:
            sa.close()
        print("\nConnection closed.")

if __name__ == "__main__":
    main()
