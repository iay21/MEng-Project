import serial
import threading
import time
import os
import csv
import datetime
import pyvisa



'''
###################################################################################

BEFORE TEST!! 

Before plugging in the 3d Printer, manually lift the print head up to the top of
the z axis to callibrate the height

Make sure to check what ports the arduino and 3d printer are connected to on your 
laptop (using device manager) and update below

Test parameters can be changed within the file or in the live terminal

###################################################################################
'''

# === UPDATE FOR YOUR SYSTEM ===

arduino_port = "COM10"
printer_port = "COM11"

SAVE_DIR = r"C:\Users\sushi\OneDrive\Documents\Imperial\.DE4\Masters project\_TEST DATA\RIG-SETUP\_Frequency Testing"

# === BASELINE TEST PARAMETERS === 
safe_force_limit = 36 # N
touch_threshold = 0.2 # N
contact_force = 10 # N
contact_frequency = 0.5 # Hz
contact_time = 0.5 # s
separation_time = 0.5 # s
separation_height = 3 # mm

no_contact_cycles = 25
no_slide_cycles = 2

range_of_forces = [5, 10, 15, 20, 25, 30]

contact_speed = 5000
slide_speed = 1000
step = 0.05
big_step = 0.5

number_of_contact_tests = 2
number_of_slide_tests = 1


'''
###################################################################################
DO NOT EDIT ANYTHING FROM HERE!!
###################################################################################
'''

neutral_z_coord = 200
separation_z_coord = 200
contact_z_coord = 200

slow_speed = 100
fast_speed = 6000

cycle_start_time = 0

latest_force = None
latest_voltage = None
last_command_sent = ""

csv_writer = None
current_log_file = None
csv_lock = threading.Lock()

load_resistance = 1e6   # Ohms (example default)
measurement_mode = "VOLTAGE"   # or "CURRENT"
counter_material = "UNKNOWN"
z_cal_test = "DEFAULT"  # Test name/material for z calibration


# ---------------- COMMS ----------------

loadcell = None
printer = None
keithly = None

import pyvisa
import threading
import time

rm = None
keithley = None

def init_keithley(resource_string=None):
    global rm, keithley

    rm = pyvisa.ResourceManager()

    resources = rm.list_resources()
    print("Available VISA resources:", resources)

    if not resources:
        raise RuntimeError("No VISA instruments found")

    # PICK ONLY INSTRUMENTS (filter out noise)
    candidates = [r for r in resources if "GPIB" in r or "USB" in r or "ASRL" in r]

    if not candidates:
        raise RuntimeError("No valid Keithley resource found")

    if resource_string is None:
        resource_string = candidates[0].strip()

    print("Opening:", repr(resource_string))

    keithley = rm.open_resource(resource_string)

    keithley.timeout = 5000
    keithley.read_termination = "\n"
    keithley.write_termination = "\n"

    print(keithley.query("*IDN?"))

    
    keithley.write("reset()")
    # keithley.write("clear()")

    # IMPORTANT: explicitly enable DC voltage mode
    keithley.write("dmm.measure.func = dmm.FUNC_DC_VOLTAGE")
    keithley.write("dmm.measure.autorange = dmm.ON")



def read_voltage():
    try:
        return float(keithley.query("print(dmm.measure.read())"))
    except Exception as e:
        print("Keithley read error:", e)
        return None

def initialise_rig():
    global loadcell, printer, keithly

    print("Connecting hardware...")

    loadcell = serial.Serial(arduino_port, 9600, timeout=2)
    printer = serial.Serial(printer_port, 115200, timeout=5)  
    init_keithley() 
    # keithly = pyvisa.ResourceManager().open_resource(keithly_port)

    time.sleep(3)

    threading.Thread(target=arduino_loop, daemon=True).start()
    threading.Thread(target=safety_loop, daemon=True).start()
    threading.Thread(target=acquisition_loop, daemon=True).start()

    print("Rig connected.")

