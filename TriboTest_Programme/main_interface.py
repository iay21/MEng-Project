import tkinter as tk
from tkinter import scrolledtext
from tkinter import simpledialog
from tkinter import filedialog
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

# Start hardware in background
threading.Thread(
    target=Testing_functions.initialise_rig,
    daemon=True
).start()

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

graph_frame = tk.LabelFrame(right_frame, text="Live Force (N)")
graph_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)


fig, ax1 = plt.subplots(figsize=(8, 4), dpi=100)
fig.tight_layout()

ax2 = ax1.twinx()  # second y-axis

canvas = FigureCanvasTkAgg(fig, master=graph_frame)
canvas.get_tk_widget().pack(fill="both", expand=True)

force_history = deque(maxlen=500)
voltage_history = deque(maxlen=500)


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

        t = time.monotonic() - start_time

        WINDOW = 60.0  # seconds visible window

        # -----------------------------
        # Store data
        # -----------------------------
        if f is not None:
            force_history.append((t, f))

        if v is not None:
            voltage_history.append((t, v))

        # -----------------------------
        # Keep only last 60 seconds
        # -----------------------------
        while force_history and (t - force_history[0][0]) > WINDOW:
            force_history.popleft()

        while voltage_history and (t - voltage_history[0][0]) > WINDOW:
            voltage_history.popleft()

        # Need enough data
        if len(force_history) < 2:
            root.after(100, update_graph)
            return

        t_f, f_vals = zip(*force_history)

        if len(voltage_history) > 0:
            t_v, v_vals = zip(*voltage_history)
        else:
            t_v, v_vals = [], []

        # -----------------------------
        # Clear plots
        # -----------------------------
        ax1.cla()
        ax2.cla()

        # -----------------------------
        # FORCE plot (left axis)
        # -----------------------------
        ax1.plot(t_f, f_vals, color="tab:red")
        ax1.set_ylabel("Force (N)", color="tab:red")
        ax1.tick_params(axis='y', labelcolor="tab:red")

        # -----------------------------
        # VOLTAGE plot (right axis)
        # -----------------------------
        ax2.plot(t_v, v_vals, color="tab:blue")
        ax2.set_ylabel("Voltage (V)", color="tab:blue")
        ax2.tick_params(axis='y', labelcolor="tab:blue")
        ax2.yaxis.set_label_position("right")
        ax2.yaxis.tick_right()

        # -----------------------------
        # X axis (scrolling 60s window)
        # -----------------------------
        ax1.set_xlim(max(0, t - WINDOW), t)
        ax1.set_xlabel("Time (s)", labelpad=8)
        ax1.tick_params(axis='x', rotation=25)

        # -----------------------------
        # FORCE Y axis (with padding to prevent clipping)
        # -----------------------------
        f_min_base, f_max_base = -1, 11
        f_data_min = min(f_vals)
        f_data_max = max(f_vals)

        f_range = max(1e-6, f_data_max - f_data_min)
        f_pad = max(0.5, 0.05 * f_range)

        ax1.set_ylim(
            min(f_min_base, f_data_min - f_pad),
            max(f_max_base, f_data_max + f_pad)
        )

        # Set ticks every 1N on force axis
        y_min, y_max = ax1.get_ylim()
        ax1.set_yticks(range(int(y_min), int(y_max) + 1))

        # -----------------------------
        # VOLTAGE Y axis (with padding)
        # -----------------------------
        v_min_base, v_max_base = -5, 5

        if len(v_vals) > 0:
            v_data_min = min(v_vals)
            v_data_max = max(v_vals)

            v_range = max(1e-6, v_data_max - v_data_min)
            v_pad = max(0.1, 0.05 * v_range)

            ax2.set_ylim(
                min(v_min_base, v_data_min - v_pad),
                max(v_max_base, v_data_max + v_pad)
            )
        else:
            ax2.set_ylim(v_min_base, v_max_base)

        # -----------------------------
        # Grid styling
        # -----------------------------
        ax1.grid(True, which="both", axis="both",
                 linestyle="--", linewidth=0.5, alpha=0.7)

        # -----------------------------
        # Layout cleanup
        # -----------------------------
        fig.tight_layout()
        fig.subplots_adjust(right=0.88)

        canvas.draw_idle()

    except Exception as e:
        print("Graph error:", e)

    root.after(100, update_graph)


# def update_graph():
#     global update_graph_job

