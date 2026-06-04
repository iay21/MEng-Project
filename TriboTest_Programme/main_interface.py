import tkinter as tk
from tkinter import scrolledtext
from tkinter import simpledialog
from tkinter import filedialog
from tkinter import messagebox
import threading
import sys
import os
import Testing_functions
import time

# NEW imports for graph
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# =====================================================
# GUI WINDOW
# =====================================================

root = tk.Tk()
root.title("Triboelectric Test Rig Controller")
root.geometry("1450x820")
root.minsize(1200, 700)


def rebuild_live_plot():
    global fig, canvas, ax_force, ax_voltage, ax_current

    for widget in graph_frame.winfo_children():
        widget.destroy()

    axes_needed = ["force"]

    if Testing_functions.measurement_mode in ["VOLTAGE", "DUAL"]:
        axes_needed.append("voltage")

    if Testing_functions.measurement_mode in ["CURRENT", "DUAL"]:
        axes_needed.append("current")

    fig, axes = plt.subplots(
        len(axes_needed),
        1,
        figsize=(8, 6),
        dpi=100,
        sharex=True
    )

    if len(axes_needed) == 1:
        axes = [axes]

    ax_force = axes[0]
    ax_voltage = None
    ax_current = None

    axis_index = 1

    if "voltage" in axes_needed:
        ax_voltage = axes[axis_index]
        axis_index += 1

    if "current" in axes_needed:
        ax_current = axes[axis_index]

    graph_frame.config(
        text=f"Live Data — {Testing_functions.measurement_mode} mode"
    )

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=graph_frame)
    canvas.get_tk_widget().pack(fill="both", expand=True)



def startup_measurement_popup():
    dialog = tk.Toplevel(root)
    dialog.title("Measurement Mode Setup")
    dialog.geometry("520x320")
    dialog.transient(root)
    dialog.grab_set()
    dialog.lift()
    dialog.focus_force()

    mode_var = tk.StringVar(value="VOLTAGE")
    voltage_resource_var = tk.StringVar(
        value=Testing_functions.VOLTAGE_KEITHLEY_RESOURCE
    )
    current_resource_var = tk.StringVar(
        value=Testing_functions.CURRENT_KEITHLEY_RESOURCE
    )

    frame = tk.Frame(dialog, padx=15, pady=15)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Select acquisition mode",
        font=("Segoe UI", 12, "bold")
    ).pack(anchor="w", pady=(0, 8))

    tk.OptionMenu(
        frame,
        mode_var,
        "FORCE",
        "VOLTAGE",
        "CURRENT",
        "DUAL"
    ).pack(fill="x", pady=5)

    tk.Label(frame, text="Voltage Keithley VISA resource").pack(anchor="w")
    tk.Entry(frame, textvariable=voltage_resource_var).pack(fill="x", pady=5)

    tk.Label(frame, text="Current Keithley VISA resource").pack(anchor="w")
    tk.Entry(frame, textvariable=current_resource_var).pack(fill="x", pady=5)

    tk.Label(
        frame,
        text="For one Keithley, choose VOLTAGE or CURRENT and put the connected Keithley resource in that box.",
        wraplength=470
    ).pack(anchor="w", pady=8)

    def start():
        mode = mode_var.get().upper()

        Testing_functions.measurement_mode = mode
        Testing_functions.VOLTAGE_KEITHLEY_RESOURCE = voltage_resource_var.get().strip()
        Testing_functions.CURRENT_KEITHLEY_RESOURCE = current_resource_var.get().strip()

        dialog.destroy()

        threading.Thread(
            target=Testing_functions.initialise_rig,
            daemon=True
        ).start()

        rebuild_live_plot()

    tk.Button(
        frame,
        text="Start Rig",
        command=start,
        height=2
    ).pack(fill="x", pady=10)

    root.wait_window(dialog)


# # Start hardware in background
# threading.Thread(
#     target=Testing_functions.initialise_rig,
#     daemon=True
# ).start()

running = True

# =====================================================
# MAIN LAYOUT
# =====================================================

root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=0)   # controls
root.grid_columnconfigure(1, weight=1)   # graph + console

# =====================================================
# LEFT PANEL (SCROLLABLE CONTROLS)
# =====================================================

left_container = tk.Frame(root)
left_container.grid(row=0, column=0, sticky="ns")