# ---------------- CORE PRINTER FUNCTIONS ----------------

def send_gcode(command):
    global last_command_sent
    last_command_sent = command

    printer.write((command + "\n").encode())
    printer.flush()

    while True:
        line = printer.readline().decode(errors="ignore").strip()

        if line:
            print("Printer:", line)

            if line.lower().startswith("ok"):
                break


def speed(v):
    send_gcode(f"G1 F{v}")

def z_go_to(z):
    send_gcode(f"G1 Z{z}")

def adjust_z_up():
    send_gcode("G91")
    send_gcode("G1 Z0.01")
    send_gcode("G90")

def adjust_z_down():
    send_gcode("G91")
    send_gcode("G1 Z-0.01")
    send_gcode("G90")

def y_slide(d):
    send_gcode("G91")
    send_gcode(f"G1 Y{d}")
    send_gcode("G90")

def y_centre():
    send_gcode("G1 Y111.5")

def x_y_centre():
    send_gcode("G1 X126.5 Y111.5")

def re_centre():
    send_gcode("G1 X124.5 Y109.5")
    x_y_centre()

def pause(t):
    send_gcode(f"G04 S{t}")

def emergency_stop():
    print("EMERGENCY STOP ACTIVATED!")
    try:
        # Send emergency stop command multiple times to ensure it gets through
        for _ in range(3):
            printer.write(b"M112\n")
            time.sleep(0.001)  # Very short delay between commands
        print("Emergency stop commands sent to printer")
    except Exception as e:
        print(f"Error sending emergency stop: {e}")

# ---------------- SETUP ----------------

def setup():
    speed(fast_speed)
    send_gcode("G28 X Y")
    send_gcode("G91")
    send_gcode("G1 Z5")
    send_gcode("G90")
    send_gcode("G1 X126 Y111.5")
    send_gcode("G92 X126 Y111.5 Z200")
    send_gcode("G1 Z85")

def reset():
    speed(fast_speed)
    send_gcode("G1 X126 Y111.5 Z200")

# ---------------- CALIBRATION ----------------

# corrected_target_force = ((contact_force - 1.6331) / 1.0612) # conservative estimate to ensure we don't overshoot too much


def calibrate_z(z_coord=85, buffer = 0.01):
    """
    Move Z down incrementally until the force thresholds are reached.
    Returns the neutral Z coordinate, separation z coordinate
    and the contact force z coordinate
    """
    print("Neutral calibration starting")

    global latest_force, neutral_z_coord, separation_z_coord, contact_z_coord, step, big_step, contact_force

    corrected_target_force = contact_force
    # corrected_target_force = ((contact_force - 1.6331) / 1.0612) # conservative estimate to ensure we don't overshoot too much
    print(f"Target force for calibration: {corrected_target_force:.2f}N")
    
    neutral_callibration = True
    # === Loop 1: find neutral z ===
    while neutral_callibration:
        # send_gcode(f"G1 Z{z_coord} F60")  # slow movement
        speed(200)
        z_go_to(z_coord)
        time.sleep(0.5)  # give printer time to move and force to update

        if latest_force < touch_threshold:
            z_coord -= step  # move down by small step (mm)
            print(f"Moving down by step to z={z_coord:.2f} (force={latest_force:.2f} N)")

        else:
            neutral_z_coord = z_coord # sets the z at which the material is just being touched
            neutral_callibration = False
            print(f"neutral_z_coord = {neutral_z_coord}")
            print("Neutral calibration complete")

    force_callibration = True

    # === Loop 2: find contact force z ===
    while force_callibration:
        # send_gcode(f"G1 Z{z_coord} F60")
        speed(1000)
        z_go_to(z_coord)
        time.sleep(1) # give printer time to move and force to update 
        # pause(1)

        if latest_force < (0.65 * corrected_target_force):
            z_coord -= big_step # move down by big step
            print(f"Moving down by big step to z={z_coord:.2f} (force={latest_force:.2f} N)")

        elif (0.65 * corrected_target_force) <= latest_force and latest_force <= (0.99 * corrected_target_force):
            z_coord -= step # move down by step
            print(f"Moving down by step to z={z_coord:.2f} (force={latest_force:.2f} N)")
        
        else:
            contact_z_coord = z_coord # sets the z at which desired force is delivered
            force_callibration = False
            print(f"contact_z_coord = {contact_z_coord}")
            print(f"Force calibration complete")

    separation_z_coord = neutral_z_coord + separation_height
    print(f"separation_z_coord = {separation_z_coord}")
    send_gcode(f"G1 Z{separation_z_coord}") 

    return neutral_z_coord, contact_z_coord, separation_z_coord

