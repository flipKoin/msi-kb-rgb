#!/usr/bin/env python3
"""MSI Cyborg 17 Keyboard RGB LED Control — GUI with tray icon & presets"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")
from gi.repository import Gtk, Gdk, GLib, AppIndicator3

import os
import fcntl
import json

# --- HID backend ---

HIDIOCSFEATURE = lambda size: 0xC0004806 | (size << 16)
HIDIOCGFEATURE = lambda size: 0xC0004807 | (size << 16)
REPORT_SIZE = 64
HIDRAW_DEVICE = "/dev/hidraw4"
CONFIG_DIR = os.path.expanduser("~/.config/msi-kb-rgb")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PRESETS_FILE = os.path.join(CONFIG_DIR, "presets.json")

MODES = {
    "Off": 0x00,
    "Static": 0x01,
    "Breathing": 0x02,
    "Rainbow": 0x03,
    "Breathing 2": 0x04,
    "Effect 5": 0x05,
    "Effect 6": 0x06,
    "Effect 7": 0x07,
    "Effect 8": 0x08,
    "Effect 9": 0x09,
    "Effect 10": 0x0A,
    "Effect 11": 0x0B,
    "Effect 12": 0x0C,
    "Effect 13": 0x0D,
    "Effect 14": 0x0E,
    "Effect 15": 0x0F,
    "Effect 16": 0x10,
    "Effect 17": 0x11,
    "Effect 18": 0x12,
    "Effect 19": 0x13,
    "Effect 20": 0x14,
}

ZONE_MASKS = {1: 0x01, 2: 0x02, 3: 0x04, 4: 0x08}

RAINBOW_COLORS = [
    (0xFF, 0x00, 0x00, 0x00),
    (0xFF, 0xFF, 0x00, 0x10),
    (0x00, 0xFF, 0x00, 0x20),
    (0x00, 0xFF, 0xFF, 0x30),
    (0x00, 0x00, 0xFF, 0x40),
    (0xFF, 0x00, 0xFF, 0x50),
    (0xFF, 0x00, 0x00, 0x64),
]

DEFAULT_PRESETS = {
    "Red Static": {"brightness": 100, "linked": True, "zones": [{"mode_name": "Static", "color": [255, 0, 0], "speed": 600}]},
    "Green Static": {"brightness": 100, "linked": True, "zones": [{"mode_name": "Static", "color": [0, 255, 0], "speed": 600}]},
    "Blue Static": {"brightness": 100, "linked": True, "zones": [{"mode_name": "Static", "color": [0, 0, 255], "speed": 600}]},
    "Cyan Static": {"brightness": 100, "linked": True, "zones": [{"mode_name": "Static", "color": [0, 255, 255], "speed": 600}]},
    "Purple Breathing": {"brightness": 100, "linked": True, "zones": [{"mode_name": "Breathing", "color": [128, 0, 255], "speed": 600}]},
    "Rainbow": {"brightness": 100, "linked": True, "zones": [{"mode_name": "Rainbow", "color": [255, 0, 0], "speed": 600}]},
    "Off": {"brightness": 100, "linked": True, "zones": [{"mode_name": "Off", "color": [0, 0, 0], "speed": 600}]},
}


def make_packet(data):
    return bytes(data + [0x00] * (REPORT_SIZE - len(data)))


def send_feature_report(fd, data):
    buf = bytearray(data)
    fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf)


def get_feature_report(fd, report_id=0x02):
    buf = bytearray([report_id] + [0x00] * (REPORT_SIZE - 1))
    fcntl.ioctl(fd, HIDIOCGFEATURE(len(buf)), buf)
    return bytes(buf)


def send_and_ack(fd, data):
    send_feature_report(fd, data)
    return get_feature_report(fd)


def apply_config(zones_config):
    """Apply LED config to hardware. zones_config is a list of 4 zone dicts."""
    fd = os.open(HIDRAW_DEVICE, os.O_RDWR)
    try:
        for i, zone in enumerate(zones_config, 1):
            pkt = make_packet([0x02, 0x01, ZONE_MASKS[i]])
            send_and_ack(fd, pkt)

            mode = zone["mode"]
            speed = zone["speed"]
            bright_pct = zone.get("brightness", 100) / 100.0
            r, g, b = zone["color"]

            r = int(r * bright_pct)
            g = int(g * bright_pct)
            b = int(b * bright_pct)

            speed_lo = speed & 0xFF
            speed_hi = (speed >> 8) & 0xFF

            if mode == MODES["Rainbow"]:
                colors = [(int(cr * bright_pct), int(cg * bright_pct), int(cb * bright_pct), pos)
                          for cr, cg, cb, pos in RAINBOW_COLORS]
            else:
                colors = [(r, g, b, 0x00), (r, g, b, 0x64)]

            data = [0x02, 0x02, mode, speed_lo, speed_hi, 0x00, 0x00, 0x0F, 0x01, 0x00, 0x00]
            for cr, cg, cb, pos in colors:
                data.extend([cr, cg, cb, pos])

            pkt = make_packet(data)
            send_and_ack(fd, pkt)

        pkt = make_packet([0x02, 0xA0])
        send_and_ack(fd, pkt)
    finally:
        os.close(fd)


# --- Presets ---

def load_presets():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_PRESETS)


def save_presets(presets):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PRESETS_FILE, "w") as f:
        json.dump(presets, f, indent=2)


# --- GUI ---

class ZoneBox(Gtk.Box):
    def __init__(self, zone_num, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.zone_num = zone_num
        self.on_change = on_change

        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        label = Gtk.Label()
        label.set_markup(f"<b>Zone {zone_num}</b>")
        self.pack_start(label, False, False, 0)

        self.color_btn = Gtk.ColorButton()
        self.color_btn.set_rgba(Gdk.RGBA(1, 0, 0, 1))
        self.color_btn.set_title(f"Zone {zone_num} Color")
        self.color_btn.connect("color-set", lambda w: self.on_change())
        self.pack_start(self.color_btn, False, False, 0)

        effect_box = Gtk.Box(spacing=4)
        effect_box.pack_start(Gtk.Label(label="Effect:"), False, False, 0)
        self.effect_combo = Gtk.ComboBoxText()
        for name in MODES:
            self.effect_combo.append_text(name)
        self.effect_combo.set_active(1)
        self.effect_combo.connect("changed", lambda w: self._on_effect_changed())
        effect_box.pack_start(self.effect_combo, True, True, 0)
        self.pack_start(effect_box, False, False, 0)

        speed_box = Gtk.Box(spacing=4)
        speed_box.pack_start(Gtk.Label(label="Speed:"), False, False, 0)
        self.speed_adj = Gtk.Adjustment(value=600, lower=100, upper=3000, step_increment=100)
        self.speed_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.speed_adj)
        self.speed_scale.set_digits(0)
        self.speed_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.speed_scale.connect("value-changed", lambda w: self.on_change())
        speed_box.pack_start(self.speed_scale, True, True, 0)
        self.pack_start(speed_box, False, False, 0)

        self._on_effect_changed()

    def _on_effect_changed(self):
        mode_name = self.effect_combo.get_active_text()
        needs_speed = mode_name not in ("Off", "Static")
        needs_color = mode_name != "Off"
        self.speed_scale.set_sensitive(needs_speed)
        self.color_btn.set_sensitive(needs_color)
        self.on_change()

    def get_config(self):
        rgba = self.color_btn.get_rgba()
        r = int(rgba.red * 255)
        g = int(rgba.green * 255)
        b = int(rgba.blue * 255)
        mode_name = self.effect_combo.get_active_text() or "Static"
        return {
            "mode": MODES[mode_name],
            "mode_name": mode_name,
            "color": (r, g, b),
            "speed": int(self.speed_adj.get_value()),
            "brightness": 100,
        }

    def set_config(self, config):
        r, g, b = config.get("color", (255, 0, 0))
        self.color_btn.set_rgba(Gdk.RGBA(r / 255, g / 255, b / 255, 1))

        mode_name = config.get("mode_name", "Static")
        model = self.effect_combo.get_model()
        for i, row in enumerate(model):
            if row[0] == mode_name:
                self.effect_combo.set_active(i)
                break

        self.speed_adj.set_value(config.get("speed", 600))


class MSIKeyboardRGB(Gtk.Window):
    def __init__(self, app_indicator):
        super().__init__(title="MSI Keyboard RGB")
        self.set_default_size(750, 420)
        self.set_border_width(12)
        self.set_resizable(True)
        self.indicator = app_indicator

        self._apply_timeout_id = None
        self._linked = True
        self.presets = load_presets()

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        # Title
        title = Gtk.Label()
        title.set_markup("<big><b>MSI Cyborg 17 — Keyboard RGB</b></big>")
        vbox.pack_start(title, False, False, 0)

        # Top bar: link + presets
        top_bar = Gtk.Box(spacing=12)
        top_bar.set_halign(Gtk.Align.CENTER)

        self.link_check = Gtk.CheckButton(label="Link all zones")
        self.link_check.set_active(True)
        self.link_check.connect("toggled", self._on_link_toggled)
        top_bar.pack_start(self.link_check, False, False, 0)

        top_bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)

        # Preset dropdown
        top_bar.pack_start(Gtk.Label(label="Preset:"), False, False, 0)
        self.preset_combo = Gtk.ComboBoxText()
        self._populate_presets()
        self.preset_combo.connect("changed", self._on_preset_selected)
        top_bar.pack_start(self.preset_combo, False, False, 0)

        save_preset_btn = Gtk.Button(label="Save Preset")
        save_preset_btn.connect("clicked", self._on_save_preset)
        top_bar.pack_start(save_preset_btn, False, False, 0)

        del_preset_btn = Gtk.Button(label="Delete")
        del_preset_btn.connect("clicked", self._on_delete_preset)
        top_bar.pack_start(del_preset_btn, False, False, 0)

        vbox.pack_start(top_bar, False, False, 0)

        # Brightness slider
        bright_box = Gtk.Box(spacing=8)
        bright_box.pack_start(Gtk.Label(label="Brightness:"), False, False, 0)
        self.bright_adj = Gtk.Adjustment(value=100, lower=5, upper=100, step_increment=5)
        self.bright_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.bright_adj)
        self.bright_scale.set_digits(0)
        self.bright_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.bright_scale.connect("value-changed", lambda w: self._schedule_apply())
        bright_box.pack_start(self.bright_scale, True, True, 0)
        vbox.pack_start(bright_box, False, False, 0)

        # Zone controls
        zones_box = Gtk.Box(spacing=4, homogeneous=True)
        self.zone_widgets = []
        for i in range(1, 5):
            zone = ZoneBox(i, self._on_zone_changed)
            self.zone_widgets.append(zone)
            frame = Gtk.Frame()
            frame.add(zone)
            zones_box.pack_start(frame, True, True, 0)
        vbox.pack_start(zones_box, True, True, 0)

        # Buttons
        btn_box = Gtk.Box(spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)

        apply_btn = Gtk.Button(label="Apply")
        apply_btn.get_style_context().add_class("suggested-action")
        apply_btn.connect("clicked", lambda w: self._do_apply())
        btn_box.pack_start(apply_btn, False, False, 0)

        off_btn = Gtk.Button(label="Off")
        off_btn.get_style_context().add_class("destructive-action")
        off_btn.connect("clicked", self._on_off)
        btn_box.pack_start(off_btn, False, False, 0)

        vbox.pack_start(btn_box, False, False, 0)

        # Status bar
        self.status = Gtk.Label(label="Ready")
        self.status.set_halign(Gtk.Align.START)
        vbox.pack_start(self.status, False, False, 0)

        # Close to tray instead of quitting
        self.connect("delete-event", self._on_close)

        self._load_config()
        self.show_all()
        self._update_zone_sensitivity()

    def _populate_presets(self):
        self.preset_combo.remove_all()
        for name in sorted(self.presets.keys()):
            self.preset_combo.append_text(name)

    def _on_preset_selected(self, widget):
        name = widget.get_active_text()
        if not name or name not in self.presets:
            return
        preset = self.presets[name]
        self._apply_preset_data(preset)
        self._do_apply()
        self.status.set_text(f"Preset: {name}")

    def _apply_preset_data(self, data):
        self.bright_adj.set_value(data.get("brightness", 100))
        self._linked = data.get("linked", True)
        self.link_check.set_active(self._linked)

        zones = data.get("zones", [])
        for i, zcfg in enumerate(zones):
            if i < 4:
                self.zone_widgets[i].set_config(zcfg)
        # If linked and only 1 zone config, apply to all
        if self._linked and len(zones) == 1:
            for z in self.zone_widgets:
                z.set_config(zones[0])

    def _on_save_preset(self, widget):
        dialog = Gtk.Dialog(title="Save Preset", parent=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)

        label = Gtk.Label(label="Preset name:")
        box.add(label)
        entry = Gtk.Entry()
        current = self.preset_combo.get_active_text()
        if current:
            entry.set_text(current)
        box.add(entry)
        dialog.show_all()

        response = dialog.run()
        name = entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and name:
            cfg = self._get_current_config()
            # Store color as list for JSON
            for z in cfg["zones"]:
                z["color"] = list(z["color"])
            self.presets[name] = cfg
            save_presets(self.presets)
            self._populate_presets()
            self._rebuild_tray_menu()
            self.status.set_text(f"Saved preset: {name}")

    def _on_delete_preset(self, widget):
        name = self.preset_combo.get_active_text()
        if not name:
            return
        if name in self.presets:
            del self.presets[name]
            save_presets(self.presets)
            self._populate_presets()
            self._rebuild_tray_menu()
            self.status.set_text(f"Deleted preset: {name}")

    def _get_current_config(self):
        brightness = int(self.bright_adj.get_value())
        if self._linked:
            cfg = self.zone_widgets[0].get_config()
            zones = [{"mode_name": cfg["mode_name"], "color": cfg["color"], "speed": cfg["speed"]}]
        else:
            zones = []
            for z in self.zone_widgets:
                c = z.get_config()
                zones.append({"mode_name": c["mode_name"], "color": c["color"], "speed": c["speed"]})
        return {"brightness": brightness, "linked": self._linked, "zones": zones}

    def _on_link_toggled(self, widget):
        self._linked = widget.get_active()
        self._update_zone_sensitivity()
        if self._linked:
            cfg = self.zone_widgets[0].get_config()
            for z in self.zone_widgets[1:]:
                z.set_config(cfg)

    def _update_zone_sensitivity(self):
        for z in self.zone_widgets[1:]:
            z.set_sensitive(not self._linked)

    def _on_zone_changed(self):
        if len(self.zone_widgets) < 4:
            return
        if self._linked:
            cfg = self.zone_widgets[0].get_config()
            for z in self.zone_widgets[1:]:
                z.set_config(cfg)
        self._schedule_apply()

    def _schedule_apply(self):
        if self._apply_timeout_id:
            GLib.source_remove(self._apply_timeout_id)
        self._apply_timeout_id = GLib.timeout_add(300, self._do_apply)

    def _do_apply(self):
        self._apply_timeout_id = None
        brightness = int(self.bright_adj.get_value())

        if self._linked:
            cfg = self.zone_widgets[0].get_config()
            zones = [dict(cfg, brightness=brightness) for _ in range(4)]
        else:
            zones = [dict(z.get_config(), brightness=brightness) for z in self.zone_widgets]

        try:
            apply_config(zones)
            self.status.set_text("Applied!")
            self._save_config()
        except Exception as e:
            self.status.set_text(f"Error: {e}")

        return False

    def _on_off(self, widget):
        for z in self.zone_widgets:
            model = z.effect_combo.get_model()
            for i, row in enumerate(model):
                if row[0] == "Off":
                    z.effect_combo.set_active(i)
                    break
        self._do_apply()

    def _on_close(self, widget, event):
        self.hide()
        return True  # Prevent destruction, minimize to tray

    def _save_config(self):
        data = self._get_current_config()
        # Store color as list for JSON
        for z in data["zones"]:
            z["color"] = list(z["color"])
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            self._apply_preset_data(data)
        except Exception:
            pass

    def _rebuild_tray_menu(self):
        if self.indicator:
            build_tray_menu(self.indicator, self)


def apply_preset_by_name(presets, name):
    """Apply a preset directly (used by tray and CLI)."""
    if name not in presets:
        return
    preset = presets[name]
    brightness = preset.get("brightness", 100)
    zones_data = preset.get("zones", [])
    linked = preset.get("linked", True)

    zones = []
    for i in range(4):
        zcfg = zones_data[i] if i < len(zones_data) else zones_data[0]
        if linked and len(zones_data) == 1:
            zcfg = zones_data[0]
        zones.append({
            "mode": MODES.get(zcfg.get("mode_name", "Static"), 0x01),
            "color": tuple(zcfg.get("color", (255, 0, 0))),
            "speed": zcfg.get("speed", 600),
            "brightness": brightness,
        })
    apply_config(zones)


def build_tray_menu(indicator, win):
    menu = Gtk.Menu()

    show_item = Gtk.MenuItem(label="Show")
    show_item.connect("activate", lambda w: win.present())
    menu.append(show_item)

    menu.append(Gtk.SeparatorMenuItem())

    # Presets submenu
    presets = win.presets
    for name in sorted(presets.keys()):
        item = Gtk.MenuItem(label=name)
        item.connect("activate", lambda w, n=name: _tray_apply_preset(win, n))
        menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())

    off_item = Gtk.MenuItem(label="Off")
    off_item.connect("activate", lambda w: _tray_apply_preset(win, "Off"))
    menu.append(off_item)

    menu.append(Gtk.SeparatorMenuItem())

    quit_item = Gtk.MenuItem(label="Quit")
    quit_item.connect("activate", lambda w: Gtk.main_quit())
    menu.append(quit_item)

    menu.show_all()
    indicator.set_menu(menu)


def _tray_apply_preset(win, name):
    try:
        apply_preset_by_name(win.presets, name)
        win.status.set_text(f"Preset: {name}")
    except Exception as e:
        win.status.set_text(f"Error: {e}")


def main():
    css = Gtk.CssProvider()
    css.load_from_data(b"""
        window { background: #1a1a2e; }
        label { color: #e0e0e0; }
        frame { border-radius: 8px; background: #16213e; border: 1px solid #0f3460; }
        scale trough { background: #0f3460; }
        scale highlight { background: #e94560; }
    """)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    # System tray icon
    indicator = AppIndicator3.Indicator.new(
        "msi-kb-rgb",
        "keyboard-brightness",
        AppIndicator3.IndicatorCategory.HARDWARE,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    win = MSIKeyboardRGB(indicator)
    build_tray_menu(indicator, win)

    Gtk.main()


if __name__ == "__main__":
    main()