left_canvas = tk.Canvas(left_container, width=420)
left_scroll = tk.Scrollbar(
    left_container,
    orient="vertical",
    command=left_canvas.yview
)

controls_frame = tk.Frame(left_canvas)

controls_frame.bind(
    "<Configure>",
    lambda e: left_canvas.configure(
        scrollregion=left_canvas.bbox("all")
    )
)

left_canvas.create_window(
    (0, 0),
    window=controls_frame,
    anchor="nw"
)

left_canvas.configure(yscrollcommand=left_scroll.set)

left_canvas.pack(side="left", fill="both", expand=True)
left_scroll.pack(side="right", fill="y")

def _on_mousewheel(event):
    left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

# =====================================================
# RIGHT PANEL (GRAPH + CONSOLE)
# =====================================================

right_frame = tk.Frame(root)
right_frame.grid(row=0, column=1, sticky="nsew")

right_frame.grid_rowconfigure(0, weight=3)   # graph larger
right_frame.grid_rowconfigure(1, weight=2)   # console
right_frame.grid_columnconfigure(0, weight=1)


# =====================================================
# GRAPH
# =====================================================


graph_frame = tk.LabelFrame(
    right_frame,
    text="Live Force, Voltage and Current"
)
graph_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)


fig = None
canvas = None
ax_force = None
ax_voltage = None
ax_current = None


force_history = deque(maxlen=500)
voltage_history = deque(maxlen=500)
current_history = deque(maxlen=500)



start_time = time.monotonic()


def update_graph():

    if not running:
        return

    try:
        # -----------------------------
        # Latest values
        # -----------------------------
        f = Testing_functions.latest_force
        v = Testing_functions.latest_voltage
        # i_nA = Testing_functions.latest_current_A

        i_A = Testing_functions.latest_current_A
        if i_A is not None:
            i_uA = i_A * 1e6
        else:
            i_uA = None

        t = time.monotonic() - start_time

        WINDOW = 60.0  # seconds visible window

        # -----------------------------
        # Store data
        # -----------------------------
        if f is not None:
            force_history.append((t, f))

        if v is not None:
            voltage_history.append((t, v))

        if i_uA is not None:
            current_history.append((t, i_uA))

        # -----------------------------
        # Keep only last 60 seconds
        # -----------------------------
        while force_history and (t - force_history[0][0]) > WINDOW:
            force_history.popleft()

        while voltage_history and (t - voltage_history[0][0]) > WINDOW:
            voltage_history.popleft()

        while current_history and (t - current_history[0][0]) > WINDOW:
            current_history.popleft()

        # Need enough data
        if len(force_history) < 2:
            root.after(100, update_graph)
            return
        if(
            len(force_history) < 2 
            and len(voltage_history) < 2 
            and len(current_history) < 2
        ):
            root.after(100, update_graph)
            return
        
        ax_force.cla()

        if ax_voltage is not None:
            ax_voltage.cla()

        if ax_current is not None:
            ax_current.cla()


        # -----------------------------
        # Prepare data
        # -----------------------------

        if len(force_history) > 0:
            t_f, f_vals = zip(*force_history)
        else:
            t_f, f_vals = [], []

        if len(voltage_history) > 0:
            t_v, v_vals = zip(*voltage_history)
        else:
            t_v, v_vals = [], []

        if len(current_history) > 0:
            t_i, i_vals = zip(*current_history)
        else:
            t_i, i_vals = [], []

        # -----------------------------
        # FORCE
        # -----------------------------
        ax_force.plot(t_f, f_vals, color="tab:red")
        ax_force.set_ylabel("Force (N)", color="tab:red")
        ax_force.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        ax_force.tick_params(axis='y', labelcolor="tab:red")
        # -----------------------------
        # VOLTAGE
        # -----------------------------
        if ax_voltage is not None:
            ax_voltage.plot(t_v, v_vals, color="tab:blue")
            ax_voltage.set_ylabel("Voltage (V)", color="tab:blue")
            ax_voltage.tick_params(axis='y', labelcolor="tab:blue")
            ax_voltage.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
        # -----------------------------
        # CURRENT
        # -----------------------------
        if ax_current is not None:
            ax_current.plot(t_i, i_vals, color="tab:green")
            ax_current.set_ylabel("Current (µA)", color="tab:green")
            ax_current.set_xlabel("Time (s)")
            ax_current.tick_params(axis='y', labelcolor="tab:green")
            ax_current.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

        # -----------------------------
        # X axis
        # -----------------------------
        for ax in [ax_force, ax_voltage, ax_current]:
            if ax is not None:
                ax.set_xlim(max(0, t - WINDOW), t)

        # -----------------------------
        # Y axis padding helper
        # -----------------------------
        def set_padded_ylim(ax, values, default_min, default_max, min_pad):
            if len(values) == 0:
                ax.set_ylim(default_min, default_max)
                return

            data_min = min(values)
            data_max = max(values)
            data_range = max(1e-6, data_max - data_min)
            pad = max(min_pad, 0.05 * data_range)

            ax.set_ylim(
                min(default_min, data_min - pad),
                max(default_max, data_max + pad)
            )

        set_padded_ylim(ax_force, f_vals, -1, 11, 0.5)

        if ax_voltage is not None:
            set_padded_ylim(ax_voltage, v_vals, -5, 5, 0.1)

        if ax_current is not None:
            set_padded_ylim(ax_current, i_vals, -0.5, 0.5, 0.05)



        fig.tight_layout()
        canvas.draw_idle()

    except Exception as e:
        print("Graph error:", e)

    root.after(100, update_graph)

