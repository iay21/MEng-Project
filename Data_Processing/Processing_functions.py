from matplotlib.colors import LinearSegmentedColormap
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


def compare_force_control_methods(master_folder):

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

    plot_comparison(
    "Mean In-Cycle RMS About Mean (N)",
    "In-Cycle RMS About Cycle Mean (N)",
    "Offset-independent in-cycle stability comparison",
    "comparison_in_cycle_rms_about_mean.png"
    )

    plot_comparison(
        "Mean Steady Duration (s)",
        "Mean Steady Duration (s)",
        "Steady-region duration comparison",
        "comparison_steady_duration.png"
    )

    plot_comparison(
        "Mean Steady Points",
        "Mean Number of Steady Points",
        "Steady-region sample count comparison",
        "comparison_steady_points.png"
    )

    print(f"Saved steady force-control method comparison:\n{output_excel}")

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


# Optional alias so old GUI/buttons still work
def plot_force_voltage_vs_time(file_path):
    return plot_test_signals_vs_time(file_path)


def analyse_impedance_folder(folder_path):
    """
    Analyse an impedance-test folder containing voltage-only, current-only, or dual CSV files.

    Outputs:
        - IMPEDANCE_ANALYSIS.xlsx
        - Impedance_Peak_Voltage_Current_Power.png
        - Impedance_RMS_Voltage_Current_Power.png

    Important method choice:
        Power for impedance matching is primarily calculated from voltage across the known load:
            P_peak = V_peak^2 / R
            P_rms  = V_rms^2 / R
        Current-derived power is included as a fallback/check, but voltage-derived power is preferred
        when voltage and current are measured in separate tests.
    """

    results = []

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if f.endswith(".csv")
        and "_analysis" not in f
        and "_analysed" not in f
        and "IMPEDANCE_ANALYSIS" not in f
    ])

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")

    def resistance_label(resistance):
        if pd.isna(resistance):
            return "UNKNOWN"
        if resistance == 0:
            return "SC"
        if np.isinf(resistance):
            return "OC"
        if resistance >= 1e9:
            return f"{resistance / 1e9:g}G"
        if resistance >= 1e6:
            return f"{resistance / 1e6:g}M"
        if resistance >= 1e3:
            return f"{resistance / 1e3:g}k"
        return f"{resistance:g}"

    def valid_load_resistance(R):
        return pd.notna(R) and R > 0 and not np.isinf(R)

    def scale_power(values):
        values = np.asarray(values, dtype=float)
        if np.all(np.isnan(values)):
            return values, "W", 1

        max_value = np.nanmax(np.abs(values))

        if not np.isfinite(max_value) or max_value == 0:
            return values, "W", 1
        if max_value < 1e-9:
            return values * 1e12, "pW", 1e12
        if max_value < 1e-6:
            return values * 1e9, "nW", 1e9
        if max_value < 1e-3:
            return values * 1e6, "µW", 1e6
        if max_value < 1:
            return values * 1e3, "mW", 1e3
        return values, "W", 1

    # =====================================================
    # PROCESS EVERY CSV FILE
    # =====================================================

    for file in csv_files:

        file_path = os.path.join(folder_path, file)
        resistance = read_load_resistance(file_path)
        measurement_mode = read_measurement_mode(file_path)

        if resistance is None:
            print(f"Skipping {file}: no load resistance found.")
            continue

        df = load_data(file_path)

        if len(df) == 0:
            print(f"Skipping {file}: no data found.")
            continue

        has_voltage = "voltage" in df.columns
        has_current = "current" in df.columns

        if not has_voltage and not has_current:
            print(f"Skipping {file}: no voltage or current column found.")
            continue

        row = {
            "File": file,
            "Measurement Mode": measurement_mode,
            "Load Resistance (Ohm)": resistance,
            "Load Resistance Label": resistance_label(resistance)
        }

        if has_voltage:
            voltage_peak_stats, voltage_rms = calculate_voltage_metrics(df)
            row.update({
                "Cycles Analysed Voltage": voltage_peak_stats["n_cycles"],
                "Mean Vpeak Rectified (V)": voltage_peak_stats["mean_peak"],
                "STD Vpeak Rectified (V)": voltage_peak_stats["std_peak"],
                "Vrms (V)": voltage_rms
            })
        else:
            row.update({
                "Cycles Analysed Voltage": np.nan,
                "Mean Vpeak Rectified (V)": np.nan,
                "STD Vpeak Rectified (V)": np.nan,
                "Vrms (V)": np.nan
            })

        if has_current:
            current_peak_stats, current_rms = calculate_current_metrics(df)
            row.update({
                "Cycles Analysed Current": current_peak_stats["n_cycles"],
                "Mean Ipeak Rectified (A)": current_peak_stats["mean_peak"],
                "STD Ipeak Rectified (A)": current_peak_stats["std_peak"],
                "Irms (A)": current_rms
            })
        else:
            row.update({
                "Cycles Analysed Current": np.nan,
                "Mean Ipeak Rectified (A)": np.nan,
                "STD Ipeak Rectified (A)": np.nan,
                "Irms (A)": np.nan
            })

        if has_voltage and has_current:
            power_stats = calculate_cycle_instantaneous_power_metrics(df)
            row.update({
                "Mean Cycle Max Instantaneous Power max(|V*I|) (W)": power_stats["mean_cycle_max_abs_power"],
                "STD Cycle Max Instantaneous Power max(|V*I|) (W)": power_stats["std_cycle_max_abs_power"],
                "Overall Max Instantaneous Power max(|V*I|) (W)": power_stats["overall_max_abs_power"],
                "Cycles Analysed Instantaneous Power": power_stats["n_cycles"]
            })
        else:
            row.update({
                "Mean Cycle Max Instantaneous Power max(|V*I|) (W)": np.nan,
                "STD Cycle Max Instantaneous Power max(|V*I|) (W)": np.nan,
                "Overall Max Instantaneous Power max(|V*I|) (W)": np.nan,
                "Cycles Analysed Instantaneous Power": np.nan
            })

        results.append(row)

    raw_df = pd.DataFrame(results)

    if len(raw_df) == 0:
        raise ValueError("No valid impedance data found.")

    # =====================================================
    # COMBINE SEPARATE VOLTAGE/CURRENT SWEEPS BY LOAD R
    # =====================================================

    numeric_cols = [
        "Cycles Analysed Voltage",
        "Mean Vpeak Rectified (V)",
        "STD Vpeak Rectified (V)",
        "Vrms (V)",
        "Cycles Analysed Current",
        "Mean Ipeak Rectified (A)",
        "STD Ipeak Rectified (A)",
        "Irms (A)",
        "Mean Cycle Max Instantaneous Power max(|V*I|) (W)",
        "STD Cycle Max Instantaneous Power max(|V*I|) (W)",
        "Overall Max Instantaneous Power max(|V*I|) (W)",
        "Cycles Analysed Instantaneous Power"
    ]

    summary_df = (
        raw_df
        .groupby("Load Resistance (Ohm)", dropna=False)
        .agg({
            "Load Resistance Label": "first",
            **{col: "mean" for col in numeric_cols}
        })
        .reset_index()
        .sort_values("Load Resistance (Ohm)")
        .reset_index(drop=True)
    )

    # =====================================================
    # POWER CALCULATIONS
    # =====================================================

    summary_df["Peak Power from Vpeak^2/R (W)"] = np.nan
    summary_df["RMS Power from Vrms^2/R (W)"] = np.nan
    summary_df["Peak Power from Ipeak^2R (W)"] = np.nan
    summary_df["RMS Power from Irms^2R (W)"] = np.nan
    summary_df["Peak Power Vpeak*Ipeak (W)"] = np.nan
    summary_df["RMS Power Vrms*Irms (W)"] = np.nan

    for idx, row in summary_df.iterrows():
        R = row["Load Resistance (Ohm)"]

        if valid_load_resistance(R):
            if pd.notna(row["Mean Vpeak Rectified (V)"]):
                summary_df.loc[idx, "Peak Power from Vpeak^2/R (W)"] = (
                    row["Mean Vpeak Rectified (V)"] ** 2 / R
                )

            if pd.notna(row["Vrms (V)"]):
                summary_df.loc[idx, "RMS Power from Vrms^2/R (W)"] = (
                    row["Vrms (V)"] ** 2 / R
                )

            if pd.notna(row["Mean Ipeak Rectified (A)"]):
                summary_df.loc[idx, "Peak Power from Ipeak^2R (W)"] = (
                    row["Mean Ipeak Rectified (A)"] ** 2 * R
                )

            if pd.notna(row["Irms (A)"]):
                summary_df.loc[idx, "RMS Power from Irms^2R (W)"] = (
                    row["Irms (A)"] ** 2 * R
                )

        if pd.notna(row["Mean Vpeak Rectified (V)"]) and pd.notna(row["Mean Ipeak Rectified (A)"]):
            summary_df.loc[idx, "Peak Power Vpeak*Ipeak (W)"] = (
                row["Mean Vpeak Rectified (V)"] * row["Mean Ipeak Rectified (A)"]
            )

        if pd.notna(row["Vrms (V)"]) and pd.notna(row["Irms (A)"]):
            summary_df.loc[idx, "RMS Power Vrms*Irms (W)"] = row["Vrms (V)"] * row["Irms (A)"]

    summary_df["Associated Peak Power (W)"] = (
        summary_df["Peak Power from Vpeak^2/R (W)"]
        .combine_first(summary_df["Peak Power from Ipeak^2R (W)"])
    )

    summary_df["Associated RMS Power (W)"] = (
        summary_df["RMS Power from Vrms^2/R (W)"]
        .combine_first(summary_df["RMS Power from Irms^2R (W)"])
    )

    # =====================================================
    # SAVE EXCEL
    # =====================================================

    output_excel = os.path.join(folder_path, "IMPEDANCE_ANALYSIS.xlsx")

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        raw_df.to_excel(writer, sheet_name="RAW_FILE_RESULTS", index=False)
        summary_df.to_excel(writer, sheet_name="SUMMARY_BY_RESISTANCE", index=False)

    # =====================================================
    # PLOT HELPERS
    # =====================================================

    def has_valid_column(df, col):
        return col in df.columns and df[col].notna().any()

    def plot_impedance_summary(
        voltage_col,
        current_col,
        power_col,
        title,
        filename,
        voltage_label,
        current_label,
        power_label
    ):
        finite_df = summary_df[
            summary_df["Load Resistance (Ohm)"].apply(valid_load_resistance)
        ].copy()

        if len(finite_df) == 0:
            return None

        if (
            not has_valid_column(finite_df, voltage_col)
            and not has_valid_column(finite_df, current_col)
            and not has_valid_column(finite_df, power_col)
        ):
            return None

        short_row = summary_df[summary_df["Load Resistance (Ohm)"] == 0]
        open_row = summary_df[summary_df["Load Resistance (Ohm)"].apply(lambda R: pd.notna(R) and np.isinf(R))]

        fig, ax_voltage = plt.subplots(figsize=(10, 6))
        lines = []

        if has_valid_column(finite_df, voltage_col):
            line_voltage, = ax_voltage.plot(
                finite_df["Load Resistance (Ohm)"],
                finite_df[voltage_col],
                marker="o",
                color=PLOT_COLOURS["voltage"],
                label=voltage_label
            )
            ax_voltage.set_ylabel("Voltage (V)", color=PLOT_COLOURS["voltage"])
            ax_voltage.tick_params(axis="y", labelcolor=PLOT_COLOURS["voltage"])
            lines.append(line_voltage)

        ax_current = ax_voltage.twinx()

        if has_valid_column(finite_df, current_col):
            current_uA = finite_df[current_col] * 1e6
            line_current, = ax_current.plot(
                finite_df["Load Resistance (Ohm)"],
                current_uA,
                marker="s",
                color=PLOT_COLOURS["current"],
                label=current_label
            )
            ax_current.set_ylabel("Current (µA)", color=PLOT_COLOURS["current"])
            ax_current.tick_params(axis="y", labelcolor=PLOT_COLOURS["current"])
            lines.append(line_current)

        ax_power = ax_voltage.twinx()
        ax_power.spines["right"].set_position(("outward", 75))

        if has_valid_column(finite_df, power_col):
            power_scaled, power_unit, scale_factor = scale_power(finite_df[power_col].to_numpy())
            line_power, = ax_power.plot(
                finite_df["Load Resistance (Ohm)"],
                power_scaled,
                marker="^",
                linestyle=":",
                linewidth=2,
                color=PLOT_COLOURS["power"],
                label=power_label
            )
            ax_power.set_ylabel(f"Power ({power_unit})", color=PLOT_COLOURS["power"])
            ax_power.tick_params(axis="y", labelcolor=PLOT_COLOURS["power"])
            lines.append(line_power)

            max_idx = finite_df[power_col].idxmax()
            max_R = finite_df.loc[max_idx, "Load Resistance (Ohm)"]
            max_R_label = finite_df.loc[max_idx, "Load Resistance Label"]
            max_power_W = finite_df.loc[max_idx, power_col]
            max_power_scaled = max_power_W * scale_factor

            ax_power.axvline(
                max_R,
                color=PLOT_COLOURS["target"],
                linestyle="--",
                linewidth=1.5
            )

            ax_power.annotate(
                f"Max power\nR = {max_R_label}\nP = {max_power_scaled:.3g} {power_unit}",
                xy=(max_R, max_power_scaled),
                xytext=(10, 20),
                textcoords="offset points",
                arrowprops=dict(arrowstyle="->", color=PLOT_COLOURS["target"]),
                fontsize=9,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    fc="white",
                    ec=PLOT_COLOURS["target"],
                    alpha=0.85
                )
            )

        # Annotate SC/OC instead of plotting 0 or infinity on a log axis.
        if len(open_row) > 0 and has_valid_column(open_row, voltage_col):
            open_voltage = open_row[voltage_col].iloc[0]
            ax_voltage.annotate(
                f"OC\n{open_voltage:.3g} V",
                xy=(finite_df["Load Resistance (Ohm)"].max(), finite_df[voltage_col].max()),
                xytext=(40, 20),
                textcoords="offset points",
                fontsize=9,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    fc="white",
                    ec=PLOT_COLOURS["voltage"],
                    alpha=0.85
                )
            )

        if len(short_row) > 0 and has_valid_column(short_row, current_col):
            short_current_uA = short_row[current_col].iloc[0] * 1e6
            ax_current.annotate(
                f"SC\n{short_current_uA:.3g} µA",
                xy=(finite_df["Load Resistance (Ohm)"].min(), (finite_df[current_col] * 1e6).max()),
                xytext=(-10, 30),
                textcoords="offset points",
                fontsize=9,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    fc="white",
                    ec=PLOT_COLOURS["current"],
                    alpha=0.85
                )
            )

        ax_voltage.set_xscale("log")
        ax_voltage.set_xlabel("Load Resistance (Ω)")
        ax_voltage.set_title(title)
        ax_voltage.grid(True, which="both", linestyle="--", alpha=0.35)

        ax_voltage.legend(
            lines,
            [line.get_label() for line in lines],
            loc="best"
        )

        fig.tight_layout()

        plot_path = os.path.join(folder_path, filename)
        plt.savefig(plot_path, dpi=300)
        plt.close()

        return plot_path

    peak_plot = plot_impedance_summary(
        voltage_col="Mean Vpeak Rectified (V)",
        current_col="Mean Ipeak Rectified (A)",
        power_col="Associated Peak Power (W)",
        title="Impedance Matching: Mean Rectified Peak Voltage, Current and Power",
        filename="Impedance_Peak_Voltage_Current_Power.png",
        voltage_label="Mean rectified Vpeak (V)",
        current_label="Mean rectified Ipeak (µA)",
        power_label="Associated peak power"
    )

    rms_plot = plot_impedance_summary(
        voltage_col="Vrms (V)",
        current_col="Irms (A)",
        power_col="Associated RMS Power (W)",
        title="Impedance Matching: RMS Voltage, Current and Power",
        filename="Impedance_RMS_Voltage_Current_Power.png",
        voltage_label="Vrms (V)",
        current_label="Irms (µA)",
        power_label="Associated RMS power"
    )

    print(f"Saved impedance analysis:\n{output_excel}")
    if peak_plot is not None:
        print(f"Saved peak summary plot:\n{peak_plot}")
    if rms_plot is not None:
        print(f"Saved RMS summary plot:\n{rms_plot}")

    return output_excel


