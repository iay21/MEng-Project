import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

FORCE_THRESHOLD = 0.5
MIN_CYCLE_POINTS = 5


'''
RIG VALIDATION FUNCTIONS:
'''

def analyse_calibration_folder(folder_path):

    # =====================================================
    # STORAGE
    # =====================================================

    all_cycle_data = []

    test_summary_data = []

    # =====================================================
    # FIND FILES
    # =====================================================

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if (
            f.endswith(".csv")
            and "_analysis" not in f
            and "_analysed" not in f
        )
    ])

    if len(csv_files) == 0:
        raise ValueError(
            "No CSV files found."
        )

    # =====================================================
    # PROCESS EACH FILE
    # =====================================================

    for file_index, file in enumerate(csv_files):

        full_path = os.path.join(
            folder_path,
            file
        )

        # =================================================
        # READ TARGET FORCE
        # =================================================

        target_force = read_target_force(full_path)

        # =================================================
        # FIND DATA START
        # =================================================

        data_start = 0

        with open(full_path, "r") as f:

            for i, line in enumerate(f):

                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                if "time" in line.lower():
                    continue

                data_start = i
                break

        # =================================================
        # LOAD DATA
        # =================================================

        df = pd.read_csv(
            full_path,
            sep=r"[\s,\t]+",
            engine="python",
            skiprows=data_start,
            header=None
        )

        df = df.iloc[:, :2]

        df.columns = [
            "time",
            "force"
        ]

        df["force"] = pd.to_numeric(
            df["force"],
            errors="coerce"
        )

        df["time"] = pd.to_numeric(
            df["time"],
            errors="coerce"
        )

        df = df.dropna()

        if len(df) == 0:
            continue

        # =================================================
        # CONTACT DETECTION
        # =================================================

        df["contact"] = (
            df["force"] > FORCE_THRESHOLD
        )

        df["contact_shift"] = (
            df["contact"].shift(1)
        )

        cycle_starts = df[
            (df["contact"] == True)
            &
            (df["contact_shift"] == False)
        ].index.tolist()

        cycle_ends = df[
            (df["contact"] == False)
            &
            (df["contact_shift"] == True)
        ].index.tolist()

        if (
            len(cycle_starts) == 0
            or
            len(cycle_ends) == 0
        ):
            continue

        if cycle_ends[0] < cycle_starts[0]:
            cycle_ends.pop(0)

        min_len = min(
            len(cycle_starts),
            len(cycle_ends)
        )

        cycle_starts = cycle_starts[:min_len]
        cycle_ends = cycle_ends[:min_len]

        # =================================================
        # PEAK FORCE PER CYCLE
        # =================================================

        peak_forces = []

        for cycle_num, (start, end) in enumerate(
            zip(cycle_starts, cycle_ends),
            start=1
        ):

            cycle = df.loc[start:end]

            if len(cycle) < MIN_CYCLE_POINTS:
                continue

            peak_force = cycle[
                "force"
            ].max()

            peak_forces.append(
                peak_force
            )

            absolute_error = (
                peak_force - target_force
            )

            percent_error = (
                absolute_error / target_force
            ) * 100

            all_cycle_data.append({

                "File": file,

                "Target Force (N)": target_force,

                "Cycle": cycle_num,

                "Peak Force (N)": peak_force,

                "Absolute Error (N)": absolute_error,

                "Percent Error (%)": percent_error
            })

        # =================================================
        # SKIP IF NO VALID CYCLES
        # =================================================

        if len(peak_forces) == 0:
            continue

        peak_forces = np.array(
            peak_forces
        )

        # =================================================
        # METRICS
        # =================================================

        mean_peak = np.mean(
            peak_forces
        )

        std_peak = np.std(
            peak_forces,
            ddof=1
        )

        cv_peak = (
            std_peak / mean_peak
        ) * 100

        force_range = (
            np.max(peak_forces)
            -
            np.min(peak_forces)
        )

        abs_error = (
            mean_peak - target_force
        )

        pct_error = (
            abs_error / target_force
        ) * 100

        rms_error = np.sqrt(
            np.mean(
                (peak_forces - target_force) ** 2
            )
        )

        # =================================================
        # SAVE SUMMARY
        # =================================================

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

        # =================================================
        # DRIFT PLOT
        # =================================================

        plt.figure(figsize=(7,5))

        plt.plot(
            range(1, len(peak_forces)+1),
            peak_forces,
            marker="o"
        )

        plt.axhline(
            target_force,
            linestyle="--"
        )

        plt.xlabel("Cycle Number")

        plt.ylabel("Peak Force (N)")

        plt.title(
            f"{int(target_force)}N Calibration Drift"
        )

        plt.tight_layout()

        plt.savefig(
            os.path.join(
                folder_path,
                f"{int(target_force)}N_Drift.png"
            ),
            dpi=300
        )

        plt.close()

        # =================================================
        # INDIVIDUAL BOXPLOT
        # =================================================

        plt.figure(figsize=(4,6))

        plt.boxplot(
            peak_forces
        )

        plt.axhline(
            target_force,
            linestyle="--"
        )

        plt.ylabel("Peak Force (N)")

        plt.title(
            f"{int(target_force)}N Repeatability"
        )

        plt.tight_layout()

        plt.savefig(
            os.path.join(
                folder_path,
                f"{int(target_force)}N_Boxplot.png"
            ),
            dpi=300
        )

        plt.close()

    # =====================================================
    # CREATE DATAFRAMES
    # =====================================================

    all_cycles_df = pd.DataFrame(
        all_cycle_data
    )

    test_summary_df = pd.DataFrame(
        test_summary_data
    )

    if len(test_summary_df) == 0:
        raise ValueError(
            "No valid calibration data."
        )

    # =====================================================
    # FORCE SUMMARY
    # =====================================================

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

    force_summary_df = force_summary_df.sort_values(
        "Target Force (N)"
    )

    # =====================================================
    # SAVE EXCEL
    # =====================================================

    output_excel = os.path.join(
        folder_path,
        "CALIBRATION_ANALYSIS.xlsx"
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

    # =====================================================
    # MEASURED VS TARGET
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        force_summary_df[
            "Target Force (N)"
        ],
        force_summary_df[
            "Mean Peak Force (N)"
        ],
        marker="o",
        label="Measured"
    )

    plt.plot(
        force_summary_df[
            "Target Force (N)"
        ],
        force_summary_df[
            "Target Force (N)"
        ],
        linestyle="--",
        label="Ideal"
    )

    plt.xlabel("Target Force (N)")

    plt.ylabel("Measured Force (N)")

    plt.title("Measured vs Target Force")

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "Measured_vs_Target.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # PERCENT ERROR
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        force_summary_df[
            "Target Force (N)"
        ],
        force_summary_df[
            "Percent Error (%)"
        ],
        marker="o"
    )

    plt.xlabel("Target Force (N)")

    plt.ylabel("Percent Error (%)")

    plt.title("Calibration Percent Error")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "Percent_Error.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # STD VS FORCE
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        force_summary_df[
            "Target Force (N)"
        ],
        force_summary_df[
            "STD Peak Force (N)"
        ],
        marker="o"
    )

    plt.xlabel("Target Force (N)")

    plt.ylabel("STD (N)")

    plt.title("Calibration Repeatability")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "STD_vs_Force.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # CV VS FORCE
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        force_summary_df[
            "Target Force (N)"
        ],
        force_summary_df[
            "CV (%)"
        ],
        marker="o"
    )

    plt.xlabel("Target Force (N)")

    plt.ylabel("CV (%)")

    plt.title("Coefficient of Variation")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "CV_vs_Force.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # RMS ERROR
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        force_summary_df[
            "Target Force (N)"
        ],
        force_summary_df[
            "RMS Error (N)"
        ],
        marker="o"
    )

    plt.xlabel("Target Force (N)")

    plt.ylabel("RMS Error (N)")

    plt.title("Calibration RMS Error")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "RMS_vs_Force.png"
        ),
        dpi=300
    )

    plt.close()

    print(
        f"\nSaved calibration analysis:\n"
        f"{output_excel}"
    )

    return output_excel

