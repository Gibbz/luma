# SPDX-License-Identifier: Apache-2.0
"""Independent Messages account lifecycle and the shared application UI."""
import os,json,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
os.environ['LUMA_MESSAGES_STANDALONE']='1'
os.environ['LUMA_MESSAGES_AGENT']='0'
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Adw','1')
from gi.repository import Gtk,GLib,Gio
from luma_appkit import Card,LayerHost,TextButton,Toast,apply_type
from .messages import MessagesApplication,MessagesWindow
from .messages_account import MessagesAccount,MessagesKeyring
from .notes_account import HUB
from .connect_sync import ConnectError
from . import messages_accounts

class StandaloneMessagesApplication(MessagesApplication):
    def __init__(self):
        self.base_data=Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'luma/messages-standalone'
        self.base_data.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.session=None;self.account=None;self.initialized=False;self.pending_activation=False
        self.busy=False;self.account_error='';self.account_dialog=None
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='messages-account')
        super().__init__()
        self.set_application_id('org.projectluma.Messages.Standalone')
        messages_accounts.BridgeProcess.credential_loader=staticmethod(self._credential)
    def _credential(self,executable):
        if Path(executable).name!='luma':return None
        try:session=self.account.saved_session() if self.account else None
        except Exception:raise messages_accounts.KeyringLocked('The saved Messages sign-in is unavailable.') from None
        if self.session is None or session is None or self.session.device_id!=session.device_id:
            raise messages_accounts.KeyringLocked('Sign in to Luma Messages before connecting.')
        return {'hub':session.hub,'token':session.access_token,'device_id':session.device_id}
    def do_startup(self):
        super().do_startup();self.hold()
        def load():
            origin=os.environ.get('LUMA_MESSAGES_HUB',HUB)
            from .notes_account import NotesHubClient
            self.account=MessagesAccount(MessagesKeyring(origin),client=NotesHubClient(origin))
            return self.account.saved_session()
        future=self.executor.submit(load);future.add_done_callback(lambda result:GLib.idle_add(self._loaded,result))
    def _loaded(self,future):
        try:self.session=future.result()
        except Exception:self.account_error='The saved sign-in could not be opened. Unlock your keyring or try again.'
        self._profile();self.initialized=True
        if self.pending_activation:super().do_activate()
        self.release();return False
    def _profile(self):
        root=self.session.profile_directory(self.base_data) if self.session else self.base_data/'local'
        root.mkdir(mode=0o700,parents=True,exist_ok=True)
        os.environ['XDG_DATA_HOME']=str(root)
        marker=root/'luma/connect/device.json'
        if self.session:
            marker.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            # Public registration metadata enables the shared account UI. The
            # helper receives its credential only through a sealed memory FD.
            temporary=marker.with_suffix('.new')
            fd=os.open(temporary,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as stream:
                json.dump({'device_id':self.session.device_id,'hub':self.session.hub,'scope':'messages'},stream);stream.flush();os.fsync(stream.fileno())
            temporary.replace(marker)
        else:marker.unlink(missing_ok=True)
    def do_activate(self):
        if not self.initialized:self.pending_activation=True
        else:super().do_activate()
    def show_luma_account(self,window):
        if self.busy:return
        card=Card(padded=True);card.add_css_class('lumaui-dialog');card.set_margin_start(16);card.set_margin_end(16);card.set_margin_bottom(16)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);card.append(box)
        box.append(apply_type(Gtk.Label(label='Luma Messages',xalign=0),'title-1'))
        message=Gtk.Label(xalign=0,wrap=True,label=self.account_error or ('Signed in to Luma Messages.' if self.session else 'Sign in to Luma Hub in your browser, then enter its one-time connection code.'))
        box.append(message)
        entry=Gtk.Entry(placeholder_text='Connection code',max_length=128,visible=self.session is None);box.append(entry)
        error=Gtk.Label(xalign=0,wrap=True,visible=False);apply_type(error,'caption');box.append(error)
        browser=TextButton('Open Luma Hub',style='fill',size='touch')
        browser.set_visible(self.session is None);box.append(browser)
        buttons=Gtk.Box(spacing=8,homogeneous=True);close=TextButton('Close',style='fill',size='touch');connect=TextButton('Sign out' if self.session else 'Sign in',style='key',size='touch');buttons.append(close);buttons.append(connect);box.append(buttons)
        handle=LayerHost.window_host(window).present_modal(card,drawer=getattr(window,'phone',False))
        close.connect('clicked',lambda *_:handle.close())
        browser.connect('clicked',lambda *_:Gio.AppInfo.launch_default_for_uri(self.account.client.origin+'/account/sign-in',None))
        def submit(*_):
            if self.busy:return
            code=entry.get_text();self.busy=True;connect.set_sensitive(False);close.set_sensitive(False);entry.set_sensitive(False);error.set_visible(False)
            future=self.executor.submit(self.account.sign_out if self.session else lambda:self.account.connect(code))
            def finished():
                self.busy=False;connect.set_sensitive(True);close.set_sensitive(True);entry.set_sensitive(True)
                try:
                    future.result();session=self.account.saved_session()
                except Exception as failure:
                    error.set_label(str(failure).replace('Notes','Messages') if isinstance(failure,ConnectError) else 'Sign-in could not complete. Please try again.');error.set_visible(True);return False
                handle.close();entry.set_text('')
                # Stop old providers before changing the account's data root.
                self.hold()
                try:
                    for old in tuple(self.get_windows()):
                        if isinstance(old,MessagesWindow):old.quit()
                    self.session=session;self._profile();self.activate()
                finally:self.release()
                return False
            future.add_done_callback(lambda _result:GLib.idle_add(finished))
        connect.connect('clicked',submit);entry.connect('activate',submit)

