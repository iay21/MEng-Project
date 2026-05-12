import pandas as pd
import numpy as np

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

    # =====================================================
    # SAVE RESULTS
    # =====================================================

    parent_folder = os.path.dirname(file)

    analysed_folder = os.path.join(
        parent_folder,
        "analysed"
    )

    os.makedirs(analysed_folder, exist_ok=True)

    base_name = os.path.basename(file)

    name_no_ext = os.path.splitext(base_name)[0]

    output_file = os.path.join(
        analysed_folder,
        f"{name_no_ext}_force_analysis.csv"
    )

    results_df.to_csv(output_file, index=False)

    print(f"Saved:\n{output_file}")

    return results_df