startup_measurement_popup()
# =====================================================
# CONSOLE
# =====================================================

console_frame = tk.LabelFrame(
    right_frame,
    text="System Console",
    padx=5,
    pady=5
)
console_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

output = scrolledtext.ScrolledText(
    console_frame,
    wrap="word",
    font=("Consolas", 10)
)
output.pack(fill="both", expand=True)

# =====================================================
# COLOUR TAGS
# =====================================================

output.tag_config("error", foreground="red")
output.tag_config("command", foreground="blue")
output.tag_config("printer", foreground="gray40")
output.tag_config("success", foreground="green")
output.tag_config("normal", foreground="black")

# =====================================================
# LOGGER
# =====================================================

class Logger:
    def write(self, msg):

        if not msg.strip():
            return

        msg = msg.rstrip()

        def append():

            lower = msg.lower()

            if "error" in lower:
                tag = "error"

            elif msg.startswith(">>"):
                tag = "command"

            elif "printer:" in lower:
                tag = "printer"

            elif "updated" in lower or "ready" in lower:
                tag = "success"

            else:
                tag = "normal"

            output.insert("end", msg + "\n", tag)
            output.see("end")

        root.after(0, append)

    def flush(self):
        pass

sys.stdout = Logger()
sys.stderr = Logger()

# =====================================================
# RUN COMMANDS
# =====================================================

def run(cmd):

    def worker():
        try:
            print(">> " + cmd)
            eval(cmd, {"Testing_functions": Testing_functions})

        except Exception as e:
            print("ERROR:", e)

    threading.Thread(target=worker, daemon=True).start()

def safe_stop():
    """Button callback - gracefully exits after cleanup"""
    print("SAFE STOP pressed - cleaning up and exiting!")
    sys.stdout.flush()
    Testing_functions.stop_test()  # Close log file
    Testing_functions.cleanup_keithleys()  # Close instruments
    os._exit(1)

# =====================================================
# TITLE
# =====================================================

tk.Label(
    controls_frame,
    text="Triboelectric Rig Controls",
    font=("Segoe UI", 16, "bold")
).pack(pady=10)

# =====================================================
# BUTTONS
# =====================================================

save_dir_var = tk.StringVar(value=Testing_functions.SAVE_DIR)

folder_frame = tk.LabelFrame(
    controls_frame,
    text="Data Save Folder",
    padx=10,
    pady=10
)
folder_frame.pack(fill="x", padx=10, pady=(0, 5))

folder_label = tk.Label(
    folder_frame,
    textvariable=save_dir_var,
    anchor="w",
    justify="left",
    wraplength=380
)
folder_label.pack(fill="x", pady=(0, 5))


def choose_save_folder():
    initial_dir = save_dir_var.get()
    if not os.path.isdir(initial_dir):
        initial_dir = os.path.expanduser("~")

    folder = filedialog.askdirectory(
        parent=root,
        title="Select Folder to Save Data",
        initialdir=initial_dir
    )

    if folder:
        Testing_functions.SAVE_DIR = folder
        save_dir_var.set(folder)
        print(f"Save folder set to: {folder}")


