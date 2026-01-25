""" "
Ce fichier contient la tâche principale de création de la vidéo d'une présentation d'une EU.
"""
# pylint: disable=abstract-method
from pathlib import Path
from urllib.parse import urlparse
from itertools import chain

from pydantic import TypeAdapter, BaseModel
from doit.task import Task

from cnam.video_downloader.tasks.presentation.make_video import (
    make_video_task,
    Slide,
    DeskShares,
    DeskShare,
    Metadata,
    Dimension
)
from cnam.video_downloader.model.presentation.shapes_svg import Svg
from cnam.video_downloader.model.presentation.desk_shares_xml import (
    Recording as DesksharesRecording,
)
from cnam.video_downloader.model.presentation.metadata_xml import (
    Recording as MetadataRecording,
)
from cnam.video_downloader.model.presentation.external_videos_json import (
    ExternalVideo as ExternalVideoJson,
)
from cnam.video_downloader.tasks.shared.generic_task import GenericTask
from cnam.video_downloader.session import download_file
from cnam.video_downloader.utils import (
    build_local_file, build_download_video_youtube_task, is_file_exist
)


class PresentationIdMissing(Exception):
    """
    Erreur émise quand l'id de la présentation est manquant
    """
    def __init__(self):
        super().__init__("Presentation id is missing")


def get_base_files_from_presentation(presentation_id):
    """
    Donne tous les fichiers à télécharger et leur emplacement
    """
    return {
        build_local_file(presentation_id, "captions.json"): "captions.json",
        build_local_file(presentation_id, "deskshare.xml"): "deskshare.xml",
        build_local_file(
            presentation_id, "external_videos.json"
        ): "external_videos.json",
        build_local_file(presentation_id, "metadata.xml"): "metadata.xml",
        build_local_file(presentation_id, "panzooms.xml"): "panzooms.xml",
        build_local_file(
            presentation_id, "presentation_text.json"
        ): "presentation_text.json",
        build_local_file(presentation_id, "shapes.svg"): "shapes.svg",
        build_local_file(presentation_id, "cursor.xml"): "cursor.xml",
        build_local_file(presentation_id, "slides_new.xml"): "slides_new.xml",
        build_local_file(presentation_id, "tldraw.json"): "tldraw.json",
        build_local_file(presentation_id, "webcams.mp4"): "video/webcams.mp4",
        build_local_file(presentation_id, "webcams.webm"): "video/webcams.webm",
        build_local_file(presentation_id, "deskshare.mp4"): "deskshare/deskshare.mp4",
        build_local_file(presentation_id, "deskshare.webm"): "deskshare/deskshare.webm",
    }



class PresentationId(BaseModel):
    """
    L'ensemble des informations pour identifier une présentation.
    """
    recording_id: str
    first_url: str
    redirect_url: str

    @property
    def id(self):
        "Récupère l'id depuis l'url"
        return Path(self.redirect_url).name


class BasePresentationTask(GenericTask, BaseModel):
    """
    Element de base pour les tâches liées aus présentations.
    """
    presentation_id: PresentationId

    @property
    def id(self):
        """
        Donne l'id de la présentation
        """
        return self.presentation_id.id

    def save_id(self):
        """
        Sauvegarde l'id pour le debug.
        """
        with open(
            self.build_local_file("presentation_id.json"), "w", encoding="utf-8"
        ) as fd:
            fd.write(self.presentation_id.json())

    def build_local_file(self, filename):
        """
        Construit le chemin global du fichier
        """
        return build_local_file(self.presentation_id.id, filename)

    def build_presentation_dir(self):
        """
        Construit le chemin de dossier pour une présentation.
        """
        return self.build_local_file("")

    def build_url(self, path):
        """
        Construire une url à partir de l'url après redirection.
        """
        url = urlparse(self.presentation_id.redirect_url)
        return url._replace(path=path).geturl()

    def build_presentation_url(self, path):
        """
        Construit une url liée à la présentation.
        """
        return self.build_url(f"presentation/{self.presentation_id.id}/{path}")

    @property
    def video_path(self):
        """
        Donne le chemin de la vidéo finale.
        """
        return self.build_local_file("video.mkv")

    @property
    def metadata(self) -> Metadata:
        """
        Charge les metadata de la présentation.
        """
        try:
            with open(
                self.build_local_file("metadata.xml"), mode="r", encoding="utf-8"
            ) as fd:
                data = fd.read()
                mydoc: MetadataRecording = MetadataRecording.from_xml(data)
                return Metadata(
                    duration_in_ms=mydoc.playback.duration,
                    start_time_in_ms=mydoc.start_time,
                )
        except FileNotFoundError:
            return None

    @property
    def shapes(self) -> Svg:
        """
        Charge le détaille des diapositives de la présentation.
        """
        try:
            with open(
                self.build_local_file("shapes.svg"), mode="r", encoding="utf-8"
            ) as fd:
                return Svg.from_xml(fd.read())
        except FileNotFoundError:
            return None

    @property
    def deskshare(self) -> DesksharesRecording:
        """
        Charge le partage d'écran de la présentation.
        """
        try:
            with open(
                self.build_local_file("deskshare.xml"), mode="r", encoding="utf-8"
            ) as fd:
                return DesksharesRecording.from_xml(fd.read())
        except FileNotFoundError:
            return None


