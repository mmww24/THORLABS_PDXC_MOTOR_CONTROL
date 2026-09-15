# PDXR1 제어 매뉴얼 (한국어)

이 프로젝트는 Thorlabs PDXC에 연결된 PDXR1 회전 스테이지를 제어합니다. 각도는 절대각도이며 PDXR1의 범위는 `-180..180°`, 목표 속도는 `10..30°/s`입니다. 양방향 모드는 `A → B → A`를 반복하고, 단방향 모드는 현재 위치에서 `B`로 한 번 이동합니다.

현재 장치가 분리되어 있으면 아래 명령은 설치·구문·dry-run 확인에만 사용하십시오. `--execute`를 포함한 실제 이동과 Homing은 모터가 연결되고 주변 이동 범위를 확인한 뒤에만 수행해야 합니다.

실제 장치 작업 전에는 회전 범위에 장애물이 없는지 확인하십시오. `DIS=1`은 컨트롤러를 비활성화하고 이번 장치 시험에서 구동음을 멈췄지만, Thorlabs가 이를 비상 정지로 보장하지는 않습니다. 이동 중 문제가 생기면 장비의 물리적 안전 절차를 우선하십시오.

## Windows

### 1. 준비

1. Thorlabs PDXC 프로그램과 PDXC 드라이버/SDK를 설치합니다.
2. PDXR1을 USB로 연결합니다.
3. PDXC 프로그램에서 장치를 확인한 뒤, 이 프로젝트의 직접 시리얼 GUI를 사용할 때는 PDXC 프로그램에서 장치 연결을 해제하고 프로그램을 종료합니다. 두 프로그램이 같은 COM 포트를 동시에 열 수 없습니다.
4. PowerShell에서 프로젝트 폴더로 이동합니다.

```powershell
cd <clone-dir>\THORLABS
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

PowerShell 실행 정책으로 활성화가 막히면 활성화하지 않고 `.\.venv\Scripts\python.exe`를 직접 사용해도 됩니다.

### 2. 설치와 테스트 확인

```powershell
python -m pytest -q
python tools\smoke_gui.py
```

정상 결과는 전체 테스트 통과와 `simulate_gui_smoke=ok`입니다. 시뮬레이터는 실제 포트나 모터를 사용하지 않습니다.

### 3. GUI 실행

안전하게 먼저 시뮬레이터를 실행합니다.

```powershell
python -m pdxc_gui --simulate
```

실제 장치에서는 Windows 장치 관리자에서 COM 포트를 확인한 뒤 다음처럼 실행합니다.

```powershell
python -m pdxc_gui --port <COM_PORT>
```

GUI 순서:

1. `Refresh`로 포트를 갱신하고 표시된 PDXC 포트를 선택합니다.
2. `Connect`를 누릅니다. 연결 단계는 상태 조회만 수행합니다.
3. 필요하면 `Home`을 별도로 누릅니다. Homing은 실제로 움직이며, 완료될 때까지 기다립니다.
4. `A deg`, `B deg`, `Speed deg/s`, `Repeats`를 입력합니다.
5. `Bidirectional return`을 켜면 `A → B → A` 반복, 끄면 현재 위치에서 `B`로 1회 이동합니다.
6. `Play`를 누릅니다. 실행이 끝나면 컨트롤러를 자동으로 비활성화하고 포트를 닫습니다.
7. 이동 중 `Pause/Resume`을 누르면 `DIS=1`을 보내고 disabled readback을 확인한 뒤 일시정지합니다. 재개할 때 `DIS=0`을 확인하고 중단했던 목표각 명령을 다시 보냅니다. `Cancel`은 이후 목표 명령을 보내지 않고 종료합니다.

### 4. Windows SDK CLI

공식 Windows DLL 경로를 사용하는 기존 CLI도 유지됩니다. DLL의 Python 비트 수가 Python 프로세스와 일치해야 합니다.

```powershell
python .\pdxc_controller.py 0 120 --speed 20 --cycles 1
```

위 명령은 dry-run입니다. 실제 실행은 `--execute`, `--dll`, `--serial`과 필요한 `--closed-loop` 또는 `--home`을 명시해야 합니다. 실제 장치에서 임의의 명령을 실행하기 전에 대상 serial과 각도를 다시 확인하십시오.

## Ubuntu Linux

### 케이블 연결

현재 사용하는 컴퓨터와 PDXC의 연결은 다음과 같습니다.

```text
컴퓨터 USB-A 포트  <->  PDXC 컨트롤러 USB-B 포트
```

충전 전용 케이블이 아닌 USB 데이터 케이블을 사용하십시오. PDXC와 PDXR1의
전원 및 스테이지 연결은 장비 매뉴얼의 연결 절차에 따라 완료한 뒤 프로그램을
실행합니다.

- Windows: PDXC 프로그램 또는 장치 목록에서 컨트롤러와 COM 포트를 확인합니다.
- Linux: 보통 `/dev/ttyUSB0`과 같은 장치 파일로 나타납니다.
- 실행 전 선택한 포트와 컨트롤러 serial을 다시 확인합니다.

Thorlabs의 공식 Linux DLL은 제공되지 않습니다. Linux 경로는 프로젝트의 `pdxc_serial.py`가 FTDI USB-시리얼 포트에 직접 연결하는 방식입니다. 이 raw serial 경로는 Windows 호스트의 실제 PDXR1에서 읽기, 이동, pause/resume까지 검증했지만 Ubuntu의 실제 USB passthrough는 아직 검증하지 않았습니다.

### 1. 패키지와 권한

Ubuntu 22.04 기준입니다.

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk
cd /path/to/THORLABS
python3 -m venv .venv-linux
source .venv-linux/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

실제 장치가 `/dev/ttyUSB0`으로 나타나면 현재 사용자를 `dialout` 그룹에 추가하고 다시 로그인합니다.

```bash
sudo usermod -aG dialout "$USER"
```

FTDI 장치를 확인합니다.

```bash
python -m serial.tools.list_ports -v
```

WSL에서는 USB passthrough가 별도로 필요합니다. `/dev/ttyUSB0`이 보이지 않으면 GUI나 실제 모터를 실행하지 말고 먼저 USB 연결을 Linux에 전달하십시오.

### 2. Linux에서 테스트와 시뮬레이터

```bash
python -m pytest -q
python tools/smoke_gui.py
python -m pdxc_gui --simulate
```

GUI를 쓰려면 `python3-tk`와 실행 중인 X11/Wayland 디스플레이가 필요합니다. 디스플레이가 없는 서버에서는 backend와 headless 테스트만 실행할 수 있습니다.

### 3. Linux 실제 GUI 실행

```bash
python -m pdxc_gui --port /dev/ttyUSB0
```

연결 후 먼저 현재 모델, 위치, 오류, closed-loop, calibration, manual trigger 상태를 확인합니다. `Play` 전에는 controller가 enabled 상태여야 하며, disabled 상태라면 GUI의 명시적 enable 절차를 거칩니다. `Home`은 자동 실행되지 않고 버튼을 눌렀을 때만 실행됩니다.

### 4. 직접 시리얼 backend 사용

터미널에서 Linux CLI를 사용할 수도 있습니다. `--a-angle`와 `--b-angle`은
절대각도(°), `--speed-deg-s`는 각속도(°/s)입니다. 기본은 dry-run입니다.

```bash
python -m pdxc_serial_cli --a-angle 0 --b-angle 120 \
  --speed-deg-s 20 --mode bidirectional --cycles 1
