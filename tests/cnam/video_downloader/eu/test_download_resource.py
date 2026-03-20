import unittest

from dataclasses import dataclass

import requests_mock

from cnam.video_downloader.tasks.eu.download_resource import (
    build_resource_name,
    LinkResource,
    build_default_name,
    rename_element_if_duplicated
)

class TestBuildDefaultName(unittest.TestCase):
    def test_totalcount_0(self):
        name = build_default_name('name', 0, 0)
        self.assertEqual(name, 'name')

    def test_totalcount_1(self):
        name = build_default_name('name', 1, 0)
        self.assertEqual(name, 'name')

    def test_totalcount_2(self):
        name = build_default_name('name', 2, 0)
        self.assertEqual(name, 'name_1')
        name = build_default_name('name', 2, 10)
        self.assertEqual(name, 'name_11')

class TestRenameIfDuplicate(unittest.TestCase):

    def test_empty(self):
        names = rename_element_if_duplicated([], lambda x:x, lambda x, y:y)
        self.assertEqual(names, [])

    def test_one_element(self):
        names = rename_element_if_duplicated(['name'], lambda x:x, lambda x, y:y)
        self.assertEqual(names, ['name'])

    def test_no_duplicate(self):
        names = rename_element_if_duplicated(['name', 'foo'], lambda x:x, lambda x, y:y)
        self.assertEqual(names, ['name', 'foo'])

    def test_all_duplicate(self):
        names = rename_element_if_duplicated(['name', 'name'], lambda x:x, lambda x, y:y)
        self.assertEqual(names, ['name_1', 'name_2'])

    def test_mix_duplicate_keep_order(self):
        names = rename_element_if_duplicated(['name', 'foo', 'bar', 'name', 'foo', 'name'], lambda x:x, lambda x, y:y)
        self.assertEqual(names, ['name_1', 'foo_1', 'bar', 'name_2', 'foo_2', 'name_3'])


class TestBuildResourceName(unittest.TestCase):
    def test_without_suffix_and_url_with_one_ext(self):
        page = LinkResource(url='page.php', text='page_test', from_html=True)
        link = LinkResource(url='link.pdf', text='link_test', from_html=True)
        name = build_resource_name(page, link)
        self.assertEqual(name, 'page_test__link_test.pdf')

    def test_without_suffix_and_url_with_one_ext_and_options(self):
        page = LinkResource(url='page.php', text='page_test', from_html=True)
        link = LinkResource(url='link.pdf?test=1&test=2', text='link_test', from_html=True)
        name = build_resource_name(page, link)
        self.assertEqual(name, 'page_test__link_test.pdf')

    def test_without_suffix_and_url_with_two_ext(self):
        page = LinkResource(url='page.php', text='page_test', from_html=True)
        link = LinkResource(url='https://par.moodle.lecnam.net/pluginfile.php/1817617/mod_label/intro/cours_biv.pdf?time=1675419798889', text='link_test', from_html=True)
        name = build_resource_name(page, link)
        self.assertEqual(name, 'page_test__link_test.pdf')


    def test_with_suffix_and_url_with_one_ext(self):
        page = LinkResource(url='page.php', text='page_test', from_html=True)
        link = LinkResource(url='link.pdf', text='link_test.docx', from_html=True)
        name = build_resource_name(page, link)
        self.assertEqual(name, 'page_test__link_test.docx')

    def test_with_suffix_and_url_with_one_ext_and_options(self):
        page = LinkResource(url='page.php', text='page_test', from_html=True)
        link = LinkResource(url='link.pdf?test=1&test=2', text='link_test.docx', from_html=True)
        name = build_resource_name(page, link)
        self.assertEqual(name, 'page_test__link_test.docx')

    def test_with_suffix_and_url_with_two_ext(self):
        page = LinkResource(url='page.php', text='page_test', from_html=True)
        link = LinkResource(url='https://par.moodle.lecnam.net/pluginfile.php/1817617/mod_label/intro/cours_biv.pdf?time=1675419798889', text='link_test.docx', from_html=True)
        name = build_resource_name(page, link)
        self.assertEqual(name, 'page_test__link_test.docx')

if __name__ == "__main__":
    unittest.main()
