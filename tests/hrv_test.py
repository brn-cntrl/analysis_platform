import neurokit2 as nk
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

pg_data = pd.read_csv("../data/G3_1.4.2_2025-05-22T204215.885316_eGFub25vdmFhcmlhQHlhaG9vLmNvbQ/emotibit_data/2025-05-22_20-42-36_eGFub25vdmFhcmlhQHlhaG9vLmNvbQ==_emotibit_ground_truth_PG.csv")
pi_data = pd.read_csv("../data/G3_1.4.2_2025-05-22T204215.885316_eGFub25vdmFhcmlhQHlhaG9vLmNvbQ/emotibit_data/2025-05-22_20-42-36_eGFub25vdmFhcmlhQHlhaG9vLmNvbQ==_emotibit_ground_truth_PI.csv")
pr_data = pd.read_csv("../data/G3_1.4.2_2025-05-22T204215.885316_eGFub25vdmFhcmlhQHlhaG9vLmNvbQ/emotibit_data/2025-05-22_20-42-36_eGFub25vdmFhcmlhQHlhaG9vLmNvbQ==_emotibit_ground_truth_PR.csv")

pg_signal = pg_data.iloc[:, -1].values
pi_signal = pi_data.iloc[:, -1].values
pr_signal = pr_data.iloc[:, -1].values

timestamps = pi_data['LocalTimestamp'].values
sampling_rate = int(round(1 / np.mean(np.diff(timestamps))))

pg_signal = pg_signal[~np.isnan(pg_signal)]
pi_signal = pi_signal[~np.isnan(pi_signal)]
pr_signal = pr_signal[~np.isnan(pr_signal)]

pg_cleaned = nk.ppg_clean(pg_signal, sampling_rate=sampling_rate)
pi_cleaned = nk.ppg_clean(pi_signal, sampling_rate=sampling_rate)
pr_cleaned = nk.ppg_clean(pr_signal, sampling_rate=sampling_rate)

# Try PI first
signals, info = nk.ppg_process(pi_cleaned, sampling_rate=sampling_rate)

peaks = info["PPG_Peaks"]
hrv_indices = nk.hrv(peaks, sampling_rate=sampling_rate, show=True)

print("\n=== HRV Indices from PI Signal ===")
print(hrv_indices.T)

def assess_signal_quality(signal, name, sampling_rate):
    cleaned = nk.ppg_clean(signal, sampling_rate=sampling_rate)
    signals, info = nk.ppg_process(cleaned, sampling_rate=sampling_rate)
    peaks = info["PPG_Peaks"]

    num_peaks = len(peaks)
    duration = len(signal) / sampling_rate / 60 # in minutes
    avg_hr = num_peaks / duration if duration > 0 else 0

    print(f"\n=== {name} Signal Quality Assessment ===")
    print(f"Number of detected peaks: {num_peaks}")
    print(f"Duration (minutes): {duration:.2f}")
    print(f"Average Heart Rate (bpm): {avg_hr:.2f}")

    return signals, info

signals_pi, info_pi = assess_signal_quality(pi_signal, "Infrared (PI)", sampling_rate)
signals_pg, info_pg = assess_signal_quality(pg_signal, "Green (PG)", sampling_rate)
signals_pr, info_pr = assess_signal_quality(pr_signal, "Red (PR)", sampling_rate)

# ========== NEUROKIT HRV VISUALIZATIONS ==========

# 1. Plot PPG signal with detected peaks
nk.ppg_plot(signals, info)
plt.suptitle('PPG Signal Analysis', fontsize=14, fontweight='bold')
plt.show()

# 2. Time Domain HRV Analysis
nk.hrv_time(peaks, sampling_rate=sampling_rate, show=True)
plt.suptitle('Time Domain HRV Metrics', fontsize=14, fontweight='bold')
plt.show()

# 3. Frequency Domain HRV Analysis
nk.hrv_frequency(peaks, sampling_rate=sampling_rate, show=True)
plt.suptitle('Frequency Domain HRV Analysis', fontsize=14, fontweight='bold')
plt.show()

# 4. Non-linear HRV Analysis (Poincaré Plot)
nk.hrv_nonlinear(peaks, sampling_rate=sampling_rate, show=True)
plt.suptitle('Non-linear HRV Analysis', fontsize=14, fontweight='bold')
plt.show()

# Optional: Save results
hrv_indices.to_csv('hrv_results.csv', index=False)
print("\nHRV results saved to 'hrv_results.csv'")