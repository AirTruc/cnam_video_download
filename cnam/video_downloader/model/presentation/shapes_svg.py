"""
Modèle de donnée du fichier shapes.svg.xml.
Voici un exemple de contenu :
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     id="svgfile" style="position:absolute;height:600px;width:800px"
     version="1.1"
     viewBox="0 0 800 600">
  <image 
    id="image1"
    class="slide"
    in="0.0"
    out="86.9"
    xlink:href="presentation/ff5dfdf460cebcba1f22fa139845ef28e0e7a024-1741370292233/svgs/slide2.svg"
    width="960" height="540" x="0" y="0" style="visibility:hidden"
    text="presentation/ff5dfdf460cebcba1f22fa139845ef28e0e7a024-1741370292233/textfiles/slide-2.txt"
    />
  <image
    id="image2"
    class="slide"
    in="86.9" out="261.5"
    xlink:href="presentation/ff5dfdf460cebcba1f22fa139845ef28e0e7a024-1741370292233/svgs/slide3.svg"
    width="960" height="540" x="0" y="0" style="visibility:hidden"
    text="presentation/ff5dfdf460cebcba1f22fa139845ef28e0e7a024-1741370292233/textfiles/slide-3.txt"
    />
  <image
    id="image3"
    class="slide" in="261.5" out="325.5"
    xlink:href="presentation/ff5dfdf460cebcba1f22fa139845ef28e0e7a024-1741370292233/svgs/slide4.svg"
    width="960" height="540" x="0" y="0" style="visibility:hidden"
    text="presentation/ff5dfdf460cebcba1f22fa139845ef28e0e7a024-1741370292233/textfiles/slide-4.txt"
    />
</svg>
"""
from typing import List, Optional
from pathlib import Path

from pydantic import computed_field
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element



NSMAP = {'':"http://www.w3.org/2000/svg",'xlink':"http://www.w3.org/1999/xlink"}

class Image(BaseXmlModel, tag='image', nsmap=NSMAP):
    """
    Noeud image
    """
    a_id: str = attr(name='id')
    a_class: str = attr(name='class')
    a_in: float = attr(name='in')
    a_out: float = attr(name='out')
    a_href: str = attr(name='href', ns='xlink')
    a_width: int = attr(name='width')
    a_height: int = attr(name='height')
    a_x: int = attr(name='x')
    a_y: int = attr(name='y')
    a_style: str = attr(name='style')
    a_text: Optional[str] = attr(name='text', default=None)

    @computed_field
    @property
    def suffix(self) -> str:
        """
        Donne le suffix de l'image
        """
        return Path(self.a_href).suffix

    @computed_field
    @property
    def is_desk_share_image(self) -> bool:
        """
        Test si l'image est un partage d'écran
        """
        return not self.a_text

    @computed_field
    @property
    def width(self) -> int:
        """
        Donne la largeur
        """
        return self.a_width

    @computed_field
    @property
    def height(self) -> int:
        """
        Donne la taille
        """
        return self.a_height
class Svg(RootXmlModel, tag='svg', nsmap=NSMAP):
    """
    Noeud svg
    """
    root: List[Image] = element(tag='image')
