from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _build_wheel(dist: Path) -> Path:
    result = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from hatchling.build import build_wheel; "
                f"print(build_wheel({str(dist)!r}))",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        pytest.skip(
            "wheel build tooling unavailable:\n"
            f"{result.stdout}\n{result.stderr}"
        )
    wheels = list(dist.glob("*.whl"))
    assert wheels, "expected a wheel artifact"
    return wheels[0]


def test_wheel_contains_sdk_and_optional_platform_only(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = _build_wheel(dist)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    assert any(name.startswith("sentinelai/") for name in names)
    assert any(name.startswith("sentinelai_platform/") for name in names)
    assert "sentinelai_platform/storage/local_provider.py" in names
    assert "sentinelai_platform/storage/supabase_provider.py" in names
    assert not any(name.startswith("examples/") for name in names)
    assert not any(name.startswith("app/") for name in names)


def test_core_wheel_install_imports_public_api(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    venv = tmp_path / "venv"
    dist.mkdir()
    wheel = _build_wheel(dist)

    create = subprocess.run(
        ["uv", "venv", str(venv)],
        check=False,
        capture_output=True,
        text=True,
    )
    if create.returncode != 0:
        pytest.skip(f"uv venv unavailable:\n{create.stdout}\n{create.stderr}")

    install = subprocess.run(
        ["uv", "pip", "install", "--python", str(venv / "bin" / "python"), str(wheel)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr

    probe = subprocess.run(
        [
            str(venv / "bin" / "python"),
            "-c",
            "import importlib.util; "
            "import sentinelai; "
            "import sys; "
            "from sentinelai import observe, observe_execution, configure, "
            "ExecutionContext, ExecutionSnapshot, ExecutionRepository, "
            "TraceRepository, ExecutionMetadata, ObservedResult; "
            "from sentinelai.execution_stream import "
            "ExecutionStarted, InMemoryExecutionStream; "
            "assert 'sentinelai_platform' not in sys.modules; "
            "assert importlib.util.find_spec('fastapi') is None; "
            "assert importlib.util.find_spec('sqlalchemy') is None; "
            "assert importlib.util.find_spec('supabase') is None; "
            "print(sentinelai.__version__)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.strip() == "2.0.0"
