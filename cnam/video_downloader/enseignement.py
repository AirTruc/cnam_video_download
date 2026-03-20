"""
Ce fichier traite de l'enseignement d'un étudiant du CNAM.
"""
import re

from bs4 import BeautifulSoup

from cnam.video_downloader.session import requests_session
from cnam.video_downloader.tasks.eu.eu_id import EuId

class EuNameError(Exception):
    """
    La récupération du nom d'une EU échoue.
    """
# pylint: disable=too-few-public-methods
class Enseignement:
    """
    Représente l'ensemble de l'enseignement d'un étudiant du CNAM.
    """

    def get_eu(self):
        """
        Donne l'ensemble des EUs disponible dans l'enseignement d'un étudiant du CNAM.
        """
        session = requests_session.get()
        response = session.get('https://lecnam.net/enseignements')
        soup = BeautifulSoup(response.text, features='html.parser')
        cards = soup.select('a.card.description-card.one-card')

        ret= []
        for card in cards:
            href = card['href']
            p_title = card.select_one('div.card-block p.text:nth-child(1) p.text')
            match = re.match(r'^(\w+)', p_title.text)
            eu_name = match.group(1)
            if not eu_name:
                raise EuNameError()
            ret.append(EuId(url=href, name=eu_name))
        return ret
