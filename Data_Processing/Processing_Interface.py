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

def voltage_convergence():

    folder_path = filedialog.askdirectory(
        title="Select folder containing voltage convergence CSV files"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_voltage_cycle_convergence(
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

def analyse_impedance():

    folder_path = filedialog.askdirectory(
        title="Select folder containing impedance CSV files"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_impedance_folder(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Impedance analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )

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
root = tk.Tk()
root.title("Triboelectric Data Processor")
root.geometry("700x420")

main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(fill="both", expand=True)
main_frame.columnconfigure(0, weight=1)
main_frame.columnconfigure(1, weight=1)

header = tk.Label(
    main_frame,
    text="Data Processing Tool",
    font=("Segoe UI", 14, "bold")
)
header.grid(row=0, column=0, columnspan=2, pady=(0, 15))

rig_frame = tk.LabelFrame(main_frame, text="Rig Validation", padx=10, pady=10)
rig_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)
rig_frame.columnconfigure(0, weight=1)

teng_frame = tk.LabelFrame(main_frame, text="TENG Data Analysis", padx=10, pady=10)
teng_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=5)
teng_frame.columnconfigure(0, weight=1)

# Buttons for TENG Data Analysis

tk.Button(
    teng_frame,
    text="Plot Force & Voltage vs Time",
    width=30,
    height=2,
    command=plot_force_voltage
).grid(row=0, column=0, pady=5, sticky="ew")

tk.Button(
    teng_frame,
    text="Analyse Impedance",
    width=30,
    height=2,
    command=analyse_impedance
).grid(row=1, column=0, pady=5, sticky="ew")

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
    text="3b - Compare Force-Control Methods SIMPLE",
    width=30,
    height=2,
    command=compare_force_control_methods_simple_gui
).grid(row=3, column=0, pady=5, sticky="ew")

tk.Button(
    rig_frame,
    text="4 - Analyse Voltage Convergence",
    width=30,
    height=2,
    command=voltage_convergence
).grid(row=4, column=0, pady=5, sticky="ew")

root.mainloop()