_original_accounts=MessagesWindow._show_accounts

def show_accounts(self,*_args):
    if isinstance(self.get_application(),StandaloneMessagesApplication):
        from luma_appkit.action_bubble import FloatingMenu,MenuItem
        anchor=getattr(getattr(self,'surface',None),'center',None) or self
        menu=FloatingMenu([MenuItem('Luma Messages…',icon='user',on_activate=lambda:self.get_application().show_luma_account(self)),MenuItem('Other accounts…',icon='users',on_activate=lambda:_original_accounts(self))],label='Accounts')
        menu.popup(anchor)
    else:_original_accounts(self)
MessagesWindow._show_accounts=show_accounts
from .messages_port import MessagesSurface
_original_luma_profile=MessagesSurface._open_luma_account
_original_link=MessagesSurface._link_google
_original_surface_init=MessagesSurface.__init__
def surface_init(self,owner,*args,**kwargs):
    _original_surface_init(self,owner,*args,**kwargs)
    app=owner.get_application()
    if isinstance(app,StandaloneMessagesApplication):
        from luma_appkit import EmptyState,icons
        old=self.empty;parent=old.get_parent()
        self.empty=EmptyState('Luma Messages','Sign in to message your Luma friends, or link another messaging account.' if app.session is None else 'Start an encrypted conversation with your Luma friends.',icons.icon_name('message-square'),primary=('Sign in to Luma',lambda:app.show_luma_account(owner)) if app.session is None else ('Choose your Luma username',lambda:owner._show_luma_profile()),secondary=('Other accounts',lambda:_original_accounts(owner)))
        self.empty.set_name('msg-empty');parent.remove_overlay(old);parent.add_overlay(self.empty)
MessagesSurface.__init__=surface_init
MessagesSurface._open_luma_account=lambda self:self.owner.get_application().show_luma_account(self.owner) if isinstance(self.owner.get_application(),StandaloneMessagesApplication) and self.owner.get_application().session is None else _original_luma_profile(self)
MessagesSurface._link_google=lambda self:_original_accounts(self.owner) if isinstance(self.owner.get_application(),StandaloneMessagesApplication) else _original_link(self)


def main():return StandaloneMessagesApplication().run([])
if __name__=='__main__':raise SystemExit(main())
