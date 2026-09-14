"""Linux/pyserial command-line controller for a PDXR1 stage.

Angles are absolute degrees (°).  Speed is degrees per second (°/s).
The command is dry-run unless --execute is supplied.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from pdxc_serial import PDXCSerial, SerialConfig


def _calibrated(value: str) -> bool:
    return value.strip().upper().rstrip(">\r\n").startswith("YES")


def build_targets(a_angle: float, b_angle: float, mode: str, cycles: int) -> list[float]:
    if not -180 <= a_angle <= 180 or not -180 <= b_angle <= 180:
        raise ValueError("각도는 절대각도이며 -180..180° 범위여야 합니다")
    if cycles < 1:
        raise ValueError("cycles는 1 이상이어야 합니다")
    if mode == "single":
        return [b_angle]
    return [value for _ in range(cycles) for value in (a_angle, b_angle, a_angle)]


def _wait_position(io: PDXCSerial, target: float, tolerance: float, timeout: float, writer) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        error = io.get_error()
        position = io.get_position()
        if writer:
            writer.writerow([time.time(), target, position, error])
        if error != 0:
            raise RuntimeError(f"장치 오류 코드: {error}")
        if abs(position - target) <= tolerance:
            return
        time.sleep(0.1)
    raise TimeoutError(f"목표각 {target:.4f}° 도달 시간 초과")


def run(args: argparse.Namespace) -> list[float]:
    targets = build_targets(args.a_angle, args.b_angle, args.mode, args.cycles)
    if not args.execute:
        print("dry-run 계획:", " -> ".join(f"{target:g}°" for target in targets))
        print(f"속도: {args.speed_deg_s:g}°/s")
        return targets

    if not args.port:
        raise ValueError("실제 실행에는 --port /dev/ttyUSB0 또는 COM 포트가 필요합니다")
    io = PDXCSerial(SerialConfig(args.port, timeout=args.serial_timeout))
    writer = None
    output = None
    try:
        io.open()
        stage = io.get_stage()
        if "PDXR" not in stage.upper():
            raise RuntimeError(f"PDXR stage가 아닙니다: {stage!r}")
        if io.get_error() != 0:
            raise RuntimeError("연결 직후 장치 오류가 있습니다")
        if io.get_loop() != 0:
            raise RuntimeError("closed-loop가 필요합니다. 장치 모드를 먼저 설정하세요")
        if not io.get_trigger_mode().strip().upper().startswith("ML"):
            raise RuntimeError("manual trigger mode(ML)가 필요합니다")
        if not _calibrated(io.get_calibration()):
            if not args.home:
                raise RuntimeError("보정되지 않았습니다. 필요하면 --home을 명시하세요")
            io.home()
            deadline = time.monotonic() + args.home_timeout
            while time.monotonic() < deadline and not _calibrated(io.get_calibration()):
                if io.get_error() != 0:
                    raise RuntimeError("homing 중 장치 오류")
                time.sleep(0.5)
            if not _calibrated(io.get_calibration()):
                raise TimeoutError("homing 시간 초과")
        if io.get_disabled():
            if not args.enable:
                raise RuntimeError("컨트롤러가 disabled입니다. 실제 실행에는 --enable이 필요합니다")
            io.set_disabled(0)
            if io.get_disabled():
                raise RuntimeError("enable 확인 실패")

        if args.csv:
            output = Path(args.csv)
            output.parent.mkdir(parents=True, exist_ok=True)
            handle = output.open("w", newline="", encoding="utf-8")
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "target_angle_deg", "position_deg", "error_code"])

        io.set_speed(args.speed_deg_s)
        for target in targets:
            print(f"이동: {target:g}° (속도 {args.speed_deg_s:g}°/s)")
            io.set_position(target)
            _wait_position(io, target, args.tolerance, args.leg_timeout, writer)
        print("완료")
        return targets
    finally:
        if writer:
            handle.close()
        try:
            if io.ser is not None and not args.keep_enabled:
                io.set_disabled(1)
        finally:
            io.close()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="PDXR1 Linux serial CLI: angles are absolute degrees (°), speed is degrees/second (°/s).",
        epilog="single = current position -> B once; bidirectional = A -> B -> A per cycle.",
    )
    p.add_argument("--port", help="serial port, for example /dev/ttyUSB0")
    p.add_argument("--a-angle", type=float, default=0.0, help="A absolute angle in degrees (°)")
    p.add_argument("--b-angle", type=float, default=120.0, help="B absolute angle in degrees (°)")
    p.add_argument("--speed-deg-s", type=float, required=True, help="target speed in degrees per second (°/s)")
    p.add_argument("--mode", choices=("single", "bidirectional"), default="bidirectional")
    p.add_argument("--cycles", type=int, default=1, help="bidirectional A->B->A repetitions")
    p.add_argument("--execute", action="store_true", help="open the port and move the hardware")
    p.add_argument("--enable", action="store_true", help="enable a disabled controller")
    p.add_argument("--home", action="store_true", help="home if calibration is incomplete")
    p.add_argument("--keep-enabled", action="store_true", help="do not disable after completion")
    p.add_argument("--tolerance", type=float, default=0.05, help="arrival tolerance in degrees (°)")
    p.add_argument("--leg-timeout", type=float, default=30.0, help="per-leg timeout in seconds")
    p.add_argument("--serial-timeout", type=float, default=1.0, help="serial response timeout in seconds")
    p.add_argument("--home-timeout", type=float, default=120.0, help="homing timeout in seconds")
    p.add_argument("--csv", help="CSV path for timestamped position/error samples")
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if not 10 <= args.speed_deg_s <= 30:
        parser().error("--speed-deg-s는 10..30°/s 범위여야 합니다")
    if args.tolerance <= 0 or args.leg_timeout <= 0:
        parser().error("--tolerance와 --leg-timeout은 양수여야 합니다")
    try:
        run(args)
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