tk.Button(
    folder_frame,
    text="Choose Save Folder",
    command=choose_save_folder,
    width=38,
    height=2
).pack()

button_frame = tk.LabelFrame(
    controls_frame,
    text="Functions",
    padx=10,
    pady=10
)
button_frame.pack(fill="x", padx=10, pady=5)

buttons = [
    ("Setup", "Testing_functions.setup()"),
    ("Calibrate Force", "Testing_functions.calibrate_z()"),
    ("Contact Cycle", "Testing_functions.contact_cycle()"),
    ("Slide Cycle", "Testing_functions.sliding_cycle()"),
    ("Reset", "Testing_functions.reset()"),
    ("XY Home", "Testing_functions.x_y_centre()"),
    # ("STOP", "Testing_functions.emergency_stop()"),
    # ("SAFE LOG STOP", "Testing_functions.emergency_stop()")
]

def change_measurement_mode_gui():

    dialog = tk.Toplevel(root)
    dialog.title("Change Measurement Mode")
    dialog.geometry("520x280")
    dialog.transient(root)
    dialog.grab_set()
    dialog.lift()
    dialog.focus_force()

    mode_var = tk.StringVar(value=Testing_functions.measurement_mode)
    voltage_resource_var = tk.StringVar(value=Testing_functions.VOLTAGE_KEITHLEY_RESOURCE)
    current_resource_var = tk.StringVar(value=Testing_functions.CURRENT_KEITHLEY_RESOURCE)

    frame = tk.Frame(dialog, padx=15, pady=15)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Measurement Mode").pack(anchor="w")
    tk.OptionMenu(frame, mode_var, "FORCE", "VOLTAGE", "CURRENT", "DUAL").pack(fill="x", pady=5)

    tk.Label(frame, text="Voltage Keithley Resource").pack(anchor="w")
    tk.Entry(frame, textvariable=voltage_resource_var).pack(fill="x", pady=5)

    tk.Label(frame, text="Current Keithley Resource").pack(anchor="w")
    tk.Entry(frame, textvariable=current_resource_var).pack(fill="x", pady=5)

    def apply_change():
        try:
            Testing_functions.set_measurement_mode(
                mode_var.get(),
                voltage_resource_var.get().strip(),
                current_resource_var.get().strip()
            )

            dialog.destroy()
            rebuild_live_plot()

            messagebox.showinfo(
                "Mode Changed",
                f"Measurement mode is now {Testing_functions.measurement_mode}"
            )

        except Exception as e:
            messagebox.showerror("Error", str(e))

    tk.Button(
        frame,
        text="Apply Mode Change",
        command=apply_change,
        height=2
    ).pack(fill="x", pady=10)

def prompt_and_start_test(test_type):

    dialog = tk.Toplevel(root)
    dialog.title("Test Setup")
    dialog.geometry("350x300")
    dialog.transient(root)
    dialog.grab_set()  # makes it modal (blocks main window)

    # bring to front
    dialog.lift()
    dialog.focus_force()

    # -----------------------------
    # VARIABLES
    # -----------------------------
    material_var = tk.StringVar()
    counter_var = tk.StringVar()
    resistance_var = tk.StringVar(value="1M")

    # -----------------------------
    # LAYOUT
    # -----------------------------
    frame = tk.Frame(dialog, padx=10, pady=10)
    frame.pack(fill="both", expand=True)

    # Primary material
    tk.Label(frame, text="Primary Material").pack(anchor="w")
    tk.Entry(frame, textvariable=material_var).pack(fill="x", pady=5)

    # Counter material
    tk.Label(frame, text="Counter Material").pack(anchor="w")
    tk.Entry(frame, textvariable=counter_var).pack(fill="x", pady=5)

    # Load resistance dropdown
    tk.Label(frame, text="Load Resistance").pack(anchor="w")
    resistance_options = [
        "short", "10k", "100k", "549k", "1M", "5.1M",
        "10M", "50M", "100M", "1G", "open"
    ]
    tk.OptionMenu(frame, resistance_var, *resistance_options).pack(fill="x", pady=5)

    # -----------------------------
    # HELPER: convert resistance to Ohms
    # -----------------------------
    def parse_resistance(r_str):
        s = str(r_str).strip().lower()
        # special keywords
        if s in ("short", "0", "short-circuit"):
            return 0.0
        if s in ("open", "inf", "infinity", "infinite"):
            return float("inf")

        multipliers = {
            "k": 1e3,
            "m": 1e6,
            "g": 1e9
        }
        if len(s) > 1 and s[-1] in multipliers:
            try:
                return float(s[:-1]) * multipliers[s[-1]]
            except ValueError:
                raise ValueError(f"Invalid resistance value: {r_str}")
        try:
            return float(s)
        except ValueError:
            raise ValueError(f"Invalid resistance value: {r_str}")

    # -----------------------------
    # START BUTTON
    # -----------------------------
    def start():
        material = material_var.get().strip()
        counter = counter_var.get().strip()


        if not material or not counter:
            print("Test cancelled (missing material).")
            dialog.destroy()
            return

        resistance_ohm = parse_resistance(resistance_var.get())
        mode = Testing_functions.measurement_mode

        dialog.destroy()

        threading.Thread(
            target=lambda: Testing_functions.start_test(
                test_type,
                material,
                counter,
                resistance_ohm,
                mode,
                Testing_functions.contact_force
            ),
            daemon=True
        ).start()

    tk.Button(frame, text="Start Test", command=start, height=2).pack(pady=10)

    # allow Enter key to submit
    dialog.bind("<Return>", lambda event: start())
    