def analyse_force_characterisation_folder(folder_path, signal_col, output_name, baseline_method="median"):
    """
    Analyse voltage or current output versus force for a folder of CSV files.

    Use this for:
        - Voc vs force: signal_col="voltage"
        - Isc vs force: signal_col="current"
        - matched-load voltage/current vs force

    Exports per-cycle metrics, summary metrics, and two plots:
        - rectified peak vs force
        - RMS vs force
    """

    results = []
    all_cycles = []

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if f.endswith(".csv")
        and "_analysis" not in f
        and "_analysed" not in f
    ])

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")

    for file in csv_files:
        file_path = os.path.join(folder_path, file)
        target_force = read_target_force(file_path)
        load_resistance = read_load_resistance(file_path)
        measurement_mode = read_measurement_mode(file_path)

        if target_force is None:
            print(f"Skipping {file}: no target force found.")
            continue

        df = load_data(file_path)

        if signal_col not in df.columns:
            print(f"Skipping {file}: no {signal_col} column.")
            continue

        cycle_df, summary = calculate_cycle_peak_rms_metrics(
            df,
            signal_col=signal_col,
            baseline_method=baseline_method
        )

        for _, row in cycle_df.iterrows():
            all_cycles.append({
                "File": file,
                "Measurement Mode": measurement_mode,
                "Load Resistance (Ohm)": load_resistance,
                "Target Force (N)": target_force,
                "Cycle": row["cycle"],
                "Positive Peak": row["positive_peak"],
                "Negative Peak Abs": row["negative_peak_abs"],
                "Rectified Peak": row["rectified_peak"],
                "Max Abs Peak": row["max_abs_peak"],
                "RMS": row["rms"]
            })

        results.append({
            "File": file,
            "Measurement Mode": measurement_mode,
            "Load Resistance (Ohm)": load_resistance,
            "Target Force (N)": target_force,
            "Mean Rectified Peak": summary["mean_rectified_peak"],
            "STD Rectified Peak": summary["std_rectified_peak"],
            "Mean Max Abs Peak": summary["mean_max_abs_peak"],
            "STD Max Abs Peak": summary["std_max_abs_peak"],
            "Mean RMS": summary["mean_rms"],
            "STD RMS": summary["std_rms"],
            "Cycles Analysed": summary["n_cycles"]
        })

    summary_df = pd.DataFrame(results)
    cycles_df = pd.DataFrame(all_cycles)

    if len(summary_df) == 0:
        raise ValueError("No valid characterisation data found.")

    force_summary_df = (
        summary_df
        .groupby("Target Force (N)")
        .agg({
            "Mean Rectified Peak": "mean",
            "STD Rectified Peak": "mean",
            "Mean Max Abs Peak": "mean",
            "STD Max Abs Peak": "mean",
            "Mean RMS": "mean",
            "STD RMS": "mean",
            "Cycles Analysed": "sum"
        })
        .reset_index()
        .sort_values("Target Force (N)")
    )

    output_excel = os.path.join(folder_path, f"{output_name}_ANALYSIS.xlsx")

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        cycles_df.to_excel(writer, sheet_name="ALL_CYCLES", index=False)
        summary_df.to_excel(writer, sheet_name="FILE_SUMMARY", index=False)
        force_summary_df.to_excel(writer, sheet_name="FORCE_SUMMARY", index=False)

    unit = "V" if signal_col == "voltage" else "A"
    scaled_peak = force_summary_df["Mean Rectified Peak"].copy()
    scaled_peak_std = force_summary_df["STD Rectified Peak"].copy()
    scaled_rms = force_summary_df["Mean RMS"].copy()
    scaled_rms_std = force_summary_df["STD RMS"].copy()
    ylabel_unit = unit

    if signal_col == "current":
        scaled_peak *= 1e6
        scaled_peak_std *= 1e6
        scaled_rms *= 1e6
        scaled_rms_std *= 1e6
        ylabel_unit = "µA"

    plt.figure(figsize=(8, 6))
    plt.errorbar(
        force_summary_df["Target Force (N)"],
        scaled_peak,
        yerr=scaled_peak_std,
        marker="o",
        capsize=4,
        color=PLOT_COLOURS["voltage"] if signal_col == "voltage" else PLOT_COLOURS["current"],
        label="Mean rectified peak"
    )
    plt.xlabel("Target Force (N)")
    plt.ylabel(f"{signal_col.capitalize()} peak ({ylabel_unit})")
    plt.title(f"{output_name}: Mean Rectified Peak vs Force")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    peak_plot = os.path.join(folder_path, f"{output_name}_rectified_peak_vs_force.png")
    plt.savefig(peak_plot, dpi=300)
    plt.close()

    plt.figure(figsize=(8, 6))
    plt.errorbar(
        force_summary_df["Target Force (N)"],
        scaled_rms,
        yerr=scaled_rms_std,
        marker="s",
        capsize=4,
        color=PLOT_COLOURS["voltage_rms"] if signal_col == "voltage" else PLOT_COLOURS["current_rms"],
        label="RMS"
    )
    plt.xlabel("Target Force (N)")
    plt.ylabel(f"{signal_col.capitalize()} RMS ({ylabel_unit})")
    plt.title(f"{output_name}: RMS vs Force")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    rms_plot = os.path.join(folder_path, f"{output_name}_rms_vs_force.png")
    plt.savefig(rms_plot, dpi=300)
    plt.close()

    print(f"Saved force characterisation analysis:\n{output_excel}")
    print(f"Saved peak plot:\n{peak_plot}")
    print(f"Saved RMS plot:\n{rms_plot}")

    return output_excel