```

실제 실행은 포트와 `--execute`를 명시합니다. 컨트롤러가 disabled 상태라면
`--enable`도 명시해야 합니다. 완료 후에는 기본적으로 `DIS=1`을 보내고 포트를 닫습니다.

```bash
python -m pdxc_serial_cli --port /dev/ttyUSB0 \
  --a-angle 0 --b-angle 120 --speed-deg-s 20 \
  --mode bidirectional --cycles 1 --execute --enable --csv artifacts/linux-run.csv
```

단방향은 현재 위치에서 B까지 한 번 이동합니다.

```bash
python -m pdxc_serial_cli --port /dev/ttyUSB0 \
  --b-angle 45 --speed-deg-s 20 --mode single --execute --enable
```

`pdxc-serial` entry point를 설치했다면 `python -m pdxc_serial_cli` 대신
`pdxc-serial`을 사용해도 됩니다.

### 5. 직접 시리얼 backend 사용

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

`PDXCSerial`은 `115200 8N1`, CR 종료 ASCII 명령을 사용합니다. 통신 오류나 응답이 불명확할 때 setter를 자동 재시도하지 않습니다. 완료·취소·창 닫기 시에는 disabled readback을 확인하고 포트를 닫습니다.

## 문제 해결

- `Open` 실패: PDXC GUI가 포트를 점유하고 있지 않은지 확인하고, 장치가 실제로 열거되는지 확인합니다.
- 포트가 보이지 않음: USB 케이블/드라이버/`dialout` 권한 또는 WSL USB passthrough를 확인합니다.
- calibration이 `No`: `Home`을 명시적으로 실행한 뒤 완료 상태를 확인합니다.
- Pause 후 소리가 남음: 위치가 변하지 않는지 먼저 확인하고, disabled readback이 `1`인지 확인합니다. `DIS=1`은 비상 정지 보장이 아닙니다.
- `python3-tk` 오류: Ubuntu에서 `sudo apt install python3-tk`를 실행하고 GUI 디스플레이가 있는 세션에서 다시 실행합니다.

실제 장치 시험 기록은 `artifacts/`에 저장하고, 각도·속도·대상 serial·최종 disabled/error 상태를 함께 남기십시오.
