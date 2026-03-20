#"""
#Ensemble des classes et fonctions servant à la création des vidéos de toutes les présentations
#de l'EU.
#"""
# pylint: disable=abstract-method
from datetime import datetime
from pathlib import Path
import json
import re

from requests.cookies import RequestsCookieJar

from doit.tools import create_folder

from bs4 import BeautifulSoup
import click

from cnam.video_downloader.tasks.presentation.presentation import (
    Presentation,
    PresentationId,
)
from cnam.video_downloader.session import requests_session
from cnam.video_downloader.utils import (
    save_request as save_request_with_euid, youtube_dl_bin, is_file_exist
)

from cnam.video_downloader.tasks.eu.eu_page import EuPageTask
from cnam.video_downloader.tasks.eu.eu_generic import EuGenericTask
from cnam.video_downloader.tasks.eu.download_resource import DownloadAllResourcesTask, DownloadResourceTask
from cnam.video_downloader.tasks.eu.download_youtube import DownloadYoutubePlaylistInformation, DownloadYoutubeResourceTask
from cnam.video_downloader.tasks.eu.utils import connect_moodle







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
        save_request_with_euid(response, self.eu_id.id)
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

        save_request_with_euid(response, self.eu_id.id)
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

        save_request_with_euid(response, self.eu_id.id)

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