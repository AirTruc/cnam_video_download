import re
from urllib.parse import urlparse




from pydantic import BaseModel






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