class CreateDirTask(BasePresentationTask):
    """
    Tâche de création de dossier.
    """
    def to_tasks(self):
        folders_to_create = [
            self.build_presentation_dir(),
            self.build_local_file("slides"),
            self.build_local_file("videos"),
        ]

        def is_dir_exist():
            return all(Path(d).is_dir() for d in folders_to_create)

        yield Task(
            name=self.build_presentation_dir(),
            uptodate=[is_dir_exist],
            actions=[f"mkdir -p {' '.join(folders_to_create)}"],
            subtask_of=self.main_task.name,
        )


class DownloadBaseFilesTask(BasePresentationTask):
    """
    Tâche de téléchargement des fichiers de la présentation.
    """
    def to_tasks(self):
        yield self.main_task
        for filename, url in get_base_files_from_presentation(
            self.presentation_id.id
        ).items():
            task = Task(
                name=filename,
                targets=[filename],
                uptodate=[is_file_exist(filename)],
                actions=[(download_file, [self.build_presentation_url(url)])],
                subtask_of=self.main_task.name,
            )
            self.main_task.task_dep.append(task.name)
            yield task


class DownloadSlides(BasePresentationTask):
    """
    Tâche de téléchargement des diapositives définies dans le fichier shapes.svg.
    """
    def to_tasks(self):
        def gen_tasks(fd):
            mydoc: Svg = Svg.from_xml(fd.read())
            for image in mydoc.root:
                if image.is_desk_share_image:
                    continue
                filename = image.a_id
                target_svg = self.build_local_file(f"slides/{filename}{image.suffix}")
                target_png = self.build_local_file(f"slides/{filename}.png")

                url = image.a_href
                task = Task(
                    name=target_svg,
                    actions=[(download_file, [self.build_presentation_url(url)])],
                    uptodate=[is_file_exist(target_svg)],
                    targets=[target_svg],
                    subtask_of=self.main_task.name,
                )
                self.main_task.task_dep.append(task.name)
                yield task
                if image.suffix != ".png":
                    task = Task(
                        name=f"{target_svg} to png",
                        actions=[
                            f"rsvg-convert -w {image.a_width} -h {image.a_height}"
                            f" -o {target_png} {target_svg}"
                        ],
                        file_dep=[target_svg],
                        targets=[target_png],
                        subtask_of=self.main_task.name,
                    )
                    self.main_task.task_dep.append(task.name)
                    yield task

        try:
            with open(
                self.build_local_file("shapes.svg"), mode="r", encoding="utf-8"
            ) as fd:
                yield from gen_tasks(fd)
        except FileNotFoundError:
            pass


class DownloadExternalVideos(BasePresentationTask):
    """
    Tâche de téléchargement des vidéos externes définies dans le fichier external_videos.json.
    """
    def to_tasks(self):
        def gen_tasks(fd):
            external_videos = TypeAdapter(ExternalVideoJson).validate_json(fd.read())
            for index, external_video in enumerate(external_videos.root):
                target = self.build_local_file(f"video/external_video_{index}.mkv")
                if external_video.external_video_url is None:
                    continue
                yield build_download_video_youtube_task(external_video.external_video_url, target)

        try:
            with open(
                self.build_local_file("external_videos.json"),
                mode="r",
                encoding="utf-8",
            ) as fd:
                yield from gen_tasks(fd)
        except FileNotFoundError:
            pass


class MakeVideoTask(BasePresentationTask):
    """
    Tâche de création de la vidéo finale.
    """
    def to_tasks(self):
        slides = []
        desk_shares = None
        mydoc = self.shapes
        if mydoc:
            slides = [
                Slide(
                    path=Path(self.build_local_file(f"slides/{image.a_id}.png")),
                    start=image.a_in,
                    end=image.a_out,
                    x=image.a_x,
                    y=image.a_y,
                    width=image.a_width,
                    height=image.a_height,
                )
                for image in mydoc.root if not image.is_desk_share_image
            ]
        mydoc = self.deskshare
        if mydoc:
            desk_shares = DeskShares(
                path=self.build_local_file("deskshare.webm"),
                desk_shares=[
                    DeskShare(
                        start=event.start_timestamp,
                        end=event.stop_timestamp,
                        width=event.video_width,
                        height=event.video_height,
                    )
                    for event in mydoc.root
                ],
            )
        max_width = max(map(lambda x: x.width, chain(self.shapes.root, self.deskshare.root)))
        max_height = max(map(lambda x: x.height, chain(self.shapes.root, self.deskshare.root)))
        yield from make_video_task(
            output=self.build_local_file("video.mkv"),
            slides=slides,
            metadata=self.metadata,
            dimension=Dimension(width=max_width, height=max_height),
            audio_file=self.build_local_file("webcams.webm"),
            desk_shares=desk_shares,
        )


class Presentation(BasePresentationTask):
    """
    Tâche principal de création de la vidéo liée à la présentation.
    """
    def to_tasks(self):
        yield self.main_task
        create_dir = CreateDirTask(presentation_id=self.presentation_id)
        download_base_file = DownloadBaseFilesTask(presentation_id=self.presentation_id)
        download_slides = DownloadSlides(presentation_id=self.presentation_id)
        download_external_videos = DownloadExternalVideos(
            presentation_id=self.presentation_id
        )
        make_video = MakeVideoTask(presentation_id=self.presentation_id)
        yield from create_dir.to_tasks()
        yield from download_base_file.to_tasks()
        yield from download_slides.to_delayed_tasks(
            executed=download_base_file.main_task.name,
            target_regex=download_slides.build_local_file("slides/*"),
        )
        yield from download_external_videos.to_delayed_tasks(
            executed=download_base_file.main_task.name,
            target_regex=download_base_file.build_local_file("video/*"),
        )
        yield from make_video.to_delayed_tasks(executed=download_slides.main_task.name)
