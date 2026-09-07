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


@pytest.fixture
def mac_plugin_install(tmp_path):
    import runpy
    installer = runpy.run_path(str(REPO_ROOT / 'scripts/installer/install-plugin.py'))
    home, source, apps = [tmp_path / name for name in ('home', 'source', 'apps')]
    source.mkdir()
    apps.mkdir()
    (source / 'rhino-mcp.rhp').write_bytes(b'plugin')
    (source / 'dependency.dll').write_bytes(b'dependency')
    return installer['install'], home, source, apps


def test_mac_plugin_bundle_discovery_path(mac_plugin_install):
    install, home, source, apps = mac_plugin_install
    for major in (7, 8, 9):
        (apps / f'Rhino {major}.app').mkdir()
    installed = install(home, source, apps)
    assert len(installed) == 2
    for major, bundle in zip((8, 9), installed):
        assert bundle == home / f'Library/Application Support/McNeel/Rhinoceros/{major}.0/MacPlugIns/rhino-mcp.rhp'
        assert (bundle / 'rhino-mcp.rhp').read_bytes() == b'plugin'
        assert (bundle / 'dependency.dll').read_bytes() == b'dependency'


def test_mac_plugin_repairs_registration_and_preserves_settings(mac_plugin_install):
    import xml.etree.ElementTree as ET
    install, home, source, apps = mac_plugin_install
    (apps / 'Rhino 8.app').mkdir()
    base = home / 'Library/Application Support/McNeel/Rhinoceros/8.0'
    settings = base / 'settings/settings-Scheme__Default.xml'
    settings.parent.mkdir(parents=True)
    settings.write_text('<settings><entry key="unrelated">keep me</entry><child key="b70f7d84-06a9-42df-a44b-2808f9a7f430"><child key="PlugIn"><entry key="FileName">/Applications/Rhino 8.app/Contents/PlugIns/rhino-mcp.rhp</entry></child></child></settings>')
    legacy = base / 'Plug-ins/rhino-mcp.rhp'
    legacy.parent.mkdir(); legacy.write_bytes(b'old')
    bundle = install(home, source, apps)[0]
    tree = ET.parse(settings)
    assert tree.find(".//entry[@key='FileName']").text == str(bundle / 'rhino-mcp.rhp')
    assert tree.find(".//entry[@key='unrelated']").text == 'keep me'
    assert not legacy.exists()
    backups = home / 'Library/Application Support/rhino-mcp/backups'
    assert any(p.read_bytes() == b'old' for p in backups.rglob('*') if p.is_file())


def test_mac_plugin_rerun_repairs_missing_dependency(mac_plugin_install):
    install, home, source, apps = mac_plugin_install
    (apps / 'Rhino 8.app').mkdir()
    bundle = install(home, source, apps)[0]
    assembly_mtime = (bundle / 'rhino-mcp.rhp').stat().st_mtime_ns
    (bundle / 'dependency.dll').unlink()
    install(home, source, apps)
    assert (bundle / 'dependency.dll').read_bytes() == b'dependency'
    assert (bundle / 'rhino-mcp.rhp').stat().st_mtime_ns == assembly_mtime


def test_mac_plugin_missing_source_fails_before_mutation(mac_plugin_install):
    install, home, source, apps = mac_plugin_install
    (source / 'rhino-mcp.rhp').unlink()
    with pytest.raises(FileNotFoundError):
        install(home, source, apps)
    assert not home.exists()