def analyse_repeatability_across_repeats(
    folder_path,
    signal_col,
    output_name,
    baseline_method="median"
):
    """
    Analyse repeatability across repeated test runs.

    Intended for folders containing repeated tests under the same condition,
    e.g. three repeats of:
        - VOC at 10 N
        - ISC at 20 N
        - matched-load voltage at 15 N

    For each CSV:
        - calculates mean rectified peak
        - calculates RMS

    Across files:
        - calculates mean, STD, CV%
        - plots repeat-to-repeat peak and RMS
    """

    rows = []

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if f.endswith(".csv")
        and "_analysis" not in f
        and "_analysed" not in f
    ])

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")

    for repeat_num, file in enumerate(csv_files, start=1):

        file_path = os.path.join(folder_path, file)

        df = load_data(file_path)

        if signal_col not in df.columns:
            print(f"Skipping {file}: no {signal_col} column.")
            continue

        _, summary = calculate_cycle_peak_rms_metrics(
            df,
            signal_col=signal_col,
            baseline_method=baseline_method
        )

        target_force = read_target_force(file_path)
        load_resistance = read_load_resistance(file_path)
        measurement_mode = read_measurement_mode(file_path)

        rows.append({
            "Repeat": repeat_num,
            "File": file,
            "Target Force (N)": target_force,
            "Load Resistance (Ohm)": load_resistance,
            "Measurement Mode": measurement_mode,
            "Mean Rectified Peak": summary["mean_rectified_peak"],
            "STD Rectified Peak Within File": summary["std_rectified_peak"],
            "Mean RMS": summary["mean_rms"],
            "STD RMS Within File": summary["std_rms"],
            "Cycles Analysed": summary["n_cycles"]
        })

    repeat_df = pd.DataFrame(rows)

    if len(repeat_df) == 0:
        raise ValueError("No valid repeat data found.")

    unit = "V" if signal_col == "voltage" else "A"

    summary = {
        "Signal": signal_col,
        "Unit": unit,
        "N Repeats": len(repeat_df),

        "Mean Peak Across Repeats": repeat_df["Mean Rectified Peak"].mean(),
        "STD Peak Across Repeats": repeat_df["Mean Rectified Peak"].std(ddof=1),
        "CV Peak Across Repeats (%)": (
            repeat_df["Mean Rectified Peak"].std(ddof=1)
            / repeat_df["Mean Rectified Peak"].mean()
            * 100
        ),

        "Mean RMS Across Repeats": repeat_df["Mean RMS"].mean(),
        "STD RMS Across Repeats": repeat_df["Mean RMS"].std(ddof=1),
        "CV RMS Across Repeats (%)": (
            repeat_df["Mean RMS"].std(ddof=1)
            / repeat_df["Mean RMS"].mean()
            * 100
        )
    }

    summary_df = pd.DataFrame([summary])

    output_excel = os.path.join(
        folder_path,
        f"{output_name}_REPEATABILITY_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        repeat_df.to_excel(
            writer,
            sheet_name="REPEAT_RESULTS",
            index=False
        )

        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

    scale = 1
    ylabel_unit = unit

    if signal_col == "current":
        scale = 1e6
        ylabel_unit = "µA"

    plt.figure(figsize=(8, 6))

    plt.plot(
        repeat_df["Repeat"],
        repeat_df["Mean Rectified Peak"] * scale,
        marker="o",
        label="Mean rectified peak"
    )

    plt.plot(
        repeat_df["Repeat"],
        repeat_df["Mean RMS"] * scale,
        marker="s",
        label="Mean RMS"
    )

    plt.xlabel("Repeat Number")
    plt.ylabel(f"{signal_col.capitalize()} ({ylabel_unit})")
    plt.title(f"{output_name}: Repeatability Across Repeats")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()

    plot_path = os.path.join(
        folder_path,
        f"{output_name}_repeatability_across_repeats.png"
    )

    plt.savefig(plot_path, dpi=300)
    plt.close()

    print(f"Saved repeatability analysis:\n{output_excel}")
    print(f"Saved repeatability plot:\n{plot_path}")

    return output_excel



