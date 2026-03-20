from typing import  Self





from pydantic import BaseModel



class LinkResource(BaseModel):
    url: str
    text: str
    from_html: bool

    @property
    def name(self):
        return self.text

    def change_name(self, name: str) -> Self:
        return LinkResource(
            url=self.url,
            text=name,
            from_html=self.from_html
        )