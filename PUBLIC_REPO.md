# Public repository scope

The intended public repository contains the portable source, tests, GUI, README,
and `manual_ko.md` / `manual_en.md`. It does not contain vendor SDK binaries, extracted vendor
manual text, device logs, or local machine metadata.

Keep these files private or excluded by `.gitignore`:

- `tmp_pdx.txt` and the investigation/protocol notes under `docs/`: extracted
  or derived from the installed Thorlabs SDK/manual and useful for local work,
  but unnecessary for users of the project.
- `pdxc_investigation.md`, `docs/validation.md`, and `artifacts/`: contain local
  installation details, hardware observations, ports, serial identifiers, or
  experiment logs.
- `.venv/`, `.idea/`, `__pycache__/`, pytest caches, and CSV output: generated
  machine-specific files.
- Thorlabs DLL, LIB, PDF, and executable files: proprietary vendor material.

Before publishing, inspect the staged files and confirm that no controller
serial number, COM port, absolute user path, SDK binary, or experiment CSV is
included. Use placeholders such as `<COM_PORT>`, `<CONTROLLER_SERIAL>`, and
`<PDXC_SDK>` in public examples.
