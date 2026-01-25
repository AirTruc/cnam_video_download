import unittest
from pathlib import Path
from cnam.video_downloader.tasks.presentation.make_video import (
    Slide,
    to_image_clip
)

class TestImage2Clip(unittest.TestCase):
    def test_convert_with_end(self):
        slide = Slide(path=Path('/tmp/test'),start=0.0, end=2.0, x=0,y=0, width=10, height=0)
        result = to_image_clip(slide, width=100, height=100)
        expected_action = [
                "ffmpeg -y -loop 1 -i '/tmp/test' -c:v libx264 -t '2.0s'"
                " -pix_fmt yuv420p -vf 'pad=ceil(100/2)*2:ceil(100/2)*2' -r 5 '/tmp/test.mp4'"
                ]
        self.assertEqual(expected_action, result.action['actions'])

    def test_convert_without_end(self):
        slide = Slide(path=Path('/tmp/test'),start=0.0, end=0, x=0,y=0, width=10, height=0)
        result = to_image_clip(slide, width=100, height=100)
        expected_action = [
                "ffmpeg -y -loop 1 -i '/tmp/test' -c:v libx264 -t '0.0s'"
                " -pix_fmt yuv420p -vf 'pad=ceil(100/2)*2:ceil(100/2)*2' -r 5 '/tmp/test.mp4'"
                ]
        self.assertEqual(expected_action, result.action['actions'])

if __name__ == '__main__':
    unittest.main()