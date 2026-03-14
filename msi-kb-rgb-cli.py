#!/usr/bin/env python3
"""MSI Cyborg 17 Keyboard RGB LED Control via USB HID Feature Reports"""

import sys
import struct
import fcntl
import os
import argparse

# HID ioctl constants
HID_MAX_DESCRIPTOR_SIZE = 4096
HIDIOCSFEATURE = lambda size: 0xC0004806 | (size << 16)  # Set Feature Report
HIDIOCGFEATURE = lambda size: 0xC0004807 | (size << 16)  # Get Feature Report

REPORT_SIZE = 64
HIDRAW_DEVICE = "/dev/hidraw4"

# Effect modes
MODES = {
    "off": 0x00,
    "static": 0x01,
    "breathing": 0x02,
    "rainbow": 0x03,
    "breathe2": 0x04,
}

# Zone bitmasks
ZONES = {1: 0x01, 2: 0x02, 3: 0x04, 4: 0x08}


def make_packet(data: list[int]) -> bytes:
    """Pad data to 64 bytes."""
    return bytes(data + [0x00] * (REPORT_SIZE - len(data)))


def send_feature_report(fd, data: bytes):
    """Send a HID Set Feature Report."""
    buf = bytearray(data)
    fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf)


def get_feature_report(fd, report_id: int = 0x02) -> bytes:
    """Read a HID Get Feature Report (ACK)."""
    buf = bytearray([report_id] + [0x00] * (REPORT_SIZE - 1))
    fcntl.ioctl(fd, HIDIOCGFEATURE(len(buf)), buf)
    return bytes(buf)


def send_and_ack(fd, data: bytes):
    """Send feature report and read ACK."""
    send_feature_report(fd, data)
    return get_feature_report(fd)


def select_zone(fd, zone: int):
    """Select a zone (1-4)."""
    pkt = make_packet([0x02, 0x01, ZONES[zone]])
    send_and_ack(fd, pkt)


def set_zone_color(fd, mode: int, speed: int, brightness: int, colors: list[tuple[int, int, int, int]]):
    """Set color/effect for the currently selected zone.

    colors: list of (R, G, B, position) tuples. Position 0-100 (0x00-0x64).
    """
    speed_lo = speed & 0xFF
    speed_hi = (speed >> 8) & 0xFF

    data = [0x02, 0x02, mode, speed_lo, speed_hi, 0x00, 0x00, brightness, 0x01, 0x00, 0x00]
    for r, g, b, pos in colors:
        data.extend([r, g, b, pos])

    pkt = make_packet(data)
    send_and_ack(fd, pkt)


def apply(fd):
    """Send apply/commit command."""
    pkt = make_packet([0x02, 0xA0])
    send_and_ack(fd, pkt)


def set_all_zones(fd, mode: int, speed: int, brightness: int, colors: list[tuple[int, int, int, int]]):
    """Set the same effect on all 4 zones."""
    for zone in range(1, 5):
        select_zone(fd, zone)
        set_zone_color(fd, mode, speed, brightness, colors)
    apply(fd)


def parse_color(s: str) -> tuple[int, int, int]:
    """Parse hex color like 'FF0000' or 'ff0000' or '#ff0000'."""
    s = s.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Invalid color: {s}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


RAINBOW_COLORS = [
    (0xFF, 0x00, 0x00, 0x00),  # Red
    (0xFF, 0xFF, 0x00, 0x10),  # Yellow
    (0x00, 0xFF, 0x00, 0x20),  # Green
    (0x00, 0xFF, 0xFF, 0x30),  # Cyan
    (0x00, 0x00, 0xFF, 0x40),  # Blue
    (0xFF, 0x00, 0xFF, 0x50),  # Magenta
    (0xFF, 0x00, 0x00, 0x64),  # Red (wrap)
]


def main():
    parser = argparse.ArgumentParser(description="MSI Cyborg 17 Keyboard RGB Control")
    parser.add_argument("--device", default=HIDRAW_DEVICE, help=f"HID device (default: {HIDRAW_DEVICE})")

    sub = parser.add_subparsers(dest="command", required=True)

    # off
    sub.add_parser("off", help="Turn LEDs off")

    # static
    p = sub.add_parser("static", help="Static color")
    p.add_argument("color", help="Hex color (e.g. FF0000 for red)")
    p.add_argument("--brightness", type=int, default=15, help="Brightness 0-35 (default: 15)")

    # breathing
    p = sub.add_parser("breathing", help="Breathing effect")
    p.add_argument("color", help="Hex color")
    p.add_argument("--speed", type=int, default=600, help="Speed (default: 600)")
    p.add_argument("--brightness", type=int, default=15, help="Brightness 0-35 (default: 15)")

    # rainbow
    p = sub.add_parser("rainbow", help="Rainbow effect")
    p.add_argument("--speed", type=int, default=600, help="Speed (default: 600)")
    p.add_argument("--brightness", type=int, default=15, help="Brightness 0-35 (default: 15)")

    # raw - send raw hex bytes for testing
    p = sub.add_parser("raw", help="Send raw 64-byte packet (hex)")
    p.add_argument("hex", help="Hex string of bytes to send")

    args = parser.parse_args()

    fd = os.open(args.device, os.O_RDWR)

    try:
        if args.command == "off":
            print("Setting LEDs off...")
            colors = [(0, 0, 0, 0x00), (0, 0, 0, 0x64)]
            set_all_zones(fd, MODES["off"], 500, 0x0F, colors)
            print("Done!")

        elif args.command == "static":
            r, g, b = parse_color(args.color)
            print(f"Setting static color R={r} G={g} B={b}, brightness={args.brightness}...")
            colors = [(r, g, b, 0x00), (r, g, b, 0x64)]
            set_all_zones(fd, MODES["static"], 0, args.brightness, colors)
            print("Done!")

        elif args.command == "breathing":
            r, g, b = parse_color(args.color)
            print(f"Setting breathing R={r} G={g} B={b}, speed={args.speed}, brightness={args.brightness}...")
            colors = [(r, g, b, 0x00), (r, g, b, 0x64)]
            set_all_zones(fd, MODES["breathing"], args.speed, args.brightness, colors)
            print("Done!")

        elif args.command == "rainbow":
            print(f"Setting rainbow, speed={args.speed}, brightness={args.brightness}...")
            set_all_zones(fd, MODES["rainbow"], args.speed, args.brightness, RAINBOW_COLORS)
            print("Done!")

        elif args.command == "raw":
            raw = bytes.fromhex(args.hex.replace(" ", ""))
            pkt = raw + b'\x00' * (64 - len(raw))
            print(f"Sending: {pkt[:16].hex(' ')}")
            ack = send_and_ack(fd, pkt)
            print(f"ACK:     {ack[:16].hex(' ')}")

    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
