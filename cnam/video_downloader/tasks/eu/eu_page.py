from pathlib import PurePosixPath

from urllib.parse import unquote, urljoin

from typing import Callable
import requests




from bs4 import BeautifulSoup, Tag

from cnam.video_downloader.session import requests_session
from cnam.video_downloader.utils import (
    save_request as save_request_with_euid
)
from cnam.video_downloader.tasks.eu.eu_generic import EuGenericTask
from cnam.video_downloader.tasks.eu.link_resource import LinkResource
from cnam.video_downloader.tasks.eu.utils import connect_moodle



SaveRequestCallable = Callable[[requests.Response],None]
AttrLinkExtractor = Callable[[BeautifulSoup, Tag], dict]
LinkSelector = str
def save_request_to_null(_: requests.Response) -> None:
    pass

def attr_link_extractor_from_page(attr_with_link) -> AttrLinkExtractor:
    def link_extractor_from_page(_: BeautifulSoup, element: Tag) -> dict:
        return dict(
            url=element.attrs[attr_with_link],
            text=element.text
        )
    return link_extractor_from_page

def is_html_response(response: requests.Response):
    return 'html' in response.headers.get('Content-Type','').lower()

def get_link_from_no_html_response(response: requests.Response):
    filename_with_parameters = PurePosixPath(response.url).name
    filename_without_parameters, *_ =unquote(filename_with_parameters).split('?', maxsplit=1)
    return [LinkResource(
        url=response.url,
        text=filename_without_parameters,
        from_html=False)]

def get_link_from_html_response(response: requests.Response, selector: LinkSelector, extractor: AttrLinkExtractor):
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

def get_links_from_page(get_page, selector, extractor=attr_link_extractor_from_page('href'), save_request:SaveRequestCallable=save_request_to_null) -> list[LinkResource]:
    """
    Trouve les liens d'une page
    """
    response = get_page()
    if not is_html_response(response):
        return get_link_from_no_html_response(response)
    save_request(response)
    return get_link_from_html_response(response, selector, extractor)



class EuPageTask(EuGenericTask):
    """
    Tâche nécessitant de parcourir le site CNAM.
    """
    def connect_moodle(self, session):
        """
        S'occupe de l'authentification au moodle.
        """
        return connect_moodle(session=session, url=self.eu_id.url,eu_id=self.eu_id.id)

    def save_request(self, request: requests.Response) -> None:
        save_request_with_euid(request, self.eu_id.id)

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

    def get_views(self) -> list[LinkResource]:
        """
        Récupère les vues à analyser. Les vues sont sur le bordereau de gauche.
        """
        return get_links_from_page(self.load_home_page, "a[href*='resource/view.php']", save_request=self.save_request) + \
            get_links_from_page(self.load_home_page, "a[href*='course/view.php']", save_request=self.save_request)

    def get_folders(self) -> list[LinkResource]:
        """
        Récupère les dossiers à analyser. Les dossiers sont sur le bordereau de gauche.
        """
        return get_links_from_page(self.load_home_page, "a[href*='folder/view.php']", save_request=self.save_request)

    def get_youtube_view(self) -> list[LinkResource]:
        """
        Récupère les vues référençant les liens externes à analyser. Les liens sont sur le bordereau de gauche.
        """
        return get_links_from_page(self.load_home_page, "a[href*='url/view.php']", save_request=self.save_request)

    def get_course_view(self) -> list[LinkResource]:
        """
        Récupère les vues référençant les liens externes à analyser. Les liens sont sur le bordereau de gauche.
        """
        return get_links_from_page(self.load_home_page, "a[href*='course/view.php']", save_request=self.save_request)

    def get_ubicast_view(self) -> list[LinkResource]:
        """
        Récupère les vues référençant les liens externes à analyser. Les liens sont sur le bordereau de gauche.
        """
        return get_links_from_page(self.load_home_page, "a[href*='ubicast/view.php']", save_request=self.save_request)

    def get_resources_from_page(self, url) -> list[LinkResource]:
        """
        Récupère les liens des ressources à télécharger d'une page.
        """
        return get_links_from_page(self.get_page_loader(url), "a[href*='pluginfile.php/']", save_request=self.save_request)

    def get_youtube_from_page(self, url) -> list[LinkResource]:
        """
        Récupère les liens youtubes à télécharger d'une page.
        """
        return get_links_from_page(self.get_page_loader(url), "a[href*='youtube.com']", save_request=self.save_request)

    def get_ubicast_player_from_page(self, url) -> list[LinkResource]:
        """
        Récupère les liens vidéos ubicast à télécharger d'une page.
        """
        return get_links_from_page(self.get_page_loader(url), "iframe[class='nudgis-iframe']", extractor=attr_link_extractor_from_page('src'), save_request=self.save_request)

    def get_ubicast_player_from_ltiform(self, url) -> list[LinkResource]:
        """
        Récupère les liens vidéos ubicast à télécharger d'une page.
        """
        return get_links_from_page(self.get_page_loader(url), "form[id='ltiLaunchForm']", extractor=attr_link_extractor_from_page('action'), save_request=self.save_request)

    def get_ubicast_video_from_page(self, url) -> list[LinkResource]:
        """
        Récupère les liens vidéos ubicast à télécharger d'une page.
        """
        ltiFormPageResponse = self.get_page_loader(url)()
        save_request_with_euid(ltiFormPageResponse, self.eu_id.id)
        soup = BeautifulSoup(ltiFormPageResponse.text, features="html.parser")
        form = soup.find("form")
        children = form.findChildren()
        data_to_post = {child.attrs['name']:child.attrs['value'] for child in children}
        url_to_post=form.attrs['action']
        session = requests_session.get()

        def extractor(_, element):
            return dict(
                url=urljoin(url_to_post, element.attrs['href']),
                text=element.attrs['download']
            )

        responses = get_links_from_page(
            lambda: session.post(url_to_post, data=data_to_post),
            "a[class*='download-mp4']",
            extractor=extractor, save_request=self.save_request)

        return responses

    def get_sharepoint_video_from_page(self, url):
        """
        Récupère les liens youtubes à télécharger d'une page.
        """
        return get_links_from_page(self.get_page_loader(url), "a[href*='cnam-my.sharepoint.com']")