def repeat_calibrate_z():
    for i in range(10):
        calibrate_z()
        send_gcode("M400") # waits for printer to finish moving
        re_centre()
        send_gcode("M400") # waits for printer to finish moving
        time.sleep(2)



def correct_z_for_force():
    global latest_force, contact_time, cycle_start_time

    # tolerance = 0.01 * contact_force  # 1% tolerance
    tolerance = 0.01 # N tolerance

    if latest_force > contact_force + tolerance:
        adjust_z_up() # move up if force is too high
        
    elif latest_force < contact_force - tolerance:
        adjust_z_down() # move down if force is too low
        




# ---------------- TEST CYCLES ----------------

def contact_cycle():
    global no_contact_cycles, contact_speed, separation_z_coord, contact_frequency

    print("Contact cycle start")
    speed(fast_speed)
    x_y_centre()
    z_go_to(separation_z_coord)
    speed(contact_speed)

    cycle_time = 1/contact_frequency

    for i in range(no_contact_cycles):
        cycle_start_time = time.time() # record the start time for this cycle
        z_go_to(contact_z_coord)
        send_gcode("M400") # waits for printer to finish moving

        time.sleep(0.1) # short delay to allow force to update after contact

        while time.time() - cycle_start_time < (0.5* cycle_time):
            correct_z_for_force() # actively holds correct force during the set contact time   
            # current_z = contact_z_coord
            # if latest_force > contact_force + 0.5:
            #     z_go_to(contact_z_coord + 0.1) # move up if force is too high
            # elif latest_force < contact_force - 0.5:
            #     z_go_to(contact_z_coord - 0.1) # move down if force is too low
            
            time.sleep(0.1) # wait for force to update
        
        z_go_to(separation_z_coord)
        re_centre()
        while time.time() - cycle_start_time < cycle_time:
            time.sleep(0.01)
    print("Contact cycle end")


def sliding_cycle():
    global no_slide_cycles

    print("Sliding cycle start")

    speed(fast_speed)
    x_y_centre()
    speed(slide_speed)
    z_go_to(contact_z_coord)

    for i in range(no_slide_cycles):
        y_slide(38)
        y_centre()
        y_slide(-38)
        y_centre()

    z_go_to(separation_z_coord)

    print("Sliding cycle end")


# -----------------------------------------------------------------------------
# Logging Control
# -----------------------------------------------------------------------------

