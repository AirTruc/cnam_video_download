import unittest

from dataclasses import dataclass

import requests_mock

from cnam.video_downloader.tasks.eu.eu import (
    get_links_from_page,
    LinkResource,
    attr_link_extractor_from_page,
)


@dataclass
class MockResponse:
    headers: dict
    url: str
    text: str

    @classmethod
    def new(cls, url: str, text: str, content_type="html"):
        return cls(headers={"Content-Type": content_type}, url=url, text=text)


class TestGetLinksFromPage(unittest.TestCase):
    def test_get_link_if_no_content_page(self):
        expected_link_resource = LinkResource(
            url="test.com/text_must_be_filename",
            text="text_must_be_filename",
            from_html=False,
        )
        response = MockResponse(headers={}, url=expected_link_resource.url, text="test")
        links = get_links_from_page(lambda: response, selector=None, extractor=None)
        self.assertEqual(links, [expected_link_resource])

    def test_get_link_if_page_is_no_html(self):
        expected_link_resource = LinkResource(
            url="test.com/text_must_be_filename",
            text="text_must_be_filename",
            from_html=False,
        )
        response = MockResponse.new(
            url=expected_link_resource.url, text="test", content_type="pdf"
        )
        links = get_links_from_page(lambda: response, selector=None, extractor=None)

        self.assertEqual(links, [expected_link_resource])

    def test_get_link_in_a(self):
        expected_link_resource = LinkResource(
            url="test.com/test", text="", from_html=True
        )
        html = f'<a href="{expected_link_resource.url}"/>'
        response = MockResponse.new(url=None, text=html)
        links = get_links_from_page(lambda: response, selector="a")
        self.assertEqual(links, [expected_link_resource])

    def test_get_link_in_iframe(self):
        expected_link_resource = LinkResource(
            url="test.com/test", text="", from_html=True
        )
        html = f'<iframe src="{expected_link_resource.url}"/>'
        response = MockResponse.new(url=None, text=html)
        links = get_links_from_page(
            lambda: response,
            selector="iframe",
            extractor=attr_link_extractor_from_page("src"),
        )
        self.assertEqual(links, [expected_link_resource])

    def test_no_link_in_page(self):
        html = '<div href="test.com/test"/>'
        response = MockResponse.new(url=None, text=html)
        links = get_links_from_page(lambda: response, selector="a")
        self.assertEqual(links, [])

    def test_multi_link_in_page(self):
        expected_link_resource0 = LinkResource(
            url="test.com/test0", text="", from_html=True
        )
        expected_link_resource1 = LinkResource(
            url="test.com/test1", text="", from_html=True
        )
        expected_link_resource2 = LinkResource(
            url="test.com/test2", text="test", from_html=True
        )
        html = f"""<a href="{expected_link_resource0.url}"/>
<a href="{expected_link_resource1.url}"/>
<a href="{expected_link_resource2.url}">test</a>
"""
        response = MockResponse.new(url=None, text=html)
        links = get_links_from_page(lambda: response, selector="a")
        self.assertEqual(
            links,
            [expected_link_resource0, expected_link_resource1, expected_link_resource2],
        )


if __name__ == "__main__":
    unittest.main()