def analyse_force_cycles(file, target_force=None):


    # =====================================================
    # READ TARGET FORCE FROM METADATA
    # =====================================================

    if target_force is None:

        with open(file, "r") as f:

            for line in f:

                if "# Target Force (N)" in line:

                    parts = line.strip().split(",")

                    if len(parts) >= 2:

                        try:
                            target_force = float(parts[1])

                        except:
                            pass

                # stop once data header is reached
                if line.startswith("time_s"):
                    break

    # =====================================================
    # LOAD DATA
    # =====================================================

    # find where numeric data begins
    data_start = 0

    with open(file, "r") as f:

        for i, line in enumerate(f):

            line = line.strip()

            # skip blank lines
            if not line:
                continue

            # skip metadata
            if line.startswith("#"):
                continue

            # skip column headers
            if "time" in line.lower():
                continue

            # first numeric line found
            data_start = i
            break

    # load numeric data
    df = pd.read_csv(
        file,
        sep=r"[\s,\t]+",
        engine="python",
        skiprows=data_start,
        header=None
    )

    # keep only first 2 columns
    df = df.iloc[:, :2]

    df.columns = ["time", "force"]

    # convert to numeric
    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df["force"] = pd.to_numeric(df["force"], errors="coerce")

    # remove invalid rows
    df = df.dropna()

    # =====================================================
    # CHECK TARGET FORCE
    # =====================================================

    if target_force is None:

        raise ValueError(
            "No target force found in metadata.\n"
            "Please enter a target force manually."
        )
    
    # =====================================================
    # FIND CONTACT REGIONS
    # =====================================================

    df["contact"] = df["force"] > FORCE_THRESHOLD

    df["contact_shift"] = df["contact"].shift(1)

    # start of contact
    cycle_starts = df[
        (df["contact"] == True) &
        (df["contact_shift"] == False)
    ].index.tolist()

    # end of contact
    cycle_ends = df[
        (df["contact"] == False) &
        (df["contact_shift"] == True)
    ].index.tolist()

    # align starts/ends safely
    if len(cycle_ends) > 0 and len(cycle_starts) > 0:

        if cycle_ends[0] < cycle_starts[0]:
            cycle_ends.pop(0)

        min_len = min(len(cycle_starts), len(cycle_ends))

        cycle_starts = cycle_starts[:min_len]
        cycle_ends = cycle_ends[:min_len]

    results = []

    # =====================================================
    # ANALYSE EACH CONTACT EVENT
    # =====================================================

    for i, (start, end) in enumerate(zip(cycle_starts, cycle_ends)):

        cycle = df.loc[start:end]

        if len(cycle) < MIN_CYCLE_POINTS:
            continue

        # -------------------------------------------------
        # BASIC FORCE METRICS
        # -------------------------------------------------

        max_force = cycle["force"].max()

        min_force = cycle["force"].min()

        # -------------------------------------------------
        # STEADY-STATE REGION
        # Use points above 80% of max force
        # -------------------------------------------------

        steady_region = cycle[
            cycle["force"] > (0.8 * max_force)
        ]

        # fallback if too few points
        if len(steady_region) < 3:
            steady_region = cycle

        steady_force = steady_region["force"].mean()

        steady_force_std = steady_region["force"].std()

        # -------------------------------------------------
        # RMS ERROR (steady-state only)
        # -------------------------------------------------

        steady_error = (
            steady_region["force"] - target_force
        )

        rms_error = np.sqrt(
            np.mean(steady_error ** 2)
        )

        # -------------------------------------------------
        # TIMING METRICS
        # -------------------------------------------------

        contact_duration = (
            cycle["time"].iloc[-1]
            - cycle["time"].iloc[0]
        )

        # cycle frequency from start-to-start
        if i < len(cycle_starts) - 1:

            next_start_time = df.loc[
                cycle_starts[i + 1],
                "time"
            ]

            current_start_time = df.loc[
                start,
                "time"
            ]

            full_cycle_time = (
                next_start_time - current_start_time
            )

            frequency_hz = (
                1 / full_cycle_time
                if full_cycle_time > 0
                else np.nan
            )

        else:
            full_cycle_time = np.nan
            frequency_hz = np.nan

        # -------------------------------------------------
        # SAVE RESULTS
        # -------------------------------------------------

        results.append({

            "cycle": i + 1,

            "target_force_N": target_force,

            "max_force_N": max_force,

            "min_force_N": min_force,

            "steady_force_N": steady_force,

            "steady_force_std_N": steady_force_std,

            "rms_error_N": rms_error,

            "contact_duration_s": contact_duration,

            "full_cycle_time_s": full_cycle_time,

            "frequency_hz": frequency_hz
        })

    # =====================================================
    # CREATE OUTPUT TABLE
    # =====================================================

    results_df = pd.DataFrame(results)


    return results_df

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

        for freq in frequency_folders:

            if freq in metric_df.columns:

                plt.plot(
                    forces,
                    metric_df[freq],
                    marker="o",
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
    # HEATMAP: FORCE, FREQUENCY, RMS FORCE ERROR
    # =====================================================

    heatmap_df = force_rms_df.set_index("RMS")
    heatmap_df = heatmap_df[frequency_folders]

    plt.figure(figsize=(8, 6))

    plt.imshow(
        heatmap_df.values,
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

        df = load_force_data(file_path)

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

            # contact_len = len(cycle)

            # steady_start_i = int(steady_start_fraction * contact_len)
            # steady_end_i = int(steady_end_fraction * contact_len)

            # if steady_end_i <= steady_start_i:
            #     continue

            # steady_region = cycle.iloc[steady_start_i:steady_end_i]

            # if len(steady_region) < 3:
            #     continue

            # steady_start_time = steady_region["time"].iloc[0]
            # steady_end_time = steady_region["time"].iloc[-1]

            steady_force = steady_region["force"].mean()
            steady_std = steady_region["force"].std()

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
                "In-Cycle Peak-to-Peak (N)": steady_pp
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

            "Drift Slope (N/cycle)": drift_slope
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
            label="Used cycles"
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

        "Drift Slope (N/cycle)": "mean"

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
            marker="o"
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
        label="Measured"
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

    print(f"Saved steady force-control analysis:\n{output_excel}")

    return output_excel

def compare_force_control_methods(
    master_folder,
    reject_outliers=True,
    mad_threshold=4.0
):

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

    combined_df = pd.concat(
        all_summaries,
        ignore_index=True
    )

    output_excel = os.path.join(
        master_folder,
        "STEADY_FORCE_CONTROL_METHOD_COMPARISON.xlsx"
    )

    with pd.ExcelWriter(
        output_excel,
        engine="openpyxl"
    ) as writer:

        combined_df.to_excel(
            writer,
            sheet_name="ALL_METHODS",
            index=False
        )

    def plot_comparison(y_col, ylabel, title, filename, zero_line=False):

        plt.figure(figsize=(8, 6))

        for method in sorted(combined_df["Method"].unique()):

            subset = combined_df[
                combined_df["Method"] == method
            ].sort_values("Target Force (N)")

            plt.plot(
                subset["Target Force (N)"],
                subset[y_col],
                marker="o",
                label=method
            )

        if zero_line:
            plt.axhline(0, linestyle="--")

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

    plot_comparison(
        "Steady Percent Error (%)",
        "Steady Force Error (%)",
        "Steady-force accuracy comparison",
        "comparison_steady_percent_error.png",
        zero_line=True
    )

    plot_comparison(
        "Steady Repeatability STD (N)",
        "STD of Steady Force Across Cycles (N)",
        "Steady-force repeatability STD comparison",
        "comparison_steady_repeatability_std.png"
    )

    plot_comparison(
        "Steady Repeatability CV (%)",
        "CV of Steady Force Across Cycles (%)",
        "Steady-force repeatability CV comparison",
        "comparison_steady_repeatability_cv.png"
    )

    plot_comparison(
        "Mean In-Cycle STD (N)",
        "Mean In-Cycle STD (N)",
        "In-cycle stability comparison",
        "comparison_in_cycle_std.png"
    )

    plot_comparison(
        "Mean In-Cycle RMS Error (N)",
        "Mean In-Cycle RMS Error (N)",
        "In-cycle RMS error comparison",
        "comparison_in_cycle_rms.png"
    )

    plot_comparison(
        "Mean In-Cycle Peak-to-Peak (N)",
        "Mean In-Cycle Peak-to-Peak (N)",
        "In-cycle peak-to-peak comparison",
        "comparison_in_cycle_peak_to_peak.png"
    )

    print(f"Saved steady force-control method comparison:\n{output_excel}")

    return output_excel


def analyse_voltage_cycle_convergence(
    folder_path,
    threshold_percent=5
):


    all_cycle_results = []
    summary_results = []

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if f.endswith(".csv")
        and "_analysis" not in f
        and "_analysed" not in f
    ])

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")


    def load_data(file_path):

        data_start = 0

        with open(file_path, "r") as f:

            for i, line in enumerate(f):

                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                if "time" in line.lower():
                    continue

                data_start = i
                break

        df = pd.read_csv(
            file_path,
            sep=r"[\s,\t]+",
            engine="python",
            skiprows=data_start,
            header=None
        )

        df = df.iloc[:, :3]
        df.columns = ["time", "force", "voltage"]

        df["time"] = pd.to_numeric(df["time"], errors="coerce")
        df["force"] = pd.to_numeric(df["force"], errors="coerce")
        df["voltage"] = pd.to_numeric(df["voltage"], errors="coerce")

        df = df.dropna()

        # remove isolated first-row time glitch
        if len(df) > 1 and df["time"].iloc[0] > df["time"].iloc[1]:
            df = df.iloc[1:]

        df = df.reset_index(drop=True)

        return df

    for file in csv_files:

        file_path = os.path.join(folder_path, file)

        target_force = read_target_force(file_path)

        if target_force is None:
            print(f"Skipping {file}: no target force found.")
            continue

        df = load_data(file_path)

        if len(df) == 0:
            continue

        df["contact"] = df["force"] > FORCE_THRESHOLD
        df["contact_shift"] = df["contact"].shift(1).fillna(False)

        cycle_starts = df[
            (df["contact"] == True)
            &
            (df["contact_shift"] == False)
        ].index.tolist()

        cycle_ends = df[
            (df["contact"] == False)
            &
            (df["contact_shift"] == True)
        ].index.tolist()

        if len(cycle_starts) == 0 or len(cycle_ends) == 0:
            continue

        if cycle_ends[0] < cycle_starts[0]:
            cycle_ends.pop(0)

        min_len = min(len(cycle_starts), len(cycle_ends))

        cycle_starts = cycle_starts[:min_len]
        cycle_ends = cycle_ends[:min_len]

        rectified_peak_values = []
        cycle_rms_values = []

        for cycle_num, (start, end) in enumerate(
            zip(cycle_starts, cycle_ends),
            start=1
        ):

            cycle = df.loc[start:end]

            if len(cycle) < MIN_CYCLE_POINTS:
                continue

            v_max = cycle["voltage"].max()
            v_min = cycle["voltage"].min()

            positive_peak = abs(v_max)
            negative_peak_rectified = abs(v_min)

            rectified_voltage = abs(cycle["voltage"])

            cycle_rms = np.sqrt(
                np.mean(rectified_voltage ** 2)
            )

            rectified_peak_values.extend([
                positive_peak,
                negative_peak_rectified
            ])

            cycle_rms_values.append(cycle_rms)

            all_cycle_results.append({

                "File": file,
                "Target Force (N)": target_force,
                "Cycle": cycle_num,

                "Positive Peak (V)": positive_peak,
                "Rectified Negative Peak (V)": negative_peak_rectified,
                "Mean Rectified Peak This Cycle (V)": np.mean([
                    positive_peak,
                    negative_peak_rectified
                ]),

                "RMS Rectified Voltage This Cycle (V)": cycle_rms
            })

        if len(rectified_peak_values) == 0 or len(cycle_rms_values) == 0:
            continue

        rectified_peak_values = np.array(rectified_peak_values)
        cycle_rms_values = np.array(cycle_rms_values)

        final_peak_mean = np.mean(rectified_peak_values)
        final_rms_mean = np.mean(cycle_rms_values)

        running_peak_mean = []
        running_rms_mean = []

        peak_percent_difference = []
        rms_percent_difference = []

        peak_ci_95 = []
        rms_ci_95 = []

        total_cycles = len(cycle_rms_values)

        for n in range(1, total_cycles + 1):

            peak_subset = rectified_peak_values[:2 * n]
            rms_subset = cycle_rms_values[:n]

            peak_mean_n = np.mean(peak_subset)
            rms_mean_n = np.mean(rms_subset)

            running_peak_mean.append(peak_mean_n)
            running_rms_mean.append(rms_mean_n)

            if final_peak_mean != 0:
                peak_pct_diff = (
                    (peak_mean_n - final_peak_mean)
                    / final_peak_mean
                ) * 100
            else:
                peak_pct_diff = np.nan

            if final_rms_mean != 0:
                rms_pct_diff = (
                    (rms_mean_n - final_rms_mean)
                    / final_rms_mean
                ) * 100
            else:
                rms_pct_diff = np.nan

            peak_percent_difference.append(peak_pct_diff)
            rms_percent_difference.append(rms_pct_diff)

            if n > 1:
                peak_ci = (
                    1.96
                    * np.std(peak_subset, ddof=1)
                    / np.sqrt(len(peak_subset))
                )

                rms_ci = (
                    1.96
                    * np.std(rms_subset, ddof=1)
                    / np.sqrt(len(rms_subset))
                )

            else:
                peak_ci = np.nan
                rms_ci = np.nan

            peak_ci_95.append(peak_ci)
            rms_ci_95.append(rms_ci)

        running_peak_mean = np.array(running_peak_mean)
        running_rms_mean = np.array(running_rms_mean)

        peak_percent_difference = np.array(peak_percent_difference)
        rms_percent_difference = np.array(rms_percent_difference)

        peak_ci_95 = np.array(peak_ci_95)
        rms_ci_95 = np.array(rms_ci_95)

        peak_stable_cycle = np.nan
        rms_stable_cycle = np.nan
        both_stable_cycle = np.nan

        for i in range(total_cycles):

            if np.all(
                np.abs(peak_percent_difference[i:]) <= threshold_percent
            ):
                peak_stable_cycle = i + 1
                break

        for i in range(total_cycles):

            if np.all(
                np.abs(rms_percent_difference[i:]) <= threshold_percent
            ):
                rms_stable_cycle = i + 1
                break

        for i in range(total_cycles):

            if (
                np.all(
                    np.abs(peak_percent_difference[i:])
                    <= threshold_percent
                )
                and
                np.all(
                    np.abs(rms_percent_difference[i:])
                    <= threshold_percent
                )
            ):
                both_stable_cycle = i + 1
                break

        summary_results.append({

            "File": file,
            "Target Force (N)": target_force,
            "Total Mechanical Cycles": total_cycles,
            "Total Voltage Peaks Used": len(rectified_peak_values),

            "Final Mean Rectified Peak (V)": final_peak_mean,
            "Final Rectified Peak STD (V)": np.std(
                rectified_peak_values,
                ddof=1
            ),
            "Final Rectified Peak CV (%)": (
                np.std(rectified_peak_values, ddof=1)
                / final_peak_mean
            ) * 100 if final_peak_mean != 0 else np.nan,

            "Final Mean RMS Rectified Voltage (V)": final_rms_mean,
            "Final RMS STD (V)": np.std(
                cycle_rms_values,
                ddof=1
            ),
            "Final RMS CV (%)": (
                np.std(cycle_rms_values, ddof=1)
                / final_rms_mean
            ) * 100 if final_rms_mean != 0 else np.nan,

            "Threshold (%)": threshold_percent,
            "Cycles Needed - Rectified Peak": peak_stable_cycle,
            "Cycles Needed - RMS": rms_stable_cycle,
            "Cycles Needed - Both": both_stable_cycle
        })

        force_label = int(round(target_force))

        # =================================================
        # PLOT 1: RUNNING MEAN PEAK + RUNNING RMS
        # =================================================

        plt.figure(figsize=(8, 5))

        plt.plot(
            range(1, total_cycles + 1),
            running_peak_mean,
            marker="o",
            label="Mean rectified peak"
        )

        plt.plot(
            range(1, total_cycles + 1),
            running_rms_mean,
            marker="o",
            label="Mean RMS rectified signal"
        )

        plt.axhline(
            final_peak_mean,
            linestyle="--",
            label="Final rectified peak mean"
        )

        plt.axhline(
            final_rms_mean,
            linestyle=":",
            label="Final RMS mean"
        )

        if not np.isnan(both_stable_cycle):

            plt.axvline(
                both_stable_cycle,
                linestyle="-.",
                label=f"Both stable: {both_stable_cycle} cycles"
            )

        plt.xlabel("Number of Mechanical Cycles Included")
        plt.ylabel("Voltage (V)")
        plt.title(f"{force_label}N: voltage convergence")
        plt.legend()

        plt.tight_layout()

        plt.savefig(
            os.path.join(
                folder_path,
                f"{force_label}N_voltage_convergence.png"
            ),
            dpi=300
        )

        plt.close()

        # =================================================
        # PLOT 2: % DIFFERENCE FROM FINAL VALUE
        # =================================================

        plt.figure(figsize=(8, 5))

        plt.plot(
            range(1, total_cycles + 1),
            peak_percent_difference,
            marker="o",
            label="Rectified peak mean"
        )

        plt.plot(
            range(1, total_cycles + 1),
            rms_percent_difference,
            marker="o",
            label="RMS rectified signal"
        )

        plt.axhline(
            threshold_percent,
            linestyle="--"
        )

        plt.axhline(
            -threshold_percent,
            linestyle="--"
        )

        plt.axhline(
            0,
            linestyle=":"
        )

        if not np.isnan(both_stable_cycle):

            plt.axvline(
                both_stable_cycle,
                linestyle="-.",
                label=f"Both stable: {both_stable_cycle} cycles"
            )

        plt.xlabel("Number of Mechanical Cycles Included")
        plt.ylabel("% Difference from Final Value")
        plt.title(
            f"{force_label}N: convergence within ±{threshold_percent}%"
        )
        plt.legend()

        plt.tight_layout()

        plt.savefig(
            os.path.join(
                folder_path,
                f"{force_label}N_voltage_percent_difference.png"
            ),
            dpi=300
        )

        plt.close()

        # =================================================
        # PLOT 3: 95% CONFIDENCE INTERVALS
        # =================================================

        plt.figure(figsize=(8, 5))

        plt.plot(
            range(1, total_cycles + 1),
            peak_ci_95,
            marker="o",
            label="Rectified peak mean 95% CI"
        )

        plt.plot(
            range(1, total_cycles + 1),
            rms_ci_95,
            marker="o",
            label="RMS rectified signal 95% CI"
        )

        if not np.isnan(both_stable_cycle):

            plt.axvline(
                both_stable_cycle,
                linestyle="-.",
                label=f"Both stable: {both_stable_cycle} cycles"
            )

        plt.xlabel("Number of Mechanical Cycles Included")
        plt.ylabel("95% CI (V)")
        plt.title(f"{force_label}N: confidence interval vs cycle count")
        plt.legend()

        plt.tight_layout()

        plt.savefig(
            os.path.join(
                folder_path,
                f"{force_label}N_voltage_confidence_interval.png"
            ),
            dpi=300
        )

        plt.close()

    all_cycles_df = pd.DataFrame(all_cycle_results)
    summary_df = pd.DataFrame(summary_results)

    if len(summary_df) == 0:
        raise ValueError("No valid voltage convergence data found.")

    summary_df = summary_df.sort_values("Target Force (N)")

    output_excel = os.path.join(
        folder_path,
        "VOLTAGE_CYCLE_CONVERGENCE_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        all_cycles_df.to_excel(
            writer,
            sheet_name="ALL_CYCLES",
            index=False
        )

        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

    print(f"Saved voltage convergence analysis:\n{output_excel}")

    return output_excel

