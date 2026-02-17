"""
Ensemble des classes et fonctions servant à la création des vidéos de toutes les présentations
de l'EU.
"""
# pylint: disable=abstract-method
from datetime import datetime
from pathlib import Path, PurePosixPath
import json
import re
from urllib.parse import urlparse, unquote, urljoin
import glob
import unicodedata

import contextvars

from requests.cookies import RequestsCookieJar

from doit.tools import create_folder
from pydantic import BaseModel, TypeAdapter

from bs4 import BeautifulSoup
import click

from cnam.video_downloader.tasks.shared.generic_task import GenericTask
from cnam.video_downloader.tasks.presentation.presentation import (
    Presentation,
    PresentationId,
)
from cnam.video_downloader.session import requests_session, download_file
from cnam.video_downloader.utils import (
    save_request, build_download_video_youtube_task, youtube_dl_bin, is_file_exist
)
from cnam.video_downloader.model.youtube.playlist_json import PlaylistJsonModel

base_dir = contextvars.ContextVar("base_dir")

class FolderMissing(Exception):
    """
    Exception levée quand le dossier est manquant
    """

class LinkResource(BaseModel):
    url: str
    text: str
    from_html: bool

def connect_moodle(session, url, eu_id):
    """
    S'occupe de l'authentification au moodle.
    """
    response = session.get(url)
    if 'html' not in response.headers['Content-Type'].lower():
        return response
    soup = BeautifulSoup(response.text, features="html.parser")
    form = soup.select_one("form")
    if form is None:
        return response
    save_request(response, eu_id)
    url = form.attrs["action"]
    relay_state = soup.select_one("input[name=RelayState]")
    saml_response = soup.select_one("input[name=SAMLResponse]")
    if relay_state is None or saml_response is None:
        return response

    data = {
        "RelayState": relay_state.attrs["value"],
        "SAMLResponse": saml_response.attrs["value"],
    }
    response = session.post(url=url, data=data)
    save_request(response, eu_id)
    return response


class EuId(BaseModel):
    """
    Identification de l'EU
    """
    url: str
    name: str

    @property
    def id(self):
        """
        Donne l'id de l'EU. Se calcule à partir de l'url.
        """
        query = urlparse(self.url).query
        m = re.search(r"id=(\d+)", query)
        return m.group(1)

    @property
    def netloc(self):
        """
        Donne la location réseau de l'EU.
        Chaque CNAM à des urls différentes.
        """
        return urlparse(self.url).netloc



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
class CreateDirTask(EuGenericTask):
    """
    Tâche de création des dossiers de l'EU.
    """
    def to_tasks(self):
        folder_to_create = self.folder_eu
        yield self.new_sub_task(
            name=f"{folder_to_create}", actions=[(create_folder, [folder_to_create])]
        )


class CopyPresentationVideoTask(EuGenericTask):
    """
    Tâche de copie de la vidéo d'une présentation dans le dossier final.
    """
    presentation: Presentation

    @property
    def id(self):
        """
        L'id de la tâche en fonction de l'EU et de la présentation.
        """
        return f"{self.eu_id.id}_{self.presentation.id}"

    @property
    def target_video_path(self) -> Path:
        """
        Le chemin de la vidéo finale.
        """
        date_presentation = datetime.fromtimestamp(
            self.presentation.metadata.start_time_in_sec
        )
        return Path(
            self.folder_eu,
            f"presentation_{date_presentation.strftime('%Y%m%d__%H_%M_%S')}.mkv",
        )

    def to_tasks(self):
        target = self.target_video_path
        source = self.presentation.video_path
        yield self.new_sub_task(
            name=str(target),
            actions=[(create_folder, [self.folder_eu]), f"cp {source} {target}"],
            file_dep=[str(source)],
            targets=[str(target)],
        )

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


def attr_link_extractor_from_page(attr_with_link):
    def link_extractor_from_page(soup, element) -> dict:
        return dict(
            url=element.attrs[attr_with_link],
            text=element.text
        )
    return link_extractor_from_page

