from matplotlib.colors import LinearSegmentedColormap
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

FORCE_THRESHOLD = 0.5
MIN_CYCLE_POINTS = 5

CURRENT_SHUNT_RESISTOR_OHM = 50


'''
DATA PROCESSING FUNCTIONS
'''

contact_start_threshold = 0.5
contact_end_threshold = 0.2


def load_data(file_path):
    """
    Loads old or new CSV files.

    Supports metadata at the top of the file, then a real CSV header such as:

        time_s,force_N,voltage_V,current_A

    Output columns are normalised to:

        time, force, voltage, current

    Current is assumed to already be real current in amps.
    """

    header_row = None

    # Find the actual data header row
    with open(file_path, "r", errors="ignore") as f:
        for i, line in enumerate(f):
            line_clean = line.strip().lower()

            if not line_clean:
                continue

            if line_clean.startswith("#"):
                continue

            if "time" in line_clean and "force" in line_clean:
                header_row = i
                break

    if header_row is None:
        raise ValueError(f"Could not find data header row in {file_path}")

    # Important: use normal comma CSV reading.
    # Do NOT use a regex separator, because it collapses empty fields.
    df = pd.read_csv(
        file_path,
        skiprows=header_row
    )

    # Clean column names
    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    # Rename new saved column names to analysis-friendly names
    rename_map = {
        "time_s": "time",
        "force_N": "force",
        "voltage_V": "voltage",
        "current_A": "current",

        # Older possible names
        "time": "time",
        "force": "force",
        "voltage": "voltage",
        "current": "current",
    }

    df = df.rename(columns=rename_map)

    # Keep only recognised columns
    keep_cols = [
        c for c in ["time", "force", "voltage", "current"]
        if c in df.columns
    ]

    df = df[keep_cols].copy()

    if "time" not in df.columns or "force" not in df.columns:
        raise ValueError(f"File must contain time and force columns: {file_path}")

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Only require time and force
    df = df.dropna(subset=["time", "force"]).reset_index(drop=True)

    # Remove voltage/current only if completely empty
    if "voltage" in df.columns and df["voltage"].isna().all():
        df = df.drop(columns=["voltage"])

    if "current" in df.columns and df["current"].isna().all():
        df = df.drop(columns=["current"])

    # Remove out-of-order time glitches
    bad_rows = df.index[
        df["time"].shift(-1) < df["time"]
    ]

    df = df.drop(bad_rows).reset_index(drop=True)

    return df


def read_target_force(file_path):
    target_force = None

    with open(file_path, "r") as f:
        for line in f:

            if "# Target Force (N)" in line:
                parts = line.strip().split(",")

                if len(parts) >= 2:
                    try:
                        target_force = float(parts[1])
                    except:
                        pass

            if "time" in line.lower():
                break

    return target_force


def read_load_resistance(file_path):

    with open(file_path, "r") as f:
        for line in f:

            if "# Load Resistance (Ohm)" in line:
                parts = line.strip().split(",")

                if len(parts) >= 2:
                    value = parts[1].strip()

                    if value.lower() in ["inf", "infinity", "open"]:
                        return np.inf

                    if value.lower() in ["0", "short"]:
                        return 0

                    return float(value)

            if "time" in line.lower():
                break

    return None

def read_measurement_mode(file_path):
    """
    Reads the measurement mode from CSV metadata.

    Expected metadata line:
        # Measurement Mode,VOLTAGE
        # Measurement Mode,CURRENT
        # Measurement Mode,DUAL

    Returns None if not found.
    """

    with open(file_path, "r") as f:

        for line in f:

            if "# Measurement Mode" in line:

                parts = line.strip().split(",")

                if len(parts) >= 2:
                    return parts[1].strip()

            if "time" in line.lower():
                break

    return None

'''
CYCLE PROCESSING FUNCTIONS
'''


def find_cycles(
    df,
    force_col="force",
    start_threshold=contact_start_threshold,
    end_threshold=contact_end_threshold
):
    """
    Detects contact cycles using hysteresis.

    Start contact:
        force >= start_threshold

    End contact:
        force <= end_threshold
    """

    cycles = []
    in_contact = False
    start_index = None

    for idx, force in zip(df.index, df[force_col]):

        if not in_contact and force >= start_threshold:
            in_contact = True
            start_index = idx

        elif in_contact and force <= end_threshold:
            in_contact = False
            end_index = idx

            if start_index is not None:
                cycles.append(
                    (start_index, end_index)
                )

            start_index = None

    return cycles


def find_steady_force_region(
    cycle_df,
    target_force,
    steady_force_tolerance=0.12,
    max_steady_dfdt=45.0,
    min_steady_points=2,
    smoothing_window=3,
    max_gap_points=2,
    fallback_ratio=0.99,
    start_padding_points=0
):
    import numpy as np

    cycle = cycle_df.copy().reset_index(drop=True)

    # -------------------------
    # Smooth force slightly
    # -------------------------
    cycle["force_smooth"] = (
        cycle["force"]
        .rolling(
            window=smoothing_window,
            center=True,
            min_periods=1
        )
        .mean()
    )

    # -------------------------
    # Forward derivative
    # Measures how force changes AFTER each point
    # -------------------------
    cycle["dF_dt"] = (
        cycle["force_smooth"].shift(-1) - cycle["force_smooth"]
    ) / (
        cycle["time"].shift(-1) - cycle["time"]
    )

    cycle["dF_dt"] = cycle["dF_dt"].replace([np.inf, -np.inf], np.nan)
    cycle["dF_dt"] = cycle["dF_dt"].bfill().ffill()

    # -------------------------
    # Define target-force band
    # -------------------------
    lower_force_limit = target_force * (1 - steady_force_tolerance)
    upper_force_limit = target_force * (1 + steady_force_tolerance)

    near_target = (
        (cycle["force_smooth"] >= lower_force_limit)
        &
        (cycle["force_smooth"] <= upper_force_limit)
    )

    # -------------------------
    # Define low-slope region
    # -------------------------
    low_slope = cycle["dF_dt"].abs() <= max_steady_dfdt

    cycle["steady_candidate"] = near_target & low_slope

    # -------------------------
    # Fill small gaps caused by noise
    # -------------------------
    steady = cycle["steady_candidate"].copy()

    for i in range(len(steady)):
        if not steady.iloc[i]:
            left_start = max(0, i - max_gap_points)
            right_end = min(len(steady), i + max_gap_points + 1)

            left_good = steady.iloc[left_start:i].any()
            right_good = steady.iloc[i + 1:right_end].any()

            if left_good and right_good:
                steady.iloc[i] = True

    cycle["steady_candidate"] = steady

    # -------------------------
    # Find continuous steady regions
    # -------------------------
    cycle["region_id"] = (
        cycle["steady_candidate"] != cycle["steady_candidate"].shift()
    ).cumsum()

    valid_regions = []

    for _, region in cycle.groupby("region_id"):
        if region["steady_candidate"].iloc[0] and len(region) >= min_steady_points:
            valid_regions.append(region)

    # -------------------------
    # Choose longest steady region
    # -------------------------
    if valid_regions:

        steady_region = max(valid_regions, key=len).copy()
        steady_method = "near_target_forward_dFdt_with_padding"

        start_idx = steady_region.index[0]
        end_idx = steady_region.index[-1]

        # Move start slightly earlier to avoid over-conservative detection
        start_idx = max(0, start_idx - start_padding_points)

        steady_region = cycle.loc[start_idx:end_idx].copy()

    else:
        # -------------------------
        # Fallback: use upper part of the force cycle
        # -------------------------
        max_force = cycle["force_smooth"].max()

        steady_region = cycle[
            cycle["force_smooth"] >= fallback_ratio * max_force
        ].copy()

        steady_method = "fallback_top_force_region"

    # -------------------------
    # Final fallback
    # -------------------------
    if len(steady_region) < min_steady_points:
        steady_region = cycle.copy()
        steady_method = "fallback_whole_cycle"

    steady_start_time = steady_region["time"].iloc[0]
    steady_end_time = steady_region["time"].iloc[-1]

    return steady_region, steady_method, steady_start_time, steady_end_time


def detect_mad_outliers(values, threshold=4.0):

        values = np.array(values)

        if len(values) < 4:
            return np.zeros(len(values), dtype=bool)

        median = np.median(values)
        mad = np.median(np.abs(values - median))

        if mad == 0:
            return np.zeros(len(values), dtype=bool)

        modified_z_score = 0.6745 * (values - median) / mad

        return np.abs(modified_z_score) > threshold


def baseline_correct_signal(signal, baseline_method="zero"):

    signal = np.asarray(signal, dtype=float)

    if baseline_method == "median":
        baseline = np.median(signal)

    elif baseline_method == "mean":
        baseline = np.mean(signal)

    elif baseline_method == "zero":
        baseline = 0

    else:
        baseline = 0

    return signal - baseline


'''
OUTPUT SIGNAL ANALYSIS
'''

def calculate_cycle_peak_rms_metrics(df, signal_col, baseline_method="zero"):
    """
    Calculate per-cycle positive peak, negative peak magnitude, mean rectified peak,
    max absolute peak, and RMS for one signal column.
    """

    if signal_col not in df.columns:
        raise ValueError(f"Column '{signal_col}' not found.")

    cycle_results = []
    cycles = find_cycles(df)

    for cycle_number, (start, end) in enumerate(cycles, start=1):
        cycle = df.loc[start:end]

        if len(cycle) < MIN_CYCLE_POINTS:
            continue

        signal = cycle[signal_col].dropna().to_numpy()

        if len(signal) == 0:
            continue

        corrected = baseline_correct_signal(signal, baseline_method=baseline_method)

        positive_peak = np.nanmax(corrected)
        negative_peak_abs = abs(np.nanmin(corrected))
        rectified_peak = (positive_peak + negative_peak_abs) / 2
        max_abs_peak = np.nanmax(np.abs(corrected))
        rms = np.sqrt(np.nanmean(corrected ** 2))

        cycle_results.append({
            "cycle": cycle_number,
            "positive_peak": positive_peak,
            "negative_peak_abs": negative_peak_abs,
            "rectified_peak": rectified_peak,
            "max_abs_peak": max_abs_peak,
            "rms": rms
        })

    cycle_df = pd.DataFrame(cycle_results)

    if len(cycle_df) == 0:
        summary = {
            "mean_peak": np.nan,
            "std_peak": np.nan,
            "mean_rectified_peak": np.nan,
            "std_rectified_peak": np.nan,
            "mean_max_abs_peak": np.nan,
            "std_max_abs_peak": np.nan,
            "mean_rms": np.nan,
            "std_rms": np.nan,
            "n_cycles": 0,
            "cycle_peaks": []
        }
        return cycle_df, summary

    summary = {
        "mean_peak": cycle_df["rectified_peak"].mean(),
        "std_peak": cycle_df["rectified_peak"].std(ddof=1),
        "mean_rectified_peak": cycle_df["rectified_peak"].mean(),
        "std_rectified_peak": cycle_df["rectified_peak"].std(ddof=1),
        "mean_max_abs_peak": cycle_df["max_abs_peak"].mean(),
        "std_max_abs_peak": cycle_df["max_abs_peak"].std(ddof=1),
        "mean_rms": cycle_df["rms"].mean(),
        "std_rms": cycle_df["rms"].std(ddof=1),
        "n_cycles": len(cycle_df),
        "cycle_peaks": cycle_df["rectified_peak"].tolist()
    }

    return cycle_df, summary

def plot_metric_vs_force(
    df,
    metric_col,
    ylabel,
    title,
    filename,
    output_folder,
    colour="tab:blue",
    scale=1,
    group_col=None
):

    plt.figure(figsize=(8, 6))

    if group_col is None:

        plt.plot(
            df["Target Force (N)"],
            df[metric_col] * scale,
            marker="o",
            color=colour
        )

    else:

        for group in df[group_col].unique():

            subset = df[
                df[group_col] == group
            ].sort_values("Target Force (N)")

            plt.plot(
                subset["Target Force (N)"],
                subset[metric_col] * scale,
                marker="o",
                label=group
            )

        plt.legend()

    plt.xlabel("Target Force (N)")
    plt.ylabel(ylabel)
    plt.title(title)

    plt.grid(
        True,
        linestyle="--",
        alpha=0.4
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(output_folder, filename),
        dpi=300
    )

    plt.close()

def build_signal_summary_row(
    file,
    signal_col,
    target_force,
    load_resistance,
    measurement_mode,
    summary
):

    mean_peak = summary["mean_rectified_peak"]
    std_peak = summary["std_rectified_peak"]

    mean_rms = summary["mean_rms"]
    std_rms = summary["std_rms"]

    return {
        "File": file,
        "Signal": signal_col,
        "Measurement Mode": measurement_mode,
        "Target Force (N)": target_force,
        "Load Resistance (Ohm)": load_resistance,

        "Mean Rectified Peak": mean_peak,
        "STD Rectified Peak": std_peak,
        "CV Rectified Peak (%)": (
            std_peak / mean_peak * 100
            if mean_peak != 0
            else np.nan
        ),

        "Mean RMS": mean_rms,
        "STD RMS": std_rms,
        "CV RMS (%)": (
            std_rms / mean_rms * 100
            if mean_rms != 0
            else np.nan
        ),

        "Cycles Analysed": summary["n_cycles"]
    }



'''
RIG VALIDATION FUNCTIONS:
'''