'''
TRIBO OUTPUT FUNCTIONS
'''

def plot_force_voltage_vs_time(file_path):

    
    # =========================
    # LOAD DATA
    # =========================

    df = pd.read_csv(
        file_path,
        comment="#"
    )

    df = df.iloc[:, :3]

    df.columns = [
        "time",
        "force",
        "voltage"
    ]

    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df["force"] = pd.to_numeric(df["force"], errors="coerce")
    df["voltage"] = pd.to_numeric(df["voltage"], errors="coerce")

    df = df.dropna()

    if len(df) == 0:
        raise ValueError("No valid data found.")

    # =========================
    # REMOVE OUT-OF-ORDER TIME POINTS
    # =========================
    # This removes glitches such as:
    # 80s followed by 0.1s

    bad_rows = df.index[
        df["time"].shift(-1) < df["time"]
    ]

    df = df.drop(bad_rows)

    df = df.reset_index(drop=True)

    # =========================
    # TRIM TO ACTIVE TEST REGION
    # =========================

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

    # =========================
    # PLOT
    # =========================

    fig, ax1 = plt.subplots(figsize=(25, 10))

    ax1.plot(
        df["time"],
        df["force"],
        color="red",
        # linestyle="--",
        label="Force"
    )

    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Force (N)", color="red")
    ax1.tick_params(axis="y", labelcolor="red")

    ax2 = ax1.twinx()

    ax2.plot(
        df["time"],
        df["voltage"],
        color="blue",
        linestyle="dotted",
        label="Voltage"
    )

    ax2.set_ylabel("Voltage (V)", color="blue")
    ax2.tick_params(axis="y", labelcolor="blue")

    base_name = os.path.basename(file_path)
    name_no_ext = os.path.splitext(base_name)[0]

    plt.title(name_no_ext)

    output_file = os.path.join(
        os.path.dirname(file_path),
        f"{name_no_ext}_force_voltage_plot.png"
    )

    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close()

    print(f"Saved plot:\n{output_file}")

    return output_file