class EuPageTask(EuGenericTask):
    """
    Tâche nécessitant de parcourir le site CNAM.
    """
    def connect_moodle(self, session):
        """
        S'occupe de l'authentification au moodle.
        """
        return connect_moodle(session=session, url=self.eu_id.url,eu_id=self.eu_id.id)

    def _get_links_from_page(self, get_page, selector, extractor=attr_link_extractor_from_page('href')) -> list[LinkResource]:
        """
        Trouve les liens d'une page
        """
        response = get_page()
        if 'html' not in response.headers['Content-Type'].lower():
            filename, *_ =unquote(PurePosixPath(response.url).name).split('?', maxsplit=1)
            return [LinkResource(
                url=response.url,
                text=filename,
                from_html=False)]
        save_request(response, self.eu_id.id)
        try:
            soup = BeautifulSoup(response.text, features="html.parser")
        except Exception as e:
            print(response.text)
            print(response.url)
            print(response.headers)
            raise e
        links = soup.select(selector)
        return [
            LinkResource(
                **extractor(soup, link),
                from_html=True)
            for link in links
        ]

    def load_home_page(self):
        """
        Charge la page d'accueil
        """
        session = requests_session.get()
        return self.connect_moodle(session)

    def get_page_loader(self, url):
        """
        Génère un chargeur de page
        """
        def load_page():
            session = requests_session.get()
            return session.get(url)
        return load_page

    def get_views(self):
        """
        Récupère les vues à analyser. Les vues sont sur le bordereau de gauche.
        """
        return self._get_links_from_page(self.load_home_page, "a[href*='resource/view.php']") + \
            self._get_links_from_page(self.load_home_page, "a[href*='course/view.php']")

    def get_folders(self):
        """
        Récupère les dossiers à analyser. Les dossiers sont sur le bordereau de gauche.
        """
        return self._get_links_from_page(self.load_home_page, "a[href*='folder/view.php']")

    def get_youtube_view(self):
        """
        Récupère les vues référençant les liens externes à analyser. Les liens sont sur le bordereau de gauche.
        """
        return self._get_links_from_page(self.load_home_page, "a[href*='url/view.php']")

    def get_course_view(self):
        """
        Récupère les vues référençant les liens externes à analyser. Les liens sont sur le bordereau de gauche.
        """
        return self._get_links_from_page(self.load_home_page, "a[href*='course/view.php']")

    def get_ubicast_view(self):
        """
        Récupère les vues référençant les liens externes à analyser. Les liens sont sur le bordereau de gauche.
        """
        return self._get_links_from_page(self.load_home_page, "a[href*='ubicast/view.php']")

    def get_resources_from_page(self, url):
        """
        Récupère les liens des ressources à télécharger d'une page.
        """
        return self._get_links_from_page(self.get_page_loader(url), "a[href*='pluginfile.php/']")

    def get_youtube_from_page(self, url):
        """
        Récupère les liens youtubes à télécharger d'une page.
        """
        return self._get_links_from_page(self.get_page_loader(url), "a[href*='youtube.com']")

    def get_ubicast_player_from_page(self, url):
        """
        Récupère les liens vidéos ubicast à télécharger d'une page.
        """
        return self._get_links_from_page(self.get_page_loader(url), "iframe[class='nudgis-iframe']", extractor=attr_link_extractor_from_page('src'))

    def get_ubicast_player_from_ltiform(self, url):
        """
        Récupère les liens vidéos ubicast à télécharger d'une page.
        """
        return self._get_links_from_page(self.get_page_loader(url), "form[id='ltiLaunchForm']", extractor=attr_link_extractor_from_page('action'))

    def get_ubicast_video_from_page(self, url):
        """
        Récupère les liens vidéos ubicast à télécharger d'une page.
        """
        ltiFormPageResponse = self.get_page_loader(url)()
        save_request(ltiFormPageResponse, self.eu_id.id)
        soup = BeautifulSoup(ltiFormPageResponse.text, features="html.parser")
        form = soup.find("form")
        children = form.findChildren()
        data_to_post = {child.attrs['name']:child.attrs['value'] for child in children}
        url_to_post=form.attrs['action']
        session = requests_session.get()
        
        def extractor(soup, element):
            return dict(
                url=urljoin(url_to_post, element.attrs['href']),
                text=element.attrs['download']
            )
        
        responses = self._get_links_from_page(
            lambda: session.post(url_to_post, data=data_to_post),
            "a[class*='download-mp4']",
            extractor=extractor)

        return responses

    def get_sharepoint_video_from_page(self, url):
        """
        Récupère les liens youtubes à télécharger d'une page.
        """
        return self._get_links_from_page(self.get_page_loader(url), "a[href*='cnam-my.sharepoint.com']")



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