'''
DATA PROCESSING FUNCTIONS
'''

contact_start_threshold = 0.5
contact_end_threshold = 0.2



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


def load_data(file_path):
    """
    Loads old or new CSV files.

    Supported formats after metadata/header:
        time, force
        time, force, voltage
        time, force, voltage, current

    The current column is assumed to already be real current in amps.
    Rows are only dropped if time or force is missing; this prevents voltage-only
    or current-only files being emptied because the other channel is blank.
    """

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
        sep=r"[\s,\t,]+",
        engine="python",
        skiprows=data_start,
        header=None
    )

    if df.shape[1] >= 4:
        df = df.iloc[:, :4]
        df.columns = ["time", "force", "voltage", "current"]

    elif df.shape[1] >= 3:
        df = df.iloc[:, :3]
        df.columns = ["time", "force", "voltage"]

    elif df.shape[1] >= 2:
        df = df.iloc[:, :2]
        df.columns = ["time", "force"]

    else:
        raise ValueError(f"Not enough columns in {file_path}")

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Only require time and force.
    # Do NOT drop rows just because voltage/current is blank.
    df = df.dropna(subset=["time", "force"]).reset_index(drop=True)

    # Remove voltage column if it is completely empty
    if "voltage" in df.columns and df["voltage"].isna().all():
        df = df.drop(columns=["voltage"])

    # Remove current column if it is completely empty
    if "current" in df.columns and df["current"].isna().all():
        df = df.drop(columns=["current"])

    # Remove any out-of-order time glitches
    bad_rows = df.index[
        df["time"].shift(-1) < df["time"]
    ]

    df = df.drop(bad_rows).reset_index(drop=True)

    return df


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


