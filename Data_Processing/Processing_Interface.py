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

def compare_force_control_methods_gui():

    folder_path = filedialog.askdirectory(
        title="Select force-control master folder"
    )

    if not folder_path:
        return

    try:
        Processing_functions.compare_force_control_methods(folder_path)

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
            folder_path,
            voltage_metric="V_pp",
            threshold_percent=5
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

# def plot_one_file():

#     file = filedialog.askopenfilename(
#         filetypes=[("CSV files", "*.csv")]
#     )

#     if not file:
#         return

#     try:
#         Processing_functions.plot_force_and_voltage(file)

#     except Exception as e:
#         messagebox.showerror("Error", str(e))



# def process_single():

#     file = filedialog.askopenfilename(
#         filetypes=[("CSV files", "*.csv")]
#     )

#     if not file:
#         return

#     try:
#         output = Processing_functions.process_data(file)

#         messagebox.showinfo(
#             "Success",
#             f"Processed file saved as:\n{output}"
#         )

#     except Exception as e:
#         messagebox.showerror("Error", str(e))

# def analyse_force_file():

#     file_path = filedialog.askopenfilename(
#         title="Select force data file",
#         filetypes=[("CSV files", "*.csv")]
#     )

#     if not file_path:
#         return

#     try:

#         Processing_functions.analyse_force_cycles(
#             file_path,
#             target_force=None  # Will read from metadata
#         )

#         messagebox.showinfo(
#             "Success",
#             "Force analysis complete!"
#         )

#     except Exception as e:

#         messagebox.showerror(
#             "Error",
#             str(e)
#         )
# # =========================
# # PROCESS FOLDER
# # =========================

# def process_folder():

#     folder = filedialog.askdirectory()

#     if not folder:
#         return

#     try:
#         count = 0

#         for file in os.listdir(folder):
#             if file.endswith(".csv") and not file.endswith("_analysed.csv"):

#                 full_path = os.path.join(folder, file)
#                 Processing_functions.process_data(full_path)
#                 count += 1

#         messagebox.showinfo(
#             "Done",
#             f"Processed {count} files."
#         )

#     except Exception as e:
#         messagebox.showerror("Error", str(e))


# def analyse_force_folder():

#     folder_path = filedialog.askdirectory(
#         title="Select folder containing CSV files"
#     )

#     if not folder_path:
#         return

#     try:

#         output_file = (
#             Processing_functions.analyse_force_folder_to_excel(
#                 folder_path
#             )
#         )

#         messagebox.showinfo(
#             "Success",
#             f"Combined Excel file created:\n\n{output_file}"
#         )

#     except Exception as e:

#         messagebox.showerror(
#             "Error",
#             str(e)
#         )





# # def create_heatmap():

# #     folder_path = filedialog.askdirectory(
# #         title="Select master data folder"
# #     )

# #     if not folder_path:
# #         return

# #     try:

# #         Processing_functions.create_force_error_heatmap(
# #             folder_path
# #         )

# #         messagebox.showinfo(
# #             "Success",
# #             "Heat map created!"
# #         )

# #     except Exception as e:

# #         messagebox.showerror(
# #             "Error",
# #             str(e)
# #         )

# def analyse_calibration():

#     folder_path = filedialog.askdirectory(
#         title="Select calibration data folder"
#     )

#     if not folder_path:
#         return

#     try:

#         Processing_functions.analyse_calibration_folder(folder_path)

#         messagebox.showinfo(
#             "Success",
#             "Calibration analysis complete!"
#         )

#     except Exception as e:

#         messagebox.showerror(
#             "Error",
#             str(e)
#         )


# def force_only_analysis_gui():

#     folder_path = filedialog.askdirectory(
#         title="Select folder of force data"
#     )

#     if not folder_path:
#         return

#     try:

#         Processing_functions.force_only_analysis(
#             folder_path
#         )

#         messagebox.showinfo(
#             "Success",
#             "Force-only analysis complete!"
#         )

#     except Exception as e:

#         messagebox.showerror(
#             "Error",
#             str(e)
#         )

# def repeatability_analysis():

#     folder_path = filedialog.askdirectory(
#         title="Select repeatability data folder"
#     )

#     if not folder_path:
#         return

#     try:

#         Processing_functions.analyse_force_repeatability(
#             folder_path
#         )

#         messagebox.showinfo(
#             "Success",
#             "Repeatability analysis complete!"
#         )

#     except Exception as e:

#         messagebox.showerror(
#             "Error",
#             str(e)
#         )

# # =========================
# # GUI LAYOUT
# # =========================

# root = tk.Tk()
# root.title("Triboelectric Data Processor")
# root.geometry("450x400")

# tk.Label(
#     root,
#     text="Data Processing Tool",
#     font=("Segoe UI", 14, "bold")
# ).pack(pady=20)

# # tk.Button(
# #     root,
# #     text="Process Single File",
# #     width=25,
# #     height=2,
# #     command=process_single
# # ).pack(pady=10)

# # tk.Button(
# #     root,
# #     text="Process Folder",
# #     width=25,
# #     height=2,
# #     command=process_folder
# # ).pack(pady=10)

# # tk.Button(
# #     root,
# #     text="Analyse Force Folder",
# #     width=25,
# #     height=2,
# #     command=analyse_force_folder
# # ).pack(pady=10)

# # tk.Button(
# #     root,
# #     text="Analyse Calibration Folder",
# #     width=25,
# #     height=2,
# #     command=analyse_calibration_folder
# # ).pack(pady=10)

# # tk.Button(
# #     root,
# #     text="Plot Force & Voltage",
# #     width=25,
# #     height=2,
# #     command=plot_one_file
# # ).pack(pady=10)



# # tk.Button(
# #     root,
# #     text="Create Freq Heatmap",
# #     width=25,
# #     height=2,
# #     command=create_heatmap
# # ).pack(pady=10)

# # tk.Button(
# #     root,
# #     text="Force Only Analysis",
# #     width=25,
# #     height=2,
# #     command=force_only_analysis_gui
# # ).pack(pady=10)

# tk.Button(
#     root,
#     text="Plot Force & Voltage vs Time",
#     width=35,
#     height=2,
#     command=plot_force_voltage
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="1 - Analyse Z Calibration",
#     width=35,
#     height=2,
#     command=analyse_calibration
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="2 - Comparing Testing Frequencies",
#     width=35,
#     height=2,
#     command=full_frequency_analysis_folder
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="3 - Analyse Force-Control Method",
#     width=35,
#     height=2,
#     command=analyse_force_control_method_gui
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="3 - Compare Force-Control Methods",
#     width=35,
#     height=2,
#     command=compare_force_control_methods_gui
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="4 - Analyse Voltage Convergence",
#     width=35,
#     height=2,
#     command=voltage_convergence
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="Repeatability Analysis",
#     width=25,
#     height=2,
#     command=repeatability_analysis
# ).pack(pady=10)
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
    command=compare_force_control_methods_gui
).grid(row=3, column=0, pady=5, sticky="ew")

tk.Button(
    rig_frame,
    text="4 - Analyse Voltage Convergence",
    width=30,
    height=2,
    command=voltage_convergence
).grid(row=4, column=0, pady=5, sticky="ew")

root.mainloop()