'''
Data processing functions
'''

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


def load_force_data(file_path):

        data_start = 0

        with open(file_path, "r") as f:
            for i, line in enumerate(f):

                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                if "time" in line.lower():
                    continue

                data_start = i
                break

        df = pd.read_csv(
            file_path,
            sep=r"[\s,\t]+",
            engine="python",
            skiprows=data_start,
            header=None
        )

        df = df.iloc[:, :2]
        df.columns = ["time", "force"]

        df["time"] = pd.to_numeric(df["time"], errors="coerce")
        df["force"] = pd.to_numeric(df["force"], errors="coerce")

        df = df.dropna()

        # remove isolated first-row time glitch
        if len(df) > 1 and df["time"].iloc[0] > df["time"].iloc[1]:
            df = df.iloc[1:]

        df = df.reset_index(drop=True)

        return df


def find_cycles(df, contact_start_threshold=0.5, contact_end_threshold=0.2):

        cycles = []
        in_contact = False
        start_index = None

        for idx, force in zip(df.index, df["force"]):

            if not in_contact and force >= contact_start_threshold:
                in_contact = True
                start_index = idx

            elif in_contact and force <= contact_end_threshold:
                in_contact = False
                end_index = idx

                if start_index is not None:
                    cycles.append((start_index, end_index))

                start_index = None

        return cycles


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


