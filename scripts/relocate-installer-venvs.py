"""Rewrite staged venv paths to the installed prefix before code signing."""
from pathlib import Path
import sys


def relocate(payload: Path) -> None:
    sources = sorted({str(payload), str(payload.resolve())}, key=len, reverse=True)
    target = "/Users/Shared/rhino_mcp"
    for arch in ("arm64", "x86_64"):
        venv = payload / f".venv-{arch}"
        for path in [venv / "pyvenv.cfg", *(venv / "bin").iterdir()]:
            if path.is_symlink():
                link = str(path.readlink())
                updated = link
                for source in sources:
                    updated = updated.replace(source, target)
                if updated != link:
                    path.unlink()
                    path.symlink_to(updated)
            elif path.is_file():
                try:
                    text = path.read_text()
                except UnicodeError:
                    continue
                updated = text
                for source in sources:
                    updated = updated.replace(source, target)
                if updated != text:
                    path.write_text(updated)

        python_link = venv / "bin/python3.13"
        if not str(python_link.readlink()).startswith(target + "/"):
            raise RuntimeError(f"Unrelocated Python link: {python_link}")
        if any(source in (venv / "pyvenv.cfg").read_text() for source in sources):
            raise RuntimeError(f"Unrelocated venv configuration: {venv}")


if __name__ == "__main__":
    relocate(Path(sys.argv[1]))
