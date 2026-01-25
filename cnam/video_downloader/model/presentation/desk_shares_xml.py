"""
Modèle de donnée du fichier deskshares.xml.
Voici un exemple de contenu :
<?xml version="1.0" encoding="UTF-8"?>
<recording id="deskshare_events">
  <event start_timestamp="2877.4" stop_timestamp="2971.2" video_width="720" video_height="362"/>
  <event start_timestamp="3023.8" stop_timestamp="3062.5" video_width="720" video_height="405"/>
  <event start_timestamp="3107.0" stop_timestamp="3131.0" video_width="720" video_height="405"/>
</recording>
"""
from typing import List
from pydantic import computed_field
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element


NSMAP = {'':"http://www.w3.org/2000/svg",'xlink':"http://www.w3.org/1999/xlink"}

class Event(BaseXmlModel, tag='event'):
    """
    Noeud Event
    """
    start_timestamp: float = attr()
    stop_timestamp: float = attr()
    video_width: int = attr()
    video_height: int = attr()

    @computed_field
    @property
    def width(self) -> int:
        """
        La largeur
        """
        return self.video_width

    @computed_field
    @property
    def height(self) -> int:
        """
        La hauteur
        """
        return self.video_height

class Recording(RootXmlModel, tag='recording'):
    """
    Noeud Recording
    """
    #a_id: str = attr(name='id')
    #a_style: str = attr(name='style')
    #a_version: str = attr(name='version')
    #a_viewBox: str = attr(name='viewBox')
    root: List[Event] = element(tag='event', default_factory=list)