def find_steady_force_region(
    cycle_df,
    target_force,
    steady_force_tolerance=0.10,
    max_steady_dfdt=2.0,
    min_steady_points=3,
    fallback_ratio=0.8
):

    import numpy as np

    cycle = cycle_df.copy()

    cycle["dF_dt"] = (
        cycle["force"].diff()
        /
        cycle["time"].diff()
    )

    cycle["dF_dt"] = cycle["dF_dt"].replace(
        [np.inf, -np.inf],
        np.nan
    )

    lower_force_limit = target_force * (1 - steady_force_tolerance)
    upper_force_limit = target_force * (1 + steady_force_tolerance)

    steady_region = cycle[
        (cycle["force"] >= lower_force_limit)
        &
        (cycle["force"] <= upper_force_limit)
        &
        (cycle["dF_dt"].abs() <= max_steady_dfdt)
    ].copy()

    steady_method = "target_plus_dFdt"

    if len(steady_region) < min_steady_points:

        max_force = cycle["force"].max()

        steady_region = cycle[
            cycle["force"] > fallback_ratio * max_force
        ].copy()

        steady_method = "fallback_top_force_region"

    if len(steady_region) < min_steady_points:

        steady_region = cycle.copy()

        steady_method = "fallback_whole_cycle"

    steady_start_time = steady_region["time"].iloc[0]
    steady_end_time = steady_region["time"].iloc[-1]

    return steady_region, steady_method, steady_start_time, steady_end_time



