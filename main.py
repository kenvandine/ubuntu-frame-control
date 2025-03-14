import gi
import psutil
import pulsectl
import subprocess
import socket
import os
import time
import math

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('NM', '1.0')
from gi.repository import Gtk, Adw, GLib, Gio, NM

SCAN_THRESHOLD_MSEC = 10000

class UbuntuFrameControlWindow(Adw.ApplicationWindow):

    def __init__(self, app):
        Adw.ApplicationWindow.__init__(self, application=app, title="System Information")
        self.set_default_size(1024, 400)
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_content(self.box)

        # Battery Info
        battery_row = Adw.ActionRow()
        battery_row.set_title("Battery Information")
        self.box.append(battery_row)

        self.battery_icon = Gtk.Image()
        battery_row.add_suffix(self.battery_icon)
        
        self.battery_value = Gtk.Label()
        battery_row.add_suffix(self.battery_value)

        # IP Address Display
        ip_row = Adw.ActionRow()
        ip_row.set_title("IP Address")
        self.box.append(ip_row)

        self.ip_value = Gtk.Label()
        ip_row.add_suffix(self.ip_value)

        self.update_ip_address()
        
        # Wifi Heading
        wifi = Adw.ActionRow()
        wifi.set_title("<b>WiFi SSIDs</b>")
        self.box.append(wifi)
        self.wifi_selector = Gtk.ComboBoxText()
        self.wifi_selector.append_text("Select WiFi SSID")
        self.wifi_selector.set_size_request(150, -1)
        wifi.add_suffix(self.wifi_selector)
        
        # Audio Devices Heading
        audio_devices_heading = Adw.ActionRow()
        audio_devices_heading.set_title("<b>Audio Devices</b>")
        self.box.append(audio_devices_heading)

        # Sound Card Selector for Output
        output_row = Adw.ActionRow()
        output_row.set_title("Output Device")
        self.box.append(output_row)

        self.output_combo = Gtk.ComboBoxText()
        self.output_combo.append_text("Select Output Device")
        self.output_combo.set_size_request(150, -1)
        output_row.add_suffix(self.output_combo)

        # Output Volume Control
        self.output_volume = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.output_volume.set_range(0, 100)
        self.output_volume.set_size_request(200, -1)
        output_row.add_suffix(self.output_volume)

        # Sound Card Selector for Input
        input_row = Adw.ActionRow()
        input_row.set_title("Input Device")
        self.box.append(input_row)

        self.input_combo = Gtk.ComboBoxText()
        self.input_combo.append_text("Select Input Device")
        self.input_combo.set_size_request(150, -1)
        input_row.add_suffix(self.input_combo)

        # Input Volume Control
        self.input_volume = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.input_volume.set_range(0, 100)
        self.input_volume.set_size_request(200, -1)
        input_row.add_suffix(self.input_volume)

        # Brightness Control
        """
        brightness_row = Adw.ActionRow()
        brightness_row.set_title("Display Brightness")
        self.box.append(brightness_row)

        self.brightness_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.brightness_scale.set_range(0, 100)
        self.brightness_scale.set_size_request(200, -1)
        brightness_row.add_suffix(self.brightness_scale)

        self.brightness_scale.connect("value-changed", self.on_brightness_changed)
        """

        self.update_battery_info()
        GLib.timeout_add_seconds(60, self.update_battery_info)

        self.update_sound_devices()
        self.output_combo.connect("changed", self.on_output_device_changed)
        self.input_combo.connect("changed", self.on_input_device_changed)
        self.output_volume.connect("value-changed", self.on_output_volume_changed)
        self.input_volume.connect("value-changed", self.on_input_volume_changed)
        
        self.nmc = NM.Client.new(None)
        self.devs = self.nmc.get_devices()

        self.update_wifi_devices()

    def update_battery_info(self):
        battery = psutil.sensors_battery()
        if battery:
            percent = int(round(battery.percent, 0))
            plugged = "Plugged In" if battery.power_plugged else "Not Plugged In"
            battery_info = f"{percent}% - {'Charging' if battery.power_plugged else 'Discharging'}"

            # Update icon based on charging status
            icon_name = "battery-full-charged-symbolic" if battery.power_plugged else "battery-symbolic"
            self.battery_icon.set_from_icon_name(icon_name)
        else:
            battery_info = "Battery information not available"
            self.battery_icon.clear()
        
        self.battery_value.set_text(battery_info)
        return True

    def update_ip_address(self):
        ip_address = None
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address != "127.0.0.1":
                    ip_address = addr.address
                    break
            if ip_address:
                break

        self.ip_value.set_text(ip_address or "No IP address found")

    def update_sound_devices(self):
        self.pa = pulsectl.Pulse('my-pulse-client')

        # Get output devices
        self.output_combo.remove_all()
        self.output_combo.append_text("Select Output Device")
        output_devices = self.pa.sink_list()
        current_output = self.pa.get_sink_by_name(self.pa.server_info().default_sink_name)
        for i, dev in enumerate(output_devices):
            self.output_combo.append_text(dev.description)
            if dev.name == current_output.name:
                self.output_combo.set_active(i + 1)
                self.output_volume.set_value(dev.volume.value_flat * 100)

        # Get input devices
        self.input_combo.remove_all()
        self.input_combo.append_text("Select Input Device")
        input_devices = self.pa.source_list()
        current_input = self.pa.get_source_by_name(self.pa.server_info().default_source_name)
        for i, dev in enumerate(input_devices):
            self.input_combo.append_text(dev.description)
            if dev.name == current_input.name:
                self.input_combo.set_active(i + 1)
                self.input_volume.set_value(dev.volume.value_flat * 100)

    def update_wifi_devices(self):
        # Get WiFi devices
        self.wifi_selector.remove_all()
        self.wifi_selector.append_text("Select WiFi SSID")
        is_first = True
        
        def text_exists_in_combobox(combobox, text):
            model = combobox.get_model()
            iter = model.get_iter_first()
            while iter is not None:
                if model[iter][0] == text:
                    return True
                iter = model.iter_next(iter)
            return False
        
        for device in self.devs:
            print(device.get_device_type())
            if device.get_device_type() != NM.DeviceType.WIFI:
                continue

            if not is_first:
                print("")
            else:
                is_first = False

            self.device_ensure_scanned(device)
            # print_device_info(device)
            for ap in device.get_access_points():
                # self.print_ap_info(ap)
                ssid = self.ap_get_ssid(ap)
                print(f'ssid = {ssid}')
                if not text_exists_in_combobox(self.wifi_selector, ssid):
                    self.wifi_selector.append_text(ssid)

    def on_output_device_changed(self, combo):
        device_name = combo.get_active_text()
        output_devices = self.pa.sink_list()
        for dev in output_devices:
            if dev.description == device_name:
                self.pa.sink_default_set(dev)

    def on_input_device_changed(self, combo):
        device_name = combo.get_active_text()
        input_devices = self.pa.source_list()
        for dev in input_devices:
            if dev.description == device_name:
                self.pa.source_default_set(dev)

    def on_output_volume_changed(self, scale):
        volume = scale.get_value()
        output_device = self.pa.sink_list()[0]
        self.pa.volume_set_all_chans(output_device, volume / 100.0)

    def on_input_volume_changed(self, scale):
        volume = scale.get_value()
        input_device = self.pa.source_list()[0]
        self.pa.volume_set_all_chans(input_device, volume / 100.0)

    def on_brightness_changed(self, scale):
        brightness = scale.get_value()
        subprocess.run(['brightnessctl', 'set', str(brightness)])
        print(f"Brightness set to {brightness}%")

    def device_needs_scan(self, device):
        if device.get_client() is None:
            # the device got deleted. We can forget about it.
            return False
        t = device.get_last_scan()
        return t == 0 or t < NM.utils_get_timestamp_msec() - SCAN_THRESHOLD_MSEC
 
    def device_ensure_scanned(self, device):
        if os.getenv("NO_SCAN") == "1":
            return

        if not self.device_needs_scan(device):
            return
        
        def handle_request_scan(device, params):
            print('handle_request_scan')

        # kick off a new scan.
        device.request_scan_async(None)

    def print_ap_info(self, ap):
        strength = ap.get_strength()
        frequency = ap.get_frequency()
        flags = ap.get_flags()
        wpa_flags = ap.get_wpa_flags()
        rsn_flags = ap.get_rsn_flags()

        t = ap.get_last_seen()
        if t < 0:
            last_seen = "never"
        else:
            t = time.clock_gettime(time.CLOCK_BOOTTIME) - t
            last_seen = "%s sec ago" % (math.ceil(t),)

        print("  - D-Bus path: %s" % (ap.get_path(),))
        print("    SSID:       %s" % (self.ap_get_ssid(ap),))
        print("    BSSID:      %s" % (ap.get_bssid(),))
        print("    Last seen:  %s" % (last_seen,))
        print("    Frequency:  %s" % (frequency,))
        print("    Channel:    %s" % (NM.utils_wifi_freq_to_channel(frequency),))
        print(
            "    Strength:   %s%% : %s"
            % (
                strength,
                NM.utils_wifi_strength_bars(strength),
            )
        )

    def ap_get_ssid(self, ap):
        if ap is None:
            return "not connected"
        ssid = ap.get_ssid()
        if ssid is None:
            return "no ssid"
        return '%s' % (NM.utils_ssid_to_utf8(ssid.get_data()),)

class UbuntuFrameControl(Adw.Application):

    def __init__(self):
        Adw.Application.__init__(self, application_id="com.github.kenvandine.UbuntuFrameControl", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.connect("activate", self.on_activate)


    def on_activate(self, app):
        win = UbuntuFrameControlWindow(app)
        win.present()

app = UbuntuFrameControl()
app.run(None)
