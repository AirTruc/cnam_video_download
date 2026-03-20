"""
Ensemble des classes et fonctions servant à la création des vidéos de toutes les présentations
de l'EU.
"""
# pylint: disable=abstract-method
from bs4 import BeautifulSoup
from cnam.video_downloader.utils import (
    save_request as save_request_with_euid
)



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
    save_request_with_euid(response, eu_id)
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
    save_request_with_euid(response, eu_id)
    return response