# def find_steady_force_region(
#     cycle_df,
#     target_force,
#     steady_force_tolerance=0.10,
#     max_steady_dfdt=2.0,
#     min_steady_points=3,
#     fallback_ratio=0.8
# ):


#     cycle = cycle_df.copy()

#     # =====================================================
#     # CALCULATE RATE OF CHANGE OF FORCE
#     # =====================================================

#     cycle["dF_dt"] = (
#         cycle["force"].diff()
#         /
#         cycle["time"].diff()
#     )

#     cycle["dF_dt"] = cycle["dF_dt"].replace(
#         [np.inf, -np.inf],
#         np.nan
#     )

#     # =====================================================
#     # TARGET + dF/dt STEADY REGION
#     # =====================================================

#     lower_force_limit = target_force * (
#         1 - steady_force_tolerance
#     )

#     upper_force_limit = target_force * (
#         1 + steady_force_tolerance
#     )

#     steady_region = cycle[
#         (cycle["force"] >= lower_force_limit)
#         &
#         (cycle["force"] <= upper_force_limit)
#         &
#         (cycle["dF_dt"].abs() <= max_steady_dfdt)
#     ].copy()

#     steady_method = "target_plus_dFdt"

#     # =====================================================
#     # FALLBACK 1: TOP FORCE REGION
#     # =====================================================

#     if len(steady_region) < min_steady_points:

#         max_force = cycle["force"].max()

#         steady_region = cycle[
#             cycle["force"] > fallback_ratio * max_force
#         ].copy()

#         steady_method = "fallback_top_force_region"

#     # =====================================================
#     # FALLBACK 2: WHOLE CYCLE
#     # =====================================================

#     if len(steady_region) < min_steady_points:

#         steady_region = cycle.copy()

#         steady_method = "fallback_whole_cycle"

#     return steady_region, steady_method

'''
IN PROGRESS - NOT FINALIZED
'''


