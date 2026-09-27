# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# Asset data folders to bundle inside the binary
datas = [
    ('schemas', 'schemas'),
    ('examples', 'examples'),
    ('docs', 'docs'),
]

hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'omniuart',
    'omniuart.cli',
    'omniuart.ui',
    'omniuart.ui.app',
    'omniuart.ui.models',
    'omniuart.ui.routes',
    'omniuart.ui.views',
    'omniuart.ui.desktop',
    'omniuart.desktop',
    'omniuart.desktop.app',
    'omniuart.desktop.views',
    'omniuart.entrypoints',
    'omniuart.entrypoints.cli_main',
    'omniuart.entrypoints.web_main',
    'omniuart.entrypoints.desktop_main',
    'omniuart.core',
    'omniuart.core.models',
    'omniuart.core.catalog',
    'omniuart.core.recorder',
    'omniuart.core.transport',
    'omniuart.core.fuzzer',
    'omniuart.core.replayer',
    'omniuart.docs_generator',
    'pydantic',
    'pydantic_core',
    'serial',
    'serial.tools.list_ports',
    'yaml',
    'rich',
    'typer',
    'fastapi',
    'starlette',
    'tkinter',
    'tkinter.ttk',
]

# 1. CLI Analysis & EXE
a_cli = Analysis(
    ['src/omniuart/entrypoints/cli_main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'numpy', 'IPython'],
    cipher=block_cipher,
    noarchive=False,
)
pyz_cli = PYZ(a_cli.pure, a_cli.zipped_data, cipher=block_cipher)
exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    a_cli.binaries,
    a_cli.zipfiles,
    a_cli.datas,
    [],
    name='omni-uart-cli',
    debug=False,
    strip=False,
    upx=True,
    console=True,
)

# 2. Web UI Analysis & EXE
a_web = Analysis(
    ['src/omniuart/entrypoints/web_main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'numpy', 'IPython'],
    cipher=block_cipher,
    noarchive=False,
)
pyz_web = PYZ(a_web.pure, a_web.zipped_data, cipher=block_cipher)
exe_web = EXE(
    pyz_web,
    a_web.scripts,
    a_web.binaries,
    a_web.zipfiles,
    a_web.datas,
    [],
    name='omni-uart-web',
    debug=False,
    strip=False,
    upx=True,
    console=True,
)

# 3. Desktop UI Analysis & EXE (Native Tkinter Desktop App)
a_desktop = Analysis(
    ['src/omniuart/entrypoints/desktop_main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'numpy', 'IPython'],
    cipher=block_cipher,
    noarchive=False,
)
pyz_desktop = PYZ(a_desktop.pure, a_desktop.zipped_data, cipher=block_cipher)
exe_desktop = EXE(
    pyz_desktop,
    a_desktop.scripts,
    a_desktop.binaries,
    a_desktop.zipfiles,
    a_desktop.datas,
    [],
    name='omni-uart-desktop',
    debug=False,
    strip=False,
    upx=True,
    console=True,
)