#     if not running or not root.winfo_exists():
#         return
    
#     try:
#         f = Testing_functions.latest_force
#         if f is not None:
#             force_history.append(f)
#             time_history.append(time.monotonic() - start_time)
#         ax.clear()
#         ax.plot(time_history, force_history, linewidth=2)
#         ax.set_title("Live Force")
#         ax.set_ylabel("N")
#         ax.set_xlabel("Time (s)")
#         ax.grid(True)

#         canvas.draw()

#     except Exception as e:
#         print("Graph error:", e)

#     if running:
#         update_graph_job = root.after(100, update_graph)

# =====================================================
# SAFE STOP FUNCTION
# =====================================================

# def safe_stop():
#     global running, update_graph_job

#     print("SAFE STOP ACTIVATED")

#     running = False

#     try:
#         if update_graph_job:
#             root.after_cancel(update_graph_job)
#     except:
#         pass

#     try:
#         Testing_functions.stop_test()
#     except:
#         pass

#     try:
#         Testing_functions.emergency_stop()
#     except:
#         pass


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
    """Button callback - forcefully exits"""
    print("SAFE STOP pressed - killing process!")
    sys.stdout.flush()
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
    mode_var = tk.StringVar(value="VOLTAGE")

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
        "10k", "100k", "549k", "1M", "5.1M",
        "10M", "50M", "100M", "1G"
    ]
    tk.OptionMenu(frame, resistance_var, *resistance_options).pack(fill="x", pady=5)

    # Measurement mode dropdown
    tk.Label(frame, text="Measurement Mode").pack(anchor="w")
    tk.OptionMenu(frame, mode_var, "VOLTAGE", "CURRENT").pack(fill="x", pady=5)

    # -----------------------------
    # HELPER: convert resistance to Ohms
    # -----------------------------
    def parse_resistance(r_str):
        multipliers = {
            "k": 1e3,
            "M": 1e6,
            "G": 1e9
        }
        if r_str[-1] in multipliers:
            return float(r_str[:-1]) * multipliers[r_str[-1]]
        return float(r_str)

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
        mode = mode_var.get()

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
    mode_var = tk.StringVar(value="VOLTAGE")

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
        "10k", "100k", "549k", "1M", "5.1M",
        "10M", "50M", "100M", "1G"
    ]
    tk.OptionMenu(frame, resistance_var, *resistance_options).pack(fill="x", pady=5)

    # Measurement mode dropdown
    tk.Label(frame, text="Measurement Mode").pack(anchor="w")
    tk.OptionMenu(frame, mode_var, "VOLTAGE", "CURRENT").pack(fill="x", pady=5)

    # -----------------------------
    # HELPER: convert resistance to Ohms
    # -----------------------------
    def parse_resistance(r_str):
        multipliers = {
            "k": 1e3,
            "M": 1e6,
            "G": 1e9
        }
        if r_str[-1] in multipliers:
            return float(r_str[:-1]) * multipliers[r_str[-1]]
        return float(r_str)

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
        mode = mode_var.get()

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
    

# def prompt_and_start_test(test_type):

#     material = simpledialog.askstring(
#         "Material Name",
#         f"Enter material name for {test_type} test:"
#     )

#     if not material:
#         print("Test cancelled.")
#         return

#     threading.Thread(
#         target=lambda: Testing_functions.start_test(test_type, material),
#         daemon=True
#     ).start()

for i, (txt, cmd) in enumerate(buttons):

    tk.Button(
        button_frame,
        text=txt,
        width=18,
        height=2,
        command=lambda c=cmd: run(c)
    ).grid(row=i//2, column=i%2, padx=5, pady=5)

def prompt_and_start_z_calibration_test():

    dialog = tk.Toplevel(root)
    dialog.title("Z Calibration Test Setup")
    dialog.geometry("350x200")
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

    # -------- START BUTTON --------
    def start():
        dialog.destroy()
        threading.Thread(
            target=lambda: Testing_functions.run_z_calibration_test(),
            daemon=True
        ).start()

    tk.Button(frame, text="Start Calibration Test", command=start, height=2).pack(pady=10, fill="x")
    dialog.bind("<Return>", lambda event: start())


extra_buttons = [
    ("Run Contact Test", lambda: prompt_and_start_test("contact")),
    ("Run Slide Test", lambda: prompt_and_start_test("slide")),
    ("Run Full Force Range Test", lambda: prompt_and_start_full_force_range()),
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
