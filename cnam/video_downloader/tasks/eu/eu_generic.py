from pathlib import Path

import unicodedata

import contextvars

from pydantic import BaseModel


from cnam.video_downloader.tasks.shared.generic_task import GenericTask

from cnam.video_downloader.tasks.eu.eu_id import EuId

base_dir = contextvars.ContextVar("base_dir")


class FolderMissing(Exception):
    """
    Exception levée quand le dossier est manquant
    """

class EuGenericTask(GenericTask, BaseModel):
    """
    Tâche générique liée à l'EU.
    """
    eu_id: EuId

    @property
    def id(self):
        """
        L'id de l'EU.
        """
        return self.eu_id.id

    @property
    def folder_eu(self):
        """
        Le dossier où sera sauvegardé les fichiers de l'EU. 
        """
        folder = base_dir.get()
        if folder is None:
            raise FolderMissing()
        return Path(folder, self.eu_id.name)

    @property
    def tmp_folder(self):
        """
        Le dossier où sera sauvegardé les fichiers de l'EU. 
        """
        folder = base_dir.get()
        if folder is None:
            raise FolderMissing()
        return Path('tmp', self.eu_id.name)

    @property
    def folder_video_information(self):
        """
        Dossier contenant les fichiers d'information des playlists
        """
        return Path(self.tmp_folder, 'video_information')

    @property
    def tmp_folder_video(self):
        """
        Dossier temporaire contenant les videos des playlists
        """
        return Path(self.tmp_folder, 'video')

    @property
    def folder_video(self):
        """
        Dossier contenant les videos des playlists
        """
        return Path(self.folder_eu, 'video')

    @classmethod
    def normalize_name(cls, name:str):
        """
        Normalise le nom d'une tâche
        """
        name = name.replace('/', '').replace("'",'_')
        return unicodedata.normalize('NFC', name)
