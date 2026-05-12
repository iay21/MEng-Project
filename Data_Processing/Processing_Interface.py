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

        import os

        csv_files = [
            f for f in os.listdir(folder_path)
            if f.endswith(".csv")
        ]

        for file in csv_files:

            full_path = os.path.join(folder_path, file)

            Processing_functions.analyse_force_cycles(
                full_path,
                target_force=None  # Will read from metadata
            )

        messagebox.showinfo(
            "Success",
            f"Processed {len(csv_files)} files!"
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
root.geometry("450x350")

tk.Label(
    root,
    text="Data Processing Tool",
    font=("Segoe UI", 14, "bold")
).pack(pady=20)

tk.Button(
    root,
    text="Process Single File",
    width=25,
    height=2,
    command=process_single
).pack(pady=10)

tk.Button(
    root,
    text="Process Folder",
    width=25,
    height=2,
    command=process_folder
).pack(pady=10)

force_button = tk.Button(
    root,
    text="Analyse Force File",
    command=analyse_force_file,
    width=25,
    height=2
)

force_button.pack(pady=5)

force_folder_button = tk.Button(
    root,
    text="Analyse Force Folder",
    command=analyse_force_folder,
    width=25,
    height=2
)

force_folder_button.pack(pady=5)

root.mainloop()