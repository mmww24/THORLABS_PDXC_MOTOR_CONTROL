# PDXC / PDXR1 Motor Controller

![Thorlabs PDXC](https://media.thorlabs.com/contentassets/b6bed45782c34d0996cec2a7d82e0906/14581_pdxc_sgl.webp?v=1116123909)

Unofficial Python tools for controlling a Thorlabs PDXC with a PDXR1 rotation
stage. The project supports a Windows SDK backend and an experimental direct
serial backend for Linux and Windows.

> **Windows users:** The recommended first choice is the official [Thorlabs
> PDXC software](https://www.thorlabs.com/software-pages/PDXC). Use this
> project when you specifically need the documented CLI, GUI, logging, or
> Linux direct-serial workflow.

## Features

- Bounded absolute-angle moves and repeated sweeps
- Speed control in degrees per second (`deg/s`)
- Single-leg and bidirectional operation
- Tkinter GUI with Play, Pause, Resume, Cancel, and Home controls
- Linux command-line interface for direct serial control
- Dry-run mode for planning without hardware access
- Position, status, and error-code logging to CSV

## Backends

| Backend | Platform | Entry point | Hardware status |
| --- | --- | --- | --- |
| PDXC SDK | Windows | `pdxc_controller.py` | Tested with a real PDXR1 on Windows |
| Direct serial | Linux / Windows | `pdxc_serial.py`, `pdxc_serial_cli.py` | Windows serial path tested; Ubuntu hardware still needs validation |
| GUI | Linux / Windows | `pdxc_gui.py` | Use `--simulate` without a connected stage |

The Linux path uses the FTDI serial port and PDXC ASCII commands. Thorlabs
does not provide a Linux DLL or official Linux SDK for this device.

## Motion parameters

- Angle: absolute position in degrees (`deg`), valid PDXR range `-180..180`
- Speed: degrees per second (`deg/s`), documented PDXR range `10..30`
- `single`: move from the current position to the target B angle once
- `bidirectional`: move `A -> B -> A` for each cycle

## Installation

Python 3.10 or newer is required.

## Hardware connection

The tested computer-to-controller connection is:

```text
Computer USB-A port  <->  USB-B port on the PDXC controller
```

Use a USB data cable, not a charge-only cable. Connect and power the PDXC and
PDXR1 stage according to the device documentation before starting the
software. After connecting the USB cable:

- Windows should expose the controller through the PDXC software and its COM/SDK device list.
- Linux should expose the FTDI interface as a device such as `/dev/ttyUSB0`.
- Confirm the selected port and controller serial before enabling hardware execution.

### Windows

Install the PDXC software/SDK from Thorlabs, then create an environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

The SDK DLL and Python process must have matching bitness. Keep the DLL path,
controller serial number, and SDK installation outside the repository.

### Ubuntu / Linux

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing the `dialout` group. The device normally
appears as `/dev/ttyUSB0`. WSL also needs USB passthrough before a Linux process
can access the stage.

## Windows SDK command line

Plan a move without contacting hardware:

```powershell
python .\pdxc_controller.py 0 120 --speed 20 --cycles 1
```

An actual run requires an explicit DLL, controller serial, and `--execute`:

```powershell
python .\pdxc_controller.py 0 120 --speed 20 --cycles 1 `
  --stage-model PDXR1 --serial <CONTROLLER_SERIAL> `
  --dll "<PDXC_SDK>\PDXC_COMMAND_LIB_win64.dll" `
  --closed-loop --home --enable --execute --csv artifacts\run.csv
```

Replace the placeholders only with local values. `--home`, `--closed-loop`,
and `--enable` can change hardware state and are intentionally explicit.

## GUI

Start the simulator first:

```bash
python -m pdxc_gui --simulate
```

For a live serial session, select the port and set the A angle, B angle, speed,
mode, and cycle count in the window:

```bash
python -m pdxc_gui --port /dev/ttyUSB0       # Linux
python -m pdxc_gui --port COM3               # Windows serial path
```

`Play` enables the controller and starts the selected motion. `Pause` disables
the controller so the motor should become quiet; verify the displayed position
before using `Resume`. Completion, Cancel, disconnect, and window close disable
the controller and close the serial port.

## Linux serial CLI

The default is a dry run:

```bash
python -m pdxc_serial_cli \
  --a-angle 0 --b-angle 120 --speed-deg-s 20 \
  --mode bidirectional --cycles 1
```

For a deliberate hardware run, add the port and execution flags only after
checking the connected device and travel range:

```bash
python -m pdxc_serial_cli \
  --port /dev/ttyUSB0 --a-angle 0 --b-angle 120 \
  --speed-deg-s 20 --mode bidirectional --cycles 1 \
  --execute --enable --csv artifacts/linux_run.csv
```

The installed console entry point is equivalent:

```bash
pdxc-serial --help
```

## Safety and validation

- Dry-run commands do not contact or move hardware.
- Confirm the device model, serial/port, calibration, loop mode, and safe travel range before `--execute`.
- The SDK disable command and serial `DIS=1` are not documented emergency stops.
- A communication timeout may not stop motion that has already been commanded.
- Hardware execution must be supervised and should leave the controller disabled when finished.

The Windows SDK and Windows serial paths were exercised with a real PDXR1,
including a bounded move and pause/resume trial. Ubuntu USB passthrough and
Ubuntu hardware execution have not been validated. Tests and the GUI simulator
do not require a connected motor.

## Reference material

- [Thorlabs PDXC software page](https://www.thorlabs.com/software-pages/PDXC)
- [Thorlabs Motion Control Examples: Python Serial Command](https://github.com/Thorlabs/Motion_Control_Examples/tree/main/Python/Serial%20Command)

## License

The original source code in this repository is released under the MIT License;
see [LICENSE](LICENSE). Thorlabs PDXC software, SDK libraries, manuals, device
firmware, and trademarks remain the property of their respective owners and
must be obtained and used under their applicable terms. They are intentionally
not included in this repository.