def force_only_analysis(folder_path):

    import os
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt

    # =====================================================
    # STORAGE
    # =====================================================

    summary_data = []

    # =====================================================
    # FIND CSV FILES
    # =====================================================

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if (
            f.endswith(".csv")
            and "_analysis" not in f
            and "_analysed" not in f
        )
    ])

    if len(csv_files) == 0:
        raise ValueError(
            "No CSV files found."
        )

    # =====================================================
    # PROCESS FILES
    # =====================================================

    for file in csv_files:

        full_path = os.path.join(
            folder_path,
            file
        )

        try:

            # =============================================
            # RUN FORCE ANALYSIS
            # =============================================

            results_df = analyse_force_cycles(
                full_path
            )

            if len(results_df) == 0:
                continue

            # =============================================
            # EXTRACT METRICS
            # =============================================

            target_force = int(round(
                results_df[
                    "target_force_N"
                ].iloc[0]
            ))

            mean_force = results_df[
                "steady_force_N"
            ].mean()

            abs_error = (
                mean_force - target_force
            )

            percent_error = (
                abs_error / target_force
            ) * 100

            mean_std = results_df[
                "steady_force_std_N"
            ].mean()

            mean_rms = results_df[
                "rms_error_N"
            ].mean()

            summary_data.append({

                "Target Force (N)": target_force,

                "Mean Force (N)": mean_force,

                "Absolute Error (N)": abs_error,

                "Percent Error (%)": percent_error,

                "STD (N)": mean_std,

                "RMS Error (N)": mean_rms
            })

        except Exception as e:

            print(f"Failed: {file}")
            print(e)

    # =====================================================
    # CREATE DATAFRAME
    # =====================================================

    results_df = pd.DataFrame(
        summary_data
    )

    if len(results_df) == 0:
        raise ValueError(
            "No valid data processed."
        )

    # =====================================================
    # GROUP REPEATS
    # =====================================================

    grouped_df = results_df.groupby(
        "Target Force (N)"
    ).agg({

        "Mean Force (N)": "mean",

        "Absolute Error (N)": "mean",

        "Percent Error (%)": "mean",

        "STD (N)": "mean",

        "RMS Error (N)": "mean"

    }).reset_index()

    grouped_df = grouped_df.sort_values(
        "Target Force (N)"
    )

    # =====================================================
    # SAVE EXCEL
    # =====================================================

    output_excel = os.path.join(
        folder_path,
        "FORCE_ONLY_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(
        output_excel,
        engine="openpyxl"
    ) as writer:

        results_df.to_excel(
            writer,
            sheet_name="ALL_RESULTS",
            index=False
        )

        grouped_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

    # =====================================================
    # PLOTS
    # =====================================================

    # -----------------------------------------------------
    # TARGET VS MEAN FORCE
    # -----------------------------------------------------

    plt.figure(figsize=(6,5))

    plt.plot(
        grouped_df["Target Force (N)"],
        grouped_df["Mean Force (N)"],
        marker="o"
    )

    plt.plot(
        grouped_df["Target Force (N)"],
        grouped_df["Target Force (N)"],
        linestyle="--"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("Measured Force (N)")
    plt.title("Target vs Measured Force")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "Target_vs_Measured_Force.png"
        ),
        dpi=300
    )

    plt.close()

    # -----------------------------------------------------
    # PERCENT ERROR
    # -----------------------------------------------------

    plt.figure(figsize=(6,5))

    plt.plot(
        grouped_df["Target Force (N)"],
        grouped_df["Percent Error (%)"],
        marker="o"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("Percent Error (%)")
    plt.title("Percent Error")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "Percent_Error.png"
        ),
        dpi=300
    )

    plt.close()

    # -----------------------------------------------------
    # STD
    # -----------------------------------------------------

    plt.figure(figsize=(6,5))

    plt.plot(
        grouped_df["Target Force (N)"],
        grouped_df["STD (N)"],
        marker="o"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("STD (N)")
    plt.title("Force Stability")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "Force_STD.png"
        ),
        dpi=300
    )

    plt.close()

    # -----------------------------------------------------
    # RMS ERROR
    # -----------------------------------------------------

    plt.figure(figsize=(6,5))

    plt.plot(
        grouped_df["Target Force (N)"],
        grouped_df["RMS Error (N)"],
        marker="o"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("RMS Error (N)")
    plt.title("RMS Force Error")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "RMS_Error.png"
        ),
        dpi=300
    )

    plt.close()

    print(f"Saved analysis:\n{output_excel}")

    return output_excel