def prompt_and_start_full_force_range():

    dialog = tk.Toplevel(root)
    dialog.title("Full Force Range Test Setup")
    dialog.geometry("350x300")
    dialog.transient(root)
    dialog.grab_set()  # makes it modal (blocks main window)

    # bring to front
    dialog.lift()
    dialog.focus_force()

    # -----------------------------
    # VARIABLES
    # -----------------------------
    material_var = tk.StringVar()
    counter_var = tk.StringVar()
    resistance_var = tk.StringVar(value="1M")

    # -----------------------------
    # LAYOUT
    # -----------------------------
    frame = tk.Frame(dialog, padx=10, pady=10)
    frame.pack(fill="both", expand=True)

    # Primary material
    tk.Label(frame, text="Primary Material").pack(anchor="w")
    tk.Entry(frame, textvariable=material_var).pack(fill="x", pady=5)

    # Counter material
    tk.Label(frame, text="Counter Material").pack(anchor="w")
    tk.Entry(frame, textvariable=counter_var).pack(fill="x", pady=5)

    # Load resistance dropdown
    tk.Label(frame, text="Load Resistance").pack(anchor="w")
    resistance_options = [
        "short", "10k", "100k", "549k", "1M", "5.1M",
        "10M", "50M", "100M", "1G", "open"
    ]
    tk.OptionMenu(frame, resistance_var, *resistance_options).pack(fill="x", pady=5)

    # -----------------------------
    # HELPER: convert resistance to Ohms
    # -----------------------------
    def parse_resistance(r_str):
        s = str(r_str).strip().lower()
        # special keywords
        if s in ("short", "0", "short-circuit"):
            return 0.0
        if s in ("open", "inf", "infinity", "infinite"):
            return float("inf")

        multipliers = {
            "k": 1e3,
            "m": 1e6,
            "g": 1e9
        }
        if len(s) > 1 and s[-1] in multipliers:
            try:
                return float(s[:-1]) * multipliers[s[-1]]
            except ValueError:
                raise ValueError(f"Invalid resistance value: {r_str}")
        try:
            return float(s)
        except ValueError:
            raise ValueError(f"Invalid resistance value: {r_str}")

    # -----------------------------
    # START BUTTON
    # -----------------------------
    def start():
        material = material_var.get().strip()
        counter = counter_var.get().strip()

        if not material or not counter:
            print("Test cancelled (missing material).")
            dialog.destroy()
            return

        resistance_ohm = parse_resistance(resistance_var.get())
        mode = Testing_functions.measurement_mode

        dialog.destroy()

        threading.Thread(
            target=lambda: Testing_functions.run_contact_full_force_range(
                material,
                counter,
                resistance_ohm,
                mode
            ),
            daemon=True
        ).start()

    tk.Button(frame, text="Start Full Force Range Test", command=start, height=2).pack(pady=10)

    # allow Enter key to submit
    dialog.bind("<Return>", lambda event: start())
    