class DownloadAllResourcesTask(EuPageTask):
    """
    Tâche téléchargeant des ressources disponible pour une EU.
    """

    def to_tasks(self):
        url_with_resources = []
        for link_resource in self.get_views():
            url_with_resources.append(link_resource.url)
        for link_resource in self.get_folders():
            url_with_resources.append(link_resource.url)

        file_already_downloaded = set()
        for url in url_with_resources:
            for link_resource in self.get_resources_from_page(url):
                name = DownloadResourceTask.normalize_name(link_resource.text)
                if name in file_already_downloaded:
                    continue
                file_already_downloaded.add(name)
                yield from DownloadResourceTask(
                    eu_id=self.eu_id, url=link_resource.url, filename=name
                ).to_tasks()

class DownloadUbicastResourcesTask(EuPageTask):
    """
    Tâche téléchargeant des ressources disponible pour une EU.
    """

    def to_tasks(self):
        url_with_resources = []
        for link_player in self.get_ubicast_view():
            for link_ltiform in self.get_ubicast_player_from_page(link_player.url):
                url_with_resources.append(link_ltiform.url)

        file_already_downloaded = set()
        for url in url_with_resources:
            for link_resource in self.get_ubicast_video_from_page(url):
                name = DownloadResourceTask.normalize_name(link_resource.text)
                if name in file_already_downloaded:
                    continue
                file_already_downloaded.add(name)
                yield from DownloadResourceTask(
                    eu_id=self.eu_id, url=link_resource.url, filename=name
                ).to_tasks()


def to_netscape_string(cookie_data: RequestsCookieJar) -> str:
    """
    Convert cookies to Netscape cookie format.

    This function takes a list of cookie dictionaries and transforms them into
    a single string in Netscape cookie file format, which is commonly used by
    web browsers and other HTTP clients for cookie storage. The Netscape string
    can be used to programmatically interact with websites by simulating the
    presence of cookies that might be set during normal web browsing.

    Args:
        cookie_data (list of dict): A list of dictionaries where each dictionary
            represents a cookie. Each dictionary should have the following keys:
            - 'domain': The domain of the cookie.
            - 'expires': The expiration date of the cookie as a timestamp.
            - 'path': The path for which the cookie is valid.
            - 'secure': A boolean indicating if the cookie is secure.
            - 'name': The name of the cookie.
            - 'value': The value of the cookie.

    Returns:
        str: A string representing the cookie data in Netscape cookie file format.

    Example of Netscape cookie file format:
        .example.com	TRUE	/	TRUE	0	CloudFront-Key-Pair-Id	APKAIAHLS7PK3GAUR2RQ
    """
    result = []
    for cookie in cookie_data:
        domain = cookie.domain or ""
        expiration_date = cookie.expires or 0
        path = cookie.path or ""
        secure = cookie.secure or False
        name = cookie.name or ""
        value = cookie.value or ""

        include_sub_domain = domain.startswith(".") if domain else False
        expiry = str(int(expiration_date)) if expiration_date > 0 else "0"
        result.append(
            [
                domain,
                str(include_sub_domain).upper(),
                path,
                str(secure).upper(),
                expiry,
                name,
                value,
            ]
        )
    return "\n".join("\t".join(cookie_parts) for cookie_parts in result)


def save_cookies_to_file(
    cookie_data: RequestsCookieJar, file_path='cookies.txt'
) -> None:
    """
    Save cookies to txt file
    """
    netscape_string = to_netscape_string(cookie_data)
    with open(file_path, "w", encoding="utf-8") as file:

        header = """\
# Netscape HTTP Cookie File
# http://www.netscape.com/newsref/std/cookie_spec.html
# This is a generated file!  Do not edit.\n
"""
        file.write(header)
        file.write(netscape_string)
     



