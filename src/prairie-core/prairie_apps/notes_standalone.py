# SPDX-License-Identifier: Apache-2.0
"""Independent Notes account UI; network and keyring work stays off the UI thread."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import os
from pathlib import Path
import sys

from .notes import NotesApplication, NotesWindow
from .notes_account import HUB, NotesAccount, NotesKeyring
from .connect_sync import ConnectError, HubResponseError
from gi.repository import Adw, Gio, GLib, Gtk
from luma_appkit import BarAction, Command, TextField, Toast
from luma_appkit.action_center import make_control


class StandaloneNotesApplication(NotesApplication):
    def __init__(self):
        super().__init__()
        self.set_application_id('org.projectluma.Notes.Standalone')
        self.notes_independent_account = True
        data_home = Path(os.environ.get('XDG_DATA_HOME', ''))
        if not data_home.is_absolute():
            data_home = Path.home() / '.local/share'
        self.local_directory = data_home / 'luma/notes'
        self.notes_store_path = self.local_directory / 'notes.sqlite3'
        self.session = None
        self.view_local = False
        self.sync_source = 0
        self.sync_status = ''
        self.sync_retry_at = 0.0
        self.sync_failures = 0
        self.sync_cancel = threading.Event()
        self.connect('window-removed', self._window_removed)
        self.account = None
        self.busy = False
        self.initialized = False
        self.pending_activation = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='notes-account')
        self.account_error = ''
        self.dialog = None

    def do_startup(self):
        super().do_startup()
        self.hold()
        self.busy = True
        def load():
            self.account = NotesAccount(NotesKeyring())
            return self.account.saved_session()
        future = self.executor.submit(load)
        future.add_done_callback(lambda result: GLib.idle_add(self._loaded, result))

    def _loaded(self, future):
        try:
            self.session = future.result()
        except ConnectError as error:
            self.account_error = str(error)
        except Exception:
            self.account_error = 'The desktop keyring could not be opened.'
        self._choose_directory()
        self.busy = False
        self.initialized = True
        if self.pending_activation:
            super().do_activate()
        self.sync_source = GLib.timeout_add_seconds(30, self._automatic_sync)
        if self.session:
            GLib.idle_add(lambda: (self._automatic_sync(), GLib.SOURCE_REMOVE)[1])
        self.release()
        return GLib.SOURCE_REMOVE

    def _choose_directory(self):
        directory = self.session.profile_directory(self.local_directory) if self.session and not self.view_local else self.local_directory
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.notes_store_path = directory / 'notes.sqlite3'
        os.environ['LUMA_NOTES_DATA_DIR'] = str(directory)

    def do_activate(self):
        if not self.initialized:
            self.pending_activation = True
        else:
            super().do_activate()

    def account_commands(self, window):
        commands = [Command('notes.account', 'Luma account…', lambda: self.show_account(window), 'user')]
        if self.session and not self.view_local:
            commands.append(Command('notes.sync', 'Sync now', lambda: self.sync_now(window), 'refresh-cw'))
        if self.session:
            commands.append(Command('notes.library', 'Cloud library' if self.view_local else 'Notes on this computer',
                                    lambda: self.switch_library(not self.view_local), 'folder'))
        return tuple(commands)

    def _automatic_sync(self):
        window = next((window for window in self.get_windows() if isinstance(window, NotesWindow)), None)
        if window is not None and self.session and not self.view_local and not self.busy and time.monotonic() >= self.sync_retry_at:
            self.sync_now(window)
        return GLib.SOURCE_CONTINUE

    def _window_removed(self, _application, _window):
        if not any(isinstance(window,NotesWindow) for window in self.get_windows()):
            self.sync_cancel.set()

    def sync_now(self, window):
        if self.busy or not self.session or self.view_local:
            return
        from .notes_library_sync import NotesLibrarySync
        session, client, directory = self.session, self.account.client, self.notes_store_path.parent
        self.sync_status = 'Syncing…'
        self.sync_cancel.clear()
        def done(value):
            self.sync_status = value
            self.sync_failures = 0
            self.sync_retry_at = 0.0
            if self.dialog is not None:
                self.status.set_label(value)
        self._run(lambda: NotesLibrarySync(session, client, directory, cancel=self.sync_cancel).run(), done, window, sync_job=True)

    def switch_library(self, local):
        if self.busy:
            return
        self.hold()
        try:
            self.view_local = local
            self._switch(self.session)
        finally:
            self.release()

    def _run(self, operation, done, window, *, sync_job=False):
        if self.busy:
            return
        if not window._can_leave_document():
            if self.dialog is not None:
                self.status.set_label('Save the current note before changing accounts or syncing.')
                self.actions.set_sensitive(True)
            return
        self.busy = True
        self.hold()
        future = self.executor.submit(operation)
        def completed():
            self.busy = False
            try:
                value = future.result()
            except ConnectError as error:
                self.account_error = str(error)
                self.sync_status = self.account_error
                if sync_job:
                    self.sync_failures += 1
                    delay = min(30 * 2**min(self.sync_failures-1,4),300)
                    if isinstance(error,HubResponseError):
                        delay = max(delay,error.retry_after)
                        if error.status == 401:
                            delay = 3600
                            self.account_error = 'This Notes connection was revoked. Sign out and connect again. Your local notes are kept.'
                            self.sync_status = self.account_error
                    self.sync_retry_at = time.monotonic()+delay
                if self.dialog is not None:
                    self.status.set_label(self.account_error)
                    self.actions.set_sensitive(True)
            except Exception:
                self.account_error = 'The account operation could not be completed. Your local notes have been kept. Try again.'
                if self.dialog is not None:
                    self.status.set_label(self.account_error)
                    self.actions.set_sensitive(True)
            else:
                self.account_error = ''
                try:
                    done(value)
                except ConnectError as error:
                    self.account_error = str(error)
                    if self.dialog is not None:
                        self.status.set_label(self.account_error)
            finally:
                if self.dialog is not None:
                    self.actions.set_sensitive(True)
                self.release()
            return GLib.SOURCE_REMOVE
        future.add_done_callback(lambda _result: GLib.idle_add(completed))

    def _switch(self, session):
        # The serial worker finished before any account directory changes.
        # Flush and close all library windows; detached text-file windows keep
        # their own document paths and are unaffected.
        windows = [window for window in self.get_windows() if isinstance(window, NotesWindow)]
        if any(not window._can_leave_document() for window in windows):
            raise ConnectError('The current note could not be saved. Its library remains open.')
        if self.dialog is not None:
            self.dialog.force_close()
            self.dialog = None
        for window in windows:
            if window._close_notes(window):
                raise ConnectError('The current note could not be saved. Its library remains open.')
            window.destroy()
        self.session = session
        if session is None:
            self.view_local = False
        self._choose_directory()
        if windows:
            super().do_activate()

    def show_account(self, window):
        if self.dialog is not None:
            self.dialog.present(window)
            return
        dialog = Adw.Dialog(title='Luma account', content_width=420)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                      margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
        title = Gtk.Label(label=self.session.name if self.session else 'Connect Notes to Luma Hub', xalign=0)
        title.add_css_class('title-2')
        box.append(title)
        description = Gtk.Label(wrap=True, xalign=0)
        description.set_label('Your account library is kept separately from notes on this computer. Signing out keeps the local copy.' if self.session else
            'Sign in on Luma Hub, create a connection code, then enter it here. Notes on this computer stay in a separate local library.')
        box.append(description)
        self.status = Gtk.Label(label=self.account_error or self.sync_status, wrap=True, xalign=0)
        self.status.set_name('notes-account-status')
        box.append(self.status)
        self.actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        self.dialog = dialog
        dialog.connect('closed', lambda _dialog: setattr(self, 'dialog', None))
        def action(label, callback, primary=False):
            button = make_control(BarAction('', label, primary=primary, on_activate=callback))
            self.actions.append(button)
            return button
        action('Close', dialog.close)
        if self.session:
            def sign_out():
                if self.busy:
                    return
                self.actions.set_sensitive(False)
                self.status.set_label('Signing out…')
                self._run(self.account.sign_out, lambda _value: self._switch(None), window)
            action('Sign out', sign_out)
        else:
            field = TextField('Connection code', placeholder='Code from Luma Hub')
            field.entry.set_name('notes-connection-code')
            box.append(field)
            def open_hub():
                Gtk.UriLauncher.new(HUB + '/connect').launch(window, None, None, None)
            action('Open Luma Hub', open_hub)
            def connect():
                if self.busy:
                    return
                code = field.text
                self.actions.set_sensitive(False)
                self.status.set_label('Connecting…')
                def enroll():
                    if self.account is None:
                        self.account = NotesAccount(NotesKeyring())
                    self.account.secrets.unlock()
                    return self.account.connect(code)
                self._run(enroll, self._switch, window)
            def unlock():
                if self.busy:
                    return
                self.actions.set_sensitive(False)
                self.status.set_label('Unlocking the desktop keyring…')
                def restore():
                    if self.account is None:
                        self.account = NotesAccount(NotesKeyring())
                    self.account.secrets.unlock()
                    return self.account.saved_session()
                self._run(restore, self._switch, window)
            if self.account_error:
                action('Unlock keyring', unlock)
            action('Connect', connect, primary=True)
            field.entry.connect('activate', lambda _entry: connect())
        self.actions.set_sensitive(not self.busy)
        box.append(self.actions)
        dialog.set_child(box)
        dialog.present(window)

    def do_shutdown(self):
        # Bounded HTTP/keyring operations finish before process exit.
        if self.sync_source:
            GLib.source_remove(self.sync_source)
            self.sync_source = 0
        self.sync_cancel.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
        Gio.Application.do_shutdown(self)


def main():
    return StandaloneNotesApplication().run(sys.argv)


if __name__ == '__main__':
    raise SystemExit(main())