def prompt_and_start_impedance_test():

    dialog = tk.Toplevel(root)
    dialog.title("Impedance Test Setup")
    dialog.geometry("350x240")
    dialog.transient(root)
    dialog.grab_set()
    dialog.lift()
    dialog.focus_force()

    material_var = tk.StringVar()
    counter_var = tk.StringVar()
   
    frame = tk.Frame(dialog, padx=10, pady=10)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Primary Material").pack(anchor="w")
    tk.Entry(frame, textvariable=material_var).pack(fill="x", pady=5)

    tk.Label(frame, text="Counter Material").pack(anchor="w")
    tk.Entry(frame, textvariable=counter_var).pack(fill="x", pady=5)


    def start():
        material = material_var.get().strip()
        counter = counter_var.get().strip()
        mode = Testing_functions.measurement_mode

        if not material or not counter:
            messagebox.showerror("Error", "Please enter both materials.")
            return

        dialog.destroy()

        def worker():

            for label, resistance in Testing_functions.IMPEDANCE_RESISTANCES:

                confirm_event = threading.Event()

                def resistance_popup():
                    popup = tk.Toplevel(root)
                    popup.title("Set Resistance")
                    popup.geometry("360x160")
                    popup.transient(root)
                    popup.grab_set()
                    popup.lift()
                    popup.focus_force()

                    frame = tk.Frame(popup, padx=15, pady=15)
                    frame.pack(fill="both", expand=True)

                    tk.Label(
                        frame,
                        text=f"Set the resistance to {label}",
                        font=("Segoe UI", 12, "bold")
                    ).pack(pady=(0, 10))

                    tk.Label(
                        frame,
                        text="Press Done once the resistor/load is correctly connected.",
                        wraplength=320
                    ).pack(pady=(0, 10))

                    def done():
                        popup.destroy()
                        confirm_event.set()

                    tk.Button(
                        frame,
                        text="Done",
                        command=done,
                        width=20,
                        height=2
                    ).pack()

                    popup.protocol("WM_DELETE_WINDOW", done)

                root.after(0, resistance_popup)
                confirm_event.wait()

                Testing_functions.run_single_impedance_test(
                    material,
                    counter,
                    resistance,
                    mode,
                    label
                )

            print("✅ Impedance test sequence complete.")

        threading.Thread(target=worker, daemon=True).start()

    tk.Button(
        frame,
        text="Start Impedance Test",
        command=start,
        height=2
    ).pack(pady=10, fill="x")

    dialog.bind("<Return>", lambda event: start())


def prompt_and_start_fixed_load_force_test(title, load_resistance, required_mode, test_category):

    if Testing_functions.measurement_mode != required_mode:
        messagebox.showwarning(
            "Wrong Mode",
            f"{title} should be run in {required_mode} mode.\n"
            f"Current mode is {Testing_functions.measurement_mode}.\n\n"
            "Use Change Measurement Mode first."
        )
        return

    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.geometry("350x220")
    dialog.transient(root)
    dialog.grab_set()
    dialog.lift()
    dialog.focus_force()

    material_var = tk.StringVar()
    counter_var = tk.StringVar()

    frame = tk.Frame(dialog, padx=10, pady=10)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Primary Material").pack(anchor="w")
    tk.Entry(frame, textvariable=material_var).pack(fill="x", pady=5)

    tk.Label(frame, text="Counter Material").pack(anchor="w")
    tk.Entry(frame, textvariable=counter_var).pack(fill="x", pady=5)

    tk.Label(
        frame,
        text=f"Mode: {Testing_functions.measurement_mode}",
        font=("Segoe UI", 9, "italic")
    ).pack(anchor="w", pady=5)

    def start():
        material = material_var.get().strip()
        counter = counter_var.get().strip()

        if not material or not counter:
            messagebox.showerror("Error", "Please enter both materials.")
            return

        dialog.destroy()

        threading.Thread(
            target=lambda: Testing_functions.run_contact_full_force_range(
                material,
                counter,
                load_resistance,
                Testing_functions.measurement_mode,
                test_category=test_category
            ),
            daemon=True
        ).start()

    tk.Button(
        frame,
        text=f"Start {title}",
        command=start,
        height=2
    ).pack(fill="x", pady=10)


def prompt_and_start_voc_test():

    prompt_and_start_fixed_load_force_test(
        title="VOC Force Test",
        load_resistance=float("inf"),
        required_mode="VOLTAGE",
        test_category="voc"
    )