def start_test(test_name, material, counter_material, load_resistance, measurement_mode, contact_force):
    """
    Start a new test session and create a CSV log file.
    Creates a subfolder for the material.
    Only one test can run at a time.
    """

    # Sets up the data collection

    global current_log_file, csv_writer, SAVE_DIR
    with csv_lock:
        if current_log_file is not None:
            print("⚠ A test is already running! Stop it first.")
            return
        
        # Create folder for the material
        material_dir = os.path.join(SAVE_DIR, material)
        os.makedirs(material_dir, exist_ok=True)

        # -----------------------------
        # Format timestamp
        # -----------------------------
        x = datetime.datetime.now()

        timestamp = x.strftime("%Y-%m-%d_%H-%M-%S")

        # -----------------------------
        # Clean strings (no spaces or illegal chars)
        # -----------------------------
        def clean(s):
            return str(s).replace(" ", "_").replace("/", "-")

        material_str = clean(material)
        counter_str = clean(counter_material)
        test_str = clean(test_name)
        mode_str = clean(measurement_mode)
        contact_force_str = clean(contact_force)

        # convert resistance nicely
        def format_resistance(r):
            if r >= 1e9:
                return f"{r/1e9:.0f}G"
            elif r >= 1e6:
                return f"{r/1e6:.1f}M"
            elif r >= 1e3:
                return f"{r/1e3:.0f}k"
            else:
                return str(int(r))

        res_str = format_resistance(load_resistance)


        # -----------------------------
        # FINAL FILENAME
        # -----------------------------
        filename = f"{material_str}_{counter_str}_{test_str}_{mode_str}_{res_str}_{contact_force_str}N_{timestamp}.csv"

        filepath = os.path.join(material_dir, filename)
        counter = 1

        while os.path.exists(filepath):
            filepath = os.path.join(material_dir, filename.replace(".csv", f"_{counter}.csv"))
            counter += 1

        
        current_log_file = open(filepath, "w", newline="")
        csv_writer = csv.writer(current_log_file)

        # -----------------------------
        # Write metadata (top of file)
        # -----------------------------
        csv_writer.writerow(["# Test Metadata"])
        csv_writer.writerow(["# Primary Material", material])
        csv_writer.writerow(["# Counter Material", counter_material])
        csv_writer.writerow(["# Test Type", test_name])
        csv_writer.writerow(["# Target Force (N)", contact_force])
        csv_writer.writerow(["# Load Resistance (Ohm)", load_resistance])
        csv_writer.writerow(["# Measurement Mode", measurement_mode])
        csv_writer.writerow(["# Start Time", timestamp])
        csv_writer.writerow([])  # blank line


        
        csv_writer.writerow(["time_s", "force_N", "voltage_V"])

        global acquisition_running, start_time
        start_time = time.monotonic()
        acquisition_running = True

        print(f"✅ Started logging to {filepath}")

    # tells the printer to start running a test

    if test_name == "contact":
        print("Contact separation test starting")
        contact_cycle()

    elif test_name == "slide":
        print("Lateral slide test starting")
        sliding_cycle()

    elif test_name == "z-calibration":
        print("Z calibration starting")
        repeat_calibrate_z()
    
    else:
        print("Invalid test type")
        print("Please input either 'contact' or 'slide'")
        stop_test()

    send_gcode("M400") # waits until all motion completed
    z_go_to(85) # move up to safe height after test
    send_gcode("M400") # waits until all motion completed
    stop_test() # close CSV safely after motion is finished

def stop_test():
    """Stop the current test and close the CSV log file."""
    global current_log_file, csv_writer, acquisition_running

    acquisition_running = False

    with csv_lock:
        if current_log_file:
            current_log_file.close()
            print("🛑 Test logging stopped.")
        current_log_file = None
        csv_writer = None
    

# -----------------------------------------------------------------------------
# Full Test Protocol
# -----------------------------------------------------------------------------

def run_test_protocol(material):
    ''' runs whole protocol for both'''
    setup() # calibrates x, y, z coords and moves to "home"
    send_gcode("M400") # waits for printer to finish moving
    calibrate_z() # determines z coords for neutral, contact and separation
    send_gcode("M400") # waits for printer to finish moving

    for i in range(number_of_contact_tests):
        start_test('contact', material)
        z_go_to(85)
        send_gcode("M400") # waits for printer to finish moving
    
    for i in range(number_of_slide_tests):
        start_test('slide', material)
        z_go_to(85)
        send_gcode("M400") # waits for printer to finish moving
    
    reset()
    send_gcode("M400") # waits for printer to finish moving

