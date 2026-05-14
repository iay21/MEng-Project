import tkinter as tk
from tkinter import filedialog, messagebox
import os

import Processing_functions  # your file


# =========================
# PROCESS SINGLE FILE
# =========================

def process_single():

    file = filedialog.askopenfilename(
        filetypes=[("CSV files", "*.csv")]
    )

    if not file:
        return

    try:
        output = Processing_functions.process_data(file)

        messagebox.showinfo(
            "Success",
            f"Processed file saved as:\n{output}"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))

def analyse_force_file():

    file_path = filedialog.askopenfilename(
        title="Select force data file",
        filetypes=[("CSV files", "*.csv")]
    )

    if not file_path:
        return

    try:

        Processing_functions.analyse_force_cycles(
            file_path,
            target_force=None  # Will read from metadata
        )

        messagebox.showinfo(
            "Success",
            "Force analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )
# =========================
# PROCESS FOLDER
# =========================

def process_folder():

    folder = filedialog.askdirectory()

    if not folder:
        return

    try:
        count = 0

        for file in os.listdir(folder):
            if file.endswith(".csv") and not file.endswith("_analysed.csv"):

                full_path = os.path.join(folder, file)
                Processing_functions.process_data(full_path)
                count += 1

        messagebox.showinfo(
            "Done",
            f"Processed {count} files."
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


def analyse_force_folder():

    folder_path = filedialog.askdirectory(
        title="Select folder containing CSV files"
    )

    if not folder_path:
        return

    try:

        output_file = (
            Processing_functions.analyse_force_folder_to_excel(
                folder_path
            )
        )

        messagebox.showinfo(
            "Success",
            f"Combined Excel file created:\n\n{output_file}"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


def analyse_calibration_folder():

    folder_path = filedialog.askdirectory(
        title="Select calibration folder"
    )

    if not folder_path:
        return

    try:

        output_file = (
            Processing_functions
            .analyse_calibration_folder_to_excel(
                folder_path
            )
        )

        messagebox.showinfo(
            "Success",
            f"Calibration analysis saved:\n\n"
            f"{output_file}"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )



def full_analysis_folder():

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

def create_heatmap():

    folder_path = filedialog.askdirectory(
        title="Select master data folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.create_force_error_heatmap(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Heat map created!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )

def analyse_calibration():

    folder_path = filedialog.askdirectory(
        title="Select calibration data folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.analyse_calibration_folder(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Calibration analysis complete!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


def calibration_plots():

    folder_path = filedialog.askdirectory(
        title="Select calibration analysis folder"
    )

    if not folder_path:
        return

    try:

        Processing_functions.create_calibration_plots(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Calibration plots created!"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )

def force_only_analysis_gui():

    folder_path = filedialog.askdirectory(
        title="Select folder of force data"
    )

    if not folder_path:
        return

    try:

        Processing_functions.force_only_analysis(
            folder_path
        )

        messagebox.showinfo(
            "Success",
            "Force-only analysis complete!"
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
root.geometry("450x400")

tk.Label(
    root,
    text="Data Processing Tool",
    font=("Segoe UI", 14, "bold")
).pack(pady=20)

# tk.Button(
#     root,
#     text="Process Single File",
#     width=25,
#     height=2,
#     command=process_single
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="Process Folder",
#     width=25,
#     height=2,
#     command=process_folder
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="Analyse Force Folder",
#     width=25,
#     height=2,
#     command=analyse_force_folder
# ).pack(pady=10)

# tk.Button(
#     root,
#     text="Analyse Calibration Folder",
#     width=25,
#     height=2,
#     command=analyse_calibration_folder
# ).pack(pady=10)

tk.Button(
    root,
    text="Full Freq Comparision",
    width=25,
    height=2,
    command=full_analysis_folder
).pack(pady=10)

tk.Button(
    root,
    text="Create Freq Heatmap",
    width=25,
    height=2,
    command=create_heatmap
).pack(pady=10)

tk.Button(
    root,
    text="Force Only Analysis",
    width=25,
    height=2,
    command=force_only_analysis_gui
).pack(pady=10)

tk.Button(
    root,
    text="Analyse Z Calibration",
    width=25,
    height=2,
    command=analyse_calibration
).pack(pady=10)

tk.Button(
    root,
    text="Z Calibration Plots",
    width=25,
    height=2,
    command=calibration_plots
).pack(pady=10)

root.mainloop()