def prompt_and_start_isc_test():

    prompt_and_start_fixed_load_force_test(
        title="ISC Force Test",
        load_resistance=0,
        required_mode="CURRENT",
        test_category="isc"
    )

    

def prompt_and_start_matched_load_test():

    dialog = tk.Toplevel(root)
    dialog.title("Matched Load Test Setup")
    dialog.geometry("350x260")
    dialog.transient(root)
    dialog.grab_set()
    dialog.lift()
    dialog.focus_force()

    material_var = tk.StringVar()
    counter_var = tk.StringVar()
    resistance_var = tk.StringVar(value="10M")

    frame = tk.Frame(dialog, padx=10, pady=10)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Primary Material").pack(anchor="w")
    tk.Entry(frame, textvariable=material_var).pack(fill="x", pady=5)

    tk.Label(frame, text="Counter Material").pack(anchor="w")
    tk.Entry(frame, textvariable=counter_var).pack(fill="x", pady=5)

    tk.Label(frame, text="Matched Load Resistance").pack(anchor="w")
    tk.Entry(frame, textvariable=resistance_var).pack(fill="x", pady=5)

    tk.Label(
        frame,
        text=f"Current mode: {Testing_functions.measurement_mode}",
        font=("Segoe UI", 9, "italic")
    ).pack(anchor="w", pady=5)

    def parse_resistance(r_str):
        r_str = r_str.strip()
        multipliers = {"k": 1e3, "M": 1e6, "G": 1e9}

        if r_str[-1] in multipliers:
            return float(r_str[:-1]) * multipliers[r_str[-1]]

        return float(r_str)

    def start():
        material = material_var.get().strip()
        counter = counter_var.get().strip()

        if not material or not counter:
            messagebox.showerror("Error", "Please enter both materials.")
            return

        resistance = parse_resistance(resistance_var.get())

        if Testing_functions.measurement_mode == "VOLTAGE":
            test_category = "matched_voltage"

        elif Testing_functions.measurement_mode == "CURRENT":
            test_category = "matched_current"

        else:
            messagebox.showerror(
                "Error",
                "Matched-load test should be run in VOLTAGE or CURRENT mode."
            )
            return

        dialog.destroy()

        threading.Thread(
            target=lambda: Testing_functions.run_contact_full_force_range(
                material,
                counter,
                resistance,
                Testing_functions.measurement_mode,
                test_category=test_category
            ),
            daemon=True
        ).start()


    tk.Button(frame, text="Start Matched-Load Test", command=start, height=2).pack(fill="x", pady=10)


def prompt_and_start_z_calibration_test():

    dialog = tk.Toplevel(root)
    dialog.title("Z Calibration Test Setup")
    dialog.geometry("350x250")
    dialog.transient(root)
    dialog.grab_set()

    dialog.lift()
    dialog.focus_force()

    # -------- LAYOUT --------
    frame = tk.Frame(dialog, padx=10, pady=10)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Z Calibration Test", font=("Arial", 12, "bold")).pack(anchor="w", pady=10)
    tk.Label(frame, text="This will run calibration across all force ranges", wraplength=300).pack(anchor="w")
    tk.Label(frame, text="(10 cycles per force level)", wraplength=300).pack(anchor="w", pady=10)

    # -------- TEST NAME INPUT --------
    tk.Label(frame, text="Test Name/Material:").pack(anchor="w")
    test_entry = tk.Entry(frame, width=30)
    test_entry.pack(anchor="w", pady=5)
    test_entry.insert(0, Testing_functions.z_cal_test)  # Default value

    # -------- START BUTTON --------
    def start():
        test_name = test_entry.get().strip()
        if not test_name:
            tk.messagebox.showerror("Error", "Please enter a test name.")
            return
        Testing_functions.z_cal_test = test_name
        dialog.destroy()
        threading.Thread(
            target=lambda: Testing_functions.run_z_calibration_test(),
            daemon=True
        ).start()

    tk.Button(frame, text="Start Calibration Test", command=start, height=2).pack(pady=10, fill="x")
    dialog.bind("<Return>", lambda event: start())



