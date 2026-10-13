# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from luma_leaf import application


class LaunchArguments(unittest.TestCase):
    def test_desktop_file_arguments_reach_application(self):
        arguments = ['Leaf', 'file:///run/user/1000/doc/book/example.epub']
        with patch.object(application, 'LeafApplication') as constructor, patch.object(application.sys, 'argv', arguments):
            application.main()
            constructor.return_value.run.assert_called_once_with(arguments)

    def test_explicit_arguments_are_preserved(self):
        with patch.object(application, 'LeafApplication') as constructor:
            application.main([])
            constructor.return_value.run.assert_called_once_with([])
