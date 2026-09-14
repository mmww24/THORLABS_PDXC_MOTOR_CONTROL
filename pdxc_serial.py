"""Cross-platform PDXC serial transport (query-only by default).

The command spellings come from the installed PDXC DLL. Framing is CR-terminated
ASCII at 115200 8N1; this module never sends setters unless explicitly called.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass
class SerialConfig:
    port: str
    baudrate: int = 115200
    timeout: float = 1.0

class PDXCSerial:
    def __init__(self, config, serial_factory=None):
        self.config=config; self._factory=serial_factory
        self.ser=None
    def open(self):
        if self._factory is None:
            import serial
            self._factory=serial.Serial
        self.ser=self._factory(self.config.port, self.config.baudrate, timeout=self.config.timeout,
                                bytesize=8, parity='N', stopbits=1, xonxoff=False, rtscts=False, dsrdtr=False)
    def close(self):
        if self.ser is not None: self.ser.close(); self.ser=None
    def query(self, command):
        if not command.endswith('?'): raise ValueError('query-only transport accepts ? commands')
        self.ser.reset_input_buffer(); self.ser.write((command+'\r').encode('ascii')); self.ser.flush()
        raw=self.ser.read_until(b'\r\n')
        return raw.decode('ascii','replace').strip()
    def command(self, command):
        """Send one documented setter; never retries an ambiguous write."""
        if '=' not in command: raise ValueError('setter requires documented assignment')
        self.ser.reset_input_buffer(); self.ser.write((command+'\r').encode('ascii')); self.ser.flush()
        raw=self.ser.read_until(b'\r\n').decode('ascii','replace').strip()
        if not raw.startswith('OK!'): raise IOError(f'PDXC setter not acknowledged: {raw!r}')
        return raw
    def get_position(self):
        m=re.search(r'[-+]?\d+(?:\.\d+)?', self.query('POS?'))
        if not m: raise ValueError('invalid POS? response')
        return float(m.group())
    def get_status(self): return self.query('STUS?')
    def get_error(self): return int(self.query('ERR?').rstrip('>'))
    def get_stage(self): return self.query('SN2?')
    def get_trigger_mode(self): return self.query('ETM?')
    def get_loop(self): return int(self.query('LP?').rstrip('>'))
    def get_disabled(self): return int(self.query('DIS?').rstrip('>'))
    def get_calibration(self): return self.query('HOM?')
    def set_position(self, degrees):
        if not -180 <= degrees <= 180: raise ValueError('PDXR position must be -180..180')
        return self.command(f'POS={degrees:f}')
    def set_speed(self, degrees_per_s):
        if not 10 <= degrees_per_s <= 30: raise ValueError('PDXR speed must be 10..30 deg/s')
        return self.command(f'SPD={int(degrees_per_s)}')
    def set_loop(self, loop):
        if loop not in (0,1): raise ValueError('loop must be 0 or 1')
        return self.command(f'LP={loop}')
    def set_disabled(self, disabled):
        if disabled not in (0,1): raise ValueError('disabled must be 0 or 1')
        return self.command(f'DIS={disabled}')
    def home(self): return self.command('HOM=1')