class DownloadSharePointVideoPlaylistInformation(EuPageTask):
    """
    Tâche récupérant les informations des playlists youtube disponible pour une EU.
    """

    def to_tasks(self):
        yield self.main_task
        youtube_dl = youtube_dl_bin.get()
        file_already_downloaded = set()
        for view_link_resource in self.get_course_view():
            for link_resource in self.get_sharepoint_video_from_page(view_link_resource.url):
                name = self.normalize_name(link_resource.text)
                if name in file_already_downloaded:
                    continue
                file_already_downloaded.add(name)
                #yield from DownloadYoutubeResourceTask(
                #    eu_id=self.eu_id, url=url_resource, filename=name
                #).to_tasks()
                target=str(Path(self.folder_video_information, f'{name}.sharepoint.json'))
                cookie_target = str(Path(self.folder_video_information, f'{name}.cookie.txt'))
                print(requests_session.get().cookies)
                connect_moodle(requests_session.get(), link_resource, self.eu_id.id)
                yield self.new_sub_task(
                    name=target,
                    actions=[
                        (create_folder, [self.folder_video_information]),
                        (save_cookies_to_file, [requests_session.get().cookies, cookie_target]),
                        f"'{youtube_dl}' --no-warnings --dump-single-json"
                        f" --simulate '{link_resource.url}' --cookies '{cookie_target}' > '{target}'"
                    ],
                    uptodate=[is_file_exist(target)],
                    verbosity=2,
                    targets=[target, cookie_target]
                )


class EuTask(EuPageTask):
    """
    Tâche principal de l'EU.
    """



    def get_presentations_from_group(self, session, url, sesskey):
        """
        Donne les présentations d'un groupe de webconférence de l'EU.
        """
        response = session.get(url)
        save_request(response, self.eu_id.id)
        soup = BeautifulSoup(response.text, features="html.parser")
        room = soup.select_one("div[id^=bigbluebuttonbn-recording-table]")
        data = [
            {
                "index": 0,
                "methodname": "mod_bigbluebuttonbn_get_recordings",
                "args": {
                    "bigbluebuttonbnid": room.attrs["data-bbbid"],
                    "tools":  room.attrs["data-tools"],
                    "groupid": room.attrs["data-group-id"],
                },
            }
        ]
        response = session.post(
            f"https://{self.eu_id.netloc}/lib/ajax/service.php"
            f"?sesskey={sesskey}&info=mod_bigbluebuttonbn_get_recordings",
            data=json.dumps(data),
            headers={
                "content-type": "application/json",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )

        save_request(response, self.eu_id.id)
        data = json.loads(response.json()[0]["data"]["tabledata"]["data"])
        pres = []
        for play in data:
            soup = BeautifulSoup(play["playback"], features="html.parser")
            recording_id = soup.div.attrs["data-recordingid"]
            url = soup.a.attrs["href"]
            r = session.get(url, allow_redirects=False)
            redirect_url = r.headers["Location"]
            pres.append(
                PresentationId(
                    recording_id=recording_id, first_url=url, redirect_url=redirect_url
                )
            )
        return pres

    def get_presentations(self):
        """
        Donne les présentations pour l'EU.
        """
        response = self.load_home_page()
        #print(response.request.url)
        #print(response.request.body)
        #print(response.text)
        m = re.search(r'sesskey=([^"]+)', response.text)
        sesskey = m.group(1)

        save_request(response, self.eu_id.id)

        soup = BeautifulSoup(response.text, features="html.parser")
        links = soup.select("li.modtype_bigbluebuttonbn a.aalink")
        pres = []
        session = requests_session.get()
        for link in links:
            pres.extend(
                self.get_presentations_from_group(
                    session, link.attrs["href"], sesskey=sesskey
                )
            )

        return pres


    def to_tasks(self):
        click.echo(f"Analyse de l'UE {self.eu_id.name}")
        pres_ids = self.get_presentations()
        for pres_id in pres_ids:
            pres = Presentation(presentation_id=pres_id)
            yield from pres.to_tasks()
            yield from CopyPresentationVideoTask(
                eu_id=self.eu_id, presentation=pres
            ).to_delayed_tasks(executed=pres.main_task_name)

        yield from DownloadAllResourcesTask(eu_id=self.eu_id).to_tasks()
        yield from DownloadUbicastResourcesTask(eu_id=self.eu_id).to_tasks()

        playlist_information = DownloadYoutubePlaylistInformation(eu_id=self.eu_id)
        yield from playlist_information.to_tasks()
        yield from DownloadYoutubeResourceTask(eu_id=self.eu_id).to_delayed_tasks(
            executed=playlist_information.main_task_name,
            target_regex=f'{self.folder_video}/*'
        )
        #playlist_information = DownloadSharePointVideoPlaylistInformation(eu_id=self.eu_id)
        #yield from playlist_information.to_tasks()
        #yield from DownloadYoutubeResourceTask(eu_id=self.eu_id).to_delayed_tasks(
        #    executed=playlist_information.main_task_name,
        #    target_regex=f'{self.folder_video}/*'
        #)