Simple script to interface with an HP8953EM spectrum analyzer to perform semi-automated emissions testing.

It should be pretty easy to modify for other devices, though it leans pretty heavily on the auto-measure function which detects peaks, then zero-spans on each detected peak to get a more accurate measurement. 
Really overkill for my purposes, but it's the SA I've got, so I may as well use it!

To use:
0. Ensure your SA is accessible on GPIB address 18, (or adjust the code to your address).
1. Run the script, let it send the initial setup commands.
2. Send the signal of interest, let the SA auto-range the amplitude and attenuation as needed.
3. Continuing to send the signal of interest, enter the expected carrier frequency of your emission.
4. Let it run to completion.

This should produce a report on the command line as well as an output file called peak_report.csv with the info for further analysis. 
Each run will append to the report with a new measurement index, so you should be fine to run it multiple times for different devices as long as you keep track of what the measurement indices mean.
Leave yourself a note when prompted about the measurement!

If you are using an external attenuator or RF tap, add a file called 'ext_att_compensation.csv' with lines containing freq (Hz), dB pairs.
The program will use linear interpolation, so if you just enter one value it will assume a flat attenuator.
However, if you have characterized your attenuator flatness across data points near frequencies of interest, it will be a somewhat more accurate measurement.

The output file contains both the measured power, compensation factor used, and the corrected power, so if you made a mistake in the compensation factors you don't have to remeasure everything.

### Compensation File Generator

A program, `generate_compensation.py`, is included to help generate or update the `ext_att_compensation.csv` file. This is useful for characterizing the loss of cables, attenuators, or antennas.

To use `generate_compensation.py`:
1. Connect the output of the spectrum analyzer's tracking generator to its input (or through the device/system you want to characterize).
2. Run the script: `python generate_compensation.py`
3. Enter the start and end frequencies for the range you want to measure.
4. The script will then perform one or more sweeps to cover the requested frequency range.
    * If the requested frequency range has an end frequency more than 10 times the start frequency, the script will automatically break the measurement into multiple segments.
    * For each sweep, the script captures 401 data points.
5. The measured attenuation values are saved to `ext_att_compensation.csv`.
6. If the file already exists, the script will intelligently update it, removing any old data points that are within a 10% frequency tolerance of new measurements to prevent duplicates.
