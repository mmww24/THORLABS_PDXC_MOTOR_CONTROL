"""Headless GUI/serial contract tests; no hardware or OS serial port is used."""
import threading
import time

from pdxc_gui import GuiConfig, LiveBackend, SweepWorker
from pdxc_serial import PDXCSerial, SerialConfig


class FakePort:
    def __init__(self, *args, **kwargs):
        self.writes = []
        self.closed = False
        self.responses = []
        self.disabled_state = 1

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.writes.append(data)

    def flush(self):
        command = self.writes[-1].decode().strip()
        if command == "DIS?":
            self.responses.append(f"{self.disabled_state}\r\n".encode())
        elif command == "DIS=1":
            self.disabled_state = 1
            self.responses.append(b"OK!\r\n")
        elif command == "DIS=0":
            self.disabled_state = 0
            self.responses.append(b"OK!\r\n")
        else:
            self.responses.append(b"OK!\r\n" if "=" in command else b"0\r\n")

    def read_until(self, terminator):
        return self.responses.pop(0)

    def close(self):
        self.closed = True


class GuiSerialAdapter:
    """Small explicit adapter documenting the GUI worker's backend contract."""

    def __init__(self, transport):
        self.transport = transport
        self.moves = []

    def open(self, _port="fake"):
        self.transport.open()

    def close(self):
        self.transport.close()

    def enable(self):
        self.transport.set_disabled(0)

    def disable(self):
        self.transport.set_disabled(1)

    def move(self, target, speed, cancel):
        if cancel.is_set():
            return False
        self.transport.set_speed(speed)
        self.transport.set_position(target)
        self.moves.append((target, speed))
        return True


def test_worker_uses_serial_backend_and_disables_on_completion():
    holder = []

    def factory(*args, **kwargs):
        port = FakePort(*args, **kwargs)
        holder.append(port)
        return port

    serial = PDXCSerial(SerialConfig("fake"), factory)
    backend = GuiSerialAdapter(serial)
    backend.open()
    worker = SweepWorker(backend, lambda _event: None)
    worker.run(GuiConfig(0, 120, 20, 1, False))

    assert backend.moves == [(120, 20)]
    assert holder[0].writes[-1] == b"DIS=1\r"
    assert holder[0].closed


def test_worker_cancel_before_run_sends_no_motion_setter():
    holder = []

    def factory(*args, **kwargs):
        port = FakePort(*args, **kwargs)
        holder.append(port)
        return port

    serial = PDXCSerial(SerialConfig("fake"), factory)
    backend = GuiSerialAdapter(serial)
    backend.open()
    worker = SweepWorker(backend, lambda _event: None)
    worker.cancel.set()
    worker.run(GuiConfig(0, 120, 20, 1, False))

    assert backend.moves == []
    assert all(not write.startswith((b"SPD=", b"POS=")) for write in holder[0].writes)


def test_pause_io_has_single_worker_owner():
    """Pause must be serialized through the worker, never called from Tk thread."""
    calls = []
    started = threading.Event()
    release = threading.Event()

    class BlockingBackend:
        def open(self, _port="fake"):
            calls.append(("open", threading.get_ident()))

        def enable(self):
            calls.append(("enable", threading.get_ident()))

        def disable(self):
            calls.append(("disable", threading.get_ident()))

        def is_disabled(self):
            calls.append(("is_disabled", threading.get_ident()))
            return True

        def move(self, target, speed, cancel):
            calls.append(("move", threading.get_ident()))
            started.set()
            release.wait(1)
            return False

        def close(self):
            calls.append(("close", threading.get_ident()))

    backend = BlockingBackend()
    backend.open()
    worker = SweepWorker(backend, lambda _event: None)
    thread = threading.Thread(target=worker.run, args=(GuiConfig(0, 120, 20, 1, False),))
    thread.start()
    assert started.wait(1)
    worker.pause_run()  # regression: current implementation performs I/O on caller thread
    release.set()
    thread.join(1)
    io_threads = {tid for name, tid in calls if name in {"enable", "move", "disable", "is_disabled", "close"}}
    assert io_threads == {thread.ident}


def test_moving_pause_writes_disable_before_arrival_and_resume_reissues_target():
    """Regression test for real serial pause semantics using only a fake port."""
    class SlowPort(FakePort):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.position_reads = 0
            self.events = []

        def flush(self):
            command = self.writes[-1].decode().strip()
            self.events.append(("write", command))
            super().flush()

        def read_until(self, terminator):
            command = self.writes[-1].decode().strip()
            # `flush()` queues a generic response; replace it with the
            # command-specific response so stale bytes cannot mask ordering.
            self.responses.clear()
            if command == "POS?":
                self.position_reads += 1
                if self.position_reads < 6:
                    self.responses.append(b"0\r\n")
                else:
                    self.events.append(("arrival", 120.0))
                    self.responses.append(b"120\r\n")
            elif command == "ERR?":
                self.responses.clear(); self.responses.append(b"0\r\n")
            elif command == "DIS?":
                self.responses.append(f"{self.disabled_state}\r\n".encode())
            elif command == "DIS=1":
                self.disabled_state = 1
                self.responses.append(b"OK!\r\n")
            elif command == "DIS=0":
                self.disabled_state = 0
                self.responses.append(b"OK!\r\n")
            else:
                self.responses.append(b"OK!\r\n" if "=" in command else b"0\r\n")
            return super().read_until(terminator)

    holder = []

    def factory(*args, **kwargs):
        port = SlowPort(*args, **kwargs)
        holder.append(port)
        return port

    serial = PDXCSerial(SerialConfig("fake"), factory)
    backend = LiveBackend("fake")
    backend.io = serial
    # The worker's polling contract is position()/error(); bind the serial
    # getters explicitly here so this test exercises the real polling path.
    backend.position = serial.get_position
    backend.error = serial.get_error
    backend.open()
    events = []
    worker = SweepWorker(backend, events.append)
    thread = threading.Thread(target=worker.run, args=(GuiConfig(0, 120, 20, 1, False),))
    thread.start()
    time.sleep(0.08)
    worker.pause_run()
    deadline = time.time() + 2
    while ("state", "paused") not in events and time.time() < deadline:
        time.sleep(0.01)
    worker.resume_run()
    thread.join(2)

    log = holder[0].events
    disable_i = next(i for i, event in enumerate(log) if event == ("write", "DIS=1"))
    arrival_i = next((i for i, event in enumerate(log) if event == ("arrival", 120.0)), None)
    assert arrival_i is not None, f"wire={log!r}; worker_events={events!r}"
    assert disable_i < arrival_i
    assert [event for event in log if event == ("write", "POS=120.000000")].__len__() >= 2
