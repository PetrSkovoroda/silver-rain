#!/usr/bin/env python3
"""
Copyright (C) 2015 Petr Skovoroda <petrskovoroda@gmail.com>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
Boston, MA 02110-1301 USA
"""

from gi.repository import Gtk

import silver.config as config

from silver.messenger import Messenger
from silver.notifications import Notifications
from silver.player import SilverPlayer
from silver.player import SilverRecorder
from silver.schedule import SilverSchedule
from silver.timer import Timer

from silver.gui.about import About
from silver.gui.controlpanel import ControlPanel
from silver.gui.menubar import Menubar
from silver.gui.preferences import Preferences
from silver.gui.schedtree import SchedTree
from silver.gui.selection import Selection
from silver.gui.statusicon import StatusIcon
from silver.gui.window import MainWindow

### Application
class SilverApp():
    """ GUI """
    def __init__(self):
        # Initialize GStreamer
        self._player = SilverPlayer(self._on_player_error)
        self._recorder = SilverRecorder(self._on_recorder_error)
        # Schedule
        self._schedule = SilverSchedule()
        # On event timer
        self._t_event = Timer(self.update_now_playing)
        # Record timer
        self._t_recorder = Timer(self.stop_record)
        ## Window
        # Menubar
        self._menubar = Menubar(self)
        # Selection
        self._selection = Selection(self)
        # Controls
        self._panel = ControlPanel(self)
        # Main window
        self._window = MainWindow(self._menubar, self._selection, self._panel)
        # Schedule tree
        self._sched_tree = SchedTree(self._schedule)
        self._window.set_widget(self._sched_tree)
        # Don't show if should stay hidden
        if not config.start_hidden:
            self.show()
        # Messenger
        self._messenger = Messenger(self._window)
        # Notifications
        self._notifications = Notifications()
        # Satus icon
        self._status_icon = StatusIcon(self)
        # Update schedule
        #self.schedule_update()
        # Autoplay
        if config.autoplay:
            self.play()

    def clean(self):
        """ Cleanup """
        self._t_event.cancel()
        self._t_recorder.cancel()
        self._player.clean()
        self._recorder.clean()

# Application API
    def show(self):
        """ Show main window """
        self._window.show()
        self._window.hidden = False

    def hide(self):
        """ Hide main window """
        self._window.hide()
        self._window.hidden = True

    def toggle(self):
        """ Show/hide window """
        if self._window.hidden:
            self.show()
        else:
            self.hide()

    def about(self):
        """ Open about dialog """
        dialog = About(self._window)
        dialog.run()
        dialog.destroy()

    def im(self):
        """ Open messenger """
        self._messenger.show()

    def prefs(self):
        """ Open preferences window """
        dialog = Preferences(self._window)
        # Apply settings
        apply = []
        while dialog.run() == Gtk.ResponseType.APPLY:
            if dialog.validate():
                apply = dialog.apply_settings()
                break
            else:
                self.error_show("Invalid recordings storage location")
        dialog.destroy()
        if "IM" in apply:
            # Update messenger
            self._messenger.update_sender()
        if "APPEARANCE" in apply:
            # Update schedule
            self.selection_update()
            self.sched_tree_model_create()
            self.sched_tree.set_model(self.sched_tree_model)
            self.sched_tree_mark_current()
        if "NETWORK" in apply:
            # Update player
            self._player.reset_connection_settings()
            self._recorder.reset_connection_settings()

    def play(self):
        """ Update interface, start player """
        # Update interface
        self._menubar.update_playback_menu(True)
        self._panel.update_playback_button(True)
        self._status_icon.update_playback_menu(True)
        # Play
        self._player.play()
        # Get current event
        title = self._schedule.get_event_title()
        host = self._schedule.get_event_host()
        img = self._schedule.get_event_icon()
        # Show notification
        self._notifications.show_playing(title=title, host=host, icon=img)

    def stop(self):
        """ Update interface, stop player """
        # Update interface
        self._menubar.update_playback_menu(False)
        self._panel.update_playback_button(False)
        self._status_icon.update_playback_menu(False)
        # Stop player
        self._player.stop()
        # Show notification
        self._notifications.show_stopped()

    def set_volume(self):
        #XXX
        if not self._player.muted and self._player.volume == 0:
            self.on_mute_toggled()
        elif self._player.muted and self._player.volume > 0:
            self._player.muted = self._player.volume
            self.on_mute_toggled()
        self._player.set_volume(self._player.volume)

    def volume_increase(self, value):
        pass

    def volume_decrease(self, value):
        pass

    def on_mute_toggled(self):
        """ Since it's impossible to just set checkbox status
            without activating it (which is stupid, by the way),
            this function should toggle checkbox from menubar
            which will run actual mute method """
        self._menubar.raise_mute(not self._player.muted)

    def mute(self):
        """ Mute player """
        pass

    def record(self):
        """ Start recorder """
        self._recorder.play()
        pass

    def stop_record(self):
        """ Stop recorder """
        self._recorder.stop()
        pass

    def refilter(self, weekday):
        """ Refilter TreeView """
        self._sched_tree.refilter(weekday)

    def status_set_error(self):
        #XXX PUT SOMEWHERE
        self._panel.status_set_text(_("Couldn't update schedule"))

    def update_schedule(self, refresh):
        # TODO
        #
        # TODO update statusicon tooltip
        # Get current event
        # title = self._schedule.get_event_title()
        # host = self._schedule.get_event_host()
        # time = self._schedule.get_event_time()
        # img = self._schedule.get_event_icon()
        # self._status_icon.update_event(title, host, time, img)
        """ Initialize schedule, create treeview and start timers
            This might take a while, so run in thread """
        def init_sched():
            # Initialize schedule
            ret = self._schedule.update_schedule(refresh)
            if not ret:
                GObject.idle_add(error)
            else:
                if not refresh:
                    # Initialization
                    # Create treeview
                    self._schedule.sched_tree_create()
                    # Initialize timers
                    self.timers_init_event_timer()
                else:
                    # Refresh treeview
                    self.sched_tree_model_create()
                    self.sched_tree.set_model(self.sched_tree_model)
                    self.timers_reset()
                GObject.idle_add(cleanup)

        def cleanup():
            t.join()
            # Draw sched tree if just created
            if not refresh:
                self.sched_tree.show()
            # Show playing status
            self.status_set_playing()
            # Update selection
            self.selection_update()
            # Mark current row
            self.sched_tree_mark_current()

        def error():
            t.join()
            # Show error status
            self.status_set_error()
            GObject.timeout_add(10000, self._status_update)
            self.status_set_playing()

        # Show updating status
        self.status_set_schedule_updating()
        # Show updating message
        t = threading.Thread(target=init_sched)
        t.start()

    def quit(self):
        """ Exit """
        Gtk.main_quit()
    