def run_contact_full_force_range(material, counter_material, load_resistance, measurement_mode):
    ''' runs tests for full range of forces in the contact mode'''
    global contact_force
    for f in range_of_forces:
        contact_force = f
        print(f"Running contact test for target force {contact_force}N")
        calibrate_z()  # determines z coords for neutral, contact and separation
        send_gcode("M400")  # waits for printer to finish moving
        start_test('contact', material, counter_material, load_resistance, measurement_mode, contact_force)
        send_gcode("M400")  # waits for printer to finish moving

    reset()
    send_gcode("M400")  # waits for printer to finish moving

def run_slide_protocol(material):
    ''' runs whole protocol for only slide mode'''
    setup() # calibrates x, y, z coords and moves to "home"
    send_gcode("M400") # waits for printer to finish moving
    calibrate_z() # determines z coords for neutral, contact and separation
    send_gcode("M400") # waits for printer to finish moving
    
    for i in range(number_of_slide_tests):
        start_test('slide', material)
        z_go_to(85)
        send_gcode("M400") # waits for printer to finish moving
    
    reset()
    send_gcode("M400") # waits for printer to finish moving

def run_z_calibration_test():
    global contact_force, z_cal_test
    original_force = contact_force  # Save original value
    
    for f in range_of_forces:
        contact_force = f
        print(f"Running z calibration for target force {contact_force}N")
        start_test('z-calibration', z_cal_test, "NA", load_resistance, measurement_mode, contact_force) 
        send_gcode("M400")  # Wait for calibration to complete
        time.sleep(2)
    
    contact_force = original_force  # Restore original value


# ---------------- BACKGROUND ----------------

def arduino_loop():
    global latest_force

    while True:
        try:
            if loadcell.in_waiting:
                val = loadcell.readline().decode().strip()
                try:
                    new_force = float(val)
                    latest_force = new_force
                except ValueError:
                    # Silently ignore invalid readings instead of printing
                    pass
        except Exception as e:
            # Only print serious errors, not communication glitches
            if "device has been disconnected" in str(e).lower():
                print(f"Arduino connection error: {e}")
        time.sleep(0.01) 


# ---------------- SYNCHRONISED ACQUISITION ----------------

acquisition_running = False
start_time = None


def acquisition_loop():
    global latest_force, latest_voltage, csv_writer, start_time

    dt = 0.05
    start_time = time.monotonic()  # Initialize time at loop start

    while True:
        t = time.monotonic() - start_time
        force = latest_force

        try:
            voltage = read_voltage()
            latest_voltage = voltage
        except:
            voltage = None

        with csv_lock:
            if current_log_file is not None:
                csv_writer.writerow([t, force, voltage])

        time.sleep(dt)




def safety_loop():
    global safe_force_limit, latest_force
    emergency_triggered = False
    check_count = 0

    while True:
        try:
            check_count += 1
            if latest_force is not None and latest_force > safe_force_limit and not emergency_triggered:
                print(f"🚨 SAFETY TRIGGER: Force {latest_force:.2f}N exceeds limit {safe_force_limit}N")
                emergency_stop()
                emergency_triggered = True
                # Continue monitoring but don't spam emergency stops
            elif latest_force is not None and latest_force <= safe_force_limit * 0.8:
                # Reset emergency flag when force drops significantly below limit
                if emergency_triggered:
                    print(f"✓ Safety reset: Force {latest_force:.2f}N back below threshold")
                emergency_triggered = False

            # Reduced status logging - only every 1000 checks (≈10 seconds) or on significant changes
            # Comment out or remove this block if you want no periodic logging at all
            # if check_count % 1000 == 0 and latest_force is not None:
            #     print(f"Safety OK: Force {latest_force:.2f}N (limit: {safe_force_limit}N)")

        except Exception as e:
            print(f"Safety loop error: {e}")

        time.sleep(0.01)  # Check more frequently (10ms instead of 50ms)
