# MSI Keyboard RGB Control for Linux

Control the keyboard RGB LEDs on MSI Cyborg 17 (and potentially other MSI laptops using the MysticLight MS-1606 USB HID device) from Linux.

![GTK3 GUI with color picker, effects, per-zone control, presets, and system tray](screenshot.png)

## Features

- **GUI** with color picker, 21 effects, speed slider, brightness control
- **Per-zone control** — 4 independent keyboard zones, or link them all
- **Presets** — save, load, and delete named color schemes
- **System tray** — minimize to tray with quick preset switching
- **CLI tool** — scriptable command-line interface
- **Auto-restore** — systemd service restores your config on boot and wake from sleep

## Supported Hardware

- **MSI Cyborg 17** (MS-1606, VID `0x0DB0`, PID `0x1606`)
- Other MSI laptops with the MysticLight MS-1606 HID device may also work

## How It Works

The keyboard LEDs are controlled via USB HID Feature Reports (Report ID `0x02`), not through EC registers or WMI. The protocol was reverse-engineered by capturing USB traffic from MSI Center on Windows using USBlyzer.

### Protocol Summary

| Command | Purpose |
|---------|---------|
| `02 01 01/02/04/08` | Select zone (bitmask) |
| `02 02 MODE SPEED_LO SPEED_HI 00 00 0F 01 00 00 R G B POS ...` | Set color/effect |
| `02 A0` | Apply/commit |

## Requirements

- Python 3
- GTK3 (`python3-gi`, `gir1.2-gtk-3.0`)
- AppIndicator3 (`gir1.2-appindicator3-0.1`) — for system tray
- Root access (for HID device writes)

## Install

```bash
# Install dependencies (Debian/Ubuntu/Zorin)
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-appindicator3-0.1

# Clone and install
git clone https://github.com/flipKoin/msi-kb-rgb.git
cd msi-kb-rgb
sudo ./install.sh
```

## Usage

### GUI
```bash
# From app menu: search "MSI Keyboard RGB"
# Or from terminal:
sudo python3 msi-kb-rgb-gui.py
```

### CLI
```bash
# Static color
sudo python3 msi-kb-rgb-cli.py static FF0000

# Rainbow effect
sudo python3 msi-kb-rgb-cli.py rainbow

# Breathing blue, custom speed
sudo python3 msi-kb-rgb-cli.py breathing 0000FF --speed 400

# Turn off
sudo python3 msi-kb-rgb-cli.py off

# Custom brightness (0-35)
sudo python3 msi-kb-rgb-cli.py static 00FFFF --brightness 20
```

### HID Device

The default device is `/dev/hidraw4`. If your device is at a different path, use:

```bash
# CLI
sudo python3 msi-kb-rgb-cli.py --device /dev/hidrawN static FF0000
```

To find your device:
```bash
# Look for MysticLight or VID 0x0DB0
cat /sys/class/hidraw/hidraw*/device/uevent | grep -B1 0DB0
```

## Uninstall

```bash
sudo ./install.sh --uninstall
```

## License

MIT
