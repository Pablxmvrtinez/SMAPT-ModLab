"""Descarga reproducible del modelo que se incluye en el paquete de escritorio."""
import hashlib
from pathlib import Path
import requests

REVISION='a06e946bb6b655725eafa393f4a9745d460374c9'
FILENAME='Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
SHA256='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
SIZE=2497281120
ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'assets/models';folder.mkdir(parents=True,exist_ok=True)
    dest=folder/FILENAME
    if dest.is_file() and dest.stat().st_size==SIZE:
        with dest.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()==SHA256:
                print('Modelo ya verificado.');return
    tmp=dest.with_suffix('.part')
    url=f'https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/{REVISION}/{FILENAME}'
    digest=hashlib.sha256();size=0
    try:
        with requests.get(url,stream=True,timeout=(20,180)) as r:
            r.raise_for_status()
            with tmp.open('wb') as f:
                for chunk in r.iter_content(4*1024*1024):
                    if chunk:
                        f.write(chunk);digest.update(chunk);size+=len(chunk)
        if size!=SIZE or digest.hexdigest()!=SHA256:
            raise ValueError('La descarga no coincide con el modelo oficial.')
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    for filename in ('LICENSE','NOTICE'):
        r=requests.get(f'https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/{REVISION}/{filename}',timeout=30)
        if r.ok:(folder/filename).write_bytes(r.content)
    print('Modelo integrado y verificado:',dest)


if __name__=='__main__':main()
