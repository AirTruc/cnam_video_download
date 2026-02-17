"""
Fichier principal du programme. Initialise le chargeur des tâches DoIt.
Gère les options du programme.
"""
import sys

from itertools import chain
import click

from doit.doit_cmd import DoitMain
from doit.cmd_base import TaskLoader2
from pydantic import  BaseModel


from cnam.video_downloader.tasks.presentation.presentation import Presentation, PresentationId
from cnam.video_downloader.tasks.eu.eu import EuTask, base_dir, EuId
from cnam.video_downloader.enseignement import Enseignement
from cnam.video_downloader.session import authentification
from cnam.video_downloader.utils import youtube_dl_bin, ffmpeg_bin


class Credential(BaseModel):
    """
    Les identifiants de l'étudiant
    """
    username: str
    password: str

class MyLoader(TaskLoader2):
    """
    Charge les tâches
    """
    # pylint: disable=too-many-arguments
    def __init__(self,
                 output_dir,
                 eu_id_items: list[tuple[int, str]],
                 presentation_urls,
                 *,
                 credential:Credential,
                 verbosity,
                 yt_dl_path,
                 ffmpeg_path
    ):
        super().__init__()
        self.eu_id_items = eu_id_items
        self.presentation_urls = presentation_urls
        self.credential = credential
        self.verbosity = verbosity
        base_dir.set(output_dir)
        youtube_dl_bin.set(yt_dl_path)
        ffmpeg_bin.set(ffmpeg_path)

    def setup(self, opt_values):
        authentification(self.credential.username, self.credential.password)

    def load_doit_config(self):
        return {'verbosity': self.verbosity, 'action_string_formatting':'new'}

    def load_tasks(self, cmd, pos_args):
        def get_eu_id_in_enseignement(eu_id, eu_ids_of_enseignement):
            for eu in eu_ids_of_enseignement:
                if eu_id == eu.name:
                    return eu
        list_to_tasks = []
        eu_ids_of_enseignement = Enseignement().get_eu()
        click.echo('Listes des EUs trouvées:')
        for eu in eu_ids_of_enseignement:
            click.echo(f'\t- {eu.name} ({eu.url})')
        for eu_id_item in self.eu_id_items:
            eu = get_eu_id_in_enseignement(eu_id_item, eu_ids_of_enseignement)
            if eu:
                list_to_tasks.append(EuTask(eu_id=eu))

        for presentation_url in self.presentation_urls:
            list_to_tasks.append(
                Presentation(
                    presentation_id=PresentationId(
                        recording_id='',
                        first_url='',
                        redirect_url=presentation_url
                    )
                )
            )

        if not list_to_tasks:
            for eu_id in eu_ids_of_enseignement:
                list_to_tasks.append(EuTask(eu_id=eu_id))

        return list(chain(
            *(element.to_tasks() for element in list_to_tasks)
            ))


@click.group
def main():
    pass

@main.command()
@click.option('--output-dir',required=True , type=click.Path(
        file_okay=False, dir_okay=True, writable=True, exists=True
    )
)
@click.option('eu_id_items', '--eu-id', multiple=True, type=str)
@click.option('--presentation-url', multiple=True, type=str)
@click.option('--username', envvar='CNAM_USERNAME', prompt=True, hide_input=True, required=True)
@click.option('--password', envvar='CNAM_PASSWORD', prompt=True, required=True)
@click.option('--verbosity', type=click.IntRange(0, 2), default=0)
@click.option('--yt-dl-path', type=str, default='yt-dlp')
@click.option('--ffmpeg-path', type=str, default='ffmpeg')
# pylint: disable=too-many-arguments
def download(*,output_dir, eu_id_items, presentation_url, username, password, verbosity, yt_dl_path, ffmpeg_path):
    """
    Fonction principale
    """
    sys.exit(
        DoitMain(
            MyLoader(
                output_dir,
                eu_id_items,
                presentation_url,
                credential=Credential(username=username, password=password),
                verbosity=verbosity,
                yt_dl_path=yt_dl_path,
                ffmpeg_path=ffmpeg_path
            )
        ).run([])
    )

@main.command()
@click.option('--username', envvar='CNAM_USERNAME', prompt=True, hide_input=True, required=True)
@click.option('--password', envvar='CNAM_PASSWORD', prompt=True, required=True)
def list_eu(username, password):
    authentification(username, password)
    for eu in Enseignement().get_eu():
        print(eu.name)

if __name__ =='__main__':
    # pylint: disable=no-value-for-parameter, missing-kwoa
    main()