def analyse_calibration_folder(folder_path):

    all_cycle_data = []
    test_summary_data = []

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if (
            f.endswith(".csv")
            and "_analysis" not in f
            and "_analysed" not in f
        )
    ])

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")

    for file_index, file in enumerate(csv_files):

        full_path = os.path.join(folder_path, file)

        target_force = read_target_force(full_path)

        if target_force is None:
            print(f"Skipping {file}: no target force found.")
            continue

        df = load_data(full_path)

        if len(df) == 0:
            continue

        # Keep only the columns needed for force calibration
        df = df[["time", "force"]].dropna()

        cycles = find_cycles(df)

        if len(cycles) == 0:
            continue

        peak_forces = []

        for cycle_num, (start, end) in enumerate(cycles, start=1):

            cycle = df.loc[start:end]

            if len(cycle) < MIN_CYCLE_POINTS:
                continue

            peak_force = cycle["force"].max()
            peak_forces.append(peak_force)

            absolute_error = peak_force - target_force
            percent_error = (absolute_error / target_force) * 100

            all_cycle_data.append({
                "File": file,
                "Target Force (N)": target_force,
                "Cycle": cycle_num,
                "Peak Force (N)": peak_force,
                "Absolute Error (N)": absolute_error,
                "Percent Error (%)": percent_error
            })

        if len(peak_forces) == 0:
            continue

        peak_forces = np.array(peak_forces)

        mean_peak = np.mean(peak_forces)

        std_peak = (
            np.std(peak_forces, ddof=1)
            if len(peak_forces) > 1
            else np.nan
        )

        cv_peak = (
            (std_peak / mean_peak) * 100
            if mean_peak != 0 and not np.isnan(std_peak)
            else np.nan
        )

        force_range = np.max(peak_forces) - np.min(peak_forces)
        abs_error = mean_peak - target_force
        pct_error = (abs_error / target_force) * 100

        rms_error = np.sqrt(
            np.mean((peak_forces - target_force) ** 2)
        )

        test_summary_data.append({
            "File": file,
            "Target Force (N)": target_force,
            "Mean Peak Force (N)": mean_peak,
            "STD Peak Force (N)": std_peak,
            "CV (%)": cv_peak,
            "Range (N)": force_range,
            "Min Peak Force (N)": np.min(peak_forces),
            "Max Peak Force (N)": np.max(peak_forces),
            "Absolute Error (N)": abs_error,
            "Percent Error (%)": pct_error,
            "RMS Error (N)": rms_error
        })

        # Drift plot
        plt.figure(figsize=(7, 5))

        plt.plot(
            range(1, len(peak_forces) + 1),
            peak_forces,
            marker="o",
            color = PLOT_COLOURS['force']
        )

        plt.axhline(target_force, linestyle="--", color="red", label="Target")

        plt.xlabel("Cycle Number")
        plt.ylabel("Peak Force (N)")
        plt.title(f"{int(target_force)}N Calibration Drift")

        plt.tight_layout()

        plt.savefig(
            os.path.join(folder_path, f"{int(target_force)}N_Drift.png"),
            dpi=300
        )

        plt.close()

        # Individual violin plot
        plt.figure(figsize=(4, 6))
        
        FORCE_WINDOW = 0.4  # total displayed range in N

        half_window = FORCE_WINDOW / 2

        plt.ylim(
            target_force - half_window,
            target_force + half_window
        )

        # plt.boxplot(peak_forces)
        # plt.axhline(target_force, linestyle="--")

        violinplt = plt.violinplot(peak_forces, showmeans=True)
        
        for bodies in violinplt['bodies']:
            bodies.set_facecolor(PLOT_COLOURS['force'])
            bodies.set_alpha(0.7)

        for partname in ('cbars', 'cmins', 'cmaxes', 'cmeans'):
            vp = violinplt[partname]
            vp.set_edgecolor("#CFAE4A")
            vp.set_linewidth(1)

        plt.axhline(target_force, linestyle="--", color="red", label="Target")


        plt.ylabel("Peak Force (N)")
        plt.title(f"{int(target_force)}N Repeatability")

        plt.tight_layout()

        plt.savefig(
            os.path.join(folder_path, f"{int(target_force)}N_Boxplot.png"),
            dpi=300
        )

        plt.close()

    all_cycles_df = pd.DataFrame(all_cycle_data)
    test_summary_df = pd.DataFrame(test_summary_data)

    if len(test_summary_df) == 0:
        raise ValueError("No valid calibration data.")

    force_summary_df = test_summary_df.groupby(
        "Target Force (N)"
    ).agg({
        "Mean Peak Force (N)": "mean",
        "STD Peak Force (N)": "mean",
        "CV (%)": "mean",
        "Range (N)": "mean",
        "Absolute Error (N)": "mean",
        "Percent Error (%)": "mean",
        "RMS Error (N)": "mean"
    }).reset_index()

    force_summary_df = force_summary_df.sort_values("Target Force (N)")

    output_excel = os.path.join(
        folder_path,
        "CALIBRATION_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        all_cycles_df.to_excel(
            writer,
            sheet_name="ALL_CYCLES",
            index=False
        )

        test_summary_df.to_excel(
            writer,
            sheet_name="TEST_SUMMARY",
            index=False
        )

        force_summary_df.to_excel(
            writer,
            sheet_name="FORCE_SUMMARY",
            index=False
        )

    # Measured vs target
    plt.figure(figsize=(6, 5))

    plt.plot(
        force_summary_df["Target Force (N)"],
        force_summary_df["Mean Peak Force (N)"],
        marker="o",
        color = PLOT_COLOURS['force'],
        label="Measured"
    )

    plt.plot(
        force_summary_df["Target Force (N)"],
        force_summary_df["Target Force (N)"],
        linestyle="--",
        color = "#FF4F61",
        label="Ideal"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("Measured Force (N)")
    plt.title("Measured vs Target Force")
    plt.legend()

    plt.tight_layout()

    plt.savefig(
        os.path.join(folder_path, "Measured_vs_Target.png"),
        dpi=300
    )

    plt.close()

    def plot_force_summary(y_col, ylabel, title, filename):

        plt.figure(figsize=(6, 5))

        plt.plot(
            force_summary_df["Target Force (N)"],
            force_summary_df[y_col],
            marker="o",
            color = PLOT_COLOURS['force']
        )

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(title)

        plt.tight_layout()

        plt.savefig(
            os.path.join(folder_path, filename),
            dpi=300
        )

        plt.close()

    plot_force_summary(
        "Percent Error (%)",
        "Percent Error (%)",
        "Calibration Percent Error",
        "Percent_Error.png"
    )

    plot_force_summary(
        "STD Peak Force (N)",
        "STD (N)",
        "Calibration Repeatability",
        "STD_vs_Force.png"
    )

    plot_force_summary(
        "CV (%)",
        "CV (%)",
        "Coefficient of Variation",
        "CV_vs_Force.png"
    )

    plot_force_summary(
        "RMS Error (N)",
        "RMS Error (N)",
        "Calibration RMS Error",
        "RMS_vs_Force.png"
    )

    print(f"\nSaved calibration analysis:\n{output_excel}")

    return output_excel


def analyse_force_cycles(file):


    target_force = read_target_force(file)

    if target_force is None:
        raise ValueError(
            "No target force found in metadata. Please enter a target force manually."
        )

    df = load_data(file)

    if len(df) == 0:
        return pd.DataFrame()

    df = df[["time", "force"]].dropna()

    cycles = find_cycles(df)

    results = []

    if len(cycles) == 0:
        return pd.DataFrame(results)

    for i, (start, end) in enumerate(cycles):

        cycle = df.loc[start:end]

        if len(cycle) < MIN_CYCLE_POINTS:
            continue

        max_force = cycle["force"].max()
        min_force = cycle["force"].min()

        steady_region, steady_method, steady_start_time, steady_end_time = find_steady_force_region(
            cycle,
            target_force
        )

        steady_force = steady_region["force"].mean()
        steady_force_std = steady_region["force"].std()

        steady_error = steady_region["force"] - target_force

        rms_error = np.sqrt(
            np.mean(steady_error ** 2)
        )

        contact_duration = (
            cycle["time"].iloc[-1]
            - cycle["time"].iloc[0]
        )

        if i < len(cycles) - 1:

            next_start = cycles[i + 1][0]

            next_start_time = df.loc[
                next_start,
                "time"
            ]

            current_start_time = df.loc[
                start,
                "time"
            ]

            full_cycle_time = next_start_time - current_start_time

            frequency_hz = (
                1 / full_cycle_time
                if full_cycle_time > 0
                else np.nan
            )

        else:
            full_cycle_time = np.nan
            frequency_hz = np.nan

        results.append({
            "cycle": i + 1,
            "target_force_N": target_force,
            "max_force_N": max_force,
            "min_force_N": min_force,
            "steady_force_N": steady_force,
            "steady_force_std_N": steady_force_std,
            "steady_method": steady_method,
            "steady_start_time_s": steady_start_time,
            "steady_end_time_s": steady_end_time,
            "rms_error_N": rms_error,
            "contact_duration_s": contact_duration,
            "full_cycle_time_s": full_cycle_time,
            "frequency_hz": frequency_hz
        })

    return pd.DataFrame(results)


def full_frequency_force_analysis(master_folder):

    frequency_folders = [
        f for f in os.listdir(master_folder)
        if os.path.isdir(os.path.join(master_folder, f))
    ]

    if len(frequency_folders) == 0:
        raise ValueError("No frequency folders found.")

    frequency_folders = sorted(
        frequency_folders,
        key=lambda x: float(x.replace("Hz", ""))
    )

    force_error_data = {}
    force_rms_data = {}
    force_std_data = {}

    freq_error_data = {}
    freq_rms_data = {}
    freq_std_data = {}

    for freq_folder in frequency_folders:

        folder_path = os.path.join(master_folder, freq_folder)

        try:
            target_frequency = float(freq_folder.replace("Hz", ""))
        except:
            print(f"Skipping invalid folder: {freq_folder}")
            continue

        csv_files = [
            f for f in os.listdir(folder_path)
            if f.endswith(".csv")
            and "_analysed" not in f
            and "_force_analysis" not in f
        ]

        temp_force_error = {}
        temp_force_rms = {}
        temp_force_std = {}

        temp_freq_error = {}
        temp_freq_rms = {}
        temp_freq_std = {}

        for file in csv_files:

            full_path = os.path.join(folder_path, file)

            try:
                results_df = analyse_force_cycles(full_path)

                if results_df is None or len(results_df) == 0:
                    continue

                target_force = int(round(
                    results_df["target_force_N"].iloc[0]
                ))

                mean_force = results_df["steady_force_N"].mean()

                force_error_pct = (
                    (mean_force - target_force)
                    / target_force
                ) * 100

                force_rms = results_df["rms_error_N"].mean()

                force_std = results_df[
                    "steady_force_std_N"
                ].mean()

                mean_freq = results_df[
                    "frequency_hz"
                ].mean()

                freq_error_pct = (
                    (mean_freq - target_frequency)
                    / target_frequency
                ) * 100

                freq_std = results_df[
                    "frequency_hz"
                ].std()

                freq_rms = np.sqrt(
                    np.mean(
                        (
                            results_df["frequency_hz"]
                            - target_frequency
                        ) ** 2
                    )
                )

                temp_force_error.setdefault(target_force, [])
                temp_force_rms.setdefault(target_force, [])
                temp_force_std.setdefault(target_force, [])

                temp_freq_error.setdefault(target_force, [])
                temp_freq_rms.setdefault(target_force, [])
                temp_freq_std.setdefault(target_force, [])

                temp_force_error[target_force].append(force_error_pct)
                temp_force_rms[target_force].append(force_rms)
                temp_force_std[target_force].append(force_std)

                temp_freq_error[target_force].append(freq_error_pct)
                temp_freq_rms[target_force].append(freq_rms)
                temp_freq_std[target_force].append(freq_std)

            except Exception as e:
                print(f"Failed processing {file}: {e}")

        for force in sorted(temp_force_error.keys()):

            force_error_data.setdefault(force, {})
            force_rms_data.setdefault(force, {})
            force_std_data.setdefault(force, {})

            freq_error_data.setdefault(force, {})
            freq_rms_data.setdefault(force, {})
            freq_std_data.setdefault(force, {})

            force_error_data[force][freq_folder] = np.mean(
                temp_force_error[force]
            )

            force_rms_data[force][freq_folder] = np.mean(
                temp_force_rms[force]
            )

            force_std_data[force][freq_folder] = np.mean(
                temp_force_std[force]
            )

            freq_error_data[force][freq_folder] = np.mean(
                temp_freq_error[force]
            )

            freq_rms_data[force][freq_folder] = np.mean(
                temp_freq_rms[force]
            )

            freq_std_data[force][freq_folder] = np.mean(
                temp_freq_std[force]
            )

    def build_metric_table(metric_dict, metric_name):

        rows = []

        for force in sorted(metric_dict.keys()):

            row = {
                metric_name: force
            }

            for freq in frequency_folders:
                row[freq] = metric_dict[force].get(freq, np.nan)

            rows.append(row)

        return pd.DataFrame(rows)

    force_error_df = build_metric_table(force_error_data, "% error")
    force_rms_df = build_metric_table(force_rms_data, "RMS")
    force_std_df = build_metric_table(force_std_data, "STD")

    freq_error_df = build_metric_table(freq_error_data, "% error")
    freq_rms_df = build_metric_table(freq_rms_data, "RMS")
    freq_std_df = build_metric_table(freq_std_data, "STD")

    output_file = os.path.join(
        master_folder,
        "FULL_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:

        start_row = 0

        force_error_df.to_excel(
            writer,
            sheet_name="FORCE_ANALYSIS",
            index=False,
            startrow=start_row
        )

        start_row += len(force_error_df) + 3

        force_rms_df.to_excel(
            writer,
            sheet_name="FORCE_ANALYSIS",
            index=False,
            startrow=start_row
        )

        start_row += len(force_rms_df) + 3

        force_std_df.to_excel(
            writer,
            sheet_name="FORCE_ANALYSIS",
            index=False,
            startrow=start_row
        )

        start_row = 0

        freq_error_df.to_excel(
            writer,
            sheet_name="FREQUENCY_ANALYSIS",
            index=False,
            startrow=start_row
        )

        start_row += len(freq_error_df) + 3

        freq_rms_df.to_excel(
            writer,
            sheet_name="FREQUENCY_ANALYSIS",
            index=False,
            startrow=start_row
        )

        start_row += len(freq_rms_df) + 3

        freq_std_df.to_excel(
            writer,
            sheet_name="FREQUENCY_ANALYSIS",
            index=False,
            startrow=start_row
        )

    def plot_metric(metric_df, metric_col, ylabel, title, filename):

        plt.figure(figsize=(7, 5))

        forces = metric_df[metric_col]


        for i, freq in enumerate(frequency_folders):

            if freq in metric_df.columns:

                plt.plot(
                    forces,
                    metric_df[freq],
                    marker="o",
                    color=get_default_colour(i),
                    label=freq
                )

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.legend(title="Target Frequency")
        plt.tight_layout()

        plt.savefig(
            os.path.join(master_folder, filename),
            dpi=300
        )

        plt.close()

    plot_metric(
        force_error_df,
        "% error",
        "Force Error (%)",
        "Mean Stable Force Percentage Error",
        "Force_Percent_Error_vs_Target_Force.png"
    )

    plot_metric(
        force_rms_df,
        "RMS",
        "RMS Force Error (N)",
        "RMS Error of Stable Force",
        "Force_RMS_Error_vs_Target_Force.png"
    )

    plot_metric(
        force_std_df,
        "STD",
        "Force STD (N)",
        "Force Stability STD",
        "Force_STD_vs_Target_Force.png"
    )

    plot_metric(
        freq_error_df,
        "% error",
        "Frequency Error (%)",
        "Frequency Percentage Error",
        "Frequency_Percent_Error_vs_Target_Force.png"
    )

    plot_metric(
        freq_rms_df,
        "RMS",
        "Frequency RMS Error (Hz)",
        "Frequency RMS Error",
        "Frequency_RMS_Error_vs_Target_Force.png"
    )

    plot_metric(
        freq_std_df,
        "STD",
        "Frequency STD (Hz)",
        "Frequency Stability STD",
        "Frequency_STD_vs_Target_Force.png"
    )
    

    # =====================================================
    # HEATMAP: FORCE, FREQUENCY, RMS FREQ ERROR
    # =====================================================

    heatmap_df = freq_rms_df.set_index("RMS")
    heatmap_df = heatmap_df[frequency_folders]


    plt.figure(figsize=(8, 6))

    plt.imshow(
        heatmap_df.values,
        cmap=custom_cmap,
        aspect="auto"
    )

    plt.xticks(
        range(len(heatmap_df.columns)),
        heatmap_df.columns
    )

    plt.yticks(
        range(len(heatmap_df.index)),
        [f"{int(force)}N" for force in heatmap_df.index]
    )

    plt.xlabel("Target Frequency")
    plt.ylabel("Target Force")
    plt.title("RMS Frequency Error Heatmap")

    cbar = plt.colorbar()
    cbar.set_label("RMS Frequency Error (Hz)")

    for i in range(len(heatmap_df.index)):
        for j in range(len(heatmap_df.columns)):

            value = heatmap_df.iloc[i, j]

            if pd.notna(value):
                plt.text(
                    j,
                    i,
                    f"{value:.2f}",
                    ha="center",
                    va="center"
                )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            master_folder,
            "RMS_Frequency_Error_Heatmap.png"
        ),
        dpi=300
    )

    plt.close()




    # =====================================================
    # HEATMAP: FORCE, FREQUENCY, RMS FORCE ERROR
    # =====================================================

    heatmap_df = force_rms_df.set_index("RMS")
    heatmap_df = heatmap_df[frequency_folders]


    plt.figure(figsize=(8, 6))

    plt.imshow(
        heatmap_df.values,
        cmap=custom_cmap,
        aspect="auto"
    )

    plt.xticks(
        range(len(heatmap_df.columns)),
        heatmap_df.columns
    )

    plt.yticks(
        range(len(heatmap_df.index)),
        [f"{int(force)}N" for force in heatmap_df.index]
    )

    plt.xlabel("Target Frequency")
    plt.ylabel("Target Force")
    plt.title("RMS Force Error Heatmap")

    cbar = plt.colorbar()
    cbar.set_label("RMS Force Error (N)")

    for i in range(len(heatmap_df.index)):
        for j in range(len(heatmap_df.columns)):

            value = heatmap_df.iloc[i, j]

            if pd.notna(value):
                plt.text(
                    j,
                    i,
                    f"{value:.2f}",
                    ha="center",
                    va="center"
                )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            master_folder,
            "RMS_Force_Error_Heatmap.png"
        ),
        dpi=300
    )

    plt.close()

    print(f"Saved full analysis:\n{output_file}")
    print("Saved all full-analysis plots.")

    return output_file


