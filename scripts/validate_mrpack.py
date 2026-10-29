"""Comprueba un .mrpack exportado por SMAPT ModLab.

Ejemplo: python scripts/validate_mrpack.py mi-pack.mrpack
No extrae archivos ni descarga mods.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modlab.mrpack_validator import MrpackValidationError, validate_exported_mrpack  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Ruta al .mrpack que quieres validar")
    args = parser.parse_args()
    try:
        result = validate_exported_mrpack(args.archive)
    except MrpackValidationError as exc:
        print("PAQUETE INVÁLIDO:", exc, file=sys.stderr)
        return 1
    print("PAQUETE VÁLIDO:", result["mods"], "mod(s)")
    print("Minecraft:", result["minecraft"])
    print("Cargador:", result["loader"])
    print("Aviso: esta revisión no garantiza que Minecraft arranque.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
