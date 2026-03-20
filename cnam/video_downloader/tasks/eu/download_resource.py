from typing import TypeVar, Callable
from pathlib import Path
from urllib.parse import urlsplit


from doit.tools import create_folder

from cnam.video_downloader.session import requests_session, download_file
from cnam.video_downloader.utils import is_file_exist

from cnam.video_downloader.tasks.eu.eu_page import EuPageTask
from cnam.video_downloader.tasks.eu.eu_generic import EuGenericTask
from cnam.video_downloader.tasks.eu.link_resource import LinkResource
from cnam.video_downloader.tasks.eu.utils import connect_moodle


Element = TypeVar('Element')
GetNameRenameOfElement = Callable[[Element], str]
CreateNewElement = Callable[[Element, str], Element]
BuildName = Callable[[str, int, int], str]
def build_default_name(name: str, total_count_recurrence:int, index: int) -> str:
    return name + '_' + str(index + 1) if total_count_recurrence > 1 else name

def rename_element_if_duplicated(
            resources: list[Element],
            get_name:GetNameRenameOfElement,
            create_new_element:CreateNewElement,
            build_name: BuildName = build_default_name
        ) -> list[LinkResource]:
    new_resources = []
    resources_name = [get_name(r) for r in resources]
    for i, v in enumerate(resources_name):
        total_count = resources_name.count(v)
        count = resources_name[:i].count(v)
        resource = resources[i]
        new_name = build_name(v, total_count, count)
        new_resources.append(create_new_element(resource, new_name))
    return new_resources


def build_resource_name(page: LinkResource, link_resource: LinkResource):
    name = page.text.strip() + '__' + link_resource.text.strip()
    name = DownloadResourceTask.normalize_name(name)
    name_path = Path(name)
    if not name_path.suffixes:
        suffixes = Path(urlsplit(link_resource.url).path).suffixes
        name = ''.join([name] + suffixes)
    return name


class DownloadAllResourcesTask(EuPageTask):
    """
    Tâche téléchargeant des ressources disponible pour une EU.
    """

    def get_page_with_resource_to_download(self) -> list[LinkResource]:
        return self.get_views() + self.get_folders()


    def download_task_from_page(
                self,
                page: LinkResource,
                file_already_downloaded,
                url_already_downloaded
            ):
        resources_renamed = rename_element_if_duplicated(
                self.get_resources_from_page(page.url),
                get_name= lambda x: x.name,
                create_new_element=lambda r, name: r.change_name(name)
            )
        for link_resource in resources_renamed:
            name = build_resource_name(page, link_resource)
            if name in file_already_downloaded or link_resource.url in url_already_downloaded:
                continue
            file_already_downloaded.add(name)
            url_already_downloaded.add(link_resource.url)
            yield from DownloadResourceTask(
                eu_id=self.eu_id, url=link_resource.url, filename=name
            ).to_tasks()


    def to_tasks(self):
        file_already_downloaded = set()
        url_already_downloaded = set()
        for page in self.get_page_with_resource_to_download():
            yield from self.download_task_from_page(page, file_already_downloaded, url_already_downloaded)

class DownloadResourceTask(EuGenericTask):
    """
    Tâche permettant le téléchargement d'une ressource
    """
    url: str
    filename: str

    @property
    def id(self):
        """
        L'id de la tâche en fonction de l'EU, le view_id.
        """
        return f"{self.eu_id.id}_{self.filename.replace('=', '')}"

    @property
    def target_file(self):
        """
        Donne le chemin du fichier cible
        """
        return Path(self.folder_eu,self.filename)

    @property
    def tmp_target_file(self):
        """
        Donne le chemin d'un fichier temporaire
        """
        return Path(self.tmp_folder, self.filename)

    @property
    def url_with_redirect_for_download(self):
        """
        Ajout de '&redirect=1' afin d'aller directement à la ressource. Sans cette ajout, l'url
        pointe vers la page de synthèse de la ressource.
        """
        return self.url + '&redirect=1'
    def to_tasks(self):
        def get(path):
            session = requests_session.get()
            return connect_moodle(session, path, self.eu_id.id)
        target = self.target_file
        yield self.new_sub_task(
            name= f'Download: {self.url} to {target}'.replace('=', '%3D'),
            actions=[
                (create_folder, [self.folder_eu]),
                (download_file, [self.url, get])
            ],
            uptodate=[is_file_exist(target)],
            targets=[target]
        )
