from pdxc_serial_cli import build_targets, main


def test_cli_single_is_current_to_b_plan():
    assert build_targets(10, 45, "single", 8) == [45]


def test_cli_bidirectional_plan_uses_absolute_degrees():
    assert build_targets(0, 120, "bidirectional", 2) == [0, 120, 0, 0, 120, 0]


def test_cli_without_execute_is_dry_run(capsys):
    assert main(["--a-angle", "0", "--b-angle", "120", "--speed-deg-s", "20"]) == 0
    output = capsys.readouterr().out
    assert "0°" in output and "120°" in output and "20°/s" in output