def analyse_force_control_method(method_folder):

    method_name = os.path.basename(method_folder)

    all_cycles = []
    test_summaries = []

    csv_files = sorted([
        f for f in os.listdir(method_folder)
        if f.endswith(".csv")
        and "_analysis" not in f
        and "_analysed" not in f
    ])

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")


    for file in csv_files:

        file_path = os.path.join(method_folder, file)

        target_force = read_target_force(file_path)

        if target_force is None:
            print(f"Skipping {file}: no target force found.")
            continue

        df = load_data(file_path)
        df = df[["time", "force"]].dropna()
        


        if len(df) == 0:
            continue

        cycles = find_cycles(df)

        cycle_rows = []
        steady_regions_for_debug = []

        for cycle_number, (start, end) in enumerate(cycles, start=1):

            cycle = df.loc[start:end]

            if len(cycle) < MIN_CYCLE_POINTS:
                continue


            steady_region, steady_method, steady_start_time, steady_end_time = find_steady_force_region(
                cycle,
                target_force,
            )

            steady_force = steady_region["force"].mean()
            steady_std = steady_region["force"].std()

            steady_duration = steady_end_time - steady_start_time
            steady_points = len(steady_region)


            in_cycle_rms_about_mean = np.sqrt(
                np.mean(
                    (steady_region["force"] - steady_force) ** 2
                )
            )

            in_cycle_mean_abs_deviation = np.mean(
                np.abs(steady_region["force"] - steady_force)
            )

            steady_rms = np.sqrt(
                np.mean(
                    (steady_region["force"] - target_force) ** 2
                )
            )

            steady_pp = (
                steady_region["force"].max()
                -
                steady_region["force"].min()
            )

            steady_error = steady_force - target_force

            steady_percent_error = (
                steady_error / target_force
            ) * 100

            cycle_rows.append({

                "Method": method_name,
                "File": file,
                "Target Force (N)": target_force,
                "Cycle": cycle_number,

                "Cycle Start Time (s)": cycle["time"].iloc[0],
                "Cycle End Time (s)": cycle["time"].iloc[-1],
                "Steady Start Time (s)": steady_start_time,
                "Steady End Time (s)": steady_end_time,

                "Steady Force (N)": steady_force,
                "Steady Absolute Error (N)": steady_error,
                "Steady Percent Error (%)": steady_percent_error,

                "In-Cycle STD (N)": steady_std,
                "In-Cycle RMS Error (N)": steady_rms,
                "In-Cycle Peak-to-Peak (N)": steady_pp,

                "Steady Duration (s)": steady_duration,
                "Steady Points": steady_points,
                "In-Cycle RMS About Mean (N)": in_cycle_rms_about_mean,
                "In-Cycle Mean Abs Deviation (N)": in_cycle_mean_abs_deviation,
            })

            steady_regions_for_debug.append(
                (steady_start_time, steady_end_time)
            )

        if len(cycle_rows) == 0:
            continue

        cycle_df = pd.DataFrame(cycle_rows)


        outlier_mask = detect_mad_outliers(cycle_df["Steady Force (N)"].values)

        cycle_df["Outlier Rejected"] = outlier_mask

        all_cycles.extend(cycle_df.to_dict("records"))

        filtered_df = cycle_df[
            cycle_df["Outlier Rejected"] == False
        ].copy()

        if len(filtered_df) == 0:
            continue

        steady_forces = filtered_df["Steady Force (N)"].values

        mean_steady = np.mean(steady_forces)

        steady_repeatability_std = (
            np.std(steady_forces, ddof=1)
            if len(steady_forces) > 1
            else np.nan
        )

        steady_repeatability_cv = (
            steady_repeatability_std / mean_steady
        ) * 100 if mean_steady != 0 else np.nan

        steady_abs_error = mean_steady - target_force

        steady_pct_error = (
            steady_abs_error / target_force
        ) * 100

        steady_rms_across_cycles = np.sqrt(
            np.mean(
                (steady_forces - target_force) ** 2
            )
        )

        if len(steady_forces) > 1:
            drift_slope = np.polyfit(
                filtered_df["Cycle"],
                steady_forces,
                1
            )[0]
        else:
            drift_slope = np.nan

        test_summaries.append({

            "Method": method_name,
            "File": file,
            "Target Force (N)": target_force,

            "Cycles Analysed Raw": len(cycle_df),
            "Cycles Used After Outlier Rejection": len(filtered_df),
            "Cycles Rejected": int(outlier_mask.sum()),

            "Mean Steady Force (N)": mean_steady,
            "Steady Absolute Error (N)": steady_abs_error,
            "Steady Percent Error (%)": steady_pct_error,

            "Steady Repeatability STD (N)": steady_repeatability_std,
            "Steady Repeatability CV (%)": steady_repeatability_cv,
            "Steady RMS Across Cycles (N)": steady_rms_across_cycles,

            "Mean In-Cycle STD (N)": filtered_df[
                "In-Cycle STD (N)"
            ].mean(),

            "Mean In-Cycle RMS Error (N)": filtered_df[
                "In-Cycle RMS Error (N)"
            ].mean(),

            "Mean In-Cycle Peak-to-Peak (N)": filtered_df[
                "In-Cycle Peak-to-Peak (N)"
            ].mean(),

            "Drift Slope (N/cycle)": drift_slope,

            "Mean Steady Duration (s)": filtered_df["Steady Duration (s)"].mean(),
            "Steady Duration STD (s)": filtered_df["Steady Duration (s)"].std(),
            "Mean Steady Points": filtered_df["Steady Points"].mean(),

            "Mean In-Cycle RMS About Mean (N)": filtered_df[
                "In-Cycle RMS About Mean (N)"
            ].mean(),

            "Mean In-Cycle Mean Abs Deviation (N)": filtered_df[
                "In-Cycle Mean Abs Deviation (N)"
            ].mean(),
        })

        # =================================================
        # PLOT 1: STEADY FORCE PER CYCLE
        # =================================================

        plt.figure(figsize=(8, 5))

        normal_cycles = cycle_df[
            cycle_df["Outlier Rejected"] == False
        ]

        outlier_cycles = cycle_df[
            cycle_df["Outlier Rejected"] == True
        ]

        plt.plot(
            normal_cycles["Cycle"],
            normal_cycles["Steady Force (N)"],
            marker="o",
            label="Used cycles",
            color = PLOT_COLOURS['force']
        )

        if len(outlier_cycles) > 0:
            plt.scatter(
                outlier_cycles["Cycle"],
                outlier_cycles["Steady Force (N)"],
                color="red",
                marker="x",
                s=100,
                label="Rejected outlier"
            )

        plt.axhline(
            target_force,
            linestyle="--",
            label="Target force"
        )

        plt.xlabel("Cycle Number")
        plt.ylabel("Steady Force (N)")
        plt.title(
            f"{method_name}: {int(target_force)}N steady force per cycle"
        )
        plt.legend()

        plt.tight_layout()

        plt.savefig(
            os.path.join(
                method_folder,
                f"{method_name}_{int(target_force)}N_steady_force_vs_cycle.png"
            ),
            dpi=300
        )

        plt.close()

        # =================================================
        # PLOT 2: DEBUG FORCE TRACE WITH STEADY REGIONS
        # =================================================

        plt.figure(figsize=(18, 5))

        plt.plot(
            df["time"],
            df["force"],
            linewidth=1,
            label="Force"
        )

        plt.axhline(
            target_force,
            linestyle="--",
            label="Target force"
        )

        plt.axhline(
            contact_start_threshold,
            linestyle=":",
            label="Contact start threshold"
        )

        plt.axhline(
            contact_end_threshold,
            linestyle=":",
            label="Contact end threshold"
        )

        for steady_start_time, steady_end_time in steady_regions_for_debug:
            plt.axvspan(
                steady_start_time,
                steady_end_time,
                alpha=0.2
            )

        plt.xlabel("Time (s)")
        plt.ylabel("Force (N)")
        plt.title(
            f"{method_name}: {int(target_force)}N detected steady regions"
        )
        plt.legend()

        plt.tight_layout()

        plt.savefig(
            os.path.join(
                method_folder,
                f"{method_name}_{int(target_force)}N_debug_steady_regions.png"
            ),
            dpi=300
        )

        plt.close()

    all_cycles_df = pd.DataFrame(all_cycles)
    test_summary_df = pd.DataFrame(test_summaries)

    if len(test_summary_df) == 0:
        raise ValueError("No valid force-control data found.")

    force_summary_df = test_summary_df.groupby(
        "Target Force (N)"
    ).agg({

        "Cycles Analysed Raw": "sum",
        "Cycles Used After Outlier Rejection": "sum",
        "Cycles Rejected": "sum",

        "Mean Steady Force (N)": "mean",
        "Steady Absolute Error (N)": "mean",
        "Steady Percent Error (%)": "mean",

        "Steady Repeatability STD (N)": "mean",
        "Steady Repeatability CV (%)": "mean",
        "Steady RMS Across Cycles (N)": "mean",

        "Mean In-Cycle STD (N)": "mean",
        "Mean In-Cycle RMS Error (N)": "mean",
        "Mean In-Cycle Peak-to-Peak (N)": "mean",

        "Drift Slope (N/cycle)": "mean",

        "Mean Steady Duration (s)": "mean",
        "Steady Duration STD (s)": "mean",
        "Mean Steady Points": "mean",
        "Mean In-Cycle RMS About Mean (N)": "mean",
        "Mean In-Cycle Mean Abs Deviation (N)": "mean",

    }).reset_index()

    force_summary_df = force_summary_df.sort_values(
        "Target Force (N)"
    )

    output_excel = os.path.join(
        method_folder,
        f"{method_name}_STEADY_FORCE_CONTROL_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(
        output_excel,
        engine="openpyxl"
    ) as writer:

        all_cycles_df.to_excel(
            writer,
            sheet_name="ALL_CYCLES",
            index=False
        )

        test_summary_df.to_excel(
            writer,
            sheet_name="TEST_SUMMARY",
            index=False
        )

        force_summary_df.to_excel(
            writer,
            sheet_name="FORCE_SUMMARY",
            index=False
        )

    def plot_summary(y_col, ylabel, title, filename, zero_line=False):

        plt.figure(figsize=(7, 5))

        plt.plot(
            force_summary_df["Target Force (N)"],
            force_summary_df[y_col],
            marker="o",
            color = PLOT_COLOURS['force']
        )

        if zero_line:
            plt.axhline(0, linestyle="--")

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(title)

        plt.tight_layout()

        plt.savefig(
            os.path.join(method_folder, filename),
            dpi=300
        )

        plt.close()

    plt.figure(figsize=(7, 5))

    plt.plot(
        force_summary_df["Target Force (N)"],
        force_summary_df["Mean Steady Force (N)"],
        marker="o",
        label="Measured",
        color = PLOT_COLOURS['force']
    )

    plt.plot(
        force_summary_df["Target Force (N)"],
        force_summary_df["Target Force (N)"],
        linestyle="--",
        label="Target"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("Force (N)")
    plt.title(f"{method_name}: target vs mean steady force")
    plt.legend()

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            method_folder,
            f"{method_name}_target_vs_mean_steady_force.png"
        ),
        dpi=300
    )

    plt.close()

    plot_summary(
        "Steady Percent Error (%)",
        "Steady Force Error (%)",
        f"{method_name}: steady-force accuracy",
        f"{method_name}_steady_percent_error.png",
        zero_line=True
    )

    plot_summary(
        "Steady Repeatability STD (N)",
        "STD of Steady Force Across Cycles (N)",
        f"{method_name}: steady-force repeatability STD",
        f"{method_name}_steady_repeatability_std.png"
    )

    plot_summary(
        "Steady Repeatability CV (%)",
        "CV of Steady Force Across Cycles (%)",
        f"{method_name}: steady-force repeatability CV",
        f"{method_name}_steady_repeatability_cv.png"
    )

    plot_summary(
        "Mean In-Cycle STD (N)",
        "Mean In-Cycle STD (N)",
        f"{method_name}: in-cycle stability",
        f"{method_name}_in_cycle_std.png"
    )

    plot_summary(
        "Mean In-Cycle RMS Error (N)",
        "Mean In-Cycle RMS Error (N)",
        f"{method_name}: in-cycle RMS error",
        f"{method_name}_in_cycle_rms.png"
    )

    plot_summary(
        "Mean In-Cycle Peak-to-Peak (N)",
        "Mean In-Cycle Peak-to-Peak (N)",
        f"{method_name}: in-cycle peak-to-peak variation",
        f"{method_name}_in_cycle_peak_to_peak.png"
    )

    plot_summary(
    "Mean In-Cycle RMS About Mean (N)",
    "Mean In-Cycle RMS About Mean (N)",
    f"{method_name}: offset-independent in-cycle stability",
    f"{method_name}_in_cycle_rms_about_mean.png"
    )

    plot_summary(
        "Mean Steady Duration (s)",
        "Mean Steady Duration (s)",
        f"{method_name}: steady-region duration",
        f"{method_name}_steady_duration.png"
    )

    plot_summary(
        "Mean Steady Points",
        "Mean Steady Points",
        f"{method_name}: steady-region points",
        f"{method_name}_steady_points.png"
    )

    print(f"Saved steady force-control analysis:\n{output_excel}")

    return output_excel


def compare_force_control_methods_simple(master_folder):

    method_folders = sorted([
        f for f in os.listdir(master_folder)
        if os.path.isdir(os.path.join(master_folder, f))
    ])

    if len(method_folders) == 0:
        raise ValueError("No method folders found.")

    all_summaries = []

    for method in method_folders:
        method_path = os.path.join(master_folder, method)

        excel_path = analyse_force_control_method(method_path)

        summary_df = pd.read_excel(
            excel_path,
            sheet_name="FORCE_SUMMARY"
        )

        summary_df["Method"] = method
        all_summaries.append(summary_df)

    combined_df = pd.concat(all_summaries, ignore_index=True)

    # =========================
    # SIMPLIFIED SCORE
    # =========================
    # Lower is better for all these metrics

    combined_df["Abs Steady Percent Error (%)"] = (
        combined_df["Steady Percent Error (%)"].abs()
    )

    scoring_metrics = [
        "Steady Repeatability CV (%)",
        "Mean In-Cycle STD (N)",
        "Abs Steady Percent Error (%)"
    ]

    # Normalise each metric so they can be combined fairly
    for metric in scoring_metrics:
        min_val = combined_df[metric].min()
        max_val = combined_df[metric].max()

        if max_val == min_val:
            combined_df[f"{metric} Normalised"] = 0
        else:
            combined_df[f"{metric} Normalised"] = (
                (combined_df[metric] - min_val)
                /
                (max_val - min_val)
            )

    # Weighted score:
    # repeatability matters most,
    # then in-cycle stability,
    # then accuracy
    combined_df["Simple Control Score"] = (
        0.70 * combined_df["Steady Repeatability CV (%) Normalised"]
        +
        0.20 * combined_df["Mean In-Cycle STD (N) Normalised"]
        +
        0.10 * combined_df["Abs Steady Percent Error (%) Normalised"]
    )

    method_ranking = (
        combined_df
        .groupby("Method", sort=False)
        .agg({
            "Simple Control Score": "mean",
            "Steady Repeatability CV (%)": "mean",
            "Mean In-Cycle STD (N)": "mean",
            "Abs Steady Percent Error (%)": "mean",
            "Steady Repeatability CV (%) Normalised": "mean",
            "Mean In-Cycle STD (N) Normalised": "mean",
            "Abs Steady Percent Error (%) Normalised": "mean"
        })
        .reset_index()
    )


    simple_method_summary = (
        combined_df
        .groupby("Method", sort=False)
        .agg({
            "Steady Repeatability CV (%)": "mean",
            "Mean In-Cycle STD (N)": "mean",
            "Steady Percent Error (%)": lambda x: np.mean(np.abs(x))
        })
        .reset_index()
        .rename(columns={
            "Mean In-Cycle STD (N)": "In-Cycle Force STD (N)",
            "Steady Percent Error (%)": "Steady Force Error (%)"
        })
        .reset_index()
    )

    # =========================
    # SAVE EXCEL
    # =========================

    output_excel = os.path.join(
        master_folder,
        "SIMPLE_FORCE_CONTROL_METHOD_COMPARISON.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        combined_df.to_excel(
            writer,
            sheet_name="ALL_METHODS",
            index=False
        )

        method_ranking.to_excel(
            writer,
            sheet_name="METHOD_RANKING",
            index=False
        )

    # =========================
    # PLOTTING HELPER
    # =========================
    
    def plot_comparison(y_col, ylabel, title, filename, zero_line=False, y_headroom=None):
        plt.figure(figsize=(8, 6))

        for i, method in enumerate(
            sorted(combined_df["Method"].unique())
        ):

            subset = combined_df[
                combined_df["Method"] == method
            ].sort_values("Target Force (N)")

            plt.plot(
                subset["Target Force (N)"],
                subset[y_col],
                marker="o",
                color=get_compare_colour(i),
                label=method
            )

        if zero_line:
            plt.axhline(0, linestyle="--")

        if y_headroom is not None:
            ymin, ymax = plt.ylim()
            plt.ylim(ymin, ymax * y_headroom)


        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.legend(title="Control Method")
        plt.tight_layout()

        plt.savefig(
            os.path.join(master_folder, filename),
            dpi=300
        )

        plt.close()

    # =========================
    # CORE COMPARISON PLOTS
    # =========================

    plot_comparison(
        "Steady Repeatability CV (%)",
        "Repeatability CV (%)",
        "1. Cycle-to-cycle repeatability",
        "simple_1_repeatability_cv.png",
        y_headroom=1.25
    )

    plot_comparison(
        "Mean In-Cycle STD (N)",
        "Mean In-Cycle STD (N)",
        "2. In-cycle force stability",
        "simple_2_in_cycle_stability.png"
    )

    plot_comparison(
        "Steady Percent Error (%)",
        "Steady Force Error (%)",
        "3. Accuracy relative to target",
        "simple_3_accuracy.png",
        zero_line=True
    )

    plot_comparison(
        "Simple Control Score",
        "Simple Control Score",
        "Overall control score, lower is better",
        "simple_4_overall_score.png"
    )

    # =========================
    # METHOD RANKING BAR CHART
    # =========================

    plt.figure(figsize=(8, 6))

    bar_colours = [
        get_plot_colour(i)
        for i in range(len(method_ranking))
    ]

    plt.bar(
        method_ranking["Method"],
        method_ranking["Simple Control Score"],
        color=bar_colours
    )

    plt.xlabel("Control Method")
    plt.ylabel("Mean Simple Control Score")
    plt.title("Overall method score, lower is better")

    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig(
        os.path.join(master_folder, "simple_5_method_ranking.png"),
        dpi=300
    )

    plt.close()


    # =========================
    # METHOD RANKING HEATMAP
    # =========================

    heatmap_df = method_ranking[
        [
            "Method",
            "Steady Repeatability CV (%) Normalised",
            "Mean In-Cycle STD (N) Normalised",
            "Abs Steady Percent Error (%) Normalised",
            "Simple Control Score"
        ]
    ].copy()

    heatmap_df = heatmap_df.rename(columns={
        "Steady Repeatability CV (%) Normalised": "Repeatability",
        "Mean In-Cycle STD (N) Normalised": "In-cycle stability",
        "Abs Steady Percent Error (%) Normalised": "Accuracy",
        "Simple Control Score": "Overall score"
    })

    heatmap_df = heatmap_df.set_index("Method")

    plt.figure(figsize=(8, 6))

    plt.imshow(
        heatmap_df.values,
        cmap=custom_cmap,
        aspect="auto",
        vmin=0,
        vmax=1
    )

    plt.xticks(
        range(len(heatmap_df.columns)),
        heatmap_df.columns,
        rotation=45,
        ha="right"
    )

    plt.yticks(
        range(len(heatmap_df.index)),
        heatmap_df.index
    )

    plt.xlabel("Metric")
    plt.ylabel("Control Method")
    plt.title("Normalised Force Control Method Comparison")

    cbar = plt.colorbar()
    cbar.set_label("Normalised score, lower is better")

    for i in range(len(heatmap_df.index)):
        for j in range(len(heatmap_df.columns)):

            value = heatmap_df.iloc[i, j]

            if pd.notna(value):
                plt.text(
                    j,
                    i,
                    f"{value:.2f}",
                    ha="center",
                    va="center"
                )

    plt.tight_layout()

    plt.savefig(
        os.path.join(master_folder, "simple_force_control_heatmap.png"),
        dpi=300
    )

    plt.close()


    return output_excel


