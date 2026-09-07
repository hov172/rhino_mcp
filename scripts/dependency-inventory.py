"""Validate PDF dependency policy and export installed versions/license notices.

Run with the exact runtime being packaged. This is an inventory/policy check,
not a legal determination about the complete distribution.
"""

from importlib.metadata import distributions
from pathlib import Path
import hashlib
import json
import re
import sys


def inventory(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    components = []
    pdf_names = {"pypdfium2", "pdfplumber", "pdfminer-six", "psutil"}
    found = set()
    for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        normalized = re.sub(r"[-_.]+", "-", name.lower())
        if normalized in {"pymupdf", "pymupdfb", "fitz", "mupdf"}:
            raise RuntimeError(f"Forbidden PDF dependency: {name}")
        license_text = (
            dist.metadata.get("License-Expression")
            or dist.metadata.get("License")
            or ""
        )
        classifiers = dist.metadata.get_all("Classifier") or []
        if normalized in pdf_names:
            found.add(normalized)
            if "AGPL" in license_text.upper():
                raise RuntimeError(f"Unexpected PDF license: {name}")
        notices = []
        for file in dist.files or []:
            relative = Path(str(file))
            if not any(
                word in str(relative).lower()
                for word in ("license", "copying", "notice")
            ):
                continue
            if relative.is_absolute() or ".." in relative.parts:
                continue
            source = Path(dist.locate_file(file))
            if not source.is_file():
                continue
            target = destination / "licenses" / normalized / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            target.write_bytes(data)
            notices.append(
                {
                    "file": str(target.relative_to(destination)),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        if normalized in pdf_names and not notices:
            raise RuntimeError(f"Missing PDF license notices: {name}")
        components.append(
            {
                "name": name,
                "version": dist.version,
                "license": license_text,
                "license_classifiers": [
                    c for c in classifiers if c.startswith("License ::")
                ],
                "notices": notices,
            }
        )
    if found != pdf_names:
        raise RuntimeError(f"Missing PDF dependencies: {pdf_names - found}")
    (destination / "inventory.json").write_text(json.dumps(components, indent=2))
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "components": [
            {
                "type": "library",
                "name": c["name"],
                "version": c["version"],
                "purl": f"pkg:pypi/{re.sub(r'[-_.]+', '-', c['name'].lower())}@{c['version']}",
            }
            for c in components
        ],
    }
    (destination / "bom.cdx.json").write_text(json.dumps(bom, indent=2))
    print(
        f"PDF dependency policy passed; inventoried {len(components)} Python packages and copied notices."
    )


if __name__ == "__main__":
    inventory(sys.argv[1])
