# SPDX-License-Identifier: Apache-2.0
"""Real VTE exit, background-tab and process cleanup regressions.

Run in a disposable display/session; never on a user's graphical session.
"""
import os
import time
import unittest

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib
from luma_terminal.terminal import TerminalApplication, TerminalWindow


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Timed out waiting for terminal lifecycle change')


def stopped(pid):
    try:
        with open(f'/proc/{pid}/stat') as stream:
            return stream.read().rsplit(')', 1)[1].split()[0] == 'Z'
    except FileNotFoundError:
        return True


class Lifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = TerminalApplication()
        cls.app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def setUp(self):
        self.window = TerminalWindow(self.app)
        self.window.present()
        wait_for(lambda: len(self.window._child_pids) == 1)

    def tearDown(self):
        pids = list(self.window._child_pids.values())
        self.window.close()
        wait_for(lambda: all(stopped(pid) for pid in pids))

    def test_exit_closes_new_tab_and_preserves_older_shell(self):
        w = self.window
        original = w._active_terminal()
        original_session = w.model.current_id
        w.new_session()
        wait_for(lambda: len(w._child_pids) == 2)
        w._active_terminal().feed_child(b'exit\n')
        wait_for(lambda: len(w.model.sessions) == 1)
        self.assertEqual(w.model.current_id, original_session)
        self.assertIs(w._active_terminal(), original)
        self.assertEqual(len(w._child_pids), 1)

    def test_split_exit_then_last_exit_closes_window(self):
        w = self.window
        original = w._active_terminal()
        w.split('row')
        wait_for(lambda: len(w._child_pids) == 2)
        w._active_terminal().feed_child(b'exit\n')
        wait_for(lambda: len(w.model.current.panes) == 1)
        self.assertIs(w._active_terminal(), original)
        original.feed_child(b'exit\n')
        wait_for(lambda: not w.get_visible())
        self.assertFalse(w._child_pids)

    def test_background_tab_exit_does_not_switch_the_visible_tab(self):
        w = self.window
        original = w._active_terminal()
        w.new_session()
        wait_for(lambda: len(w._child_pids) == 2)
        visible = w._active_terminal()
        current = w.model.current_id
        original.feed_child(b'exit\n')
        wait_for(lambda: len(w.model.sessions) == 1)
        self.assertEqual(w.model.current_id, current)
        self.assertIs(w._active_terminal(), visible)

    def test_manual_tab_close_hangs_up_foreground_command_and_shell(self):
        w = self.window
        w.new_session()
        wait_for(lambda: len(w._child_pids) == 2)
        shell = w._child_pids[w.model.active_pane_id]
        terminal = w._active_terminal()
        terminal.feed_child(b'sleep 60\n')
        fd = terminal.get_pty().get_fd()
        wait_for(lambda: os.tcgetpgrp(fd) not in (0, shell))
        foreground = os.tcgetpgrp(fd)
        w.close_current_session()
        wait_for(lambda: stopped(shell) and stopped(foreground))
        self.assertEqual(len(w.model.sessions), 1)

    def test_window_close_hangs_up_all_tabs(self):
        w = self.window
        w.new_session()
        w.split('col')
        wait_for(lambda: len(w._child_pids) == 3)
        pids = tuple(w._child_pids.values())
        w.close()
        wait_for(lambda: all(stopped(pid) for pid in pids))
        self.assertFalse(w._child_pids)
        self.assertFalse(w.pane_views)


if __name__ == '__main__':
    unittest.main(verbosity=2)
