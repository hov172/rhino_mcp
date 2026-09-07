"""Verify all four PDF tools using the exact Python runtime being packaged."""
from pathlib import Path
from importlib.metadata import distribution, PackageNotFoundError
import os
import sys
import tempfile

from rhmcp.tools import documents


class Registry:
    def __init__(self):
        self.tools = {}

    def tool(self, **kwargs):
        def add(fn):
            self.tools[fn.__name__] = fn
            return fn
        return add


for name in ('pymupdf', 'pymupdfb', 'fitz'):
    try:
        distribution(name)
    except PackageNotFoundError:
        pass
    else:
        raise RuntimeError(f'Forbidden dependency: {name}')
registry = Registry()
documents.register(registry)
with tempfile.TemporaryDirectory(prefix='rhmcp-pdf-smoke-') as tmp:
    os.environ['RHINO_MCP_READ_ROOTS'] = tmp
    path = Path(tmp)/'smoke.pdf'
    path.write_bytes(Path(sys.argv[1]).read_bytes())
    tools = registry.tools
    assert tools['get_pdf_info'](str(path))['page_count'] == 1
    rendered = tools['read_pdf'](str(path), dpi=150, scale_hint='1/4" = 1\'')
    assert rendered['ok'], rendered
    result = tools['read_pdf_vectors'](str(path), dpi=150, real_units_per_px=rendered['scale']['real_units_per_px'])
    assert result['ok'], result
    assert abs(result['pages'][0]['segments'][0]['length_real']-4) < 1e-9
    result = tools['extract_pdf_dimensions'](str(path), dpi=150)
    assert result['ok'] and result['total_dimensions'] == 1, result
print('PASS: four packaged PDF tools, exact scale, isolated workers, and no PyMuPDF.')
