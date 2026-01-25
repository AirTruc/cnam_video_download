"""
Ce fichier est dédié la création de la vidéo final en fonction des différents éléments téléchargés.
"""
from typing import List, Dict, Callable
from pathlib import Path
from pydantic import BaseModel

from moviepy import VideoFileClip, VideoClip, AudioClip

from cnam.video_downloader.utils import ffmpeg_bin

Time = float
Position = int
Size = int


class Dimension(BaseModel):
    """
    Les dimensions d'une vidéo ou des images
    """
    width: Size
    height: Size


class Slide(BaseModel):
    """
    Les informations d'une diapositive
    """
    path: Path
    start: Time
    end: Time
    x: Position
    y: Position
    width: Size
    height: Size


Slides = List[Slide]


class Video(Slide):
    """
    Les informatins d'une vidéo
    """


class DeskShare(BaseModel):
    """
    Les informations d'un partage d'écran.
    """
    start: Time
    end: Time
    width: Size
    height: Size


class DeskShares(BaseModel):
    """
    Les informations du fichier contenant les descriptifs du partage d'écran.
    """
    path: Path
    desk_shares: List[DeskShare]


GetVideoClip = Callable[[], VideoClip]
GetAudioClip = Callable[[], AudioClip]


class Metadata(BaseModel):
    """
    Données présents dans le fichier matadata.xml
    """
    duration_in_ms: int
    start_time_in_ms: int

    @property
    def start_time_in_sec(self) -> int:
        """
        Calcul le timestamp du démarrage de la vidéo en seconde.
        """
        return self.start_time_in_ms // 1000


class ExternalVideo(BaseModel):
    """
    Informations d'une vidéo externe.
    """
    start: Time
    path: Path


class VideosToCompose(BaseModel):
    """
    Contient les informations utiles pour créer la vidéo finale.
    """
    _videos: Dict[Time, GetVideoClip] = {}
    _audio: GetAudioClip = None

    def add_get_clip(self, start: Time, get_clip: GetVideoClip):
        """
        Ajoute un récupérateur de clip vidéo
        """
        if start is None:
            raise ValueError("Start must be time type")
        self._videos[start] = get_clip

    def add_audio(self, get_clip: GetAudioClip):
        """
        Ajoute un récupérateur d'audio.
        """
        self._audio = get_clip

    @property
    def clips(self) -> List[GetVideoClip]:
        """
        Liste des récupérateur de clip.
        """
        return list(
            map(lambda x: x[1], sorted(self._videos.items(), key=lambda x: x[0]))
        )

    @property
    def videos(self) -> List[VideoClip]:
        """
        Liste des vidéos à assembler.
        """
        return list(clip() for clip in self.clips)

    @property
    def audio(self) -> GetAudioClip:
        """
        L'audio de la vidéo.
        """
        return self._audio


class ConvertElement(BaseModel):
    """
    Informations pour la conversion.
    """
    source: Path
    target: Path
    action: Dict


class ConvertVideo(ConvertElement):
    """
    Information pour la conversion d'une vidéo.
    """
    start: Time


class ConvertAudio(ConvertElement):
    """
    Information utile pour la conversion d'un audio.
    """


class ConvertToCompose(BaseModel):
    """
    Ensemble des éléments à convertir pour la composition de la vidéo.
    """
    _videos: List[ConvertVideo] = []
    _audio: ConvertAudio = None

    @property
    def videos(self) -> List[ConvertVideo]:
        """
        Les vidéos à convertir ordonnées par rapport à la horaire de démarrage.
        """
        return sorted(self._videos, key=lambda x: x.start)

    @property
    def audio(self) -> ConvertAudio:
        """
        L'audio de la vidéo.
        """
        return self._audio

    def add_video(self, video: ConvertVideo):
        """
        Ajoute des vidéos à convertir pour la vidéo.
        """
        if video.start is None:
            raise ValueError("Start must be time type")
        self._videos.append(video)

    def add_audio(self, audio: ConvertAudio):
        """
        Ajoute un audio pour la vidéo.
        """
        self._audio = audio


FPS = 1
def get_path_of_videos(videos_convert: ConvertToCompose):
    """
    Donne tous les chemins des vidéos converties.
    """
    print(videos_convert)
    return [video.target for video in videos_convert.videos]


def ffmpeg_to_composite(videos_convert: ConvertToCompose, duration_in_ms, targets):
    """
    Composition de la vidéo par ffmpeg.
    """
    def build_list_concat_file(targets):
        with open(targets[0], "w", encoding="utf-8") as fd:
            count_parent = len(Path(targets[0]).parents)
            remove_parent = Path(*[".."] * (count_parent - 1))
            for path in get_path_of_videos(videos_convert):
                print(f"file '{Path(remove_parent, path)}'", file=fd)

    file_concat = Path(targets[0] + "_concat.txt")
    video_without_audio = Path(targets[0] + "_video_without_audio.mp4")
    video = targets[0]
    video_to_concat = get_path_of_videos(videos_convert)
    yield {
        "name": file_concat,
        "actions": [(build_list_concat_file, [])],
        "file_dep": video_to_concat,
        "targets": [file_concat],
    }
    yield {
        "name": video_without_audio,
        "actions": [
            f"{ffmpeg_bin.get()} -y -f concat -safe 0 -i {file_concat} -c copy"
            #f" -video_track_timescale 600 "
            f" -t '{duration_in_ms}ms' {video_without_audio}"
        ],
        "file_dep": [file_concat] + video_to_concat,
        "targets": [video_without_audio],
    }
    yield {
        "name": video,
        "actions": [
            f"{ffmpeg_bin.get()} -y -i {video_without_audio} -i {videos_convert.audio.target} -c copy  {video}"
        ],
        "file_dep": [video_without_audio, videos_convert.audio.target],
        "targets": [video],
    }


