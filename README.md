# PDXC angle sweep controller

This project provides a command-line controller for a Thorlabs PDXC with a
PDXR1 rotation stage. It is intended to perform a bounded sweep between two
absolute angles at a requested speed and number of cycles, with preflight
diagnostics and optional position/error logging.

The supported Windows path uses the official Thorlabs PDXC SDK package and its
matching bitness DLL. Install the PDXC software/SDK from Thorlabs first, then
use the DLL path and device serial reported by the SDK. Do not load a 32-bit
DLL from a 64-bit Python process (or vice versa).

The controller validates PDXR limits of -180..180 degrees and the documented
PDXR speed range of 10..30 degrees/s. Execution verifies PDXR1, enabled state,
calibration, manual trigger mode, and closed-loop mode. `--closed-loop` permits
one explicit open-to-closed transition; `--home` permits one explicit homing
operation followed by calibration polling. Both are opt-in because they can
change hardware state and cause motion.

Dry-run planning is safe and does not contact or move hardware. Hardware
execution requires an explicit execution option and a deliberate operator
check of the selected device and targets. The SDK's disable operation is not
documented as an emergency stop or motion abort; use the controller's normal
stop/safety procedure if motion must be interrupted.

Ubuntu/Linux direct control is available through the experimental
`pdxc_serial.py` transport, which uses the FTDI serial port and the validated
CR-terminated ASCII commands. There is no Thorlabs Linux DLL or official Linux
SDK. The transport has been exercised on the Windows host against the real
PDXR1, including a bounded move and a pause/resume trial; Ubuntu USB hardware
and GUI execution have not yet been validated. Treat the raw serial layer as
device-specific and keep the serial port, model, angle, and speed checks in
place. `DIS=1` quiets and disables the stationary controller, but Thorlabs does
not document it as an emergency stop; a pause must be verified from the
position readback before relying on it.

Keep execution logs with timestamp, target, observed position, status, and
error code so a run can be audited. The actual command names and options are
defined by `pdxc_controller.py`; keep this README synchronized with the final
CLI after implementation is complete.

Example dry run (safe; no DLL or hardware access):

```powershell
python .\pdxc_controller.py 0 120 --speed 20 --cycles 1
```

Hardware execution requires an explicit matching Windows DLL path, serial, and
the opt-in closed-loop/homing flags when needed:

```powershell
python .\pdxc_controller.py 0 120 --speed 20 --cycles 1 --tolerance 0.05 --leg-timeout 30 --timeout 3 --stage-model PDXR1 --serial <CONTROLLER_SERIAL> --closed-loop --home --execute --dll "<PDXC_SDK>\PDXC_COMMAND_LIB_win64.dll" --csv artifacts\run.csv
```

After replacing the placeholders with the local SDK path and controller serial,
the command can be used for a deliberate hardware run. A later run starts with
a disabled controller and therefore requires `--enable`; if calibration is
`No!>`, add `--home` and expect homing motion before the sweep. Successful execution ends
by disabling the controller and verifying `Get_Disabled == 1`, unless
`--keep-enabled` is explicitly supplied. A communication failure or timeout
prevents further commanded motion, but the SDK does not expose a documented
emergency stop, so already commanded physical motion may continue until the
controller's own safety behavior settles.

The implementation performs read-only preflight checks before issuing motion
commands. It does not automatically change loop, enable, or calibration state.

## License

The original source code in this repository is released under the MIT License;
see [LICENSE](LICENSE). Thorlabs PDXC software, SDK libraries, manuals, device
firmware, and trademarks remain the property of their respective owners and
must be obtained and used under their applicable terms. They are intentionally
not included in this repository.

## GUI

Install the Python serial dependency and Tkinter on Ubuntu, for example
`sudo apt install python3-tk`, then install this project in a virtual
environment. Start a hardware session with `python -m pdxc_gui --port
/dev/ttyUSB0`; start the safe simulator with `python -m pdxc_gui --simulate`.
The GUI uses `pyserial` for the cross-platform serial transport and performs
connection queries before Play. Home is an explicit button. Play enables the
controller, while completion, disconnect, and window close disable it and
close the port. Pause/Resume is exposed as provisional controller-state
control; Cancel is separate.

The live serial path has been exercised on Windows with the PDXC FTDI serial
transport. Ubuntu hardware validation remains outstanding because this WSL
installation lacks Tkinter and USB passthrough. The GUI simulator smoke test
and headless worker/serial tests do not contact hardware. Install
`python3-tk`, expose the FTDI device as `/dev/ttyUSB*`, and run the simulator
before attempting a Linux hardware session.

Linux terminal CLI is also available after installation:

```bash
python -m pdxc_serial_cli --a-angle 0 --b-angle 120 --speed-deg-s 20 \
  --mode bidirectional --cycles 1
```

This is a dry-run. Add `--port /dev/ttyUSB0 --execute --enable` only after
checking the stage, loop, calibration, trigger mode, and safe travel range.