### GStreamer callbacks
    def _on_player_error(self, player, type, msg):
        pass
    def _on_recorder_error(self, player, type, msg):
        pass

### Updater
    def update_now_playing(self):
        #XXX START TIMER
        """ Update label, bg of current event, show notifications """
        # Show agenda for today if not shown
        if not (self.__weekday_filter__ == self.__today__.strftime("%A")):
            self.selection_update()
        # Reset previous line
        self.sched_tree_reset_current()
        if self._schedule.update_current_event():
            # Update selection
            self.__today__ = datetime.now(MSK())
            self.selection_update()
        if self._sched_tree.check_recorder():
            self.record()
        self.sched_tree_mark_current()
        self.status_update()
        self.show_notification_on_event()

### Dialog
class Dialog():
    def dialog_create(self, title, icon_name, message):
        dialog = Gtk.Dialog.new()
        dialog.set_title("Silver Rain: " + title)
        dialog.set_resizable(False)
        dialog.set_transient_for(self)
        # Image
        icontheme = Gtk.IconTheme.get_default()
        icon = icontheme.load_icon(icon_name, 48, 0)
        img = Gtk.Image()
        img.set_from_pixbuf(icon)
        # Message
        text = Gtk.Label("{0}: {1}".format(title,
                         "\n".join(textwrap.wrap(message, 50))))
        # Pack
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_border_width(10)
        grid.attach(img, 0, 0, 1, 1)
        grid.attach(text, 1, 0, 1, 1)
        # Content
        box = dialog.get_content_area()
        box.set_spacing(10)
        box.pack_start(grid, True, True, 0)
        # Button
        dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()

    def warning_show(self, msg):
        self.dialog_create("Warning", "dialog-warning", msg)

    def error_show(self, msg):
        self.dialog_create("Error", "dialog-error", msg)

### Common
    #def recorder_toggle(self, button):
        #""" Change status, toggle recorder, set timer """
        #recording = self._recorder.playing
        ## Menubar
        #self.menubar_record.set_sensitive(recording)
        #self.menubar_stop_recording.set_sensitive(not recording)
        ## Appindicator
        #self.appindicator_update_menu()
        #if not recording:
            ## Set timer
            #today = datetime.now(MSK())
            #now = timedelta(hours=today.hour,
                            #minutes=today.minute,
                            #seconds=today.second).total_seconds()
            #timeout = int(self._schedule.get_event_end() - now)
            #self._t_recorder = threading.Timer(timeout,
                            #self.timers_callback_recorder_stop)
            #self._t_recorder.start()
        ## Get name
        #if not self.__SCHEDULE_ERROR__:
            #name = self._schedule.get_event_title()
        #else:
            #name = "SilverRain"
        ## Start recorder
        #if not recording:
            #self._recorder.play(name)
        #else:
            #self._recorder.stop()

    def recorder_stop(self, button):
        """ Cancel timer, toggle recorder """
        self._t_recorder.cancel()
        self.recorder_toggle(None)

    def mute_toggle(self, button, val=0):
        """ Set volume, update interface """
        if self.self._player.muted:
            self._player.volume = self.self._player.muted
            self.self._player.muted = 0
        else:
            self.self._player.muted = self._player.volume or 5
            self._player.volume = 0
        # Control panel
        self.mute_button.set_icon_name(self.get_volume_icon())
        # Appindicator
        self.appindicator_update_menu()
        # This actually gonna mute player
        self.volume.set_value(self._player.volume)


        #self.playback_button.set_icon_name(self.get_playback_label()[1])
        ## Menubar
        #self.menubar_play.set_sensitive(playing)
        #self.menubar_stop.set_sensitive(not playing)
        ## Control panel
        #self.playback_button.set_tooltip_text(self.get_playback_label()[0])
        ## Appindicator
        #self.appindicator_update_menu()
        #if playing:
            #self._player.stop()
        #else:
            #self._player.play()
        #self.show_notification_on_playback()