def calculate_mean_cycle_spike(df, signal_col, baseline_method="zero"):
    """Backwards-compatible wrapper: mean rectified peak amplitude per cycle."""

    _, summary = calculate_cycle_peak_rms_metrics(
        df,
        signal_col=signal_col,
        baseline_method=baseline_method
    )

    return {
        "mean_peak": summary["mean_rectified_peak"],
        "std_peak": summary["std_rectified_peak"],
        "n_cycles": summary["n_cycles"],
        "cycle_peaks": summary["cycle_peaks"]
    }


def calculate_rms(df, signal_col, baseline_method="zero"):
    """Calculate whole-signal RMS after baseline correction."""

    if signal_col not in df.columns:
        return np.nan

    signal = df[signal_col].dropna().to_numpy()

    if len(signal) == 0:
        return np.nan

    corrected = baseline_correct_signal(signal, baseline_method=baseline_method)

    return np.sqrt(np.nanmean(corrected ** 2))


def calculate_signal_metrics(
    df,
    signal_col,
    baseline_method="zero"
):
    peak_stats = calculate_mean_cycle_spike(
        df,
        signal_col=signal_col,
        baseline_method="zero"
    )

    rms_value = calculate_rms(
        df,
        signal_col=signal_col,
        baseline_method=baseline_method
    )

    return peak_stats, rms_value


