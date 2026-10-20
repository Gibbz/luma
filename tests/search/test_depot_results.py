# SPDX-License-Identifier: Apache-2.0
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/luma-search'))
from luma_search.depot import matches
from luma_search.files import personal_candidate


def app(identifier, name, *, visibility='public'):
    return SimpleNamespace(id=identifier, name=name, summary='', categories=(),
                           identifier=identifier, visibility=visibility)


class CatalogueResults(unittest.TestCase):
    def test_exact_name_first_and_installed_or_unlisted_omitted(self):
        catalogue = (app('blue-studio', 'Blue Studio'), app('blue', 'Blue'),
                     app('hidden', 'Blue Secret', visibility='unlisted'))
        self.assertEqual(matches(catalogue, ['blue']), ('blue', 'blue-studio'))
        self.assertEqual(matches(catalogue, ['blue'], ['blue.desktop']), ('blue-studio',))
        self.assertEqual(matches(catalogue, []), ())

    def test_result_count_bounded(self):
        self.assertEqual(len(matches(tuple(app(str(i), 'Blue ' + str(i)) for i in range(30)), ['blue'])), 6)

    def test_user_documents_and_downloads_remain_searchable(self):
        for path in ('/home/user/Documents/report.pdf', '/home/user/Downloads/cover.svg'):
            self.assertTrue(personal_candidate({'path': path}))
        for path in ('/etc/report.conf', '/usr/share/icons/cover.svg',
                     '/home/user/.config/report.json', '/home/user/.cache/report.pdf'):
            self.assertFalse(personal_candidate({'path': path}))


if __name__ == '__main__':
    unittest.main()
