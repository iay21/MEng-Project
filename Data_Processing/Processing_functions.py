import pandas as pd
import numpy as np
import os

FORCE_THRESHOLD = 0.5
MIN_CYCLE_POINTS = 5

def process_data(file):

    # =========================
    # LOAD DATA
    # =========================
    df = pd.read_csv(
    file,
    sep=r"\s+|,",
    engine="python",
    comment="#",   # ✅ ignores metadata lines
    header=None
    )
    df.columns = ["time", "force", "voltage"]

    # =========================
    # CONTACT SIGNAL
    # =========================
    df["contact"] = df["force"] > FORCE_THRESHOLD
    df["contact_shift"] = df["contact"].shift(1).fillna(False)

    # =========================
    # FIND CYCLE STARTS
    # =========================
    cycle_starts = df[(df["contact"] == True) & (df["contact_shift"] == False)].index

    # =========================
    # EXTRACT CYCLES
    # =========================
    results = []

    for i in range(len(cycle_starts) - 1):

        start = cycle_starts[i]
        end = cycle_starts[i + 1]

        cycle = df.loc[start:end]

        # Ignore tiny/noisy segments
        if len(cycle) < MIN_CYCLE_POINTS:
            continue

        v_max = cycle["voltage"].max()
        v_min = cycle["voltage"].min()

        results.append({
            "cycle": i,
            "t_start": df.loc[start, "time"],
            "t_end": df.loc[end, "time"],
            "V_max": v_max,
            "V_min": v_min,
            "V_pp": v_max - v_min
        })

    results_df = pd.DataFrame(results)

    output_file = file.replace(".csv", "_analysed.csv")
    results_df.to_csv(output_file, index=False)

    return output_file


def analyse_force_cycles(file, target_force=None):

    import os
    import pandas as pd
    import numpy as np

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


