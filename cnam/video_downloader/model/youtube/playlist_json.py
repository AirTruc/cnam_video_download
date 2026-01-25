"""
Modèle de donnée du fichier playlist.json généré par yt-dlp.
Voici un exemple de contenu :
"""
from typing import List, Union, Literal, Annotated, Any
from pydantic import BaseModel, Field, AliasChoices, RootModel, model_validator

Id = str
Title = str
VideoUrl = str
Timestamp = int
Filename = str
Type = Literal
class RequestedDownload(BaseModel):
    "Noeud RequestedDownload"
    filename: Filename

class Entry(BaseModel):
    "Noeud Entrie"
    id: Id
    title: Title
    webpage_url: VideoUrl
    original_url: VideoUrl
    requested_downloads: List[RequestedDownload]

class EntryRoot(Entry):
    type: Type["video"]

    @property
    def entries(self):
        return [self]

class Playlist(BaseModel):
    "Noeud Playlist"
    id: Id
    title: Title
    entries: List[Entry]
    type: Type["playlist"]

class PlaylistJsonModel(RootModel):
    root: Union[EntryRoot, Playlist] = Field(discriminator='type')

    @model_validator(mode='before')
    @classmethod
    def set_type(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if '_type' in data:
                data['type'] = data['_type']
        return data
