"""Structural tests for local install scripts — no live Rhino required."""
from __future__ import annotations
import os
import stat
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
SH_SCRIPT = REPO_ROOT / "scripts" / "install-plugin-local.sh"
PS_SCRIPT = REPO_ROOT / "scripts" / "install-plugin-local.ps1"


def test_sh_script_exists():
    assert SH_SCRIPT.exists(), f"Expected {SH_SCRIPT} to exist"


def test_sh_script_is_executable():
    st = os.stat(SH_SCRIPT)
    assert st.st_mode & stat.S_IXUSR, "install-plugin-local.sh must be executable"


def test_sh_script_uses_find_not_ls():
    """Must use 'find' not 'ls' glob to avoid pipefail false-exit."""
    content = SH_SCRIPT.read_text()
    assert "find " in content, "Script should use 'find' for .yak file discovery"
    assert "ls " not in content, "Script should not use bare 'ls' for .yak glob"


def test_sh_script_has_yak_existence_check():
    content = SH_SCRIPT.read_text()
    assert "YAK" in content
    # Check for executable guard pattern  (! -x  or  [ -x  or  test -x)
    assert "! -x" in content or "test -x" in content or "[ -x" in content


def test_sh_script_has_set_euo_pipefail():
    content = SH_SCRIPT.read_text()
    assert "set -euo pipefail" in content


def test_sh_script_references_rhino8():
    """Script must reference Rhino 8 (the supported version)."""
    content = SH_SCRIPT.read_text()
    assert "Rhino 8" in content


def test_ps_script_exists():
    assert PS_SCRIPT.exists(), f"Expected {PS_SCRIPT} to exist"


def test_ps_script_uses_lastwritetime_sort():
    """Must use LastWriteTime sort + Select -Last 1 to pick newest .yak."""
    content = PS_SCRIPT.read_text()
    assert "LastWriteTime" in content, "PowerShell script must use Sort-Object LastWriteTime"
    assert "-Last 1" in content, "PowerShell script must select last (newest) item after sort"


def test_ps_script_has_yak_existence_check():
    content = PS_SCRIPT.read_text()
    assert "Test-Path" in content


def test_ps_script_references_rhino8():
    """Script must reference Rhino 8 (the supported version)."""
    content = PS_SCRIPT.read_text()
    assert "Rhino 8" in content


def test_publishing_md_exists():
    publishing = REPO_ROOT / "rhino_plugin" / "PUBLISHING.md"
    assert publishing.exists()


def test_publishing_md_has_required_sections():
    publishing = REPO_ROOT / "rhino_plugin" / "PUBLISHING.md"
    content = publishing.read_text()
    assert "One-time setup" in content or "one-time" in content.lower()
    assert "Per-release" in content or "per-release" in content.lower()
    # PUBLISHING.md uses "Versioning policy" heading
    assert "Versioning" in content
    assert "Verification" in content
    assert "yak" in content.lower()


def test_publishing_md_has_full_manifest_path():
    """manifest.yml should be referenced with its full path."""
    publishing = REPO_ROOT / "rhino_plugin" / "PUBLISHING.md"
    content = publishing.read_text()
    assert "rhino_plugin/package/manifest.yml" in content


def test_readme_has_install_section():
    readme = REPO_ROOT / "README.md"
    content = readme.read_text()
    # Should have PackageManager option
    assert "_PackageManager" in content or "PackageManager" in content
    # Should have install script reference
    assert "install-plugin-local" in content
    # Should have GitHub releases reference
    assert "github.com" in content.lower() and "release" in content.lower()


def test_installer_venv_relocation_handles_path_aliases(tmp_path):
    import runpy

    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    for arch in ("arm64", "x86_64"):
        venv = alias / f".venv-{arch}"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin/python3.13").symlink_to(alias / f"python-{arch}/bin/python3.13")
        (venv / "pyvenv.cfg").write_text(
            f"home = {alias}/python-{arch}/bin\n"
            f"executable = {actual}/python-{arch}/bin/python3.13\n"
        )
        script = venv / "bin/rhino-mcp"
        script.write_text(f"#!{alias}/.venv-{arch}/bin/python3.13\n")
        script.chmod(0o755)

    runpy.run_path(str(REPO_ROOT / "scripts/relocate-installer-venvs.py"))["relocate"](alias)

    for arch in ("arm64", "x86_64"):
        venv = alias / f".venv-{arch}"
        assert str((venv / "bin/python3.13").readlink()) == (
            f"/Users/Shared/rhino_mcp/python-{arch}/bin/python3.13"
        )
        for file in (venv / "pyvenv.cfg", venv / "bin/rhino-mcp"):
            assert str(alias) not in file.read_text()
            assert str(actual) not in file.read_text()
        assert (venv / "bin/rhino-mcp").stat().st_mode & 0o111
