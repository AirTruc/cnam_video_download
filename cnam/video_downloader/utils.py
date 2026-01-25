"""
Contient les fichiers utiles à tous.
"""
import contextvars
from pathlib import Path
import urllib


youtube_dl_bin = contextvars.ContextVar("youtube_dl_bin")
ffmpeg_bin = contextvars.ContextVar("ffmpeg_bin")

def build_local_file(el_id, filename):
    """
    Construit le chemin de travail pour fichier et une tâche.
    """
    return f"tmp/{el_id}/{filename}"

def save_request(request, ident):
    """
    Sauvegarde une requête Request afin de pouvoir mieux analyser les problèmes.
    """
    folder = Path('tmp', ident)
    folder.mkdir(0o755, parents=True, exist_ok=True)
    file_path = Path(folder, urllib.parse.quote_plus(request.url)[0:254])
    with open(file_path, 'w', encoding='utf-8') as fd:
        fd.write(request.text)

def build_download_video_youtube_task(url, target, width:int=1280, height:int=720, duration:int = 5, file_dep=None):
    if file_dep is None:
        file_dep=[]
    youtube_dl = youtube_dl_bin.get()
    target = str(target)
    return {
        "name": target,
        "actions": [
            f"{youtube_dl} -o '{target}' '{url}' || true" # Download youtube video
            #" || " # Si la vidéo n'existe pas
            #f"{ffmpeg_bin.get()} -t '{duration}' -f lavfi -i 'color=c=black:s={width}x{height}' -c:v libx265 '{target}'" # On créer une vidéo vide.
        ],
        "file_dep":file_dep,
        "targets": [target],
    }

def is_file_exist(filename):
    """
    Test l'exitance d'un fichier
    """
    return Path(filename).is_file()
