from pathlib import Path

import glob


from doit.tools import create_folder
from pydantic import TypeAdapter



from cnam.video_downloader.utils import (
    build_download_video_youtube_task, youtube_dl_bin, is_file_exist
)
from cnam.video_downloader.model.youtube.playlist_json import PlaylistJsonModel

from cnam.video_downloader.tasks.eu.eu_page import EuPageTask
from cnam.video_downloader.tasks.eu.eu_generic import EuGenericTask




class DownloadYoutubeResourceTask(EuGenericTask):
    """
    Tâche permettant le téléchargement d'une vidéo youtube
    """
    def to_tasks(self):
        file_even_create = set()
        def gen_tasks(fd, path):
            playlist_info = TypeAdapter(PlaylistJsonModel).validate_json(fd.read())
            for entry in playlist_info.root.entries:
                if not entry.requested_downloads:
                    continue
                filename = self.normalize_name(entry.requested_downloads[0].filename)
                target = Path(self.folder_video,filename)
                if target in file_even_create:
                    continue
                file_even_create.add(target)
                url = entry.original_url
                yield build_download_video_youtube_task(url, target, file_dep=[str(path)])



        try:
            for path in glob.glob(f'{self.folder_video_information}/*.youtube.json'):
                with open(
                    path,
                    mode="r",
                    encoding="utf-8",
                ) as fd:
                    yield from gen_tasks(fd, path)
        except FileNotFoundError:
            pass

class DownloadYoutubePlaylistInformation(EuPageTask):
    """
    Tâche récupérant les informations des playlists youtube disponible pour une EU.
    """

    def to_tasks(self):
        yield self.main_task
        youtube_dl = youtube_dl_bin.get()
        file_already_downloaded = set()
        for view_link_resource in self.get_youtube_view():
            for link_resource in self.get_youtube_from_page(view_link_resource.url):
                name = self.normalize_name(link_resource.text)
                if name in file_already_downloaded:
                    continue
                file_already_downloaded.add(name)
                #yield from DownloadYoutubeResourceTask(
                #    eu_id=self.eu_id, url=url_resource, filename=name
                #).to_tasks()
                target=str(Path(self.folder_video_information, f'{name}.youtube.json'))
                yield self.new_sub_task(
                    name=target,
                    actions=[
                        (create_folder, [self.folder_video_information]),
                        f"'{youtube_dl}' --no-warnings --dump-single-json "
                        f"--simulate '{link_resource.url}' > '{target}'"
                    ],
                    uptodate=[is_file_exist(target)],
                    verbosity=2,
                    targets=[target]
                )