def compare_force_offset_methods(master_folder):

    method_folders = sorted([
        f for f in os.listdir(master_folder)
        if os.path.isdir(os.path.join(master_folder, f))
    ])

    if len(method_folders) == 0:
        raise ValueError("No method folders found.")

    all_summaries = []

    for method in method_folders:
        method_path = os.path.join(master_folder, method)

        excel_path = analyse_force_control_method(method_path)

        summary_df = pd.read_excel(
            excel_path,
            sheet_name="FORCE_SUMMARY"
        )

        summary_df["Method"] = method
        all_summaries.append(summary_df)

    combined_df = pd.concat(all_summaries, ignore_index=True)

    # =========================
    # SIMPLIFIED SCORE
    # =========================
    # Lower is better for all these metrics

    combined_df["Abs Steady Percent Error (%)"] = (
        combined_df["Steady Percent Error (%)"].abs()
    )

    scoring_metrics = [
        "Steady Repeatability CV (%)",
        "Mean In-Cycle STD (N)",
        "Abs Steady Percent Error (%)"
    ]

    # Normalise each metric so they can be combined fairly
    for metric in scoring_metrics:
        min_val = combined_df[metric].min()
        max_val = combined_df[metric].max()

        if max_val == min_val:
            combined_df[f"{metric} Normalised"] = 0
        else:
            combined_df[f"{metric} Normalised"] = (
                (combined_df[metric] - min_val)
                /
                (max_val - min_val)
            )

    # Weighted score:
    # accuracy matters most,
    # then repeatability close second,
    # then in-cycle stability
    combined_df["Simple Control Score"] = (
        0.40 * combined_df["Steady Repeatability CV (%) Normalised"]
        +
        0.15 * combined_df["Mean In-Cycle STD (N) Normalised"]
        +
        0.45 * combined_df["Abs Steady Percent Error (%) Normalised"]
    )

    method_ranking = (
        combined_df
        .groupby("Method", sort=False)
        .agg({
            "Simple Control Score": "mean",
            "Steady Repeatability CV (%)": "mean",
            "Mean In-Cycle STD (N)": "mean",
            "Abs Steady Percent Error (%)": "mean",
            "Steady Repeatability CV (%) Normalised": "mean",
            "Mean In-Cycle STD (N) Normalised": "mean",
            "Abs Steady Percent Error (%) Normalised": "mean"
        })
        .reset_index()
    )


    simple_method_summary = (
        combined_df
        .groupby("Method", sort=False)
        .agg({
            "Steady Repeatability CV (%)": "mean",
            "Mean In-Cycle STD (N)": "mean",
            "Steady Percent Error (%)": lambda x: np.mean(np.abs(x))
        })
        .reset_index()
        .rename(columns={
            "Mean In-Cycle STD (N)": "In-Cycle Force STD (N)",
            "Steady Percent Error (%)": "Steady Force Error (%)"
        })
        .reset_index()
    )

    # =========================
    # SAVE EXCEL
    # =========================

    output_excel = os.path.join(
        master_folder,
        "SIMPLE_FORCE_CONTROL_METHOD_COMPARISON.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        combined_df.to_excel(
            writer,
            sheet_name="ALL_METHODS",
            index=False
        )

        method_ranking.to_excel(
            writer,
            sheet_name="METHOD_RANKING",
            index=False
        )

    # =========================
    # PLOTTING HELPER
    # =========================

    def plot_comparison(y_col, ylabel, title, filename, zero_line=False, y_headroom=None):
        plt.figure(figsize=(8, 6))

        for i, method in enumerate(
            sorted(combined_df["Method"].unique())
        ):

            subset = combined_df[
                combined_df["Method"] == method
            ].sort_values("Target Force (N)")

            plt.plot(
                subset["Target Force (N)"],
                subset[y_col],
                marker="o",
                color=get_compare_colour(i),
                label=method
            )

        if zero_line:
            plt.axhline(0, linestyle="--")

        if y_headroom is not None:
            ymin, ymax = plt.ylim()
            plt.ylim(ymin, ymax * y_headroom)


        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.legend(title="Control Method")
        plt.tight_layout()

        plt.savefig(
            os.path.join(master_folder, filename),
            dpi=300
        )

        plt.close()

    # =========================
    # CORE COMPARISON PLOTS
    # =========================

    plot_comparison(
        "Steady Repeatability CV (%)",
        "Repeatability CV (%)",
        "1. Cycle-to-cycle repeatability",
        "simple_1_repeatability_cv.png",
        y_headroom=1.25
    )

    plot_comparison(
        "Mean In-Cycle STD (N)",
        "Mean In-Cycle STD (N)",
        "2. In-cycle force stability",
        "simple_2_in_cycle_stability.png"
    )

    plot_comparison(
        "Steady Percent Error (%)",
        "Steady Force Error (%)",
        "3. Accuracy relative to target",
        "simple_3_accuracy.png",
        zero_line=True
    )

    plot_comparison(
        "Simple Control Score",
        "Simple Control Score",
        "Overall control score, lower is better",
        "simple_4_overall_score.png"
    )

    # =========================
    # METHOD RANKING BAR CHART
    # =========================

    plt.figure(figsize=(8, 6))

    bar_colours = [
        get_compare_colour(i)
        for i in range(len(method_ranking))
    ]

    plt.bar(
        method_ranking["Method"],
        method_ranking["Simple Control Score"],
        color=bar_colours
    )

    plt.xlabel("Control Method")
    plt.ylabel("Mean Simple Control Score")
    plt.title("Overall method score, lower is better")

    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig(
        os.path.join(master_folder, "simple_5_method_ranking.png"),
        dpi=300
    )

    plt.close()


    # =========================
    # METHOD RANKING HEATMAP
    # =========================

    heatmap_df = method_ranking[
        [
            "Method",
            "Steady Repeatability CV (%) Normalised",
            "Mean In-Cycle STD (N) Normalised",
            "Abs Steady Percent Error (%) Normalised",
            "Simple Control Score"
        ]
    ].copy()

    heatmap_df = heatmap_df.rename(columns={
        "Steady Repeatability CV (%) Normalised": "Repeatability",
        "Mean In-Cycle STD (N) Normalised": "In-cycle stability",
        "Abs Steady Percent Error (%) Normalised": "Accuracy",
        "Simple Control Score": "Overall score"
    })

    heatmap_df = heatmap_df.set_index("Method")

    plt.figure(figsize=(8, 6))

    plt.imshow(
        heatmap_df.values,
        cmap=custom_cmap,
        aspect="auto",
        vmin=0,
        vmax=1
    )

    plt.xticks(
        range(len(heatmap_df.columns)),
        heatmap_df.columns,
        rotation=45,
        ha="right"
    )

    plt.yticks(
        range(len(heatmap_df.index)),
        heatmap_df.index
    )

    plt.xlabel("Metric")
    plt.ylabel("Control Method")
    plt.title("Normalised Force Control Method Comparison")

    cbar = plt.colorbar()
    cbar.set_label("Normalised score, lower is better")

    for i in range(len(heatmap_df.index)):
        for j in range(len(heatmap_df.columns)):

            value = heatmap_df.iloc[i, j]

            if pd.notna(value):
                plt.text(
                    j,
                    i,
                    f"{value:.2f}",
                    ha="center",
                    va="center"
                )

    plt.tight_layout()

    plt.savefig(
        os.path.join(master_folder, "simple_force_control_heatmap.png"),
        dpi=300
    )

    plt.close()


    return output_excel


def analyse_force_offset_repeatability(master_folder):
    """
    Analyse repeat-to-repeat consistency of force-offset control methods.

    Expected folder structure:

        master_folder/
            method_1/
                repeat csv files for all forces
            method_2/
                repeat csv files for all forces

    The function calculates, for each file:
        - mean steady force
        - steady force percent error
        - cycle-to-cycle repeatability CV
        - mean in-cycle force stability

    Then, for each method and target force, it calculates:
        - mean across repeats
        - standard deviation across repeats
        - CV across repeats

    This answers:
        "Are repeat 1, repeat 2, and repeat 3 similar at the same force?"
    """

    all_file_rows = []

    method_folders = sorted([
        f.path for f in os.scandir(master_folder)
        if f.is_dir()
    ])

    if len(method_folders) == 0:
        raise ValueError("No method folders found.")

    for method_folder in method_folders:

        folder_name = os.path.basename(method_folder)

        method_name = (
            folder_name
            .replace("repeat 1", "")
            .replace("repeat 2", "")
            .replace("repeat 3", "")
            .strip()
        )

        csv_files = sorted([
            f for f in os.listdir(method_folder)
            if (
                f.endswith(".csv")
                and "_analysis" not in f
                and "_analysed" not in f
            )
        ])

        if len(csv_files) == 0:
            print(f"Skipping {method_name}: no CSV files.")
            continue

        for repeat_number, file in enumerate(csv_files, start=1):

            file_path = os.path.join(method_folder, file)

            target_force = read_target_force(file_path)

            if target_force is None:
                print(f"Skipping {file}: no target force found.")
                continue

            cycle_df = analyse_force_cycles(
                file_path
            )

            # =====================================================
            # MAD OUTLIER REJECTION
            # =====================================================

            outlier_mask = detect_mad_outliers(
                cycle_df["steady_force_N"].values
            )

            cycle_df["Outlier Rejected"] = outlier_mask

            cycle_df = cycle_df[
                cycle_df["Outlier Rejected"] == False
            ].copy()

            if len(cycle_df) == 0:
                print(f"Skipping {file}: all cycles rejected.")
                continue

            if len(cycle_df) == 0:
                print(f"Skipping {file}: no valid cycles.")
                continue

            mean_steady_force = cycle_df["steady_force_N"].mean()

            std_steady_force = cycle_df["steady_force_N"].std(ddof=1)

            cycle_to_cycle_cv = (
                std_steady_force
                / mean_steady_force
                * 100
                if mean_steady_force != 0
                else np.nan
            )

            steady_error_N = (
                mean_steady_force
                - target_force
            )

            steady_percent_error = (
                steady_error_N
                / target_force
                * 100
                if target_force != 0
                else np.nan
            )

            abs_steady_percent_error = abs(
                steady_percent_error
            )

            if "steady_force_std_N" in cycle_df.columns:
                mean_in_cycle_std = cycle_df[
                    "steady_force_std_N"
                ].mean()

            elif "in_cycle_std_N" in cycle_df.columns:
                mean_in_cycle_std = cycle_df[
                    "in_cycle_std_N"
                ].mean()

            else:
                mean_in_cycle_std = cycle_df[
                    "steady_force_N"
                ].std(ddof=1)

            all_file_rows.append({
                "Method": method_name,
                "Repeat Folder": folder_name,
                "File": file,
                "Target Force (N)": target_force,

                "Mean Steady Force (N)": mean_steady_force,
                "STD Steady Force Within File (N)": std_steady_force,

                "Steady Error (N)": steady_error_N,
                "Steady Percent Error (%)": steady_percent_error,
                "Abs Steady Percent Error (%)": abs_steady_percent_error,

                "Cycle-to-cycle Repeatability CV (%)": cycle_to_cycle_cv,
                "Mean In-Cycle STD (N)": mean_in_cycle_std,

                "Cycles Analysed": len(cycle_df)
            })

    file_results_df = pd.DataFrame(all_file_rows)

    if len(file_results_df) == 0:
        raise ValueError("No valid repeatability data found.")

    summary_df = (
        file_results_df
        .groupby(
            ["Method", "Target Force (N)"],
            sort=False
        )
        .agg({
            "Mean Steady Force (N)": ["mean", "std"],
            "Steady Percent Error (%)": ["mean", "std"],
            "Abs Steady Percent Error (%)": ["mean", "std"],
            "Cycle-to-cycle Repeatability CV (%)": ["mean", "std"],
            "Mean In-Cycle STD (N)": ["mean", "std"],
            "Repeat Folder": "count"
        })
    )

    summary_df.columns = [
        "Mean Steady Force Across Repeats (N)",
        "STD Steady Force Across Repeats (N)",

        "Mean Steady Percent Error Across Repeats (%)",
        "STD Steady Percent Error Across Repeats (%)",

        "Mean Abs Steady Percent Error Across Repeats (%)",
        "STD Abs Steady Percent Error Across Repeats (%)",

        "Mean Cycle-to-cycle CV Across Repeats (%)",
        "STD Cycle-to-cycle CV Across Repeats (%)",

        "Mean In-Cycle STD Across Repeats (N)",
        "STD In-Cycle STD Across Repeats (N)",

        "Number of Repeats"
    ]

    summary_df = summary_df.reset_index()

    summary_df["Repeat-to-repeat CV of Mean Steady Force (%)"] = (
        summary_df["STD Steady Force Across Repeats (N)"]
        /
        summary_df["Mean Steady Force Across Repeats (N)"]
        *
        100
    )

    output_excel = os.path.join(
        master_folder,
        "FORCE_OFFSET_REPEATABILITY_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        file_results_df.to_excel(
            writer,
            sheet_name="FILE_RESULTS",
            index=False
        )

        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY_BY_METHOD_FORCE",
            index=False
        )

    def plot_summary_metric(
        y_col,
        yerr_col,
        ylabel,
        title,
        filename
    ):

        plt.figure(figsize=(9, 6))

        for i, method in enumerate(summary_df["Method"].unique()):

            subset = summary_df[
                summary_df["Method"] == method
            ].sort_values("Target Force (N)")

            plt.errorbar(
                subset["Target Force (N)"],
                subset[y_col],
                yerr=subset[yerr_col],
                marker="o",
                capsize=4,
                color=get_default_colour(i),
                label=method
            )

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.grid(True, linestyle="--", alpha=0.4)
        plt.legend(title="Method")
        plt.tight_layout()

        plot_path = os.path.join(
            master_folder,
            filename
        )

        plt.savefig(plot_path, dpi=300)
        plt.close()

        return plot_path

    error_plot = plot_summary_metric(
        y_col="Mean Steady Percent Error Across Repeats (%)",
        yerr_col="STD Steady Percent Error Across Repeats (%)",
        ylabel="Steady Force Error (%)",
        title="Force Offset Repeatability: Steady Force Error",
        filename="force_offset_repeatability_percent_error.png"
    )

    cycle_cv_plot = plot_summary_metric(
        y_col="Mean Cycle-to-cycle CV Across Repeats (%)",
        yerr_col="STD Cycle-to-cycle CV Across Repeats (%)",
        ylabel="Cycle-to-cycle Repeatability CV (%)",
        title="Force Offset Repeatability: Cycle-to-cycle Repeatability",
        filename="force_offset_repeatability_cycle_to_cycle_cv.png"
    )

    in_cycle_plot = plot_summary_metric(
        y_col="Mean In-Cycle STD Across Repeats (N)",
        yerr_col="STD In-Cycle STD Across Repeats (N)",
        ylabel="Mean In-Cycle STD (N)",
        title="Force Offset Repeatability: In-Cycle Force Stability",
        filename="force_offset_repeatability_in_cycle_std.png"
    )

    repeat_to_repeat_plot = plot_summary_metric(
        y_col="Repeat-to-repeat CV of Mean Steady Force (%)",
        yerr_col="STD Steady Percent Error Across Repeats (%)",
        ylabel="Repeat-to-repeat CV of Mean Steady Force (%)",
        title="Force Offset Repeatability: Repeat-to-repeat Consistency",
        filename="force_offset_repeatability_repeat_to_repeat_cv.png"
    )

    print(f"Saved force offset repeatability analysis:\n{output_excel}")
    print(f"Saved plot:\n{error_plot}")
    print(f"Saved plot:\n{cycle_cv_plot}")
    print(f"Saved plot:\n{in_cycle_plot}")
    print(f"Saved plot:\n{repeat_to_repeat_plot}")

    return output_excel


def analyse_voltage_cycle_convergence(
    file_path,
    tolerance_percent=2,
    stable_window=30,
    mad_outlier_rejection=False
):
    """
    Analyse voltage convergence for one CSV file.

    Convergence outputs:
    - running mean peak voltage
    - running RMS voltage
    - relative error from final mean
    - running CV of peak voltage
    - cycles needed to remain within 5%, 2%, and 1% of final mean
    """

    import os
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_folder = os.path.dirname(file_path)

    target_force = read_target_force(file_path)

    if target_force is not None:
        force_label = f"{target_force:g}N"
        title_prefix = f"{target_force:g} N Voltage Convergence"
    else:
        force_label = "unknown_force"
        title_prefix = "Voltage Convergence"

    if target_force is not None:
        title_prefix = f"{base_name} — {target_force:g} N"
        force_label = f"{target_force:g}"
    else:
        title_prefix = base_name
        force_label = base_name

    df = load_data(file_path)

    cycles = find_cycles(df)

    if len(cycles) == 0:
        raise ValueError("No cycles found.")

    cycle_results = []

    for cycle_number, (start, end) in enumerate(cycles, start=1):

        cycle = df.loc[start:end].copy()

        if len(cycle) < MIN_CYCLE_POINTS:
            continue

        voltage = cycle["voltage"].dropna().to_numpy()

        if len(voltage) < MIN_CYCLE_POINTS:
            continue

        voltage_corrected = voltage - np.median(voltage)

        positive_peak = np.max(voltage_corrected)
        negative_peak = abs(np.min(voltage_corrected))

        rectified_peak = (positive_peak + negative_peak) / 2

        rms_voltage = np.sqrt(
            np.mean(voltage_corrected ** 2)
        )

        cycle_results.append({
            "cycle": cycle_number,
            "voltage_peak_V": rectified_peak,
            "voltage_rms_V": rms_voltage
        })

    cycle_df = pd.DataFrame(cycle_results)

    if len(cycle_df) == 0:
        raise ValueError("No valid cycle metrics calculated.")

    # =====================================================
    # OPTIONAL OUTLIER REJECTION
    # =====================================================

    if mad_outlier_rejection:
        outlier_mask = detect_mad_outliers(
            cycle_df["voltage_peak_V"].values
        )

        cycle_df["Outlier Rejected"] = outlier_mask

        cycle_df = cycle_df[
            cycle_df["Outlier Rejected"] == False
        ].copy()

        if len(cycle_df) == 0:
            raise ValueError("All cycles rejected as outliers.")

        cycle_df = cycle_df.reset_index(drop=True)
        cycle_df["cycle"] = range(1, len(cycle_df) + 1)

    else:
        cycle_df["Outlier Rejected"] = False

    # =====================================================
    # RUNNING METRICS
    # =====================================================

    cycle_df["running_mean_voltage_peak_V"] = (
        cycle_df["voltage_peak_V"]
        .expanding()
        .mean()
    )

    cycle_df["running_mean_voltage_rms_V"] = (
        cycle_df["voltage_rms_V"]
        .expanding()
        .mean()
    )

    cycle_df["running_std_voltage_peak_V"] = (
        cycle_df["voltage_peak_V"]
        .expanding()
        .std()
    )

    cycle_df["running_cv_voltage_peak_percent"] = (
        cycle_df["running_std_voltage_peak_V"]
        /
        cycle_df["running_mean_voltage_peak_V"]
        *
        100
    )

    final_mean_voltage_peak = cycle_df["voltage_peak_V"].mean()
    final_mean_voltage_rms = cycle_df["voltage_rms_V"].mean()

    cycle_df["peak_error_from_final_percent"] = (
        (
            cycle_df["running_mean_voltage_peak_V"]
            - final_mean_voltage_peak
        ).abs()
        /
        final_mean_voltage_peak
        *
        100
    )

    cycle_df["rms_error_from_final_percent"] = (
        (
            cycle_df["running_mean_voltage_rms_V"]
            - final_mean_voltage_rms
        ).abs()
        /
        final_mean_voltage_rms
        *
        100
    )

    # =====================================================
    # CONVERGENCE FINDER
    # Must remain inside threshold for the rest of the test
    # =====================================================

    def first_cycle_stays_below(error_series, threshold_percent):
        errors = error_series.to_numpy()

        for i in range(len(errors)):
            if np.all(errors[i:] <= threshold_percent):
                return int(cycle_df["cycle"].iloc[i])

        return np.nan


    cycles_to_5_percent = first_cycle_stays_below(
        cycle_df["peak_error_from_final_percent"],
        5
    )

    cycles_to_2_percent = first_cycle_stays_below(
        cycle_df["peak_error_from_final_percent"],
        2
    )

    cycles_to_1_percent = first_cycle_stays_below(
        cycle_df["peak_error_from_final_percent"],
        1
    )

    # Choose recommended cycle count
    # 2% is the main/default criterion
    if not np.isnan(cycles_to_2_percent):
        recommended_cycles = cycles_to_2_percent
        convergence_criterion = "Peak voltage mean within 2% of final mean"
    elif not np.isnan(cycles_to_5_percent):
        recommended_cycles = cycles_to_5_percent
        convergence_criterion = "Peak voltage mean within 5% of final mean"
    else:
        recommended_cycles = cycle_df["cycle"].max()
        convergence_criterion = "Did not reach 5%; use full dataset"

    # =====================================================
    # PLOT 1: RUNNING MEAN
    # =====================================================

    plt.figure(figsize=(11, 6))

    plt.plot(
        cycle_df["cycle"],
        cycle_df["running_mean_voltage_peak_V"],
        marker="o",
        markersize=3,
        color=PLOT_COLOURS["voltage"],
        label="Running mean voltage peak"
    )

    plt.plot(
        cycle_df["cycle"],
        cycle_df["running_mean_voltage_rms_V"],
        marker="o",
        markersize=3,
        color=PLOT_COLOURS["voltage_rms"],
        label="Running mean voltage RMS"
    )

    plt.axhline(
        final_mean_voltage_peak,
        linestyle="--",
        label="Final mean voltage peak"
    )

    plt.axhline(
        final_mean_voltage_rms,
        linestyle=":",
        label="Final mean voltage RMS"
    )


    plt.xlabel("Number of Mechanical Cycles Included")
    plt.ylabel("Voltage (V)")
    plt.title(
        f"{target_force:g}N\nVoltage Running Mean Convergence"
    )

    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()

    running_mean_plot = os.path.join(
        output_folder,
        f"{force_label}_voltage_running_mean_convergence.png"
    )


    plt.savefig(running_mean_plot, dpi=300)
    plt.close()

    # =====================================================
    # PLOT 2: RELATIVE ERROR FROM FINAL MEAN
    # =====================================================

    plt.figure(figsize=(11, 6))

    plt.plot(
        cycle_df["cycle"],
        cycle_df["peak_error_from_final_percent"],
        marker="o",
        markersize=3,
        color=PLOT_COLOURS["voltage"],
        label="Peak voltage mean error"
    )

    plt.plot(
        cycle_df["cycle"],
        cycle_df["rms_error_from_final_percent"],
        marker="o",
        markersize=3,
        color=PLOT_COLOURS["voltage_rms"],
        label="RMS voltage mean error"
    )


    plt.axhline(5, linestyle="--", label="5% threshold")
    plt.axhline(2, linestyle=":", label="2% threshold")
    plt.axhline(1, linestyle=":", label="1% threshold")

    plt.xlabel("Number of Mechanical Cycles Included")
    plt.ylabel("Error from Final Mean (%)")
    plt.title(
        f"{target_force:g}N\nError Relative to Final Mean"
    )

    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()

    error_plot = os.path.join(
        output_folder,
        f"{force_label}_voltage_error_from_final_mean.png"
    )

    plt.savefig(error_plot, dpi=300)
    plt.close()

    # =====================================================
    # PLOT 3: RUNNING CV
    # =====================================================

    plt.figure(figsize=(11, 6))

    plt.plot(
        cycle_df["cycle"],
        cycle_df["running_cv_voltage_peak_percent"],
        marker="o",
        markersize=3,
        color=PLOT_COLOURS["voltage"],
        label="Running CV of peak voltage"
    )


    plt.xlabel("Number of Mechanical Cycles Included")
    plt.ylabel("Running CV (%)")
    plt.title(
        f"{target_force:g}N\nRunning Coefficient of Variation"
    )

    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()

    cv_plot = os.path.join(
        output_folder,
        f"{force_label}_voltage_running_cv.png"
    )

    plt.savefig(cv_plot, dpi=300)
    plt.close()

    # =====================================================
    # SAVE EXCEL
    # =====================================================

    output_excel = os.path.join(
        output_folder,
        f"{force_label}_VOLTAGE_CONVERGENCE_ANALYSIS.xlsx"
    )

    summary = {
        "file": base_name,
        "target_force_N": target_force,
        "n_cycles_analysed": len(cycle_df),

        "final_mean_voltage_peak_V": final_mean_voltage_peak,
        "final_mean_voltage_rms_V": final_mean_voltage_rms,

        "cycles_to_5_percent_peak": cycles_to_5_percent,
        "cycles_to_2_percent_peak": cycles_to_2_percent,
        "cycles_to_1_percent_peak": cycles_to_1_percent,

        "recommended_cycles": recommended_cycles,
        "convergence_criterion": convergence_criterion,

        "final_peak_cv_percent": cycle_df["running_cv_voltage_peak_percent"].iloc[-1],

        "running_mean_plot": running_mean_plot,
        "error_plot": error_plot,
        "cv_plot": cv_plot
    }

    summary_df = pd.DataFrame([summary])

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        cycle_df.to_excel(
            writer,
            sheet_name="CYCLE_METRICS",
            index=False
        )

        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

    return cycle_df, summary