def to_image_clip(source: Slide, width, height):
    """
    Transforme une image en vidéo.
    """
    target = str(source.path.with_suffix(".mp4"))
    return ConvertVideo(
        source=source.path,
        target=target,
        action={
            "name": target,
            "actions": [
                f"{ffmpeg_bin.get()} -y -loop 1 -i '{source.path}' -c:v libx264"
                f" -t '{source.end - source.start}s'"
                f" -pix_fmt yuv420p -vf 'scale=ceil({width}/2)*2:ceil({height}/2)*2' -r 5 '{target}'"
            ],
            "file_dep": [source.path],
            "targets": [target],
        },
        start=source.start,
    )


def write_video(video: VideoClip, targets):
    """
    Sauvegarde la vidéo dans un fichier.
    """
    video.write_videofile(targets[0], fps=FPS)


def convert_video(source: Slide, width, height):
    """
    Converti une diapositive en vidéo.
    """
    convert = to_image_clip(source=source, width=width, height=height)
    return convert
    # print(convert)
    # return ConvertVideo(
    #    source=convert.source,
    #    target=convert.target,
    #    get_clip=lambda: VideoFileClip(convert.target),
    #    action={
    #        'name': convert.target,
    #        'actions': [(write_video,[convert.get_clip()])],
    #        'file_dep': [convert.source],
    #        'targets': [convert.target],
    #    },
    #    start= convert.start
    # )


def convert_audio(audio_file) -> ConvertVideo:
    """
    Converti l'audio.
    """
    audio_file = Path(audio_file)
    target = audio_file.with_suffix(".convert.opus")
    return ConvertAudio(
        source=audio_file,
        target=target,
        action={
            "name": target,
            "actions": [
                f'{ffmpeg_bin.get()} -y -i "{audio_file}" -ac 2 -c:a libopus -b:a 96K {target}'
            ],
            "file_dep": [audio_file],
            "targets": [target],
        },
    )


def desk_shares_to_video(
    path: Path, desk_share: DeskShare, dimension: Dimension, targets
):
    """
    Converti le partage d'écran en vidéo.
    """
    video = VideoFileClip(path).subclipped(desk_share.start, desk_share.end)
    video.resized(width=dimension.width, height=dimension.height)
    write_video(video, targets)


def convert_desk_shares(
    desk_shares: DeskShares, dimension: Dimension
) -> List[ConvertVideo]:
    """
    Converti le partage d'écran en vidéo.
    """
    def build_convert(index: int, path: Path, desk_share: DeskShare):
        target = Path(path.parent, f"{path.stem}_{index}.mp4")
        target_tmp = target.with_suffix('.tmp.mp4')
        return ConvertVideo(
            source=path,
            target=target,
            action={
                "name": target,
                "actions": [
                    f"{ffmpeg_bin.get()} -y -ss '{desk_share.start}s' -t '{desk_share.end-desk_share.start}s'"
                    f" -i '{path}' -acodec copy -vcodec copy '{target_tmp}'",
                    f"{ffmpeg_bin.get()} -y -i '{target_tmp}' -filter:v fps=25 "
                    f"-vf 'scale=ceil({dimension.width}/2)*2:ceil({dimension.height}/2)*2' '{target}'"
                ],
                "file_dep": [path],
                "targets": [target],
            },
            verbosity=2,
            start=desk_share.start,
        )

    return [
        build_convert(index, desk_shares.path, desk_share)
        for index, desk_share in enumerate(desk_shares.desk_shares)
    ]


def convert_external_videos(external_videos: List[ExternalVideo]) -> List[ConvertVideo]:
    """
    Converti les vidéos externes en vidéo.
    """
    def build_convert(_: int, external_video: ExternalVideo):
        return ConvertVideo(
            source=external_video.path,
            target=external_video.path,
            action={},
            start=external_video.start,
        )

    return [
        build_convert(index, external_video)
        for index, external_video in enumerate(external_videos)
    ]


def get_size(slide: Slide) -> Dimension:
    """
    Donne les dimension d'une diapositive
    """
    return Dimension(width=slide.width, height=slide.height)

# pylint: disable=too-many-arguments,too-many-positional-arguments
def make_video_task(
    output: Path,
    slides: Slides,
    metadata: Metadata,
    dimension: Dimension,
    audio_file: Path = None,
    desk_shares: DeskShares = None,
    external_videos: List[ExternalVideo] = None,
):
    """
    Créer les tâches de création de vidéo.
    Pour que la vidéo finale n'est pas de soucis, il faut que les vidéos aient les mêmes tailles et
    le même FPS.

    """
    max_width = dimension.width
    max_height = dimension.height

    converts = []
    videos_to_compose = ConvertToCompose()
    if audio_file:
        convert = convert_audio(audio_file)
        videos_to_compose.add_audio(convert)
        converts.append(convert)
    for slide in slides:
        # converts.append(to_image_clip(slide))
        converts.append(convert_video(slide, width=max_width, height=max_height))
    file_dep = []
    if desk_shares:
        converts.extend(
            convert_desk_shares(desk_shares, Dimension(width=max_width, height=max_height))
        )
    if external_videos:
        converts.extend(convert_external_videos(external_videos=external_videos))
    for convert in converts:
        if hasattr(convert, "start"):
            videos_to_compose.add_video(convert)
        file_dep.append(convert.target)
        if convert.action:
            print(convert.action)
            yield convert.action
    # yield {
    #    'name': output,
    #    'actions': [(ffmpeg_to_composite,[videos_to_compose])],
    #    'file_dep': file_dep,
    #    'targets': [output],
    # }
    yield from ffmpeg_to_composite(videos_to_compose, metadata.duration_in_ms, [output])
