# PDXR1 Control Manual

This project controls a PDXR1 rotation stage connected to a Thorlabs PDXC. Angles are absolute angles; the PDXR1 range is `-180..180°` and the target-speed range is `10..30°/s`. Bidirectional mode repeats `A → B → A`; single-direction mode moves once from the current position to `B`.

If the device is disconnected, use the commands below only to verify installation, syntax, and dry-run behavior. Perform actual motion with `--execute` and Homing only after the motor is connected and its surrounding travel range has been checked.

Before working with real hardware, make sure the rotation range is free of obstructions. `DIS=1` disables the controller and stopped the drive sound in this device test, but Thorlabs does not guarantee it as an emergency stop. If a problem occurs during motion, follow the equipment's physical safety procedures first.

## Windows

### 1. Setup

1. Install the Thorlabs PDXC software and the PDXC driver/SDK.
2. Connect the PDXR1 by USB.
3. Confirm the device in the PDXC software. Before using this project's direct-serial GUI, disconnect the device in the PDXC software and close it. The two programs cannot open the same COM port at the same time.
4. Move to the project directory in PowerShell.

```powershell
cd <clone-dir>\THORLABS
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

If the PowerShell execution policy prevents activation, invoke `.\.venv\Scripts\python.exe` directly instead.

### 2. Verify the installation and tests

```powershell
python -m pytest -q
python tools\smoke_gui.py
```

A successful result is all tests passing and `simulate_gui_smoke=ok`. The simulator does not use a real port or motor.

### 3. Run the GUI

First run the simulator safely.

```powershell
python -m pdxc_gui --simulate
```

For real hardware, identify the COM port in Windows Device Manager, then run:

```powershell
python -m pdxc_gui --port <COM_PORT>
```

GUI workflow:

1. Select `Refresh` to update the ports and choose the displayed PDXC port.
2. Click `Connect`. The connection step only queries status.
3. If needed, click `Home` separately. Homing performs real motion; wait until it completes.
4. Enter `A deg`, `B deg`, `Speed deg/s`, and `Repeats`.
5. With `Bidirectional return` enabled, `A → B → A` repeats; when disabled, the stage moves once from its current position to `B`.
6. Click `Play`. When the run ends, the controller is automatically disabled and the port is closed.
7. During motion, `Pause/Resume` sends `DIS=1`, verifies disabled readback, and pauses. On resume, it verifies `DIS=0` and resends the interrupted target-angle command. `Cancel` sends no further target commands and exits.

### 4. Windows SDK CLI

The existing CLI that uses the official Windows DLL path is also retained. The DLL's Python bitness must match the Python process.

```powershell
python .\pdxc_controller.py 0 120 --speed 20 --cycles 1
```

This command is a dry run. Actual execution requires explicit `--execute`, `--dll`, `--serial`, and any required `--closed-loop` or `--home` options. Before running an arbitrary command on real hardware, reconfirm the target serial number and angle.

## Ubuntu Linux

### Cable connection

The connection between the computer currently in use and the PDXC is:

```text
Computer USB-A port  <->  PDXC controller USB-B port
```

Use a USB data cable, not a charge-only cable. Complete the PDXC power and PDXR1 stage connections according to the equipment manual before running the software.

- Windows: Confirm the controller and COM port in the PDXC software or device list.
- Linux: The controller commonly appears as a device file such as `/dev/ttyUSB0`.
- Before execution, reconfirm the selected port and controller serial number.

Thorlabs does not provide an official Linux DLL. The Linux path connects `pdxc_serial.py` in this project directly to the FTDI USB serial port. This raw-serial path was verified for reading, motion, and pause/resume with a real PDXR1 on a Windows host, but actual Ubuntu USB passthrough has not yet been verified.

### 1. Packages and permissions

The following instructions target Ubuntu 22.04.

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk
cd /path/to/THORLABS
python3 -m venv .venv-linux
source .venv-linux/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If the real device appears as `/dev/ttyUSB0`, add the current user to the `dialout` group and log in again.

```bash
sudo usermod -aG dialout "$USER"
```

Check the FTDI device:

```bash
python -m serial.tools.list_ports -v
```

WSL requires separate USB passthrough. If `/dev/ttyUSB0` is not visible, do not run the GUI or real motor; pass the USB connection through to Linux first.

### 2. Tests and simulator on Linux

```bash
python -m pytest -q
python tools/smoke_gui.py
python -m pdxc_gui --simulate
```

Using the GUI requires `python3-tk` and an active X11/Wayland display. On a headless server, only the backend and headless tests can be run.

### 3. Run the real GUI on Linux

```bash
python -m pdxc_gui --port /dev/ttyUSB0
```

After connecting, first check the current model, position, error, closed-loop, calibration, and manual-trigger states. Before `Play`, the controller must be enabled; if it is disabled, use the GUI's explicit enable procedure. `Home` does not run automatically: it runs only when its button is clicked.

### 4. Use the direct-serial backend

You can also use the Linux CLI in a terminal. `--a-angle` and `--b-angle` are absolute angles (°); `--speed-deg-s` is angular speed (°/s). The default is dry-run mode.

```bash
python -m pdxc_serial_cli --a-angle 0 --b-angle 120 \
  --speed-deg-s 20 --mode bidirectional --cycles 1
```

For actual execution, specify the port and `--execute`. If the controller is disabled, also specify `--enable`. On completion, the default behavior sends `DIS=1` and closes the port.

```bash
python -m pdxc_serial_cli --port /dev/ttyUSB0 \
  --a-angle 0 --b-angle 120 --speed-deg-s 20 \
  --mode bidirectional --cycles 1 --execute --enable --csv artifacts/linux-run.csv
```

Single-direction mode moves once from the current position to B.

```bash
python -m pdxc_serial_cli --port /dev/ttyUSB0 \
  --b-angle 45 --speed-deg-s 20 --mode single --execute --enable
```

If the `pdxc-serial` entry point has been installed, you may use `pdxc-serial` instead of `python -m pdxc_serial_cli`.

### 5. Use the direct-serial backend from Python

```python
from pdxc_serial import PDXCSerial, SerialConfig

io = PDXCSerial(SerialConfig("/dev/ttyUSB0"))
io.open()
try:
    print(io.get_stage(), io.get_position(), io.get_error())
finally:
    io.set_disabled(1)
    io.close()
```

`PDXCSerial` uses `115200 8N1` and CR-terminated ASCII commands. It does not automatically retry setters when communication fails or the response is unclear. On completion, cancellation, or window close, it verifies disabled readback and closes the port.

## Troubleshooting

- `Open` fails: Verify that the PDXC GUI is not holding the port and that the device is actually enumerated.
- The port is not visible: Check the USB cable, driver, `dialout` permission, or WSL USB passthrough.
- Calibration is `No`: Run `Home` explicitly, then verify that it completed.
- The motor remains audible after Pause: First check that position is not changing, then verify that disabled readback is `1`. `DIS=1` is not guaranteed to be an emergency stop.
- `python3-tk` error: On Ubuntu, run `sudo apt install python3-tk`, then try again in a session with a GUI display.

Store real-device test records in `artifacts/`, including angle, speed, target serial number, and final disabled/error state.