def analyse_voltage_cycle_convergence_folder(
    folder_path,
    tolerance_percent=1,
    stable_window=15
):
    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if (
            f.endswith(".csv")
            and "_analysis" not in f
            and "_analysed" not in f
        )
    ])

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")

    summary_rows = []

    for file in csv_files:

        file_path = os.path.join(folder_path, file)

        try:
            cycle_df, summary = analyse_voltage_cycle_convergence(
                file_path=file_path,
                tolerance_percent=tolerance_percent,
                stable_window=stable_window
            )

            summary_rows.append(summary)

        except Exception as e:
            print(f"Skipping {file}: {e}")

    if len(summary_rows) == 0:
        raise ValueError("No valid convergence analyses completed.")

    summary_df = pd.DataFrame(summary_rows)

    summary_df = summary_df.sort_values(
        "target_force_N"
    )

    output_excel = os.path.join(
        folder_path,
        "MASTER_CONVERGENCE_SUMMARY.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

    plt.figure(figsize=(8, 6))

    plt.plot(
        summary_df["target_force_N"],
        summary_df["recommended_cycles"],
        marker="o",
        color=PLOT_COLOURS["voltage"]
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("Recommended Cycles to Convergence")
    plt.title("Voltage Convergence Summary")

    plt.xticks(
        summary_df["target_force_N"],
        [f"{force:g}N" for force in summary_df["target_force_N"]]
    )

    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()

    summary_plot = os.path.join(
        folder_path,
        "MASTER_voltage_recommended_cycles.png"
    )

    plt.savefig(summary_plot, dpi=300)
    plt.close()

    print(f"Saved convergence folder summary:\n{output_excel}")

    return output_excel



'''
TRIBO OUTPUT FUNCTIONS
'''

def plot_test_signals_vs_time(file_path):

    df = load_data(file_path)

    if len(df) == 0:
        raise ValueError("No valid data found.")

    active_df = df[
        df["force"] > 0.1
    ]

    if len(active_df) > 0:

        start_time = active_df["time"].min()
        end_time = active_df["time"].max()

        df = df[
            (df["time"] >= start_time)
            &
            (df["time"] <= end_time)
        ]

    fig, ax1 = plt.subplots(figsize=(25, 10))

    ax1.plot(
        df["time"],
        df["force"],
        color=PLOT_COLOURS["force"],
        label="Force"
    )

    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Force (N)", color=PLOT_COLOURS["force"])
    ax1.tick_params(axis="y", labelcolor=PLOT_COLOURS["force"])

    axes = [ax1]
    lines = ax1.get_lines()

    if "voltage" in df.columns:

        ax2 = ax1.twinx()

        ax2.plot(
            df["time"],
            df["voltage"],
            color=PLOT_COLOURS["voltage"],
            linestyle="dotted",
            label="Voltage"
        )

        ax2.set_ylabel("Voltage (V)", color=PLOT_COLOURS["voltage"])
        ax2.tick_params(axis="y", labelcolor=PLOT_COLOURS["voltage"])

        axes.append(ax2)
        lines += ax2.get_lines()

    if "current" in df.columns:

        ax3 = ax1.twinx()

        ax3.spines["right"].set_position(
            ("outward", 70)
        )

        ax3.plot(
            df["time"],
            df["current"],
            color=PLOT_COLOURS["current"],
            linestyle="--",
            label="Current"
        )

        ax3.set_ylabel("Current (A)", color=PLOT_COLOURS["current"])
        ax3.tick_params(axis="y", labelcolor=PLOT_COLOURS["current"])

        axes.append(ax3)
        lines += ax3.get_lines()

    labels = [
        line.get_label()
        for line in lines
    ]

    ax1.legend(
        lines,
        labels,
        loc="best"
    )

    base_name = os.path.basename(file_path)
    name_no_ext = os.path.splitext(base_name)[0]

    plt.title(name_no_ext)

    output_file = os.path.join(
        os.path.dirname(file_path),
        f"{name_no_ext}_force_voltage_current_plot.png"
    )

    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close()

    print(f"Saved plot:\n{output_file}")

    return output_file


# Function so old GUI/buttons still work
def plot_force_voltage_vs_time(file_path):
    return plot_test_signals_vs_time(file_path)


# IMPEDANCE ANALYSIS


def analyse_material_impedance(material_folder):
    """
    Analyse impedance data from:
        material_folder/Impedance/Voltage/
        material_folder/Impedance/Current/

    Voltage and current are treated as separately measured.
    Power is therefore reported as associated/reconstructed power, not instantaneous power.
    Impedance matching is identified using voltage-derived peak power: P = Vpeak² / R.
    """

    impedance_folder = os.path.join(material_folder, "Impedance")
    voltage_folder = os.path.join(impedance_folder, "Voltage")
    current_folder = os.path.join(impedance_folder, "Current")

    os.makedirs(impedance_folder, exist_ok=True)

    def resistance_label(R):
        if pd.isna(R):
            return "Unknown"
        if R == 0:
            return "SC"
        if np.isinf(R):
            return "OC"
        if R >= 1e9:
            return f"{R / 1e9:g}G"
        if R >= 1e6:
            return f"{R / 1e6:g}M"
        if R >= 1e3:
            return f"{R / 1e3:g}k"
        return f"{R:g}"

    def valid_impedance_R(R):
        return pd.notna(R) and R > 0 and not np.isinf(R)

    def collect_signal_folder(folder, signal_col):

        rows = []

        if not os.path.isdir(folder):
            return pd.DataFrame(rows)

        csv_files = sorted([
            f for f in os.listdir(folder)
            if f.endswith(".csv")
            and "_analysis" not in f
            and "_analysed" not in f
        ])

        for file in csv_files:

            file_path = os.path.join(folder, file)
            R = read_load_resistance(file_path)

            if R is None:
                print(f"Skipping {file}: no load resistance.")
                continue

            df = load_data(file_path)

            if signal_col not in df.columns:
                print(f"Skipping {file}: no {signal_col} data.")
                continue

            cycle_df, summary = calculate_cycle_peak_rms_metrics(
                df,
                signal_col=signal_col,
                baseline_method="median"
            )

            rows.append({
                "File": file,
                "Load Resistance (Ohm)": R,
                "Load Resistance Label": resistance_label(R),
                f"Mean {signal_col} Peak": summary["mean_rectified_peak"],
                f"STD {signal_col} Peak": summary["std_rectified_peak"],
                f"Mean {signal_col} RMS": summary["mean_rms"],
                f"STD {signal_col} RMS": summary["std_rms"],
                f"{signal_col} Cycles Analysed": summary["n_cycles"]
            })

        return pd.DataFrame(rows)

    voltage_df = collect_signal_folder(voltage_folder, "voltage")
    current_df = collect_signal_folder(current_folder, "current")

    if len(voltage_df) == 0 and len(current_df) == 0:
        raise ValueError("No valid impedance voltage or current data found.")

    summary_df = pd.merge(
        voltage_df,
        current_df,
        on=["Load Resistance (Ohm)", "Load Resistance Label"],
        how="outer"
    )

    summary_df = summary_df.sort_values(
        "Load Resistance (Ohm)"
    ).reset_index(drop=True)

    # =====================================================
    # ASSOCIATED POWER: V and I measured separately
    # =====================================================

    summary_df["Associated Peak Power (W)"] = (
        summary_df["Mean voltage Peak"]
        *
        summary_df["Mean current Peak"]
    )

    summary_df["Associated RMS Power (W)"] = (
        summary_df["Mean voltage RMS"]
        *
        summary_df["Mean current RMS"]
    )

    # =====================================================
    # VOLTAGE-DERIVED POWER: P = V²/R
    # Used for impedance matching
    # =====================================================

    summary_df["Voltage-Derived Peak Power V²/R (W)"] = np.nan
    summary_df["Voltage-Derived RMS Power V²/R (W)"] = np.nan

    for idx, row in summary_df.iterrows():

        R = row["Load Resistance (Ohm)"]

        if valid_impedance_R(R):

            if pd.notna(row["Mean voltage Peak"]):
                summary_df.loc[
                    idx,
                    "Voltage-Derived Peak Power V²/R (W)"
                ] = row["Mean voltage Peak"] ** 2 / R

            if pd.notna(row["Mean voltage RMS"]):
                summary_df.loc[
                    idx,
                    "Voltage-Derived RMS Power V²/R (W)"
                ] = row["Mean voltage RMS"] ** 2 / R

    valid_power_df = summary_df[
        summary_df["Voltage-Derived Peak Power V²/R (W)"].notna()
    ]

    if len(valid_power_df) > 0:

        max_idx = valid_power_df[
            "Voltage-Derived Peak Power V²/R (W)"
        ].idxmax()

        matched_R = summary_df.loc[max_idx, "Load Resistance (Ohm)"]
        matched_label = summary_df.loc[max_idx, "Load Resistance Label"]

    else:
        matched_R = np.nan
        matched_label = "Unknown"

    summary_df["Impedance Matched Load?"] = (
        summary_df["Load Resistance (Ohm)"] == matched_R
    )

    output_excel = os.path.join(
        impedance_folder,
        "IMPEDANCE_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

    def plot_impedance(
        voltage_col,
        current_col,
        power_col,
        title,
        filename,
        voltage_ylabel,
        current_ylabel,
        power_ylabel
    ):

        plot_df = summary_df[
            summary_df["Load Resistance (Ohm)"].apply(valid_impedance_R)
        ].copy()

        if len(plot_df) == 0:
            return None

        fig, ax1 = plt.subplots(figsize=(9, 6))
        lines = []

        if voltage_col in plot_df.columns:
            line1, = ax1.plot(
                plot_df["Load Resistance (Ohm)"],
                plot_df[voltage_col],
                marker="o",
                color=PLOT_COLOURS["voltage"],
                label=voltage_ylabel
            )
            lines.append(line1)

        ax1.set_xscale("log")
        ax1.set_xlabel("Load Resistance (Ω)")
        ax1.set_ylabel(voltage_ylabel)

        ax2 = ax1.twinx()

        if current_col in plot_df.columns:
            line2, = ax2.plot(
                plot_df["Load Resistance (Ohm)"],
                plot_df[current_col] * 1e6,
                marker="s",
                color=PLOT_COLOURS["current"],
                label=current_ylabel
            )
            lines.append(line2)

        ax2.set_ylabel(current_ylabel)

        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("outward", 70))

        if power_col in plot_df.columns:
            line3, = ax3.plot(
                plot_df["Load Resistance (Ohm)"],
                plot_df[power_col],
                marker="^",
                linestyle=":",
                color=PLOT_COLOURS["power"],
                label=power_ylabel
            )
            lines.append(line3)

        ax3.set_ylabel(power_ylabel)

        if pd.notna(matched_R):
            ax1.axvline(
                matched_R,
                linestyle="--",
                color=PLOT_COLOURS["target"]
            )

            ax1.text(
                matched_R,
                ax1.get_ylim()[1] * 0.95,
                f"Matched load:\n{matched_label}",
                rotation=90,
                va="top",
                ha="right"
            )

        ax1.legend(
            lines,
            [line.get_label() for line in lines],
            loc="best"
        )

        plt.title(title)
        plt.tight_layout()

        plot_path = os.path.join(
            impedance_folder,
            filename
        )

        plt.savefig(plot_path, dpi=300)
        plt.close()

        return plot_path

    plot_impedance(
        voltage_col="Mean voltage Peak",
        current_col="Mean current Peak",
        power_col="Voltage-Derived Peak Power V²/R (W)",
        title="Impedance Matching: Peak Voltage, Current and Voltage-Derived Power",
        filename="Impedance_Peak_Voltage_Current_Power.png",
        voltage_ylabel="Mean peak voltage (V)",
        current_ylabel="Mean peak current (µA)",
        power_ylabel="Voltage-derived peak power (W)"
    )

    plot_impedance(
        voltage_col="Mean voltage RMS",
        current_col="Mean current RMS",
        power_col="Voltage-Derived RMS Power V²/R (W)",
        title="Impedance Matching: RMS Voltage, Current and Voltage-Derived Power",
        filename="Impedance_RMS_Voltage_Current_Power.png",
        voltage_ylabel="RMS voltage (V)",
        current_ylabel="RMS current (µA)",
        power_ylabel="Voltage-derived RMS power (W)"
    )

    print(f"Saved impedance analysis:\n{output_excel}")
    print(f"Impedance matched load: {matched_label}")

    return output_excel


def analyse_voltage_only_impedance(material_folder):

    impedance_folder = os.path.join(material_folder, "Impedance")
    voltage_folder = os.path.join(impedance_folder, "Voltage")

    if not os.path.isdir(voltage_folder):
        raise ValueError(f"Voltage impedance folder not found:\n{voltage_folder}")

    os.makedirs(impedance_folder, exist_ok=True)

    def resistance_label(R):
        if pd.isna(R):
            return "Unknown"
        if R == 0:
            return "SC"
        if np.isinf(R):
            return "OC"
        if R >= 1e9:
            return f"{R / 1e9:g}G"
        if R >= 1e6:
            return f"{R / 1e6:g}M"
        if R >= 1e3:
            return f"{R / 1e3:g}k"
        return f"{R:g}"

    def valid_R(R):
        return pd.notna(R) and R > 0 and not np.isinf(R)

    rows = []

    csv_files = sorted([
        f for f in os.listdir(voltage_folder)
        if f.endswith(".csv")
        and "_analysis" not in f
        and "_analysed" not in f
    ])

    if len(csv_files) == 0:
        raise ValueError("No voltage impedance CSV files found.")

    for file in csv_files:

        file_path = os.path.join(voltage_folder, file)

        R = read_load_resistance(file_path)

        if R is None:
            print(f"Skipping {file}: no load resistance.")
            continue

        df = load_data(file_path)

        if "voltage" not in df.columns:
            print(f"Skipping {file}: no voltage column.")
            continue

        cycle_df, summary = calculate_cycle_peak_rms_metrics(
            df,
            signal_col="voltage",
            baseline_method="median"
        )

        mean_peak = summary["mean_rectified_peak"]
        std_peak = summary["std_rectified_peak"]
        mean_rms = summary["mean_rms"]
        std_rms = summary["std_rms"]

        peak_power = np.nan
        rms_power = np.nan

        if valid_R(R):
            peak_power = mean_peak ** 2 / R
            rms_power = mean_rms ** 2 / R

        rows.append({
            "File": file,
            "Load Resistance (Ohm)": R,
            "Load Resistance Label": resistance_label(R),

            "Mean Vpeak Rectified (V)": mean_peak,
            "STD Vpeak Rectified (V)": std_peak,
            "CV Vpeak Rectified (%)": (
                std_peak / mean_peak * 100
                if mean_peak != 0
                else np.nan
            ),

            "Vrms (V)": mean_rms,
            "STD Vrms (V)": std_rms,
            "CV Vrms (%)": (
                std_rms / mean_rms * 100
                if mean_rms != 0
                else np.nan
            ),

            "Peak Power from Vpeak^2/R (W)": peak_power,
            "RMS Power from Vrms^2/R (W)": rms_power,

            "Cycles Analysed": summary["n_cycles"]
        })

    summary_df = pd.DataFrame(rows)

    if len(summary_df) == 0:
        raise ValueError("No valid voltage impedance data found.")

    summary_df = summary_df.sort_values(
        "Load Resistance (Ohm)"
    ).reset_index(drop=True)

    valid_power_df = summary_df[
        summary_df["Load Resistance (Ohm)"].apply(valid_R)
        &
        summary_df["Peak Power from Vpeak^2/R (W)"].notna()
    ]

    if len(valid_power_df) > 0:
        max_idx = valid_power_df[
            "Peak Power from Vpeak^2/R (W)"
        ].idxmax()

        matched_R = summary_df.loc[
            max_idx,
            "Load Resistance (Ohm)"
        ]

        matched_label = summary_df.loc[
            max_idx,
            "Load Resistance Label"
        ]

    else:
        matched_R = np.nan
        matched_label = "Unknown"

    summary_df["Impedance Matched Load?"] = (
        summary_df["Load Resistance (Ohm)"] == matched_R
    )

    output_excel = os.path.join(
        impedance_folder,
        "VOLTAGE_ONLY_IMPEDANCE_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

    # =====================================================
    # PLOT POSITIONS INCLUDING SC AND OC
    # =====================================================

    plot_df = summary_df.copy()

    finite_R = plot_df[
        plot_df["Load Resistance (Ohm)"].apply(valid_R)
    ]["Load Resistance (Ohm)"]

    if len(finite_R) == 0:
        raise ValueError("No finite resistance values available for plotting.")

    min_R = finite_R.min()
    max_R = finite_R.max()

    def plot_position(R):
        if R == 0:
            return min_R / 10
        if np.isinf(R):
            return max_R * 10
        return R

    plot_df["Plot Resistance"] = plot_df[
        "Load Resistance (Ohm)"
    ].apply(plot_position)

    plot_df = plot_df.sort_values(
        "Plot Resistance"
    ).reset_index(drop=True)

    def plot_voltage_impedance(
        voltage_col,
        power_col,
        title,
        filename,
        voltage_ylabel,
        voltage_colour,
        power_colour
    ):

        fig, ax1 = plt.subplots(figsize=(9, 6))

        line1, = ax1.plot(
            plot_df["Plot Resistance"],
            plot_df[voltage_col],
            marker="o",
            color=voltage_colour,
            label=voltage_ylabel
        )

        ax1.set_xscale("log")
        ax1.set_xlabel("Load Resistance")
        ax1.set_ylabel(
            voltage_ylabel,
            color=voltage_colour
        )

        ax1.tick_params(
            axis="y",
            labelcolor=voltage_colour
        )

        ax1.set_xticks(
            plot_df["Plot Resistance"]
        )

        ax1.set_xticklabels(
            plot_df["Load Resistance Label"],
            rotation=45,
            ha="right"
        )

        ax2 = ax1.twinx()

        line2, = ax2.plot(
            plot_df["Plot Resistance"],
            plot_df[power_col],
            marker="s",
            linestyle=":",
            color=power_colour,
            label="Voltage-derived power"
        )

        ax2.set_ylabel(
            "Power (W)",
            color=power_colour
        )

        ax2.tick_params(
            axis="y",
            labelcolor=power_colour
        )

        if pd.notna(matched_R) and valid_R(matched_R):

            matched_plot_R = plot_position(matched_R)

            ax1.axvline(
                matched_plot_R,
                linestyle="--",
                color=PLOT_COLOURS["target"],
                label=f"Matched load = {matched_label}"
            )

            ax1.text(
                matched_plot_R,
                ax1.get_ylim()[1] * 0.95,
                f"Matched load\n{matched_label}",
                rotation=90,
                va="top",
                ha="right"
            )

        ax1.legend(
            [line1, line2],
            [line1.get_label(), line2.get_label()],
            loc="best"
        )

        plt.title(title)
        plt.tight_layout()

        plot_path = os.path.join(
            impedance_folder,
            filename
        )

        plt.savefig(plot_path, dpi=300)
        plt.close()

        return plot_path

    peak_plot = plot_voltage_impedance(
        voltage_col="Mean Vpeak Rectified (V)",
        power_col="Peak Power from Vpeak^2/R (W)",
        title="Voltage-Only Impedance: Peak Voltage and Voltage-Derived Power",
        filename="Voltage_Only_Impedance_Peak.png",
        voltage_ylabel="Mean rectified peak voltage (V)",
        voltage_colour=PLOT_COLOURS["voltage"],
        power_colour=PLOT_COLOURS["power"]
    )

    rms_plot = plot_voltage_impedance(
        voltage_col="Vrms (V)",
        power_col="RMS Power from Vrms^2/R (W)",
        title="Voltage-Only Impedance: RMS Voltage and Voltage-Derived Power",
        filename="Voltage_Only_Impedance_RMS.png",
        voltage_ylabel="RMS voltage (V)",
        voltage_colour=PLOT_COLOURS["voltage_rms"],
        power_colour=PLOT_COLOURS["power_rms"]
    )

    print(f"Saved voltage-only impedance analysis:\n{output_excel}")
    print(f"Impedance matched load: {matched_label}")
    print(f"Saved peak plot:\n{peak_plot}")
    print(f"Saved RMS plot:\n{rms_plot}")

    return output_excel


# SIGNAL CHARACTERISATION


def analyse_voltage_force_characterisation(material_folder):
    """
    Analyse:
        VOC/
        Matched_Voltage/

    for one material folder.

    Reports:
        - mean peak voltage
        - RMS voltage
        - STD peak voltage
        - CV peak voltage
        - STD RMS voltage
        - CV RMS voltage

    all vs force.
    """

    force_folder = os.path.join(
        material_folder,
        "Force_Characterisation"
    )

    voc_folder = os.path.join(
        force_folder,
        "VOC"
    )

    matched_folder = os.path.join(
        force_folder,
        "Matched_Voltage"
    )

    output_excel = os.path.join(
        force_folder,
        "VOLTAGE_FORCE_CHARACTERISATION.xlsx"
    )

    def analyse_voltage_folder(folder, test_name):

        rows = []

        if not os.path.isdir(folder):
            print(f"Missing folder: {folder}")
            return pd.DataFrame(rows)

        csv_files = sorted([
            f for f in os.listdir(folder)
            if (
                f.endswith(".csv")
                and "_analysis" not in f
                and "_analysed" not in f
            )
        ])

        for file in csv_files:

            file_path = os.path.join(
                folder,
                file
            )

            target_force = read_target_force(file_path)

            if target_force is None:
                print(f"Skipping {file}: no target force.")
                continue

            load_resistance = read_load_resistance(file_path)

            df = load_data(file_path)

            if "voltage" not in df.columns:
                continue

            cycle_df, summary = calculate_cycle_peak_rms_metrics(
                df,
                signal_col="voltage",
                baseline_method="median"
            )

            mean_peak = summary["mean_rectified_peak"]
            mean_rms = summary["mean_rms"]

            std_peak = summary["std_rectified_peak"]
            std_rms = summary["std_rms"]

            rows.append({
                "Test": test_name,
                "File": file,

                "Target Force (N)": target_force,
                "Load Resistance (Ohm)": load_resistance,

                "Mean Peak Voltage (V)": mean_peak,
                "STD Peak Voltage (V)": std_peak,
                "CV Peak Voltage (%)": (
                    std_peak
                    / mean_peak
                    * 100
                    if mean_peak != 0
                    else np.nan
                ),

                "Mean RMS Voltage (V)": mean_rms,
                "STD RMS Voltage (V)": std_rms,
                "CV RMS Voltage (%)": (
                    std_rms
                    / mean_rms
                    * 100
                    if mean_rms != 0
                    else np.nan
                ),

                "Cycles Analysed": summary["n_cycles"]
            })

        return pd.DataFrame(rows)

    voc_df = analyse_voltage_folder(
        voc_folder,
        "VOC"
    )

    matched_df = analyse_voltage_folder(
        matched_folder,
        "Matched Voltage"
    )

    combined_df = pd.concat(
        [voc_df, matched_df],
        ignore_index=True
    )

    with pd.ExcelWriter(
        output_excel,
        engine="openpyxl"
    ) as writer:

        voc_df.to_excel(
            writer,
            sheet_name="VOC",
            index=False
        )

        matched_df.to_excel(
            writer,
            sheet_name="MATCHED_VOLTAGE",
            index=False
        )

        combined_df.to_excel(
            writer,
            sheet_name="ALL_DATA",
            index=False
        )

    def plot_metric(
        df,
        metric_col,
        ylabel,
        filename,
        colour
    ):

        if len(df) == 0:
            return

        plt.figure(figsize=(8, 6))

        for test_name in df["Test"].unique():

            subset = df[
                df["Test"] == test_name
            ].sort_values("Target Force (N)")

            plt.plot(
                subset["Target Force (N)"],
                subset[metric_col],
                marker="o",
                label=test_name
            )

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(f"{ylabel} vs Force")

        plt.grid(
            True,
            linestyle="--",
            alpha=0.4
        )

        plt.legend()
        plt.tight_layout()

        plt.savefig(
            os.path.join(
                force_folder,
                filename
            ),
            dpi=300
        )

        plt.close()

    plot_metric(
        combined_df,
        "Mean Peak Voltage (V)",
        "Mean Peak Voltage (V)",
        "Voltage_peak_vs_force.png",
        PLOT_COLOURS["voltage"]
    )

    plot_metric(
        combined_df,
        "Mean RMS Voltage (V)",
        "RMS Voltage (V)",
        "Voltage_rms_vs_force.png",
        PLOT_COLOURS["voltage_rms"]
    )

    plot_metric(
        combined_df,
        "STD Peak Voltage (V)",
        "STD Peak Voltage (V)",
        "Voltage_peak_std_vs_force.png",
        PLOT_COLOURS["voltage"]
    )

    plot_metric(
        combined_df,
        "CV Peak Voltage (%)",
        "CV Peak Voltage (%)",
        "Voltage_peak_cv_vs_force.png",
        PLOT_COLOURS["voltage"]
    )

    plot_metric(
        combined_df,
        "STD RMS Voltage (V)",
        "STD RMS Voltage (V)",
        "Voltage_rms_std_vs_force.png",
        PLOT_COLOURS["voltage_rms"]
    )

    plot_metric(
        combined_df,
        "CV RMS Voltage (%)",
        "CV RMS Voltage (%)",
        "Voltage_rms_cv_vs_force.png",
        PLOT_COLOURS["voltage_rms"]
    )

    print(
        f"Saved voltage force characterisation:\n{output_excel}"
    )

    return output_excel

def analyse_material_force_characterisation(material_folder):
    """
    Whole-material force characterisation.

    Expected structure:

        material_folder/
            Force_Characterisation/
                VOC/
                ISC/
                Matched_Voltage/
                Matched_Current/

    This function:
        1. Calls the individual folder analysers.
        2. Combines their SUMMARY sheets into one material-level Excel file.
        3. Makes material-level plots using the correct voltage/current colours.
        4. Includes the material name in each individual material plot title.
    """

    import os
    import pandas as pd
    import matplotlib.pyplot as plt

    material_name = os.path.basename(os.path.normpath(material_folder))

    force_folder = os.path.join(
        material_folder,
        "Force_Characterisation"
    )

    if not os.path.isdir(force_folder):
        raise ValueError(
            f"Force_Characterisation folder not found:\n{force_folder}"
        )

    analysis_jobs = [
        {
            "test_name": "VOC",
            "folder": os.path.join(force_folder, "VOC"),
            "function": analyse_voc_force_folder,
            "signal": "voltage"
        },
        {
            "test_name": "ISC",
            "folder": os.path.join(force_folder, "ISC"),
            "function": analyse_isc_force_folder,
            "signal": "current"
        },
        {
            "test_name": "Matched Voltage",
            "folder": os.path.join(force_folder, "Matched_Voltage"),
            "function": analyse_matched_voltage_force_folder,
            "signal": "voltage"
        },
        {
            "test_name": "Matched Current",
            "folder": os.path.join(force_folder, "Matched_Current"),
            "function": analyse_matched_current_force_folder,
            "signal": "current"
        }
    ]

    combined_summary_rows = []

    for job in analysis_jobs:

        if not os.path.isdir(job["folder"]):
            print(f"Skipping missing folder: {job['folder']}")
            continue

        try:
            output_file = job["function"](job["folder"])

            summary_df = pd.read_excel(
                output_file,
                sheet_name="SUMMARY"
            )

            summary_df["Test"] = job["test_name"]
            summary_df["Signal Type"] = job["signal"]

            combined_summary_rows.append(summary_df)

        except Exception as e:
            print(
                f"Skipping {job['test_name']} analysis due to error:\n{e}"
            )

    if len(combined_summary_rows) == 0:
        raise ValueError(
            "No valid force-characterisation analyses completed."
        )

    combined_df = pd.concat(
        combined_summary_rows,
        ignore_index=True
    )

    combined_df = combined_df.sort_values(
        ["Test", "Target Force (N)"]
    ).reset_index(drop=True)

    output_excel = os.path.join(
        force_folder,
        "MATERIAL_FORCE_CHARACTERISATION_SUMMARY.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        combined_df.to_excel(
            writer,
            sheet_name="SUMMARY_ALL_TESTS",
            index=False
        )

        for test_name in combined_df["Test"].unique():

            test_df = combined_df[
                combined_df["Test"] == test_name
            ].copy()

            safe_sheet_name = str(test_name).replace("/", "_")[:31]

            test_df.to_excel(
                writer,
                sheet_name=safe_sheet_name,
                index=False
            )

    def get_line_style(test_name):
        """
        Keeps signal colour consistent while still distinguishing
        open/short circuit tests from matched-load tests.
        """

        if test_name in ["VOC", "ISC"]:
            return "-"

        return "--"

    def plot_combined_metric(
        signal_type,
        metric_col,
        ylabel,
        title,
        filename,
        scale=1,
        colour=None
    ):

        plot_df = combined_df[
            combined_df["Signal Type"] == signal_type
        ].copy()

        if len(plot_df) == 0:
            print(f"No {signal_type} data found for {material_name}.")
            return None

        if metric_col not in plot_df.columns:
            print(f"Column not found: {metric_col}")
            return None

        plt.figure(figsize=(8, 6))

        for test_name in plot_df["Test"].unique():

            subset = plot_df[
                plot_df["Test"] == test_name
            ].sort_values("Target Force (N)")

            plt.plot(
                subset["Target Force (N)"],
                subset[metric_col] * scale,
                marker="o",
                color=colour,
                linestyle=get_line_style(test_name),
                label=test_name
            )

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(f"{material_name}: {title}")

        plt.grid(
            True,
            linestyle="--",
            alpha=0.4
        )

        plt.legend()
        plt.tight_layout()

        output_path = os.path.join(force_folder, filename)

        plt.savefig(
            output_path,
            dpi=300
        )

        plt.close()

        return output_path

    # =====================================================
    # VOLTAGE SUMMARY PLOTS
    # =====================================================

    plot_combined_metric(
        signal_type="voltage",
        metric_col="Mean Rectified Peak",
        ylabel="Mean rectified peak voltage (V)",
        title="Voltage Peak vs Force",
        filename="Material_voltage_peak_vs_force.png",
        colour=PLOT_COLOURS["voltage"]
    )

    plot_combined_metric(
        signal_type="voltage",
        metric_col="Mean RMS",
        ylabel="Mean RMS voltage (V)",
        title="Voltage RMS vs Force",
        filename="Material_voltage_rms_vs_force.png",
        colour=PLOT_COLOURS["voltage_rms"]
    )

    plot_combined_metric(
        signal_type="voltage",
        metric_col="STD Rectified Peak",
        ylabel="STD rectified peak voltage (V)",
        title="Voltage Peak STD vs Force",
        filename="Material_voltage_peak_std_vs_force.png",
        colour=PLOT_COLOURS["voltage"]
    )

    plot_combined_metric(
        signal_type="voltage",
        metric_col="CV Rectified Peak (%)",
        ylabel="CV rectified peak voltage (%)",
        title="Voltage Peak CV vs Force",
        filename="Material_voltage_peak_cv_vs_force.png",
        colour=PLOT_COLOURS["voltage"]
    )

    # =====================================================
    # CURRENT SUMMARY PLOTS
    # =====================================================

    plot_combined_metric(
        signal_type="current",
        metric_col="Mean Rectified Peak",
        ylabel="Mean rectified peak current (µA)",
        title="Current Peak vs Force",
        filename="Material_current_peak_vs_force.png",
        scale=1e6,
        colour=PLOT_COLOURS["current"]
    )

    plot_combined_metric(
        signal_type="current",
        metric_col="Mean RMS",
        ylabel="Mean RMS current (µA)",
        title="Current RMS vs Force",
        filename="Material_current_rms_vs_force.png",
        scale=1e6,
        colour=PLOT_COLOURS["current_rms"]
    )

    plot_combined_metric(
        signal_type="current",
        metric_col="STD Rectified Peak",
        ylabel="STD rectified peak current (µA)",
        title="Current Peak STD vs Force",
        filename="Material_current_peak_std_vs_force.png",
        scale=1e6,
        colour=PLOT_COLOURS["current"]
    )

    plot_combined_metric(
        signal_type="current",
        metric_col="CV Rectified Peak (%)",
        ylabel="CV rectified peak current (%)",
        title="Current Peak CV vs Force",
        filename="Material_current_peak_cv_vs_force.png",
        colour=PLOT_COLOURS["current"]
    )

    print(
        f"Saved material force characterisation summary:\n{output_excel}"
    )

    return output_excel


def compare_all_material_force_characterisation(
    final_data_folder,
    run_material_analysis=True,
    voltage_test="VOC",
    current_test="ISC",
    current_scale=1e9,
    current_unit="nA"
):
    """
    Compare force characterisation across all materials.

    Expected structure:

        final_data_folder/
            Material_1/
                Force_Characterisation/
                    VOC/
                    ISC/
                    Matched_Voltage/
                    Matched_Current/

            Material_2/
                Force_Characterisation/
                    VOC/
                    ISC/
                    Matched_Voltage/
                    Matched_Current/

    This function:
        1. Loops through each material folder.
        2. Optionally reruns analyse_material_force_characterisation().
        3. Reads each MATERIAL_FORCE_CHARACTERISATION_SUMMARY.xlsx file.
        4. Combines all materials into one Excel file.
        5. Plots:
            - Vpeak vs force for all materials
            - Vrms vs force for all materials
            - Isc peak vs force for all materials
            - Irms vs force for all materials

    All-material plots use get_compare_colour(i), so material colours are
    consistent across all comparison plots.
    """

    import os
    import pandas as pd
    import matplotlib.pyplot as plt

    final_data_folder = os.path.abspath(final_data_folder)

    material_folders = sorted([
        f for f in os.listdir(final_data_folder)
        if os.path.isdir(os.path.join(final_data_folder, f))
    ])

    if len(material_folders) == 0:
        raise ValueError("No material folders found.")

    combined_rows = []

    for material in material_folders:

        material_folder = os.path.join(
            final_data_folder,
            material
        )

        force_folder = os.path.join(
            material_folder,
            "Force_Characterisation"
        )

        summary_excel = os.path.join(
            force_folder,
            "MATERIAL_FORCE_CHARACTERISATION_SUMMARY.xlsx"
        )

        if run_material_analysis:
            try:
                summary_excel = analyse_material_force_characterisation(
                    material_folder
                )

            except Exception as e:
                print(f"Skipping {material}: material analysis failed.")
                print(e)
                continue

        if not os.path.exists(summary_excel):
            print(f"Skipping {material}: no material summary found.")
            continue

        try:
            material_df = pd.read_excel(
                summary_excel,
                sheet_name="SUMMARY_ALL_TESTS"
            )

            material_df["Material"] = material

            combined_rows.append(material_df)

        except Exception as e:
            print(f"Skipping {material}: could not read summary Excel.")
            print(e)
            continue

    if len(combined_rows) == 0:
        raise ValueError("No valid material summaries were found.")

    combined_df = pd.concat(
        combined_rows,
        ignore_index=True
    )

    combined_df["Material"] = combined_df["Material"].astype(str).str.strip()
    combined_df["Test"] = combined_df["Test"].astype(str).str.strip()

    combined_df["Material Number"] = combined_df["Material"].apply(
        get_material_number
    )


    combined_df = combined_df.sort_values(
        ["Material", "Test", "Target Force (N)"]
    ).reset_index(drop=True)

    output_excel = os.path.join(
        final_data_folder,
        "ALL_MATERIAL_FORCE_CHARACTERISATION_COMPARISON.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        combined_df.to_excel(
            writer,
            sheet_name="ALL_DATA",
            index=False
        )

        for test_name in combined_df["Test"].dropna().unique():

            test_df = combined_df[
                combined_df["Test"] == test_name
            ].copy()

            safe_sheet_name = str(test_name).replace("/", "_")[:31]

            test_df.to_excel(
                writer,
                sheet_name=safe_sheet_name,
                index=False
            )

    def plot_material_comparison(
        test_name,
        metric_col,
        ylabel,
        title,
        filename,
        scale=1
    ):

        plot_df = combined_df[
            combined_df["Test"] == test_name
        ].copy()

        if len(plot_df) == 0:
            print(f"No data found for test: {test_name}")
            return None

        if metric_col not in plot_df.columns:
            print(f"Column not found: {metric_col}")
            return None

        plt.figure(figsize=(8, 6))

        for material in sort_materials_numerically(plot_df["Material"].unique()):

            subset = plot_df[
                plot_df["Material"] == material
            ].copy()

            subset = subset.sort_values("Target Force (N)")

            plt.plot(
                subset["Target Force (N)"],
                subset[metric_col] * scale,
                marker="o",
                color=get_material_colour(material),
                label=material
            )

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(title)

        plt.grid(
            True,
            linestyle="--",
            alpha=0.4
        )

        plt.legend(title="Material")
        plt.tight_layout()

        output_path = os.path.join(
            final_data_folder,
            filename
        )

        plt.savefig(
            output_path,
            dpi=300
        )

        plt.close()

        return output_path

    # =====================================================
    # VOLTAGE COMPARISON PLOTS
    # =====================================================

    vpeak_plot = plot_material_comparison(
        test_name=voltage_test,
        metric_col="Mean Rectified Peak",
        ylabel="Mean rectified peak voltage, Vpeak (V)",
        title=f"{voltage_test}: Vpeak vs Force",
        filename="ALL_MATERIAL_Vpeak_vs_force.png"
    )

    vrms_plot = plot_material_comparison(
        test_name=voltage_test,
        metric_col="Mean RMS",
        ylabel="Mean RMS voltage, Vrms (V)",
        title=f"{voltage_test}: Vrms vs Force",
        filename="ALL_MATERIAL_Vrms_vs_force.png"
    )

    # =====================================================
    # CURRENT COMPARISON PLOTS
    # =====================================================

    ipeak_plot = plot_material_comparison(
        test_name=current_test,
        metric_col="Mean Rectified Peak",
        ylabel=f"Mean rectified short-circuit current, Isc peak ({current_unit})",
        title=f"{current_test}: Isc Peak vs Force",
        filename="ALL_MATERIAL_Isc_peak_vs_force.png",
        scale=current_scale
    )

    irms_plot = plot_material_comparison(
        test_name=current_test,
        metric_col="Mean RMS",
        ylabel=f"Mean RMS short-circuit current, Irms ({current_unit})",
        title=f"{current_test}: Irms vs Force",
        filename="ALL_MATERIAL_Irms_vs_force.png",
        scale=current_scale
    )

    print("\nSaved all-material force characterisation comparison:")
    print(output_excel)

    print("\nSaved plots:")
    for plot in [vpeak_plot, vrms_plot, ipeak_plot, irms_plot]:
        if plot is not None:
            print(plot)

    return {
        "combined_df": combined_df,
        "excel": output_excel,
        "plots": {
            "Vpeak": vpeak_plot,
            "Vrms": vrms_plot,
            "Isc_peak": ipeak_plot,
            "Irms": irms_plot
        }
    }

def plot_material_voc_isc_peak_rms_errorbars(
    material_folder,
    run_material_analysis=False,
    current_scale=1e9,
    current_unit="nA"
):
    """
    Plot peak and RMS force-response graphs with error bars for one material.

    Creates:
        1. VOC_peak_RMS_errorbars.png
        2. ISC_peak_RMS_errorbars.png

    Error bars show cycle-level standard deviation:
        - STD Rectified Peak for peak values
        - STD RMS for RMS values

    Expected structure:
        material_folder/
            Force_Characterisation/
                MATERIAL_FORCE_CHARACTERISATION_SUMMARY.xlsx
    """

    import os
    import pandas as pd
    import matplotlib.pyplot as plt

    material_name = os.path.basename(
        os.path.normpath(material_folder)
    )

    force_folder = os.path.join(
        material_folder,
        "Force_Characterisation"
    )

    summary_excel = os.path.join(
        force_folder,
        "MATERIAL_FORCE_CHARACTERISATION_SUMMARY.xlsx"
    )

    # Optional: rerun material analysis first
    if run_material_analysis or not os.path.exists(summary_excel):
        summary_excel = analyse_material_force_characterisation(
            material_folder
        )

    if not os.path.exists(summary_excel):
        raise FileNotFoundError(
            f"Could not find material summary:\n{summary_excel}"
        )

    summary_df = pd.read_excel(
        summary_excel,
        sheet_name="SUMMARY_ALL_TESTS"
    )

    summary_df["Test"] = summary_df["Test"].astype(str).str.strip()

    def plot_peak_and_rms_for_test(
        test_name,
        ylabel,
        title,
        filename,
        peak_label,
        rms_label,
        peak_colour,
        rms_colour,
        scale=1
    ):
        plot_df = summary_df[
            summary_df["Test"] == test_name
        ].copy()

        if len(plot_df) == 0:
            print(f"No {test_name} data found for {material_name}.")
            return None

        plot_df = plot_df.sort_values("Target Force (N)")

        x = plot_df["Target Force (N)"]

        peak_y = plot_df["Mean Rectified Peak"] * scale
        peak_err = plot_df["STD Rectified Peak"] * scale

        rms_y = plot_df["Mean RMS"] * scale
        rms_err = plot_df["STD RMS"] * scale

        plt.figure(figsize=(8, 6))

        plt.errorbar(
            x,
            peak_y,
            yerr=peak_err,
            marker="o",
            capsize=4,
            linewidth=1.8,
            elinewidth=1,
            capthick=1,
            color=peak_colour,
            label=peak_label
        )

        plt.errorbar(
            x,
            rms_y,
            yerr=rms_err,
            marker="s",
            capsize=4,
            linewidth=1.8,
            elinewidth=1,
            capthick=1,
            color=rms_colour,
            label=rms_label
        )

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(f"{material_name}: {title}")

        plt.grid(
            True,
            linestyle="--",
            alpha=0.4
        )

        plt.legend()
        plt.tight_layout()

        output_path = os.path.join(
            force_folder,
            filename
        )

        plt.savefig(
            output_path,
            dpi=300
        )

        plt.close()

        return output_path

    voc_plot = plot_peak_and_rms_for_test(
        test_name="VOC",
        ylabel="Voltage (V)",
        title="VOC Peak and RMS vs Force",
        filename="VOC_peak_RMS_errorbars.png",
        peak_label="Mean rectified peak voltage",
        rms_label="RMS voltage",
        peak_colour=PLOT_COLOURS["voltage"],
        rms_colour=PLOT_COLOURS["voltage_rms"],
        scale=1
    )

    isc_plot = plot_peak_and_rms_for_test(
        test_name="ISC",
        ylabel=f"Current ({current_unit})",
        title="ISC Peak and RMS vs Force",
        filename="ISC_peak_RMS_errorbars.png",
        peak_label="Mean rectified peak current",
        rms_label="RMS current",
        peak_colour=PLOT_COLOURS["current"],
        rms_colour=PLOT_COLOURS["current_rms"],
        scale=current_scale
    )

    print("\nSaved material peak/RMS error-bar plots:")
    if voc_plot is not None:
        print(voc_plot)
    if isc_plot is not None:
        print(isc_plot)

    return {
        "VOC": voc_plot,
        "ISC": isc_plot
    }

def plot_best_signal_window(
    file_path,
    window_width_s=20,
    step_s=2,
    signal_col=None,
    output_folder=None,
    filename=None,
    start_buffer_s=5,
    end_buffer_s=5
):
    """
    Automatically find a clean-looking window of force + electrical signal
    and export a thesis-friendly plot.

    The chosen window favours:
        - regular repeated force cycles
        - force reaching a stable repeated peak
        - electrical signal with visible activity
        - low baseline drift
        - no very large single outlier dominating the window

    Parameters
    ----------
    file_path : str
        CSV file to analyse.

    window_width_s : float
        Width of the plotted window in seconds.

    step_s : float
        Step size used when scanning candidate windows.

    signal_col : str or None
        "voltage" or "current".
        If None, the function chooses voltage if available, otherwise current.

    output_folder : str or None
        Folder where the plot is saved. Defaults to the CSV folder.

    filename : str or None
        Output image filename. Defaults to automatic name.

    start_buffer_s : float
        Ignore the first few seconds of the file.

    end_buffer_s : float
        Ignore the last few seconds of the file.

    Returns
    -------
    dict
        Information about the selected window and output path.
    """

    import os
    import numpy as np
    import matplotlib.pyplot as plt

    df = load_data(file_path)

    if output_folder is None:
        output_folder = os.path.dirname(file_path)

    if signal_col is None:
        if "voltage" in df.columns:
            signal_col = "voltage"
        elif "current" in df.columns:
            signal_col = "current"
        else:
            raise ValueError("No voltage or current column found.")

    if signal_col not in df.columns:
        raise ValueError(f"Signal column '{signal_col}' not found.")

    df = df[["time", "force", signal_col]].dropna().copy()

    if len(df) == 0:
        raise ValueError("No valid data found after dropping NaNs.")

    time_min = df["time"].min() + start_buffer_s
    time_max = df["time"].max() - end_buffer_s

    if time_max - time_min < window_width_s:
        raise ValueError("File is too short for selected window width.")

    candidate_starts = np.arange(
        time_min,
        time_max - window_width_s,
        step_s
    )

    if len(candidate_starts) == 0:
        raise ValueError("No candidate windows found.")

    def robust_range(x):
        """
        Robust signal range using percentiles rather than absolute max/min.
        """
        return np.nanpercentile(x, 95) - np.nanpercentile(x, 5)

    def count_force_cycles(window_df):
        """
        Count cycles using the existing force thresholds.
        """
        cycles = find_cycles(window_df[["time", "force"]])
        return len(cycles)

    scores = []

    for start_time in candidate_starts:

        end_time = start_time + window_width_s

        window_df = df[
            (df["time"] >= start_time)
            &
            (df["time"] <= end_time)
        ].copy()

        if len(window_df) < 20:
            continue

        force = window_df["force"].to_numpy()
        signal = window_df[signal_col].to_numpy()
        time = window_df["time"].to_numpy()

        force_range = robust_range(force)
        signal_range = robust_range(signal)

        if force_range <= 0 or signal_range <= 0:
            continue

        n_cycles = count_force_cycles(window_df)

        # Aim for enough cycles to look useful, but not so many that it is visually dense.
        # At 0.5 Hz, a 20 s window gives about 10 cycles.
        expected_min_cycles = max(2, int(window_width_s * 0.25))
        expected_max_cycles = max(4, int(window_width_s * 1.5))

        if n_cycles < expected_min_cycles or n_cycles > expected_max_cycles:
            cycle_score = 0
        else:
            cycle_score = 1

        # Force regularity: compare peak force per detected cycle
        cycles = find_cycles(window_df[["time", "force"]])
        peak_forces = []

        for start_idx, end_idx in cycles:
            cycle_force = window_df.loc[start_idx:end_idx, "force"]

            if len(cycle_force) > 0:
                peak_forces.append(cycle_force.max())

        if len(peak_forces) >= 2:
            peak_forces = np.array(peak_forces)
            force_cv = (
                np.nanstd(peak_forces, ddof=1)
                /
                np.nanmean(peak_forces)
                if np.nanmean(peak_forces) != 0
                else np.inf
            )
        else:
            force_cv = np.inf

        force_regular_score = 1 / (1 + force_cv)

        # Signal activity: prefer windows with visible signal range
        signal_activity_score = np.log1p(abs(signal_range))

        # Penalise drift in electrical signal
        try:
            signal_slope = abs(np.polyfit(time, signal, 1)[0])
        except:
            signal_slope = 0

        drift_penalty = 1 / (1 + signal_slope / (abs(signal_range) + 1e-12))

        # Penalise huge isolated outliers
        signal_abs = np.abs(signal - np.nanmedian(signal))
        p95 = np.nanpercentile(signal_abs, 95)
        p50 = np.nanpercentile(signal_abs, 50)

        outlier_ratio = p95 / (p50 + 1e-12)
        outlier_penalty = 1 / (1 + max(0, outlier_ratio - 20))

        total_score = (
            3.0 * cycle_score
            +
            2.0 * force_regular_score
            +
            1.5 * signal_activity_score
            +
            1.0 * drift_penalty
            +
            1.0 * outlier_penalty
        )

        scores.append({
            "start_time": start_time,
            "end_time": end_time,
            "score": total_score,
            "n_cycles": n_cycles,
            "force_cv": force_cv,
            "signal_range": signal_range
        })

    if len(scores) == 0:
        raise ValueError("No suitable windows found.")

    best = max(scores, key=lambda x: x["score"])

    best_df = df[
        (df["time"] >= best["start_time"])
        &
        (df["time"] <= best["end_time"])
    ].copy()

    if filename is None:
        base = os.path.splitext(os.path.basename(file_path))[0]
        filename = (
            f"{base}_best_{int(window_width_s)}s_"
            f"{signal_col}_window.png"
        )

    output_path = os.path.join(output_folder, filename)

    # -------------------------
    # Plot formatting
    # -------------------------

    if signal_col == "voltage":
        signal_colour = PLOT_COLOURS["voltage"]
        signal_ylabel = "Voltage (V)"
        signal_title = "Open-circuit voltage"
    elif signal_col == "current":
        signal_colour = PLOT_COLOURS["current"]

        # Convert current to nA for readability
        best_df["current_plot"] = best_df[signal_col] * 1e9
        signal_col_to_plot = "current_plot"
        signal_ylabel = "Current (nA)"
        signal_title = "Short-circuit current"
    else:
        signal_colour = "tab:blue"
        signal_ylabel = signal_col
        signal_title = signal_col
        signal_col_to_plot = signal_col

    if signal_col != "current":
        signal_col_to_plot = signal_col

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(9, 5),
        sharex=True
    )

    axes[0].plot(
        best_df["time"],
        best_df["force"],
        color=PLOT_COLOURS["force"],
        linewidth=1.4
    )

    axes[0].set_ylabel("Force (N)")
    axes[0].set_title("Force-controlled contact-separation cycles")
    axes[0].grid(True, linestyle="--", alpha=0.4)

    axes[1].plot(
        best_df["time"],
        best_df[signal_col_to_plot],
        color=signal_colour,
        linewidth=1.2
    )

    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel(signal_ylabel)
    axes[1].set_title(signal_title)
    axes[1].grid(True, linestyle="--", alpha=0.4)

    fig.suptitle(
        f"Example signal window: {os.path.basename(file_path)}",
        fontsize=10
    )

    plt.tight_layout()

    plt.savefig(output_path, dpi=300)
    plt.close()

    print("\nSaved best signal window plot:")
    print(output_path)

    print("\nSelected window:")
    print(f"Start: {best['start_time']:.2f} s")
    print(f"End:   {best['end_time']:.2f} s")
    print(f"Cycles detected: {best['n_cycles']}")
    print(f"Window score: {best['score']:.3f}")

    return {
        "output_path": output_path,
        "start_time": best["start_time"],
        "end_time": best["end_time"],
        "n_cycles": best["n_cycles"],
        "score": best["score"]
    }

# def analyse_repeatability_across_repeats(
#     folder_path,
#     signal_col,
#     output_name,
#     baseline_method="median"
# ):
#     """
#     Analyse repeatability across repeated test runs.

#     Intended for folders containing repeated tests under the same condition,
#     e.g. three repeats of:
#         - VOC at 10 N
#         - ISC at 20 N
#         - matched-load voltage at 15 N

#     For each CSV:
#         - calculates mean rectified peak
#         - calculates RMS

#     Across files:
#         - calculates mean, STD, CV%
#         - plots repeat-to-repeat peak and RMS
#     """

#     rows = []

#     csv_files = sorted([
#         f for f in os.listdir(folder_path)
#         if f.endswith(".csv")
#         and "_analysis" not in f
#         and "_analysed" not in f
#     ])

#     if len(csv_files) == 0:
#         raise ValueError("No CSV files found.")

#     for repeat_num, file in enumerate(csv_files, start=1):

#         file_path = os.path.join(folder_path, file)

#         df = load_data(file_path)

#         if signal_col not in df.columns:
#             print(f"Skipping {file}: no {signal_col} column.")
#             continue

#         _, summary = calculate_cycle_peak_rms_metrics(
#             df,
#             signal_col=signal_col,
#             baseline_method=baseline_method
#         )

#         target_force = read_target_force(file_path)
#         load_resistance = read_load_resistance(file_path)
#         measurement_mode = read_measurement_mode(file_path)

#         rows.append({
#             "Repeat": repeat_num,
#             "File": file,
#             "Target Force (N)": target_force,
#             "Load Resistance (Ohm)": load_resistance,
#             "Measurement Mode": measurement_mode,
#             "Mean Rectified Peak": summary["mean_rectified_peak"],
#             "STD Rectified Peak Within File": summary["std_rectified_peak"],
#             "Mean RMS": summary["mean_rms"],
#             "STD RMS Within File": summary["std_rms"],
#             "Cycles Analysed": summary["n_cycles"]
#         })

#     repeat_df = pd.DataFrame(rows)

#     if len(repeat_df) == 0:
#         raise ValueError("No valid repeat data found.")

#     unit = "V" if signal_col == "voltage" else "A"

#     summary = {
#         "Signal": signal_col,
#         "Unit": unit,
#         "N Repeats": len(repeat_df),

#         "Mean Peak Across Repeats": repeat_df["Mean Rectified Peak"].mean(),
#         "STD Peak Across Repeats": repeat_df["Mean Rectified Peak"].std(ddof=1),
#         "CV Peak Across Repeats (%)": (
#             repeat_df["Mean Rectified Peak"].std(ddof=1)
#             / repeat_df["Mean Rectified Peak"].mean()
#             * 100
#         ),

#         "Mean RMS Across Repeats": repeat_df["Mean RMS"].mean(),
#         "STD RMS Across Repeats": repeat_df["Mean RMS"].std(ddof=1),
#         "CV RMS Across Repeats (%)": (
#             repeat_df["Mean RMS"].std(ddof=1)
#             / repeat_df["Mean RMS"].mean()
#             * 100
#         )
#     }

#     summary_df = pd.DataFrame([summary])

#     output_excel = os.path.join(
#         folder_path,
#         f"{output_name}_REPEATABILITY_ANALYSIS.xlsx"
#     )

#     with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

#         repeat_df.to_excel(
#             writer,
#             sheet_name="REPEAT_RESULTS",
#             index=False
#         )

#         summary_df.to_excel(
#             writer,
#             sheet_name="SUMMARY",
#             index=False
#         )

#     scale = 1
#     ylabel_unit = unit

#     if signal_col == "current":
#         scale = 1e6
#         ylabel_unit = "µA"

#     plt.figure(figsize=(8, 6))

#     plt.plot(
#         repeat_df["Repeat"],
#         repeat_df["Mean Rectified Peak"] * scale,
#         marker="o",
#         label="Mean rectified peak"
#     )

#     plt.plot(
#         repeat_df["Repeat"],
#         repeat_df["Mean RMS"] * scale,
#         marker="s",
#         label="Mean RMS"
#     )

#     plt.xlabel("Repeat Number")
#     plt.ylabel(f"{signal_col.capitalize()} ({ylabel_unit})")
#     plt.title(f"{output_name}: Repeatability Across Repeats")
#     plt.grid(True, linestyle="--", alpha=0.4)
#     plt.legend()
#     plt.tight_layout()

#     plot_path = os.path.join(
#         folder_path,
#         f"{output_name}_repeatability_across_repeats.png"
#     )

#     plt.savefig(plot_path, dpi=300)
#     plt.close()

#     print(f"Saved repeatability analysis:\n{output_excel}")
#     print(f"Saved repeatability plot:\n{plot_path}")

#     return output_excel


def get_material_number(material_name):
    """
    Extract leading material number from material name.

    Examples:
        '7 - 80% modal and 20% kapok' -> 7
        '13 - 99% circ lyocell 1% elastane' -> 13
        '0 - PDMS' -> 0

    If no leading number is found, returns a large number so it appears last.
    """

    import re
    import numpy as np

    match = re.match(r"^\s*(\d+)", str(material_name))

    if match:
        return int(match.group(1))

    return 9999


def sort_materials_numerically(materials):
    """
    Sort material names by their leading material number.
    """

    return sorted(
        materials,
        key=lambda name: (
            get_material_number(name),
            str(name)
        )
    )


def get_material_colour(material_name):
    """
    Fixed colour per material.

    This prevents colours changing when PDMS is added/removed from a plot.
    Edit these hex codes if you want different colours.
    """

    material_number = get_material_number(material_name)

    MATERIAL_COLOURS = {
        0:  "#7F7F7F",  # PDMS - grey

        7:   "#FF4F61",  # modal/kapok 
        8:   "#FFC618",  # PLA/hemp 
        11: "#87CB52",  # seacell 
        12: "#7CC6CF",  # vegetal fibre/elastane 
        13:   "#8EBCF8",  # circ lyocell/elastane 
        15:  "#008080",  # bamboo/seacell/elastane 
    }


    if material_number in MATERIAL_COLOURS:
        return MATERIAL_COLOURS[material_number]

    # fallback if a new material number is added
    return "#333333"


def analyse_force_characterisation_folder(
    folder_path,
    signal_col="voltage",
    output_name="FORCE_CHARACTERISATION",
    baseline_method="median"
):
    """
    Generic force-characterisation analysis.

    Works for:
        VOC voltage folders
        ISC current folders
        matched voltage folders
        matched current folders

    Produces:
        - Excel summary
        - cycle data
        - peak vs force plot
        - RMS vs force plot
        - STD peak vs force plot
        - CV peak vs force plot
    """

    if not os.path.isdir(folder_path):
        raise ValueError(f"Folder not found:\n{folder_path}")

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if (
            f.endswith(".csv")
            and "_analysis" not in f
            and "_analysed" not in f
        )
    ])

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")

    summary_rows = []
    cycle_rows = []

    for file in csv_files:

        file_path = os.path.join(folder_path, file)

        target_force = read_target_force(file_path)
        load_resistance = read_load_resistance(file_path)
        measurement_mode = read_measurement_mode(file_path)

        if target_force is None:
            print(f"Skipping {file}: no target force found.")
            continue

        df = load_data(file_path)

        # =====================================================
        # CURRENT-MODE FALLBACK
        # If current data was recorded as voltage across the shunt,
        # convert it here using I = V / R.
        # =====================================================

        if signal_col == "current" and "current" not in df.columns:

            if "voltage" in df.columns:

                print(
                    f"{file}: no current column found. "
                    f"Using voltage column as shunt voltage and converting to current."
                )

                df["current"] = (
                    df["voltage"]
                    / CURRENT_SHUNT_RESISTOR_OHM
                )

            else:
                print(f"Skipping {file}: no current or voltage column.")
                continue

        elif signal_col not in df.columns:

            print(f"Skipping {file}: no {signal_col} column.")
            continue


        cycle_df, summary = calculate_cycle_peak_rms_metrics(
            df,
            signal_col=signal_col,
            baseline_method=baseline_method
        )

        if summary["n_cycles"] == 0:
            print(f"Skipping {file}: no valid cycles.")
            continue

        mean_peak = summary["mean_rectified_peak"]
        std_peak = summary["std_rectified_peak"]
        mean_rms = summary["mean_rms"]
        std_rms = summary["std_rms"]

        cv_peak = (
            std_peak / mean_peak * 100
            if mean_peak != 0
            else np.nan
        )

        cv_rms = (
            std_rms / mean_rms * 100
            if mean_rms != 0
            else np.nan
        )

        summary_rows.append({
            "File": file,
            "Measurement Mode": measurement_mode,
            "Load Resistance (Ohm)": load_resistance,
            "Target Force (N)": target_force,
            "Signal": signal_col,

            "Mean Rectified Peak": mean_peak,
            "STD Rectified Peak": std_peak,
            "CV Rectified Peak (%)": cv_peak,

            "Mean RMS": mean_rms,
            "STD RMS": std_rms,
            "CV RMS (%)": cv_rms,

            "Cycles Analysed": summary["n_cycles"]
        })

        for _, row in cycle_df.iterrows():

            cycle_rows.append({
                "File": file,
                "Measurement Mode": measurement_mode,
                "Load Resistance (Ohm)": load_resistance,
                "Target Force (N)": target_force,
                "Signal": signal_col,
                "Cycle": row["cycle"],
                "Positive Peak": row["positive_peak"],
                "Negative Peak Abs": row["negative_peak_abs"],
                "Rectified Peak": row["rectified_peak"],
                "Max Abs Peak": row["max_abs_peak"],
                "RMS": row["rms"]
            })

    summary_df = pd.DataFrame(summary_rows)
    cycles_df = pd.DataFrame(cycle_rows)

    if len(summary_df) == 0:
        raise ValueError("No valid force-characterisation data found.")

    summary_df = summary_df.sort_values(
        "Target Force (N)"
    ).reset_index(drop=True)

    output_excel = os.path.join(
        folder_path,
        f"{output_name}_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

        cycles_df.to_excel(
            writer,
            sheet_name="CYCLES",
            index=False
        )

    if signal_col == "current":
        y_scale = 1e6
        signal_unit = "µA"
        peak_colour = PLOT_COLOURS.get("current", "tab:green")
        rms_colour = PLOT_COLOURS.get("current_rms", "tab:olive")
    else:
        y_scale = 1
        signal_unit = "V"
        peak_colour = PLOT_COLOURS.get("voltage", "tab:blue")
        rms_colour = PLOT_COLOURS.get("voltage_rms", "tab:cyan")

    def plot_metric(metric_col, ylabel, filename, colour, scale=1):

        plt.figure(figsize=(8, 6))

        plt.plot(
            summary_df["Target Force (N)"],
            summary_df[metric_col] * scale,
            marker="o",
            color=colour
        )

        plt.xlabel("Target Force (N)")
        plt.ylabel(ylabel)
        plt.title(ylabel + " vs Force")

        plt.grid(True, linestyle="--", alpha=0.4)
        plt.tight_layout()

        plt.savefig(
            os.path.join(folder_path, filename),
            dpi=300
        )

        plt.close()

    plot_metric(
        "Mean Rectified Peak",
        f"Mean rectified peak ({signal_unit})",
        f"{output_name}_peak_vs_force.png",
        peak_colour,
        scale=y_scale
    )

    plot_metric(
        "Mean RMS",
        f"Mean RMS ({signal_unit})",
        f"{output_name}_rms_vs_force.png",
        rms_colour,
        scale=y_scale
    )

    plot_metric(
        "STD Rectified Peak",
        f"STD rectified peak ({signal_unit})",
        f"{output_name}_peak_std_vs_force.png",
        peak_colour,
        scale=y_scale
    )

    plot_metric(
        "CV Rectified Peak (%)",
        "CV rectified peak (%)",
        f"{output_name}_peak_cv_vs_force.png",
        peak_colour,
        scale=1
    )

    print(f"Saved force-characterisation analysis:\n{output_excel}")

    return output_excel


def analyse_voc_force_folder(folder_path):

    return analyse_force_characterisation_folder(
        folder_path,
        signal_col="voltage",
        output_name="VOC_FORCE"
    )


def analyse_isc_force_folder(folder_path):
    return analyse_force_characterisation_folder(
        folder_path=folder_path,
        signal_col="current",
        output_name="ISC_FORCE",
        baseline_method="median"
    )


def analyse_matched_voltage_force_folder(folder_path):
    return analyse_force_characterisation_folder(
        folder_path=folder_path,
        signal_col="voltage",
        output_name="MATCHED_VOLTAGE_FORCE",
        baseline_method="median"
    )


def analyse_matched_current_force_folder(folder_path):
    return analyse_force_characterisation_folder(
        folder_path=folder_path,
        signal_col="current",
        output_name="MATCHED_CURRENT_FORCE",
        baseline_method="median"
    )


# def analyse_voltage_force_characterisation(material_folder):
#     """
#     Voltage-only material-level force characterisation.

#     Expected structure:
#         material_folder/
#             Force_Characterisation/
#                 VOC/
#                 Matched_Voltage/
#     """

#     force_folder = os.path.join(
#         material_folder,
#         "Force_Characterisation"
#     )

#     voc_folder = os.path.join(
#         force_folder,
#         "VOC"
#     )

#     matched_folder = os.path.join(
#         force_folder,
#         "Matched_Voltage"
#     )

#     if not os.path.isdir(force_folder):
#         raise ValueError(f"Force_Characterisation folder not found:\n{force_folder}")

#     output_files = []

#     if os.path.isdir(voc_folder):
#         output_files.append(
#             analyse_voc_force_folder(voc_folder)
#         )
#     else:
#         print(f"VOC folder not found:\n{voc_folder}")

#     if os.path.isdir(matched_folder):
#         output_files.append(
#             analyse_matched_voltage_force_folder(matched_folder)
#         )
#     else:
#         print(f"Matched_Voltage folder not found:\n{matched_folder}")

#     if len(output_files) == 0:
#         raise ValueError("No VOC or Matched_Voltage folders found.")

#     # =====================================================
#     # COMBINE SUMMARIES
#     # =====================================================

#     combined_rows = []

#     for output_file in output_files:

#         df = pd.read_excel(
#             output_file,
#             sheet_name="SUMMARY"
#         )

#         if "VOC_FORCE" in os.path.basename(output_file):
#             df["Test"] = "VOC"

#         elif "MATCHED_VOLTAGE_FORCE" in os.path.basename(output_file):
#             df["Test"] = "Matched Voltage"

#         else:
#             df["Test"] = "Unknown"

#         combined_rows.append(df)

#     combined_df = pd.concat(
#         combined_rows,
#         ignore_index=True
#     )

#     combined_df = combined_df.sort_values(
#         ["Test", "Target Force (N)"]
#     )

#     output_excel = os.path.join(
#         force_folder,
#         "VOLTAGE_ONLY_FORCE_CHARACTERISATION_SUMMARY.xlsx"
#     )

#     with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

#         combined_df.to_excel(
#             writer,
#             sheet_name="SUMMARY",
#             index=False
#         )

#     def plot_combined_metric(metric_col, ylabel, filename, colour_key):

#         plt.figure(figsize=(8, 6))

#         for test_name in combined_df["Test"].unique():

#             subset = combined_df[
#                 combined_df["Test"] == test_name
#             ].sort_values("Target Force (N)")

#             plt.plot(
#                 subset["Target Force (N)"],
#                 subset[metric_col],
#                 marker="o",
#                 label=test_name
#             )

#         plt.xlabel("Target Force (N)")
#         plt.ylabel(ylabel)
#         plt.title(ylabel + " vs Force")
#         plt.grid(True, linestyle="--", alpha=0.4)
#         plt.legend()
#         plt.tight_layout()

#         plt.savefig(
#             os.path.join(force_folder, filename),
#             dpi=300
#         )

#         plt.close()

#     plot_combined_metric(
#         "Mean Rectified Peak",
#         "Mean rectified peak voltage (V)",
#         "Voltage_only_peak_vs_force.png",
#         "voltage"
#     )

#     plot_combined_metric(
#         "Mean RMS",
#         "Mean RMS voltage (V)",
#         "Voltage_only_rms_vs_force.png",
#         "voltage_rms"
#     )

#     plot_combined_metric(
#         "STD Rectified Peak",
#         "STD rectified peak voltage (V)",
#         "Voltage_only_peak_std_vs_force.png",
#         "voltage"
#     )

#     plot_combined_metric(
#         "CV Rectified Peak (%)",
#         "CV rectified peak voltage (%)",
#         "Voltage_only_peak_cv_vs_force.png",
#         "voltage"
#     )

#     print(f"Saved voltage-only material force summary:\n{output_excel}")

#     return output_excel


'''
Formatting plots for consistancy
'''

PLOT_COLOURS = {
    "force": "#FFC618",
    "voltage": "#8EBCF8",  
    "voltage_rms": "#526CA1",
    "current": "#FF4F61",
    "current_rms": "#F17C64",
    "power": "#87CB52",
    "rms_power": "#479079",
    "target": "red",
    "steady": "tab:cyan",
    "error": "tab:pink"
}

DEFAULT_COLOURS = [
    "#FF4F61",
    "#FFC618",
    "#87CB52",
    "#7CC6CF",
    "#008080",
    "#526CA1",
]

def get_default_colour(index):
    """
    Returns a colour from the default colour cycle.
    Loops around if there are more plotted lines than colours.
    """
    return DEFAULT_COLOURS[
        index % len(DEFAULT_COLOURS)
    ]

DEFAULT_COLOURS_WITH_BASELINE = [
    "#797979",
    "#FF4F61",
    "#FFC618",
    "#87CB52",
    "#7CC6CF",
    "#008080",
    "#526CA1",
]

def get_compare_colour(index):
    """
    Returns a colour from the comparison colour cycle.
    Loops around if there are more plotted lines than colours.
    """
    return DEFAULT_COLOURS_WITH_BASELINE[
        index % len(DEFAULT_COLOURS_WITH_BASELINE)
    ]

PLOT_COLOUR_CYCLE = [
    "#797979",
    "#FF4F61",
    "#F17C64",
    "#FFC618",
    "#CFAE4A",
    "#87CB52",
    "#479079",
    "#7CC6CF",
    "#008080",
    "#8EBCF8",
    "#526CA1"
]


def get_plot_colour(index):
    """
    Returns a colour from the custom colour cycle.
    Loops around if there are more plotted lines than colours.
    """
    return PLOT_COLOUR_CYCLE[
        index % len(PLOT_COLOUR_CYCLE)
    ]


cmap_colors = [
    "#87CB52",
    "#FFC618",
    "#F17C64",
    "#FF4F61",
]

custom_cmap = LinearSegmentedColormap.from_list(
    "custom_cmap",
    cmap_colors,
)

def set_plot_formatting(
    ax,
    title=None,
    xlabel=None,
    ylabel=None,
    grid=True,
    legend=True,
    xscale=None,
    yscale=None
):
    """
    Applies consistent formatting to a matplotlib axis.
    """

    if title is not None:
        ax.set_title(title)

    if xlabel is not None:
        ax.set_xlabel(xlabel)

    if ylabel is not None:
        ax.set_ylabel(ylabel)

    if xscale is not None:
        ax.set_xscale(xscale)

    if yscale is not None:
        ax.set_yscale(yscale)

    if grid:
        ax.grid(
            True,
            which="both",
            linestyle="--",
            alpha=0.35
        )

    if legend:
        ax.legend(loc="best")

    return ax