"""Construye el paquete portable en el sistema de destino (Linux/Windows)."""
from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import importlib.util
import tarfile


def main():
    root=Path(__file__).resolve().parent
    model=root/'assets/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
    if not model.is_file() or model.stat().st_size!=2497281120:
        raise SystemExit('Falta el modelo integrado. Ejecuta primero python scripts/fetch_model.py.')
    if importlib.util.find_spec('llama_cpp') is None:
        raise SystemExit('Instala las dependencias de requirements.txt para construir la edición completa.')
    with tempfile.TemporaryDirectory(prefix='smapt-build-') as temp:
        import json
        config=Path(temp)/'app-config.json'
        config.write_text(json.dumps({'catalog_url':os.getenv('SMAPT_CATALOG_URL','')}))
        env=dict(os.environ,PYINSTALLER_CONFIG_DIR=str(Path(temp)/'cache'))
        subprocess.run([sys.executable,'-m','PyInstaller','--onedir','--windowed',
            '--name','SMAPT-ModLab','--noupx','--noconfirm',
            '--collect-all','llama_cpp','--exclude-module','llama_cpp.server',
            '--exclude-module','torch','--exclude-module','transformers',
            '--add-data',str(model)+':assets/models',
            '--add-data',str(root/'assets/models/LICENSE')+':assets/models',
            '--add-data',str(config)+':.',
            '--distpath',str(root/'dist'),'--workpath',str(Path(temp)/'work'),
            '--specpath',temp,'--log-level','WARN',str(root/'app.py')],
            cwd=root,env=env,check=True)
    folder=root/'dist'/'SMAPT-ModLab'
    for name in ('README.md','THIRD_PARTY.md'):
        shutil.copy2(root/name,folder/name)
    from importlib.metadata import distribution, PackageNotFoundError
    licenses=folder/'LICENSES';licenses.mkdir(exist_ok=True)
    for name in ('requests','psutil','PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','llama-cpp-python','numpy','diskcache','jinja2','urllib3','certifi','charset-normalizer','idna'):
        try:
            dist=distribution(name)
        except PackageNotFoundError:
            continue
        for file in dist.files or []:
            if any(word in str(file).lower() for word in ('license','copying','notice')):
                source=Path(dist.locate_file(file))
                if source.is_file():
                    target=licenses/name/file.name;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,target)
    # Paquetes Qt de distribuciones Linux instalan licencias fuera de los metadatos Python.
    system_licenses=Path('/usr/share/licenses')
    for name in ('qt6-base','qt6-svg','qt6-wayland','pyside6','shiboken6'):
        source=system_licenses/name
        if source.is_dir():shutil.copytree(source,licenses/name,dirs_exist_ok=True)
    if sys.platform.startswith('linux'):

        start=folder/'Abrir-ModLab.sh'
        start.write_text('#!/bin/sh\ncd -- "$(dirname -- "$0")" || exit 1\nexec ./SMAPT-ModLab "$@"\n')
        start.chmod(0o755)
    label='windows' if sys.platform=='win32' else 'linux' if sys.platform.startswith('linux') else sys.platform
    archive_path=root/'dist'/('SMAPT-ModLab-'+label+'-'+platform.machine())
    if sys.platform=='win32':
        archive=shutil.make_archive(str(archive_path),'zip',root_dir=root/'dist',base_dir='SMAPT-ModLab')
    else:
        archive=str(archive_path)+'.tar.gz'
        with tarfile.open(archive,'w:gz',compresslevel=1) as packed:
            packed.add(folder,arcname='SMAPT-ModLab')
    print('Paquete listo:',archive)


if __name__=='__main__':
    main()