def analyse_force_repeatability(folder_path):


    FORCE_THRESHOLD = 0.5
    MIN_CYCLE_POINTS = 5

    # =====================================================
    # STORAGE
    # =====================================================

    all_cycle_data = []

    test_summary_data = []

    # =====================================================
    # FIND FILES
    # =====================================================

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if (
            f.endswith(".csv")
            and "_analysis" not in f
            and "_analysed" not in f
        )
    ])

    if len(csv_files) == 0:
        raise ValueError(
            "No CSV files found."
        )

    # =====================================================
    # PROCESS EACH FILE
    # =====================================================

    for file_index, file in enumerate(csv_files):

        full_path = os.path.join(
            folder_path,
            file
        )

        # =================================================
        # READ TARGET FORCE
        # =================================================

        target_force = None

        with open(full_path, "r") as f:

            for line in f:

                if "# Target Force (N)" in line:

                    parts = line.strip().split(",")

                    try:
                        target_force = float(parts[1])
                    except:
                        pass

                if line.startswith("time"):
                    break

        if target_force is None:
            continue

        # =================================================
        # FIND DATA START
        # =================================================

        data_start = 0

        with open(full_path, "r") as f:

            for i, line in enumerate(f):

                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                if "time" in line.lower():
                    continue

                data_start = i
                break

        # =================================================
        # LOAD DATA
        # =================================================

        df = pd.read_csv(
            full_path,
            sep=r"[\s,\t]+",
            engine="python",
            skiprows=data_start,
            header=None
        )

        df = df.iloc[:, :2]

        df.columns = [
            "time",
            "force"
        ]

        df["force"] = pd.to_numeric(
            df["force"],
            errors="coerce"
        )

        df["time"] = pd.to_numeric(
            df["time"],
            errors="coerce"
        )

        df = df.dropna()

        # =================================================
        # CONTACT DETECTION
        # =================================================

        df["contact"] = (
            df["force"] > FORCE_THRESHOLD
        )

        df["contact_shift"] = (
            df["contact"].shift(1)
        )

        cycle_starts = df[
            (df["contact"] == True)
            &
            (df["contact_shift"] == False)
        ].index.tolist()

        cycle_ends = df[
            (df["contact"] == False)
            &
            (df["contact_shift"] == True)
        ].index.tolist()

        if (
            len(cycle_starts) == 0
            or
            len(cycle_ends) == 0
        ):
            continue

        if cycle_ends[0] < cycle_starts[0]:
            cycle_ends.pop(0)

        min_len = min(
            len(cycle_starts),
            len(cycle_ends)
        )

        cycle_starts = cycle_starts[:min_len]
        cycle_ends = cycle_ends[:min_len]

        # =================================================
        # PEAK FORCE PER CYCLE
        # =================================================

        peak_forces = []

        for cycle_num, (start, end) in enumerate(
            zip(cycle_starts, cycle_ends),
            start=1
        ):

            cycle = df.loc[start:end]

            if len(cycle) < MIN_CYCLE_POINTS:
                continue

            peak_force = cycle[
                "force"
            ].max()

            peak_forces.append(
                peak_force
            )

            all_cycle_data.append({

                "File": file,

                "Target Force (N)": target_force,

                "Cycle": cycle_num,

                "Peak Force (N)": peak_force
            })

        # =================================================
        # TEST SUMMARY
        # =================================================

        if len(peak_forces) == 0:
            continue

        peak_forces = np.array(
            peak_forces
        )

        mean_peak = np.mean(
            peak_forces
        )

        std_peak = np.std(
            peak_forces,
            ddof=1
        )

        cv_peak = (
            std_peak / mean_peak
        ) * 100

        force_range = (
            np.max(peak_forces)
            -
            np.min(peak_forces)
        )

        abs_error = (
            mean_peak - target_force
        )

        pct_error = (
            abs_error / target_force
        ) * 100

        test_summary_data.append({

            "File": file,

            "Target Force (N)": target_force,

            "Mean Peak Force (N)": mean_peak,

            "STD Peak Force (N)": std_peak,

            "CV (%)": cv_peak,

            "Range (N)": force_range,

            "Absolute Error (N)": abs_error,

            "Percent Error (%)": pct_error
        })

        # =================================================
        # PLOT: FORCE DRIFT
        # =================================================

        plt.figure(figsize=(7,5))

        plt.plot(
            range(1, len(peak_forces)+1),
            peak_forces,
            marker="o"
        )

        plt.axhline(
            target_force,
            linestyle="--"
        )

        plt.xlabel("Cycle Number")

        plt.ylabel("Peak Force (N)")

        plt.title(
            f"{target_force}N Repeatability"
        )

        plt.tight_layout()

        plot_name = (
            f"{int(target_force)}N_"
            f"{file_index+1}_drift.png"
        )

        plt.savefig(
            os.path.join(
                folder_path,
                plot_name
            ),
            dpi=300
        )

        plt.close()

    # =====================================================
    # CREATE DATAFRAMES
    # =====================================================

    all_cycles_df = pd.DataFrame(
        all_cycle_data
    )

    test_summary_df = pd.DataFrame(
        test_summary_data
    )

    if len(test_summary_df) == 0:
        raise ValueError(
            "No valid repeatability data."
        )

    # =====================================================
    # FORCE SUMMARY
    # =====================================================

    force_summary_df = test_summary_df.groupby(
        "Target Force (N)"
    ).agg({

        "Mean Peak Force (N)": "mean",

        "STD Peak Force (N)": "mean",

        "CV (%)": "mean",

        "Range (N)": "mean",

        "Absolute Error (N)": "mean",

        "Percent Error (%)": "mean"

    }).reset_index()

    force_summary_df = force_summary_df.sort_values(
        "Target Force (N)"
    )

    # =====================================================
    # SAVE EXCEL
    # =====================================================

    output_excel = os.path.join(
        folder_path,
        "FORCE_REPEATABILITY_ANALYSIS.xlsx"
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

    # =====================================================
    # BOXPLOT
    # =====================================================

    plt.figure(figsize=(8,6))

    grouped_data = []

    labels = []

    for force in sorted(
        all_cycles_df[
            "Target Force (N)"
        ].unique()
    ):

        subset = all_cycles_df[
            all_cycles_df[
                "Target Force (N)"
            ] == force
        ]

        grouped_data.append(
            subset["Peak Force (N)"]
        )

        labels.append(
            f"{int(force)}N"
        )

    plt.boxplot(
        grouped_data,
        labels=labels
    )

    plt.ylabel("Peak Force (N)")

    plt.title(
        "Force Repeatability"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "Force_Boxplot.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # STD VS FORCE
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        force_summary_df[
            "Target Force (N)"
        ],
        force_summary_df[
            "STD Peak Force (N)"
        ],
        marker="o"
    )

    plt.xlabel("Target Force (N)")

    plt.ylabel("STD (N)")

    plt.title(
        "Repeatability STD"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "STD_vs_Force.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # CV VS FORCE
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        force_summary_df[
            "Target Force (N)"
        ],
        force_summary_df[
            "CV (%)"
        ],
        marker="o"
    )

    plt.xlabel("Target Force (N)")

    plt.ylabel("CV (%)")

    plt.title(
        "Coefficient of Variation"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "CV_vs_Force.png"
        ),
        dpi=300
    )

    plt.close()

    print(
        f"Saved repeatability analysis:\n"
        f"{output_excel}"
    )

    return output_excel