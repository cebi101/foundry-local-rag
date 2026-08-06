"""Platform-dependent setup advice.

Every "your environment is wrong" message ends with a command to paste. The
wrong operating system's command is worse than no command at all: it sends the
reader to a tool that does not exist on their machine, and they spend the
afternoon debugging the advice instead of the problem.

These tests pin the per-OS branches so that fixing one platform cannot quietly
break another. They fake ``platform.system()`` rather than skipping on the
host OS -- otherwise the Windows branches would only ever be exercised on
Windows, which is exactly where nobody runs the test suite.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from foundry_rag.backends import foundry

DOCTOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "doctor.py"


def _load_doctor():
    """Import scripts/doctor.py, which lives outside the package."""
    spec = importlib.util.spec_from_file_location("doctor", DOCTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


doctor = _load_doctor()


# -- venv setup command --------------------------------------------------


def test_windows_advice_does_not_mention_brew(monkeypatch):
    """The original bug: Windows users were told to run a macOS package manager."""
    monkeypatch.setattr(foundry.platform, "system", lambda: "Windows")
    command = foundry.venv_setup_command()
    assert "brew" not in command
    assert "py -3.12" in command
    assert r".venv\Scripts\Activate.ps1" in command


def test_macos_advice_uses_homebrew(monkeypatch):
    monkeypatch.setattr(foundry.platform, "system", lambda: "Darwin")
    command = foundry.venv_setup_command()
    assert "brew install python@3.12" in command
    assert "source .venv/bin/activate" in command


def test_linux_advice_uses_neither_package_manager(monkeypatch):
    monkeypatch.setattr(foundry.platform, "system", lambda: "Linux")
    command = foundry.venv_setup_command()
    assert "brew" not in command
    assert "winget" not in command
    assert "python3.12 -m venv .venv" in command


@pytest.mark.parametrize("system", ["Windows", "Darwin", "Linux"])
def test_every_platform_ends_with_the_install_step(monkeypatch, system):
    """Creating the venv is not the goal; a working environment is."""
    monkeypatch.setattr(foundry.platform, "system", lambda: system)
    assert foundry.venv_setup_command().endswith("pip install -r requirements.txt")


def test_old_python_reason_names_the_macos_trap(monkeypatch):
    monkeypatch.setattr(foundry.platform, "system", lambda: "Darwin")
    assert "/usr/bin/python3" in foundry._old_python_reason()


def test_old_python_reason_stays_generic_elsewhere(monkeypatch):
    """Windows has no /usr/bin/python3 -- but pip's silent 0.5.1 resolve is real there too."""
    monkeypatch.setattr(foundry.platform, "system", lambda: "Windows")
    reason = foundry._old_python_reason()
    assert "macOS" not in reason
    assert "0.5.1" in reason


# -- architecture grading ------------------------------------------------


@pytest.mark.parametrize(
    "system,machine",
    [
        ("Darwin", "arm64"),
        ("Windows", "AMD64"),  # what platform.machine() actually returns there
        ("Windows", "ARM64"),
        ("Linux", "x86_64"),
        ("Linux", "aarch64"),
    ],
)
def test_supported_architectures_pass_cleanly(system, machine):
    status, hint = doctor.architecture_status(system, machine)
    assert status == doctor.OK
    assert hint == ""


def test_intel_mac_is_warned_about_rosetta():
    status, hint = doctor.architecture_status("Darwin", "x86_64")
    assert status == doctor.WARN
    assert "Rosetta" in hint


def test_windows_warning_never_mentions_rosetta():
    """The regression this whole module exists for."""
    status, hint = doctor.architecture_status("Windows", "x86")
    assert status == doctor.WARN
    assert "Rosetta" not in hint
    assert "Apple" not in hint


def test_unknown_os_falls_back_to_the_offline_backend():
    status, hint = doctor.architecture_status("Haiku", "x86_64")
    assert status == doctor.WARN
    assert "hashing" in hint


def test_architecture_check_is_case_insensitive():
    """platform.machine() is 'AMD64' on Windows and 'arm64' on macOS."""
    assert doctor.architecture_status("Windows", "amd64")[0] == doctor.OK
    assert doctor.architecture_status("Windows", "AMD64")[0] == doctor.OK


def test_no_architecture_is_ever_a_hard_error():
    """Foundry Local may be unusable, but the offline backend still runs."""
    for system, machine in [("Darwin", "x86_64"), ("Windows", "x86"), ("Plan9", "sparc")]:
        assert doctor.architecture_status(system, machine)[0] != doctor.BAD