def analyse_force_folder_to_excel(folder_path):

    import os
    import pandas as pd
    import numpy as np
    from collections import defaultdict

    # =====================================================
    # COLLECT FILES
    # =====================================================

    csv_files = [
        f for f in os.listdir(folder_path)
        if f.endswith(".csv")
        and "_force_analysis" not in f
        and "_analysed" not in f
    ]

    if len(csv_files) == 0:
        raise ValueError("No CSV files found.")

    # =====================================================
    # STORAGE
    # =====================================================

    run_rows = []
    force_summary_temp = []

    force_counter = defaultdict(int)

    # =====================================================
    # FIRST PASS: PROCESS ALL FILES
    # =====================================================

    for file in csv_files:

        full_path = os.path.join(folder_path, file)

        results_df = analyse_force_cycles(full_path)

        if results_df is None or len(results_df) == 0:
            continue

        force = float(results_df["target_force_N"].iloc[0])
        force_int = int(round(force))

        force_counter[force_int] += 1
        run_id = force_counter[force_int]

        # =================================================
        # BASIC STATS (per run)
        # =================================================

        mean_row = results_df.mean(numeric_only=True)

        steady = mean_row.get("steady_force_N", np.nan)
        freq = mean_row.get("frequency_hz", np.nan)

        abs_err = steady - force if pd.notna(steady) else np.nan
        pct_err = (abs_err / force * 100) if force else np.nan

        # store run-level data (OVERALL sheet)
        run_rows.append({
            "Contact Force": f"{force_int}N ({run_id})",
            "Mean steady force": steady,
            "Absolute Force Error": abs_err,
            "% Force Error": pct_err,
            "Mean RMS Error on steady force": mean_row.get("rms_error_N", np.nan),
            "Mean Steady force STD": mean_row.get("steady_force_std_N", np.nan),
            "Mean Frequency": freq,
            "Absolute Freq error": np.nan,
            "% Freq error": np.nan
        })

        # store for MEAN sheet
        force_summary_temp.append({
            "Force": force_int,
            "steady": steady,
            "error": abs_err,
            "pct": pct_err,
            "rms": mean_row.get("rms_error_N", np.nan),
            "std": mean_row.get("steady_force_std_N", np.nan),
            "freq": freq
        })

        force_counter[force_int] = run_id

    # =====================================================
    # BUILD OVERALL SHEET
    # =====================================================

    overall_df = pd.DataFrame(run_rows)

    # force order
    overall_df["sort"] = overall_df["Contact Force"].str.extract(r"(\d+)").astype(int)
    overall_df = overall_df.sort_values("sort").drop(columns=["sort"])

    # =====================================================
    # BUILD MEAN SHEET (YOUR EXACT FORMAT)
    # =====================================================

    mean_df = pd.DataFrame(force_summary_temp)

    grouped = mean_df.groupby("Force").mean(numeric_only=True).reset_index()

    grouped = grouped.sort_values("Force")

    mean_sheet = pd.DataFrame({
        "Target Contact Force (N)": grouped["Force"],

        "Steady Force": "",
        "Mean (N)": grouped["steady"],
        "Absolute Error": grouped["error"],
        "% Error": grouped["pct"],

        "Mean RMS Error": grouped["rms"],
        "Mean STD": grouped["std"],

        "Cycle Frequency": "",
        "Mean (Hz)": grouped["freq"],
        "Absolute Freq Error": np.nan,
        "% Freq Error": np.nan
    })

    # fix column order EXACTLY as requested
    mean_sheet = mean_sheet[
        [
            "Target Contact Force (N)",
            "Mean (N)",
            "Absolute Error",
            "% Error",
            "Mean RMS Error",
            "Mean STD",
            "Mean (Hz)",
            "Absolute Freq Error",
            "% Freq Error"
        ]
    ]

    # =====================================================
    # WRITE EXCEL (ORDER IMPORTANT)
    # =====================================================

    output_excel = os.path.join(folder_path, "combined_force_analysis.xlsx")

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:

        # 1. MEAN (FIRST SHEET)
        mean_sheet.to_excel(writer, sheet_name="MEAN", index=False)

        # 2. OVERALL (SECOND SHEET)
        overall_df.to_excel(writer, sheet_name="OVERALL", index=False)

        # 3. INDIVIDUAL SHEETS
        force_counter.clear()

        for file in csv_files:

            full_path = os.path.join(folder_path, file)

            results_df = analyse_force_cycles(full_path)

            force = int(round(results_df["target_force_N"].iloc[0]))

            force_counter[force] += 1
            run_id = force_counter[force]

            sheet_name = f"{force}N {run_id}"[:31]

            results_df["cycle"] = results_df["cycle"].astype(object)

            mean_row = results_df.mean(numeric_only=True)
            mean_row["cycle"] = "MEAN"

            mean_df = pd.DataFrame([mean_row])
            mean_df = mean_df.reindex(columns=results_df.columns)

            final_df = pd.concat([results_df, mean_df], ignore_index=True)

            final_df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"\nSaved:\n{output_excel}")

    return output_excel

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


