"""Install a version-specific Rhino for Mac bundle and repair cached registration."""
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

PLUGIN_ID = "b70f7d84-06a9-42df-a44b-2808f9a7f430"


def install(home: Path, source: Path, applications: Path = Path('/Applications')) -> list[Path]:
    assembly = source / 'rhino-mcp.rhp'
    if not assembly.is_file():
        raise FileNotFoundError(f'Missing plugin assembly: {assembly}')
    support = home / 'Library/Application Support/McNeel/Rhinoceros'
    backup_root = home / 'Library/Application Support/rhino-mcp/backups'
    backup = None

    def preserve(path: Path) -> None:
        nonlocal backup
        if backup is None:
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix='registration-', dir=backup_root))
        destination = backup / str(path.relative_to(support)).replace('/', '__')
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)

    installed = []
    for major in (8, 9):
        if not (applications / f'Rhino {major}.app').is_dir():
            continue
        base = support / f'{major}.0'
        bundle = base / 'MacPlugIns/rhino-mcp.rhp'
        bundle.mkdir(parents=True, exist_ok=True)
        for file in source.iterdir():
            if file.suffix not in {'.rhp', '.dll', '.json'} or not file.is_file():
                continue
            target = bundle / file.name
            if target.exists() and target.read_bytes() == file.read_bytes():
                continue
            if target.exists():
                preserve(target)
            shutil.copy2(file, target)
        legacy = base / 'Plug-ins/rhino-mcp.rhp'
        if legacy.exists():
            preserve(legacy)
            if legacy.is_dir():
                shutil.rmtree(legacy)
            else:
                legacy.unlink()
        # Rhino must be closed; configure/preinstall enforce this before calling.
        for settings in (base / 'settings').glob('settings-*.xml'):
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
            tree = ET.parse(settings, parser=parser)
            node = tree.find(f".//child[@key='{PLUGIN_ID}']/child[@key='PlugIn']/entry[@key='FileName']")
            if node is None or node.text == str(bundle / 'rhino-mcp.rhp'):
                continue
            preserve(settings)
            node.text = str(bundle / 'rhino-mcp.rhp')
            temporary = settings.with_suffix('.xml.rhino-mcp.tmp')
            try:
                tree.write(temporary, encoding='utf-8', xml_declaration=True)
                temporary.chmod(settings.stat().st_mode & 0o777)
                temporary.replace(settings)
            finally:
                temporary.unlink(missing_ok=True)
        yak = support / 'packages' / f'{major}.0' / 'rhino-mcp'
        if yak.exists():
            preserve(yak)
            shutil.rmtree(yak)
        installed.append(bundle)
    return installed


if __name__ == '__main__':
    import sys
    for bundle in install(Path.home(), Path(sys.argv[1])):
        print(f'Rhino plugin registered: {bundle}')
