"""
Contient les fonctions liées à l'authentification sur le site du CNAM.
"""
from contextvars import ContextVar
from typing import Callable

from bs4 import BeautifulSoup
import requests
requests_session: ContextVar[requests.Session] = ContextVar("requests_session")

TIMEOUT=30

def authentification(username:str, password:str):
    """
    Authentifie un utilisateur au site du CNAM. La session ainsi créée est sauvegardée dans la 
    variable de contexte global **requests_session**.
    """
    session = requests.Session()
    session.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            }
    session.timeout = TIMEOUT
    base_url = 'https://idp.lecnam.net'
    response = session.get(base_url)

    soup = BeautifulSoup(response.text, features='html.parser')
    form = soup.select_one('form')
    url = form.attrs['action']
    response = session.post(
        url=f'{base_url}{url}',
        data={'j_username':username, 'j_password':password, '_eventId_proceed':''},
        headers={'content-type': 'application/x-www-form-urlencoded'}
    )

    soup = BeautifulSoup(response.text, features='html.parser')
    form = soup.select_one('form')
    url = form.attrs['action']
    relay_state = soup.select_one('input[name=RelayState]').attrs['value']
    saml_response = soup.select_one('input[name=SAMLResponse]').attrs['value']
    data = {
        'RelayState':relay_state,
        'SAMLResponse':saml_response,
    }

    response = session.post(
        url=url,
        data=data
        )

    requests_session.set(session)

def default_get(url):
    """
    Session par defaut
    """
    session = requests_session.get()
    return session.get(url)

def download_file(path, get:Callable[[str], requests.Response]=default_get,*, targets):
    """
    Télécharge un fichier depuis le site du CNAM
    """
    req = get(path)
    if req.status_code == 200:
        with open(targets[0], mode="wb") as fd:
            fd.write(req.content)
