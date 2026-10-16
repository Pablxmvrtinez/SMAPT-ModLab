"""Motor local de S.M.A.P.T. ModLab: solo modifica ajustes tras confirmación."""
from pathlib import Path
from datetime import datetime
import json, math, shutil, subprocess
import psutil

HOME = Path.home()
ROOT = Path(__file__).resolve().parent
INSTANCES = [
    ("CurseForge", HOME / "Documents/curseforge/minecraft/Instances"),
    ("Prism", HOME / ".var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances"),
]

def read_json(path):
    try:
        val = json.loads(path.read_text())
        return val if isinstance(val, dict) else {}
    except (OSError, ValueError):
        return {}

def hardware():
    cpu = "Desconocido"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.partition(":")[2].strip()
                break
    except OSError:
        pass
    gpu, vram = "No detectada", 0
    try:
        lines = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
          "--format=csv,noheader,nounits"], text=True, capture_output=True,
          timeout=5, check=True).stdout.splitlines()
        if lines:
            gpu, mb = (s.strip() for s in lines[0].split(",", 1))
            vram = int(mb)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    vm = psutil.virtual_memory()
    return {"cpu":cpu, "threads":psutil.cpu_count() or 1,
            "ram_gb":round(vm.total/1024**3,1),
            "ram_available_gb":round(vm.available/1024**3,1),
            "gpu":gpu, "vram_gb":round(vram/1024,1)}

def instances():
    result = []
    for launcher, base in INSTANCES:
        if not base.is_dir():
            continue
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            work = folder/".minecraft" if (folder/".minecraft").is_dir() else folder
            manifest = read_json(folder/"manifest.json")
            meta = read_json(folder/"minecraftinstance.json")
            count = len(list((work/"mods").glob("*.jar")))
            if not count and not manifest and not meta and not (work/"options.txt").is_file():
                continue
            mc = manifest.get("minecraft") or {}
            version = mc.get("version", "") if isinstance(mc,dict) else ""
            result.append({"name":meta.get("name") or manifest.get("name") or folder.name,
                "path":str(work),"launcher":launcher, "mods":count,
                "version":version or meta.get("gameVersion") or ""})
    return sorted(result,key=lambda p:(p["launcher"],p["name"].casefold()))

def recommend(mods, hw, mode="Equilibrado"):
    heap = min(max(1,int(hw["ram_gb"]*.47)), max(2,math.ceil(4+mods/45)))
    render = 12 if mods<100 else 10 if mods<200 else 8
    sim = 8 if mods<180 else 6
    fps = 120 if mods<200 else 90
    shaders = hw["vram_gb"]>=8 and mods<160
    if mode=="Máximos FPS":
        render=max(6,render-2); sim=max(5,sim-1);fps=144;shaders=False
    if mode=="Calidad visual":
        render=min(14,render+2);sim=min(10,sim+1);fps=120
        shaders = hw["vram_gb"]>=8 and mods<230
    return dict(heap=heap,render=render,simulation=sim,fps=fps,shaders=shaders,mode=mode)

def is_running(path):
    for proc in psutil.process_iter(["name","cmdline"]):
        try:
            if "java" not in (proc.info["name"] or "").lower():
                continue
            text=" ".join(proc.info["cmdline"] or [])
            if str(path) in text or str(Path(path).parent) in text:
                return True
        except (psutil.AccessDenied,psutil.NoSuchProcess):
            continue
    return False

def apply_graphics(inst, settings):
    folder=Path(inst["path"]);options=folder/"options.txt"
    if not options.is_file():
        raise ValueError("No se encuentra options.txt en esta instancia.")
    if is_running(folder):
        raise RuntimeError("Cierra Minecraft antes de modificar sus gráficos.")
    shader=folder/"config/oculus.properties"
    backup=folder/".smapt-backups"/datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup.mkdir(parents=True,exist_ok=False)
    shutil.copy2(options,backup/"options.txt")
    if shader.is_file():
        shutil.copy2(shader,backup/"oculus.properties")
    changes={"renderDistance":str(settings["render"]),
      "simulationDistance":str(settings["simulation"]),
      "maxFps":str(settings["fps"]),"enableVsync":"false",
      "particles":"1" if settings["mode"]=="Máximos FPS" else "0"}
    lines=options.read_text().splitlines();seen=set();updated=[]
    for line in lines:
        k,sep,val=line.partition(":")
        if sep and k in changes:
            updated.append(k+":"+changes[k]);seen.add(k)
        else:updated.append(line)
    for key,val in changes.items():
        if key not in seen:updated.append(key+":"+val)
    options.write_text("\n".join(updated)+"\n")
    if shader.is_file():
        rows=shader.read_text().splitlines();out=[];seen=False
        for line in rows:
            if line.startswith("enableShaders="):
                out.append("enableShaders="+str(settings["shaders"]).lower());seen=True
            else:out.append(line)
        if not seen:out.append("enableShaders="+str(settings["shaders"]).lower())
        shader.write_text("\n".join(out)+"\n")
    return str(backup)

def save_plan(phrase,version,loader,mods,profile,hw,experience=None,destination=None):
    if destination:
        file=Path(destination)
    else:
        out=ROOT/"planes"
        out.mkdir(exist_ok=True,parents=True)
        file=out/("plan-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".json")
    obj={"description":phrase,"minecraft":version,"loader":loader,
         "hardware":hw,"profile":profile,"mods":mods,"experience":experience,
         "note":"Selección preliminar. No instala los mods ni verifica todas sus dependencias."}
    file.write_text(json.dumps(obj,indent=2,ensure_ascii=False))
    return file
