"""Equipo, instancias de Minecraft y ajustes gráficos. Solo modifica archivos tras confirmación."""
from datetime import datetime
from pathlib import Path
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys

import psutil

from modlab import logs

log = logs.get('core')
HOME = Path.home()
BACKUPS = '.smapt-backups'
NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0  # CREATE_NO_WINDOW: sin consola emergente


def read_json(path):
    try:
        val = json.loads(Path(path).read_text(encoding='utf-8'))
        return val if isinstance(val, dict) else {}
    except (OSError, ValueError):
        return {}


def _run(args, timeout=5):
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=True,
                              creationflags=NO_WINDOW).stdout
    except (OSError, ValueError, subprocess.SubprocessError):
        return ''


def _cpu_name():
    if sys.platform.startswith('linux'):
        try:
            for line in Path('/proc/cpuinfo').read_text().splitlines():
                if line.startswith('model name'):
                    return line.partition(':')[2].strip()
        except OSError:
            pass
    if sys.platform == 'win32':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0')
            return winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
        except OSError:
            pass
    return platform.processor() or 'Desconocido'


def _gpus():
    """Lista de (nombre, VRAM en MB). NVIDIA por nvidia-smi; AMD/Intel por sysfs o WMI."""
    found = []
    for line in _run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits']).splitlines():
        name, _, mb = line.partition(',')
        if name.strip():
            found.append((name.strip(), int(mb) if mb.strip().isdigit() else 0))
    if found:
        return found
    if sys.platform.startswith('linux'):
        for card in sorted(Path('/sys/class/drm').glob('card[0-9]')):
            device = card / 'device'
            try:
                vram = int((device / 'mem_info_vram_total').read_text()) // (1024 * 1024)
            except (OSError, ValueError):
                vram = 0
            name = _linux_gpu_name(device)
            if name:
                found.append((name, vram))
    elif sys.platform == 'win32':
        rows = _run(['powershell', '-NoProfile', '-Command',
                     'Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + "|" + $_.AdapterRAM }'], 8)
        for line in rows.splitlines():
            name, _, ram = line.partition('|')
            if name.strip() and 'basic' not in name.lower():
                found.append((name.strip(), int(ram) // (1024 * 1024) if ram.strip().isdigit() else 0))
    return found


def _linux_gpu_name(device):
    try:
        vendor = (device / 'vendor').read_text().strip()
    except OSError:
        return ''
    slot = device.resolve().name
    text = _run(['lspci', '-s', slot], 3)
    if text:
        return re.sub(r'^\S+\s+[^:]+:\s*', '', text.strip())[:80]
    return {'0x1002': 'GPU AMD', '0x8086': 'GPU Intel', '0x10de': 'GPU NVIDIA'}.get(vendor, '')


def _system_name():
    if sys.platform.startswith('linux'):
        try:
            for line in Path('/etc/os-release').read_text().splitlines():
                if line.startswith('PRETTY_NAME='):
                    name = line.partition('=')[2].strip('"')
                    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').replace(':', ' / ')
                    return name + (f' · {desktop}' if desktop else '')
        except OSError:
            pass
        return 'Linux'
    if sys.platform == 'win32':
        return f'Windows {platform.release()} ({platform.version()})'
    return platform.platform()


def hardware():
    gpus = _gpus()
    best = max(gpus, key=lambda g: g[1], default=('No detectada', 0))
    vm = psutil.virtual_memory()
    return {'cpu': _cpu_name(), 'threads': psutil.cpu_count() or 1,
            'ram_gb': round(vm.total / 1024 ** 3, 1), 'ram_available_gb': round(vm.available / 1024 ** 3, 1),
            'gpu': best[0], 'vram_gb': round(best[1] / 1024, 1), 'gpus': [g[0] for g in gpus],
            'system': _system_name()}


def launcher_folders():
    """Carpetas de instancias conocidas en Windows y Linux."""
    appdata = Path(os.environ.get('APPDATA') or HOME / 'AppData/Roaming')
    local = Path(os.environ.get('XDG_DATA_HOME') or HOME / '.local/share')
    flatpak = HOME / '.var/app'
    folders = [
        ('CurseForge', HOME / 'curseforge/minecraft/Instances'),
        ('CurseForge', HOME / 'Documents/curseforge/minecraft/Instances'),
        ('Prism', local / 'PrismLauncher/instances'),
        ('Prism', flatpak / 'org.prismlauncher.PrismLauncher/data/PrismLauncher/instances'),
        ('Prism', appdata / 'PrismLauncher/instances'),
        ('MultiMC', HOME / 'MultiMC/instances'),
        ('Modrinth App', local / 'com.modrinth.theseus/profiles'),
        ('Modrinth App', local / 'ModrinthApp/profiles'),
        ('Modrinth App', appdata / 'com.modrinth.theseus/profiles'),
        ('Modrinth App', appdata / 'ModrinthApp/profiles'),
        ('ATLauncher', local / 'ATLauncher/instances'),
        ('ATLauncher', appdata / 'ATLauncher/instances'),
        ('ATLauncher', flatpak / 'com.atlauncher.ATLauncher/data/instances'),
    ]
    seen, result = set(), []
    for launcher, path in folders:
        try:
            key = path.resolve()
        except OSError:
            continue
        if key not in seen:
            seen.add(key)
            result.append((launcher, path))
    return result


def _prism_meta(folder):
    pack = read_json(folder / 'mmc-pack.json')
    version, loader = '', ''
    names = {'net.minecraftforge': 'Forge', 'net.neoforged': 'NeoForge', 'net.fabricmc.fabric-loader': 'Fabric',
             'org.quiltmc.quilt-loader': 'Quilt'}
    for component in pack.get('components', []) if isinstance(pack.get('components'), list) else []:
        uid = component.get('uid')
        if uid == 'net.minecraft':
            version = component.get('version', '')
        elif uid in names:
            loader = names[uid]
    name = ''
    try:
        for line in (folder / 'instance.cfg').read_text(errors='ignore').splitlines():
            if line.startswith('name='):
                name = line.partition('=')[2].strip()
    except OSError:
        pass
    return name, version, loader


def _loader_name(text):
    text = (text or '').lower()
    for name in ('neoforge', 'forge', 'fabric', 'quilt'):
        if name in text:
            return {'neoforge': 'NeoForge', 'forge': 'Forge', 'fabric': 'Fabric', 'quilt': 'Quilt'}[name]
    return ''


def instance_info(launcher, folder):
    work = folder / '.minecraft' if (folder / '.minecraft').is_dir() else folder / 'minecraft' if (folder / 'minecraft').is_dir() else folder
    manifest = read_json(folder / 'manifest.json')
    meta = read_json(folder / 'minecraftinstance.json')
    profile = read_json(folder / 'profile.json')
    mods = work / 'mods'
    try:
        count = sum(1 for f in mods.iterdir() if f.suffix == '.jar') if mods.is_dir() else 0
    except OSError:
        count = 0
    if not count and not manifest and not meta and not profile and not (work / 'options.txt').is_file():
        return None
    name, version, loader = _prism_meta(folder) if (folder / 'mmc-pack.json').is_file() else ('', '', '')
    mc = manifest.get('minecraft') if isinstance(manifest.get('minecraft'), dict) else {}
    version = version or mc.get('version', '') or meta.get('gameVersion', '') or str(profile.get('game_version', ''))
    loaders = mc.get('modLoaders') if isinstance(mc.get('modLoaders'), list) else []
    base = meta.get('baseModLoader') if isinstance(meta.get('baseModLoader'), dict) else {}
    loader = loader or _loader_name(base.get('name')) or _loader_name(loaders[0].get('id') if loaders else '') or \
        _loader_name(str(profile.get('loader', '')))
    return {'name': name or meta.get('name') or manifest.get('name') or profile.get('name') or folder.name,
            'path': str(work), 'folder': str(folder), 'launcher': launcher, 'mods': count,
            'version': version, 'loader': loader}


def instances(folders=None):
    result = []
    for launcher, base in folders or launcher_folders():
        try:
            if not base.is_dir():
                continue
            children = [f for f in base.iterdir() if f.is_dir() and not f.name.startswith(('.', '_'))]
        except OSError:
            continue
        for folder in children:
            info = instance_info(launcher, folder)
            if info:
                result.append(info)
    official = Path(os.environ.get('APPDATA') or HOME / 'AppData/Roaming') / '.minecraft' if sys.platform == 'win32' else HOME / '.minecraft'
    if folders is None and (official / 'options.txt').is_file():
        mods = official / 'mods'
        result.append({'name': 'Lanzador oficial', 'path': str(official), 'folder': str(official), 'launcher': 'Minecraft',
                       'mods': len(list(mods.glob('*.jar'))) if mods.is_dir() else 0, 'version': '', 'loader': ''})
    return sorted(result, key=lambda p: (p['launcher'], p['name'].casefold()))


def recommend(mods, hw, mode='Equilibrado'):
    heap = min(max(1, int(hw['ram_gb'] * .47)), max(2, math.ceil(4 + mods / 45)))
    render = 12 if mods < 100 else 10 if mods < 200 else 8
    sim = 8 if mods < 180 else 6
    fps = 120 if mods < 200 else 90
    shaders = hw['vram_gb'] >= 8 and mods < 160
    if mode == 'Máximos FPS':
        render = max(6, render - 2)
        sim = max(5, sim - 1)
        fps = 144
        shaders = False
    if mode == 'Calidad visual':
        render = min(14, render + 2)
        sim = min(10, sim + 1)
        fps = 120
        shaders = hw['vram_gb'] >= 8 and mods < 230
    return dict(heap=heap, render=render, simulation=sim, fps=fps, shaders=shaders, mode=mode)


def is_running(path):
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if 'java' not in (proc.info['name'] or '').lower():
                continue
            text = ' '.join(proc.info['cmdline'] or [])
            if str(path) in text or str(Path(path).parent) in text:
                return True
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return False


def _shader_file(folder):
    for name in ('oculus.properties', 'iris.properties'):
        path = folder / 'config' / name
        if path.is_file():
            return path
    return folder / 'config/oculus.properties'


def apply_graphics(inst, settings):
    folder = Path(inst['path'])
    options = folder / 'options.txt'
    if not options.is_file():
        raise ValueError('No se encuentra options.txt en esta instancia. Abre Minecraft una vez para crearlo.')
    if is_running(folder):
        raise RuntimeError('Cierra Minecraft antes de modificar sus gráficos.')
    shader = _shader_file(folder)
    backup = folder / BACKUPS / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(options, backup / 'options.txt')
    if shader.is_file():
        shutil.copy2(shader, backup / shader.name)
    changes = {'renderDistance': str(settings['render']), 'simulationDistance': str(settings['simulation']),
               'maxFps': str(settings['fps']), 'enableVsync': 'false',
               'particles': '1' if settings['mode'] == 'Máximos FPS' else '0'}
    lines = options.read_text(encoding='utf-8', errors='replace').splitlines()
    seen, updated = set(), []
    for line in lines:
        k, sep, _ = line.partition(':')
        if sep and k in changes:
            updated.append(k + ':' + changes[k])
            seen.add(k)
        else:
            updated.append(line)
    for key, val in changes.items():
        if key not in seen:
            updated.append(key + ':' + val)
    options.write_text('\n'.join(updated) + '\n', encoding='utf-8')
    if shader.is_file():
        rows = shader.read_text(encoding='utf-8', errors='replace').splitlines()
        out, seen_shader = [], False
        for line in rows:
            if line.startswith('enableShaders='):
                out.append('enableShaders=' + str(settings['shaders']).lower())
                seen_shader = True
            else:
                out.append(line)
        if not seen_shader:
            out.append('enableShaders=' + str(settings['shaders']).lower())
        shader.write_text('\n'.join(out) + '\n', encoding='utf-8')
    return str(backup)


def backups(inst):
    folder = Path(inst['path']) / BACKUPS
    try:
        return sorted((p for p in folder.iterdir() if p.is_dir() and (p / 'options.txt').is_file()), reverse=True)
    except OSError:
        return []


def restore_backup(inst, backup):
    """Restaura options.txt (y el archivo de shaders) desde una copia, guardando antes el estado actual."""
    folder = Path(inst['path'])
    backup = Path(backup)
    if backup.parent != folder / BACKUPS or not (backup / 'options.txt').is_file():
        raise ValueError('La copia de seguridad no pertenece a esta instancia.')
    if is_running(folder):
        raise RuntimeError('Cierra Minecraft antes de restaurar sus gráficos.')
    current = folder / BACKUPS / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_antes-de-restaurar')
    current.mkdir(parents=True)
    shutil.copy2(folder / 'options.txt', current / 'options.txt')
    shutil.copy2(backup / 'options.txt', folder / 'options.txt')
    for name in ('oculus.properties', 'iris.properties'):
        if (backup / name).is_file():
            target = folder / 'config' / name
            if target.is_file():
                shutil.copy2(target, current / name)
            shutil.copy2(backup / name, target)
    return str(current)