def full_frequency_force_analysis(master_folder):

    import os
    import pandas as pd
    import numpy as np

    # =====================================================
    # FIND FREQUENCY FOLDERS
    # =====================================================

    frequency_folders = [
        f for f in os.listdir(master_folder)
        if os.path.isdir(os.path.join(master_folder, f))
    ]

    if len(frequency_folders) == 0:
        raise ValueError("No frequency folders found.")

    # =====================================================
    # STORAGE
    # =====================================================

    force_error_data = {}
    force_rms_data = {}
    force_std_data = {}

    freq_error_data = {}
    freq_rms_data = {}
    freq_std_data = {}

    # =====================================================
    # PROCESS EACH FREQUENCY FOLDER
    # =====================================================

    for freq_folder in sorted(frequency_folders):

        folder_path = os.path.join(master_folder, freq_folder)

        # extract target frequency from folder name
        # e.g. 0.25Hz -> 0.25
        freq_label = freq_folder.replace("Hz", "")

        try:
            target_frequency = float(freq_label)
        except:
            print(f"Skipping invalid folder: {freq_folder}")
            continue

        csv_files = [
            f for f in os.listdir(folder_path)
            if f.endswith(".csv")
            and "_analysed" not in f
            and "_force_analysis" not in f
        ]

        # temporary storage for this frequency
        temp_force_error = {}
        temp_force_rms = {}
        temp_force_std = {}

        temp_freq_error = {}
        temp_freq_rms = {}
        temp_freq_std = {}

        # =================================================
        # PROCESS EACH CSV FILE
        # =================================================

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

                mean_force_error = (
                    (mean_force - target_force)
                    / target_force
                ) * 100

                mean_rms = results_df["rms_error_N"].mean()

                mean_std = results_df[
                    "steady_force_std_N"
                ].mean()

                mean_freq = results_df[
                    "frequency_hz"
                ].mean()

                freq_error_pct = (
                    abs(mean_freq - target_frequency)
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

                # =========================================
                # STORE FORCE DATA
                # =========================================

                temp_force_error.setdefault(target_force, [])
                temp_force_rms.setdefault(target_force, [])
                temp_force_std.setdefault(target_force, [])

                temp_force_error[target_force].append(
                    mean_force_error
                )

                temp_force_rms[target_force].append(
                    mean_rms
                )

                temp_force_std[target_force].append(
                    mean_std
                )

                # =========================================
                # STORE FREQUENCY DATA
                # =========================================

                temp_freq_error.setdefault(target_force, [])
                temp_freq_rms.setdefault(target_force, [])
                temp_freq_std.setdefault(target_force, [])

                temp_freq_error[target_force].append(
                    freq_error_pct
                )

                temp_freq_rms[target_force].append(
                    freq_rms
                )

                temp_freq_std[target_force].append(
                    freq_std
                )

            except Exception as e:
                print(f"Failed processing {file}: {e}")

        # =================================================
        # AVERAGE REPEATS
        # =================================================

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

    # =====================================================
    # CREATE TABLE FUNCTION
    # =====================================================

    def build_metric_table(metric_dict, metric_name):

        # sort frequencies numerically
        frequencies = sorted(
            frequency_folders,
            key=lambda x: float(x.replace("Hz", ""))
        )

        rows = []

        for force in sorted(metric_dict.keys()):

            # left-most column becomes just the force value
            row = {
                metric_name: force
            }

            # frequency columns
            for freq in frequencies:
                row[freq] = metric_dict[force].get(freq, np.nan)

            rows.append(row)

        return pd.DataFrame(rows)

    # =====================================================
    # BUILD FORCE SHEET
    # =====================================================

    force_error_df = build_metric_table(
        force_error_data,
        "% error"
    )

    force_rms_df = build_metric_table(
        force_rms_data,
        "RMS"
    )

    force_std_df = build_metric_table(
        force_std_data,
        "STD"
    )

    # =====================================================
    # STACK TABLES VERTICALLY WITH REPEATED HEADERS
    # =====================================================

    force_sheet = pd.concat(
        [
            force_error_df,
            pd.DataFrame([[]]),
            force_rms_df,
            pd.DataFrame([[]]),
            force_std_df
        ],
        ignore_index=True
    )

    # =====================================================
    # BUILD FREQUENCY SHEET
    # =====================================================
    # =====================================================

    freq_error_df = build_metric_table(
        freq_error_data,
        "% error"
    )

    freq_rms_df = build_metric_table(
        freq_rms_data,
        "RMS"
    )

    freq_std_df = build_metric_table(
        freq_std_data,
        "STD"
    )

    frequency_sheet = pd.concat(
        [
            freq_error_df,
            pd.DataFrame([[]]),
            freq_rms_df,
            pd.DataFrame([[]]),
            freq_std_df
        ],
        ignore_index=True
    )

    # =====================================================
    # SAVE EXCEL
    # =====================================================

    output_file = os.path.join(
        master_folder,
        "FULL_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:

        # ================================================
        # FORCE SHEET
        # ================================================

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

        # ================================================
        # FREQUENCY SHEET
        # ================================================

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

    print(f"Saved full analysis:\n{output_file}")

    return output_file


def create_force_error_heatmap(master_folder):

    import os
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt

    # =====================================================
    # STORAGE
    # =====================================================

    heatmap_data = {}

    # =====================================================
    # FIND FREQUENCY FOLDERS
    # =====================================================

    frequency_folders = sorted([
        f for f in os.listdir(master_folder)
        if os.path.isdir(os.path.join(master_folder, f))
    ])

    # =====================================================
    # PROCESS EACH FREQUENCY
    # =====================================================

    for freq_folder in frequency_folders:

        folder_path = os.path.join(
            master_folder,
            freq_folder
        )

        # extract numeric frequency
        try:
            target_frequency = float(
                freq_folder.replace("Hz", "")
            )
        except:
            continue

        csv_files = [
            f for f in os.listdir(folder_path)
            if f.endswith(".csv")
            and "_analysed" not in f
            and "_force_analysis" not in f
        ]

        # temporary storage
        temp_force_data = {}

        # =================================================
        # PROCESS FILES
        # =================================================

        for file in csv_files:

            full_path = os.path.join(
                folder_path,
                file
            )

            try:

                results_df = analyse_force_cycles(
                    full_path
                )

                if len(results_df) == 0:
                    continue

                target_force = int(round(
                    results_df[
                        "target_force_N"
                    ].iloc[0]
                ))

                mean_rms = results_df[
                    "rms_error_N"
                ].mean()

                temp_force_data.setdefault(
                    target_force,
                    []
                )

                temp_force_data[
                    target_force
                ].append(mean_rms)

            except Exception as e:

                print(f"Failed: {file}")
                print(e)

        # =================================================
        # AVERAGE REPEATS
        # =================================================

        for force in temp_force_data:

            heatmap_data.setdefault(force, {})

            heatmap_data[force][
                target_frequency
            ] = np.mean(
                temp_force_data[force]
            )

    # =====================================================
    # CREATE DATAFRAME
    # =====================================================

    heatmap_df = pd.DataFrame(
        heatmap_data
    ).T

    heatmap_df = heatmap_df.sort_index()

    heatmap_df = heatmap_df[
        sorted(heatmap_df.columns)
    ]

    # =====================================================
    # PLOT
    # =====================================================

    fig, ax = plt.subplots(figsize=(8, 6))

    im = ax.imshow(
        heatmap_df.values,
        aspect="auto"
    )

    # axis labels
    ax.set_xticks(
        range(len(heatmap_df.columns))
    )

    ax.set_xticklabels([
        f"{x} Hz"
        for x in heatmap_df.columns
    ])

    ax.set_yticks(
        range(len(heatmap_df.index))
    )

    ax.set_yticklabels([
        f"{y} N"
        for y in heatmap_df.index
    ])

    ax.set_xlabel(
        "Target Frequency"
    )

    ax.set_ylabel(
        "Target Force"
    )

    ax.set_title(
        "RMS Force Error Heat Map"
    )

    # =====================================================
    # ADD CELL VALUES
    # =====================================================

    for i in range(len(heatmap_df.index)):
        for j in range(len(heatmap_df.columns)):

            value = heatmap_df.iloc[i, j]

            ax.text(
                j,
                i,
                f"{value:.2f}",
                ha="center",
                va="center"
            )

    # colour bar
    cbar = plt.colorbar(im)

    cbar.set_label(
        "RMS Error (N)"
    )

    plt.tight_layout()

    # =====================================================
    # SAVE
    # =====================================================

    output_file = os.path.join(
        master_folder,
        "RMS_Force_Error_Heatmap.png"
    )

    plt.savefig(
        output_file,
        dpi=300
    )

    plt.close()

    print(f"Saved heatmap:\n{output_file}")

    return output_file


# def analyse_calibration_file(
#     file,
#     target_force=None
# ):

#     import os
#     import pandas as pd
#     import numpy as np

#     # =====================================================
#     # READ TARGET FORCE FROM METADATA
#     # =====================================================

#     if target_force is None:

#         with open(file, "r") as f:

#             for line in f:

#                 if "# Target Force (N)" in line:

#                     parts = line.strip().split(",")

#                     if len(parts) >= 2:

#                         try:
#                             target_force = float(parts[1])

#                         except:
#                             pass

#                 if line.startswith("time_s"):
#                     break

#     if target_force is None:

#         raise ValueError(
#             f"No target force found in:\n{file}"
#         )

#     # =====================================================
#     # FIND START OF DATA
#     # =====================================================

#     data_start = 0

#     with open(file, "r") as f:

#         for i, line in enumerate(f):

#             line = line.strip()

#             if not line:
#                 continue

#             if line.startswith("#"):
#                 continue

#             if "time" in line.lower():
#                 continue

#             data_start = i
#             break

#     # =====================================================
#     # LOAD DATA
#     # =====================================================

#     df = pd.read_csv(
#         file,
#         sep=r"[\s,\t]+",
#         engine="python",
#         skiprows=data_start,
#         header=None
#     )

#     df = df.iloc[:, :2]

#     df.columns = ["time", "force"]

#     df["time"] = pd.to_numeric(
#         df["time"],
#         errors="coerce"
#     )

#     df["force"] = pd.to_numeric(
#         df["force"],
#         errors="coerce"
#     )

#     df = df.dropna()

#     # =====================================================
#     # FIND STEADY REGION
#     # =====================================================

#     steady_region = df[
#         df["force"] > (0.9 * target_force)
#     ]

#     if len(steady_region) < 5:
#         steady_region = df.tail(20)

#     # =====================================================
#     # METRICS
#     # =====================================================

#     max_force = df["force"].max()

#     steady_force = steady_region["force"].mean()

#     steady_std = steady_region["force"].std()

#     absolute_error = abs(
#         steady_force - target_force
#     )

#     percentage_error = (
#         absolute_error / target_force
#     ) * 100

#     rms_error = np.sqrt(
#         np.mean(
#             (steady_region["force"] - target_force) ** 2
#         )
#     )

#     overshoot = max_force - target_force

#     # =====================================================
#     # RISE TIME
#     # =====================================================

#     force_10 = 0.1 * target_force
#     force_90 = 0.9 * target_force

#     try:

#         t10 = df[
#             df["force"] >= force_10
#         ]["time"].iloc[0]

#         t90 = df[
#             df["force"] >= force_90
#         ]["time"].iloc[0]

#         rise_time = t90 - t10

#     except:
#         rise_time = np.nan

#     # =====================================================
#     # SETTLING TIME
#     # ±5% band
#     # =====================================================

#     lower = 0.95 * target_force
#     upper = 1.05 * target_force

#     settling_time = np.nan

#     for i in range(len(df)):

#         remaining = df.iloc[i:]

#         if (
#             (remaining["force"] >= lower) &
#             (remaining["force"] <= upper)
#         ).all():

#             settling_time = remaining["time"].iloc[0]
#             break

#     # =====================================================
#     # OUTPUT TABLE
#     # =====================================================

#     results_df = pd.DataFrame([{

#         "target_force_N": target_force,

#         "max_force_N": max_force,

#         "steady_force_N": steady_force,

#         "absolute_error_N": absolute_error,

#         "percentage_error": percentage_error,

#         "steady_force_std_N": steady_std,

#         "rms_error_N": rms_error,

#         "overshoot_N": overshoot,

#         "rise_time_s": rise_time,

#         "settling_time_s": settling_time

#     }])

#     return results_df

# def analyse_calibration_folder_to_excel(
#     folder_path
# ):

#     import os
#     import pandas as pd

#     csv_files = sorted([
#         f for f in os.listdir(folder_path)
#         if (
#             f.endswith(".csv")
#             and "_analysis" not in f
#         )
#     ])

#     if len(csv_files) == 0:
#         raise ValueError("No CSV files found.")

#     output_excel = os.path.join(
#         folder_path,
#         "_calibration_analysis.xlsx"
#     )

#     force_counts = {}

#     with pd.ExcelWriter(
#         output_excel,
#         engine="openpyxl"
#     ) as writer:

#         for file in csv_files:

#             full_path = os.path.join(
#                 folder_path,
#                 file
#             )

#             # =============================================
#             # RUN ANALYSIS
#             # =============================================

#             results_df = analyse_calibration_file(
#                 full_path
#             )

#             target_force = results_df[
#                 "target_force_N"
#             ].iloc[0]

#             # =============================================
#             # SHEET NAME
#             # =============================================

#             if target_force not in force_counts:
#                 force_counts[target_force] = 1
#             else:
#                 force_counts[target_force] += 1

#             repetition = force_counts[target_force]

#             sheet_name = (
#                 f"{target_force}N {repetition}"
#             )

#             sheet_name = sheet_name[:31]

#             # =============================================
#             # WRITE SHEET
#             # =============================================

#             results_df.to_excel(
#                 writer,
#                 sheet_name=sheet_name,
#                 index=False
#             )

#     print(
#         f"\nSaved calibration workbook:\n"
#         f"{output_excel}"
#     )

#     return output_excel
    
def analyse_calibration_folder(folder_path):

    import os
    import pandas as pd
    import numpy as np

    # =====================================================
    # STORAGE
    # =====================================================

    results = []

    # =====================================================
    # FIND FILES
    # =====================================================

    csv_files = sorted([
        f for f in os.listdir(folder_path)
        if (
            f.endswith(".csv")
            and "_analysis" not in f
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
        # FIND START OF DATA
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

        df = df.dropna()

        if len(df) == 0:
            continue

        # =================================================
        # PEAK FORCE
        # =================================================

        peak_force = df[
            "force"
        ].max()

        # =================================================
        # ERRORS
        # =================================================

        absolute_error = (
            peak_force - target_force
        )

        percent_error = (
            absolute_error / target_force
        ) * 100

        # =================================================
        # SAVE RESULTS
        # =================================================

        results.append({

            "File": file,

            "Target Force (N)": target_force,

            "Peak Force (N)": peak_force,

            "Absolute Error (N)": absolute_error,

            "Percent Error (%)": percent_error
        })

    # =====================================================
    # CREATE DATAFRAME
    # =====================================================

    results_df = pd.DataFrame(results)

    if len(results_df) == 0:
        raise ValueError(
            "No valid calibration data found."
        )

    # =====================================================
    # SUMMARY
    # =====================================================

    summary_df = results_df.groupby(
        "Target Force (N)"
    ).agg({

        "Peak Force (N)": [
            "mean",
            "std"
        ],

        "Absolute Error (N)": "mean",

        "Percent Error (%)": "mean"

    })

    summary_df.columns = [

        "Mean Peak Force (N)",

        "Peak Force STD (N)",

        "Mean Absolute Error (N)",

        "Mean Percent Error (%)"
    ]

    summary_df = summary_df.reset_index()

    # =====================================================
    # SAVE EXCEL
    # =====================================================

    output_file = os.path.join(
        folder_path,
        "_CALIBRATION_ANALYSIS.xlsx"
    )

    with pd.ExcelWriter(
        output_file,
        engine="openpyxl"
    ) as writer:

        results_df.to_excel(
            writer,
            sheet_name="ALL_RESULTS",
            index=False
        )

        summary_df.to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False
        )

    print(f"Saved:\n{output_file}")

    return output_file

def create_calibration_plots(folder_path):

    import os
    import pandas as pd
    import matplotlib.pyplot as plt

    excel_file = os.path.join(
        folder_path,
        "_CALIBRATION_ANALYSIS.xlsx"
    )

    summary_df = pd.read_excel(
        excel_file,
        sheet_name="SUMMARY"
    )

    # =====================================================
    # 1. MEASURED VS TARGET
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        summary_df["Target Force (N)"],
        summary_df["Mean Peak Force (N)"],
        marker="o",
        label="Measured"
    )

    plt.plot(
        summary_df["Target Force (N)"],
        summary_df["Target Force (N)"],
        linestyle="--",
        label="Target"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("Force (N)")
    plt.title("Measured vs Target Force")
    plt.legend()

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "_Measured_vs_Target.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # 2. ABSOLUTE ERROR
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        summary_df["Target Force (N)"],
        summary_df["Mean Absolute Error (N)"],
        marker="o"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("Absolute Error (N)")
    plt.title("Absolute Error vs Force")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "_Absolute_Error.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # 3. PERCENT ERROR
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        summary_df["Target Force (N)"],
        summary_df["Mean Percent Error (%)"],
        marker="o"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("Percent Error (%)")
    plt.title("Percent Error vs Force")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "_Percent_Error.png"
        ),
        dpi=300
    )

    plt.close()

    # =====================================================
    # 4. STD (FORCE STABILITY)
    # =====================================================

    plt.figure(figsize=(6,5))

    plt.plot(
        summary_df["Target Force (N)"],
        summary_df["Peak Force STD (N)"],
        marker="o"
    )

    plt.xlabel("Target Force (N)")
    plt.ylabel("STD (N)")
    plt.title("Force Stability (Peak Force STD)")

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            folder_path,
            "_Force_STD.png"
        ),
        dpi=300
    )

    plt.close()

    print("Calibration plots created.")