def calculate_voltage_metrics(df):
    return calculate_signal_metrics(
        df,
        signal_col="voltage",
        baseline_method="zero"
    )


def calculate_current_metrics(df):
    
    return calculate_signal_metrics(
        df,
        signal_col="current",
        baseline_method="median"
    )


def calculate_cycle_instantaneous_power_metrics(df):
    """
    Calculates cycle-based instantaneous power metrics.

    Uses simultaneously logged voltage and current:

        P(t) = V(t) * I(t)

    For each cycle:
        - calculate instantaneous power
        - take max absolute instantaneous power

    Returns:
        mean/std/max across cycles.
    """

    if "voltage" not in df.columns or "current" not in df.columns:
        return {
            "mean_cycle_max_abs_power": np.nan,
            "std_cycle_max_abs_power": np.nan,
            "overall_max_abs_power": np.nan,
            "n_cycles": 0,
            "cycle_max_abs_powers": []
        }

    df = df.copy()

    df["instantaneous_power"] = (
        df["voltage"] * df["current"]
    )

    cycles = find_cycles(df)

    cycle_max_abs_powers = []

    for start, end in cycles:

        cycle = df.loc[start:end]

        if len(cycle) < MIN_CYCLE_POINTS:
            continue

        max_abs_power = np.max(
            np.abs(cycle["instantaneous_power"])
        )

        cycle_max_abs_powers.append(max_abs_power)

    if len(cycle_max_abs_powers) == 0:
        return {
            "mean_cycle_max_abs_power": np.nan,
            "std_cycle_max_abs_power": np.nan,
            "overall_max_abs_power": np.nan,
            "n_cycles": 0,
            "cycle_max_abs_powers": []
        }

    return {
        "mean_cycle_max_abs_power": np.mean(cycle_max_abs_powers),
        "std_cycle_max_abs_power": (
            np.std(cycle_max_abs_powers, ddof=1)
            if len(cycle_max_abs_powers) > 1
            else np.nan
        ),
        "overall_max_abs_power": np.max(cycle_max_abs_powers),
        "n_cycles": len(cycle_max_abs_powers),
        "cycle_max_abs_powers": cycle_max_abs_powers
    }



def analyse_voc_force_folder(folder_path):
    return analyse_force_characterisation_folder(
        folder_path,
        signal_col="voltage",
        output_name="VOC_FORCE",
        baseline_method="median"
    )


def analyse_isc_force_folder(folder_path):
    return analyse_force_characterisation_folder(
        folder_path,
        signal_col="current",
        output_name="ISC_FORCE",
        baseline_method="median"
    )


def analyse_matched_voltage_force_folder(folder_path):
    return analyse_force_characterisation_folder(
        folder_path,
        signal_col="voltage",
        output_name="MATCHED_VOLTAGE_FORCE",
        baseline_method="median"
    )


def analyse_matched_current_force_folder(folder_path):
    return analyse_force_characterisation_folder(
        folder_path,
        signal_col="current",
        output_name="MATCHED_CURRENT_FORCE",
        baseline_method="median"
    )



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