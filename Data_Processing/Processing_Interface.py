import tkinter as tk
from tkinter import filedialog, messagebox
import os
import Processing_functions


'''
RIG VALIDATION FUNCTIONS:
'''

def analyse_calibration():

    folder_path = filedialog.askdirectory(
        title="Select calibration data folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_calibration_folder(folder_path)

        messagebox.showinfo(
            "Success",
            "Calibration analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


def full_frequency_analysis_folder():

    folder_path = filedialog.askdirectory(
        title="Select master folder containing frequency folders"
    )

    if not folder_path:
        return

    try:

        Processing_functions.full_frequency_force_analysis(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Full analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


def analyse_force_control_method_gui():

    folder_path = filedialog.askdirectory(
        title="Select one force-control method folder"
    )

    if not folder_path:
        return

    try:
        Processing_functions.analyse_force_control_method(folder_path)

        messagebox.showinfo(
            "Success",
            "Force-control method analysis complete!"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


def compare_force_control_methods_simple_gui():

    folder_path = filedialog.askdirectory(
        title="Select force-control master folder"
    )

    if not folder_path:
        return

    try:
        Processing_functions.compare_force_control_methods_simple(folder_path)

        messagebox.showinfo(
            "Success",
            "Force-control method comparison complete!"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


def compare_force_offset_methods_gui():

    folder_path = filedialog.askdirectory(
        title="Select force-control master folder"
    )

    if not folder_path:
        return

    try:
        Processing_functions.compare_force_offset_methods(folder_path)

        messagebox.showinfo(
            "Success",
            "Force-control method comparison complete!"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


def analyse_force_offset_repeatability_gui():

    folder_path = filedialog.askdirectory(
        title="Select force-offset repeatability folder"
    )

    if not folder_path:
        return

    try:
        Processing_functions.analyse_force_offset_repeatability(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Force offset repeatability analysis complete!"
        )

    except Exception as e:
        messagebox.showerror(
            "Error",
            str(e)
        )


def analyse_voltage_convergence_gui():

    folder_path = filedialog.askdirectory(
        title="Select convergence analysis folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_voltage_cycle_convergence_folder(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Voltage convergence analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


'''
INDIVIDUAL TENG DATA ANALYSIS FUNCTIONS:
'''

def analyse_impedance():

    folder_path = filedialog.askdirectory(
        title="Select folder containing impedance CSV files"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_voltage_only_impedance(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Voltage-only impedance analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


def analyse_voc_force_gui():

    folder_path = filedialog.askdirectory(
        title="Select VOC force-characterisation folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_voc_force_folder(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "VOC force analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


def analyse_isc_force_gui():

    folder_path = filedialog.askdirectory(
        title="Select ISC force-characterisation folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_isc_force_folder(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "ISC force analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


def analyse_matched_voltage_force_gui():

    folder_path = filedialog.askdirectory(
        title="Select matched-load voltage folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_matched_voltage_force_folder(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Matched-load voltage analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


def analyse_matched_current_force_gui():

    folder_path = filedialog.askdirectory(
        title="Select matched-load current folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_matched_current_force_folder(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Matched-load current analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


'''
OVERALL MATERIAL ANALYSIS FUNCTIONS:
'''

def analyse_material_impedance_gui():

    folder_path = filedialog.askdirectory(
        title="Select material folder for combined impedance analysis"
    )

    if not folder_path:
        return

    try:
        Processing_functions.analyse_material_impedance(folder_path)

        messagebox.showinfo(
            "Success",
            "Combined material impedance analysis complete!"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


def analyse_voltage_only_impedance_gui():

    folder_path = filedialog.askdirectory(
        title="Select material folder for voltage-only impedance analysis"
    )

    if not folder_path:
        return

    try:
        Processing_functions.analyse_voltage_only_impedance(folder_path)

        messagebox.showinfo(
            "Success",
            "Voltage-only impedance analysis complete!"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


def analyse_material_force_characterisation_gui():

    folder_path = filedialog.askdirectory(
        title="Select material folder for combined force characterisation"
    )

    if not folder_path:
        return

    try:
        Processing_functions.analyse_material_force_characterisation(folder_path)

        messagebox.showinfo(
            "Success",
            "Combined material force characterisation complete!"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


def analyse_voltage_force_characterisation_gui():

    folder_path = filedialog.askdirectory(
        title="Select material folder for voltage-only force characterisation"
    )

    if not folder_path:
        return

    try:
        Processing_functions.analyse_voltage_force_characterisation(folder_path)

        messagebox.showinfo(
            "Success",
            "Voltage-only force characterisation complete!"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


# =========================
# PROCESS SINGLE FILE
# =========================

def plot_force_voltage():

    file_path = filedialog.askopenfilename(
        title="Select data file",
        filetypes=[("CSV files", "*.csv")]
    )

    if not file_path:
        return

    try:

        Processing_functions.plot_force_voltage_vs_time(
            file_path
        )

        messagebox.showinfo(
            "Success",
            "Force/voltage plot created!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


# =========================
# GUI LAYOUT
# =========================

root = tk.Tk()
root.title("Triboelectric Data Processor")
root.geometry("1220x560")
root.minsize(1100, 520)

main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(fill="both", expand=True)
main_frame.columnconfigure(0, weight=1)
main_frame.columnconfigure(1, weight=1)
main_frame.columnconfigure(2, weight=1)

header = tk.Label(
    main_frame,
    text="Data Processing Tool",
    font=("Segoe UI", 14, "bold")
)
header.grid(row=0, column=0, columnspan=3, pady=(0, 15))

# Left column kept as the rig-validation column
rig_frame = tk.LabelFrame(
    main_frame,
    text="Rig Validation",
    padx=10,
    pady=10
)
rig_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)
rig_frame.columnconfigure(0, weight=1)

# Middle column: individual/folder-level analysis buttons
individual_frame = tk.LabelFrame(
    main_frame,
    text="Individual Data Analysis",
    padx=10,
    pady=10
)
individual_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
individual_frame.columnconfigure(0, weight=1)

# Right column: whole material analysis buttons
material_frame = tk.LabelFrame(
    main_frame,
    text="Overall Material Analysis",
    padx=10,
    pady=10
)
material_frame.grid(row=1, column=2, sticky="nsew", padx=(5, 0), pady=5)
material_frame.columnconfigure(0, weight=1)


# =========================
# LEFT COLUMN: RIG VALIDATION
# =========================

# Buttons for Rig Validation

tk.Button(
    rig_frame,
    text="1 - Analyse Z Calibration",
    width=30,
    height=2,
    command=analyse_calibration
).grid(row=0, column=0, pady=5, sticky="ew")

tk.Button(
    rig_frame,
    text="2 - Compare Testing Frequencies",
    width=30,
    height=2,
    command=full_frequency_analysis_folder
).grid(row=1, column=0, pady=5, sticky="ew")

tk.Button(
    rig_frame,
    text="3a - Analyse Force-Control Method",
    width=30,
    height=2,
    command=analyse_force_control_method_gui
).grid(row=2, column=0, pady=5, sticky="ew")

tk.Button(
    rig_frame,
    text="3b - Compare Force-Control Methods",
    width=30,
    height=2,
    command=compare_force_control_methods_simple_gui
).grid(row=3, column=0, pady=5, sticky="ew")

tk.Button(
    rig_frame,
    text="3c - Compare Force-Offset Methods",
    width=30,
    height=2,
    command=compare_force_offset_methods_gui
).grid(row=4, column=0, pady=5, sticky="ew")

tk.Button(
    rig_frame,
    text="3d - Analyse Force-Offset Repeatability",
    width=30,
    height=2,
    command=analyse_force_offset_repeatability_gui
).grid(row=5, column=0, pady=5, sticky="ew")

tk.Button(
    rig_frame,
    text="4 - Analyse Voltage Convergence",
    width=30,
    height=2,
    command=analyse_voltage_convergence_gui
).grid(row=6, column=0, pady=5, sticky="ew")


# =========================
# MIDDLE COLUMN: INDIVIDUAL DATA ANALYSIS
# =========================

tk.Button(
    individual_frame,
    text="Plot Force & Voltage vs Time",
    width=34,
    height=2,
    command=plot_force_voltage
).grid(row=0, column=0, pady=5, sticky="ew")

tk.Button(
    individual_frame,
    text="Analyse Voltage Only Impedance Folder",
    width=34,
    height=2,
    command=analyse_impedance
).grid(row=1, column=0, pady=5, sticky="ew")

tk.Button(
    individual_frame,
    text="Analyse VOC vs Force Folder",
    width=34,
    height=2,
    command=analyse_voc_force_gui
).grid(row=2, column=0, pady=5, sticky="ew")

tk.Button(
    individual_frame,
    text="Analyse ISC vs Force Folder",
    width=34,
    height=2,
    command=analyse_isc_force_gui
).grid(row=3, column=0, pady=5, sticky="ew")

tk.Button(
    individual_frame,
    text="Analyse Matched Voltage vs Force Folder",
    width=34,
    height=2,
    command=analyse_matched_voltage_force_gui
).grid(row=4, column=0, pady=5, sticky="ew")

tk.Button(
    individual_frame,
    text="Analyse Matched Current vs Force Folder",
    width=34,
    height=2,
    command=analyse_matched_current_force_gui
).grid(row=5, column=0, pady=5, sticky="ew")


# =========================
# RIGHT COLUMN: OVERALL MATERIAL ANALYSIS
# =========================

tk.Button(
    material_frame,
    text="Combined Material Impedance Analysis",
    width=36,
    height=2,
    command=analyse_material_impedance_gui
).grid(row=0, column=0, pady=5, sticky="ew")

tk.Button(
    material_frame,
    text="Voltage-Only Material Impedance Analysis",
    width=36,
    height=2,
    command=analyse_voltage_only_impedance_gui
).grid(row=1, column=0, pady=5, sticky="ew")

tk.Button(
    material_frame,
    text="Combined Material Force Characterisation",
    width=36,
    height=2,
    command=analyse_material_force_characterisation_gui
).grid(row=2, column=0, pady=5, sticky="ew")

tk.Button(
    material_frame,
    text="Voltage-Only Material Force Characterisation",
    width=36,
    height=2,
    command=analyse_voltage_force_characterisation_gui
).grid(row=3, column=0, pady=5, sticky="ew")

root.mainloop()