for i, (txt, cmd) in enumerate(buttons):

    tk.Button(
        button_frame,
        text=txt,
        width=18,
        height=2,
        command=lambda c=cmd: run(c)
    ).grid(row=i//2, column=i%2, padx=5, pady=5)


extra_buttons = [
    ("Change Measurement Mode", lambda: change_measurement_mode_gui()),
    ("Run Impedance Test", lambda: prompt_and_start_impedance_test()),
    ("Run VOC Force Test", lambda: prompt_and_start_voc_test()),
    ("Run ISC Force Test", lambda: prompt_and_start_isc_test()),
    ("Run Matched-Load Test", lambda: prompt_and_start_matched_load_test()),
    ("Run Z Calibration Test", lambda: prompt_and_start_z_calibration_test()),
]

start_row = (len(buttons) + 1) // 2

for j, (label, action) in enumerate(extra_buttons):
    tk.Button(
        button_frame,
        text=label,
        width=38,
        height=2,
        command=action
    ).grid(row=start_row + j, column=0, columnspan=2, padx=5, pady=5)

# SAFE STOP BUTTON
tk.Button(
    button_frame,
    text="CLOSE WINDOW",
    bg="blue",
    fg="white",
    width=38,
    height=2,
    command=safe_stop
).grid(row=99, column=0, columnspan=2, pady=10)

# EMERGENCY STOP BUTTON
tk.Button(
    button_frame,
    text="EMERGENCY STOP",
    bg="red",
    fg="white",
    width=38,
    height=2,
    command=lambda: Testing_functions.emergency_stop()  
).grid(row=100, column=0, columnspan=2, pady=10)


# =====================================================
# DIRECT GCODE
# =====================================================

gcode_frame = tk.LabelFrame(
    controls_frame,
    text="Direct Printer GCODE",
    padx=10,
    pady=10
)
gcode_frame.pack(fill="x", padx=10, pady=5)

gcode = tk.Entry(gcode_frame)
gcode.pack(fill="x", pady=5)

tk.Button(
    gcode_frame,
    text="Send GCODE",
    command=lambda: run(
        f'Testing_functions.send_gcode("{gcode.get()}")'
    )
).pack(fill="x")

# =====================================================
# VARIABLES
# =====================================================

vars_frame = tk.LabelFrame(
    controls_frame,
    text="Variables",
    padx=10,
    pady=10
)
vars_frame.pack(fill="x", padx=10, pady=5)

vars_list = [
    "contact_speed",
    "slide_speed",
    "no_contact_cycles",
    "no_slide_cycles",
    "contact_force",
    "contact_frequency",
    "separation_height",
    "safe_force_limit",
    "touch_threshold",
    "cycle_force_tolerance",
    "initial_wait",
    "z_correct_delay",
    "z_correct_step"
]

for v in vars_list:

    row = tk.Frame(vars_frame)
    row.pack(fill="x", pady=2)

    tk.Label(
        row,
        text=v,
        width=24,
        anchor="w"
    ).pack(side="left")

    e = tk.Entry(row, width=10)
    e.insert(0, str(getattr(Testing_functions, v)))
    e.pack(side="left", padx=5)

    def updater(name=v, box=e):

        try:
            val = box.get().strip()
            current = getattr(Testing_functions, name)

            if isinstance(current, int):
                if "." in val or "e" in val.lower():
                    setattr(Testing_functions, name, float(val))
                else:
                    setattr(Testing_functions, name, int(val))

            elif isinstance(current, float):
                setattr(Testing_functions, name, float(val))

            else:
                setattr(Testing_functions, name, val)

            print(f"{name} updated to {getattr(Testing_functions, name)}")

        except Exception as e:
            print("ERROR:", e)

    tk.Button(
        row,
        text="Set",
        width=6,
        command=updater
    ).pack(side="right")

# =====================================================
# PYTHON COMMAND BOX
# =====================================================

cmd_frame = tk.LabelFrame(
    controls_frame,
    text="Run Python Command",
    padx=10,
    pady=10
)
cmd_frame.pack(fill="x", padx=10, pady=5)

cmd_entry = tk.Entry(cmd_frame)
cmd_entry.pack(fill="x", pady=5)

tk.Button(
    cmd_frame,
    text="Run Command",
    command=lambda: run(cmd_entry.get())
).pack(fill="x")

def on_close():
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

# =====================================================
# START
# =====================================================


print("GUI ready.")
update_graph()
root.mainloop()
