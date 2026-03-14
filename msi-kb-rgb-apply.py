#!/usr/bin/env python3
"""Apply last saved MSI keyboard RGB config. Used by systemd on boot/wake."""

import os
import sys
import json
import fcntl
import time

HIDIOCSFEATURE = lambda size: 0xC0004806 | (size << 16)
HIDIOCGFEATURE = lambda size: 0xC0004807 | (size << 16)
REPORT_SIZE = 64
HIDRAW_DEVICE = "/dev/hidraw4"
CONFIG_DIR = os.path.expanduser("~/.config/msi-kb-rgb")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

MODES = {
    "Off": 0x00, "Static": 0x01, "Breathing": 0x02, "Rainbow": 0x03,
    "Breathing 2": 0x04, "Effect 5": 0x05, "Effect 6": 0x06, "Effect 7": 0x07,
    "Effect 8": 0x08, "Effect 9": 0x09, "Effect 10": 0x0A, "Effect 11": 0x0B,
    "Effect 12": 0x0C, "Effect 13": 0x0D, "Effect 14": 0x0E, "Effect 15": 0x0F,
    "Effect 16": 0x10, "Effect 17": 0x11, "Effect 18": 0x12, "Effect 19": 0x13,
    "Effect 20": 0x14,
}

ZONE_MASKS = {1: 0x01, 2: 0x02, 3: 0x04, 4: 0x08}

RAINBOW_COLORS = [
    (0xFF, 0x00, 0x00, 0x00), (0xFF, 0xFF, 0x00, 0x10),
    (0x00, 0xFF, 0x00, 0x20), (0x00, 0xFF, 0xFF, 0x30),
    (0x00, 0x00, 0xFF, 0x40), (0xFF, 0x00, 0xFF, 0x50),
    (0xFF, 0x00, 0x00, 0x64),
]


def make_packet(data):
    return bytes(data + [0x00] * (REPORT_SIZE - len(data)))


def send_and_ack(fd, data):
    buf = bytearray(data)
    fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf)
    ack = bytearray([0x02] + [0x00] * (REPORT_SIZE - 1))
    fcntl.ioctl(fd, HIDIOCGFEATURE(len(ack)), ack)


def apply_config(zones_config):
    fd = os.open(HIDRAW_DEVICE, os.O_RDWR)
    try:
        for i, zone in enumerate(zones_config, 1):
            send_and_ack(fd, make_packet([0x02, 0x01, ZONE_MASKS[i]]))

            mode = zone["mode"]
            speed = zone["speed"]
            bright_pct = zone.get("brightness", 100) / 100.0
            r, g, b = zone["color"]
            r, g, b = int(r * bright_pct), int(g * bright_pct), int(b * bright_pct)

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
            send_and_ack(fd, make_packet(data))

        send_and_ack(fd, make_packet([0x02, 0xA0]))
    finally:
        os.close(fd)


def main():
    # Wait for USB device to be ready after boot/wake
    for attempt in range(10):
        if os.path.exists(HIDRAW_DEVICE):
            break
        time.sleep(1)

    if not os.path.exists(CONFIG_FILE):
        print("No config file found, skipping.")
        return

    with open(CONFIG_FILE) as f:
        data = json.load(f)

    brightness = data.get("brightness", 100)
    zones_data = data.get("zones", [])
    linked = data.get("linked", True)

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
    print("RGB config applied.")


if __name__ == "__main__":
    main()
