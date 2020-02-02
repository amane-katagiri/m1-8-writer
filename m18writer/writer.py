#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from dataclasses import dataclass
from enum import IntEnum
import itertools
import logging
from logging import getLogger, StreamHandler
import math
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image
import serial

logger = getLogger(__name__)
stream_handler = StreamHandler()
stream_handler.setLevel(logging.DEBUG)
logger.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)


SLOT_MAX = 8
COLUMNS_MAX = 255
PIXEL_PER_COLUMN = 8
MAGIC_NUMBER = [0x41, 0x68, 0x65, 0x6c, 0x6c, 0x6f]
PREVIEW_PIXEL_GAP = (14, 14)


class Brightness(IntEnum):
    BRIGHTEST = 0
    BRIGHTER = 1
    DIMMER = 2
    DIMMEST = 3


class Speed(IntEnum):
    SPEED_0 = 0
    SPEED_1 = 1
    SPEED_2 = 2
    SPEED_3 = 3
    SPEED_4 = 4
    SPEED_5 = 5
    SPEED_6 = 6
    SPEED_7 = 7


class Motion(IntEnum):
    LEFT = 0b000
    RIGHT = 0b001
    UP = 0b010
    DOWN = 0b011
    FREEZE = 0b100
    ANIMATION = 0b101
    SNOW = 0b110
    CURTAIN = 0b111
    LASER = 0b1000


@dataclass
class Slot:
    bitmap: bytes = b""
    columns: int = 0
    border: bool = False
    blink: bool = False
    speed: Speed = Speed.SPEED_4
    motion: Motion = Motion.LEFT

    def get_mode(self):
        return (
            0b10000000 * self.border
            + 0b00010000 * self.speed
            + 0b00001000 * self.blink
            + (0b00000111 & self.motion)
        )


def _build_header(brightness: Brightness, slot_list: List[Slot]) -> bytes:
    slot_list = (slot_list + [Slot() for x in range(SLOT_MAX)])[:SLOT_MAX]

    mode_list = [m.get_mode() for m in slot_list]
    # 7-0 -> mode 8-1: laser(on motion=0)/freeze(on motion!=0)
    laser = sum([int(x.motion == Motion.LASER) << i for i, x in enumerate(slot_list)])
    columns_list = [x.columns for x in slot_list]
    column_offset_list = [0] + list(itertools.accumulate([x.columns for x in slot_list]))
    if max(columns_list) > 0xffff:
        raise RuntimeError(
            "Columns must be less than 65536: {}".format(columns_list)
        )
    if max(column_offset_list) > 0xffff:
        raise RuntimeError(
            "Column offset must be less than 65536: {}".format(column_offset_list)
        )

    return bytes([
        *MAGIC_NUMBER,
        brightness,
        0x00,
        *mode_list,
        0x00,
        *itertools.chain.from_iterable([
            [(column_offset_list[x] >> 8) & 0xff, column_offset_list[x] & 0xff,
             (columns_list[x] >> 8) & 0xff, columns_list[x] & 0xff]
            for x in range(SLOT_MAX)
        ]),
        laser,
        0x00, 0x00, 0x00, 0x00,
    ])


def _build_body(slot_list: List[Slot]) -> bytes:
    return bytes(itertools.chain.from_iterable([
        itertools.chain.from_iterable(x)
        for x in zip(*[zip(*[iter(x.bitmap)] * x.columns) for x in slot_list])
    ]))


def load_image(path: str, lines: int, threshold: int, **mode) -> Slot:
    image = Image.open(path).convert("L")
    image = image.resize((int(image.width * (lines / image.height)), lines), Image.BICUBIC)
    columns = min(COLUMNS_MAX, math.ceil(image.width / PIXEL_PER_COLUMN))
    pixel_list = bytes(
        [1 if x > threshold else 0
         for x in image.crop((0, 0, columns * PIXEL_PER_COLUMN, image.height)).tobytes()]
    )
    bitmap = bytes(
        [sum([x << i for i, x in enumerate(reversed(pixel_list[x:(x + PIXEL_PER_COLUMN)]))])
         for x in range(0, len(pixel_list), PIXEL_PER_COLUMN)]
    )
    return Slot(bitmap=bitmap, columns=columns, **mode)


def save_preview(path: str, lines: int, display_width: int, save_path: str):
    image = Image.open(path).convert("L")
    image = image.resize((int(image.width * (lines / image.height)), lines), Image.BICUBIC)

    mask = np.array(Image.open(Path(__file__).parent / "mask.png"))
    display_size = (PREVIEW_PIXEL_GAP[1] * lines, PREVIEW_PIXEL_GAP[0] * display_width)
    for x in range(image.width // display_width + (1 if image.width % display_width else 0)):
        im = image.crop((x * display_width, 0, (x + 1) * display_width, lines))
        preview = np.zeros(display_size, dtype=np.uint8)
        for i, p in enumerate(im.tobytes()):
            submask = np.zeros(preview.shape, dtype=preview.dtype)
            offset_x = (i % display_width) * PREVIEW_PIXEL_GAP[0]
            offset_y = (i // display_width) * PREVIEW_PIXEL_GAP[1]
            submask[offset_y:(offset_y + mask.shape[0]),
                    offset_x:(offset_x + mask.shape[1])] = mask
            preview[submask != 0] = p
        Image.fromarray(preview).save(save_path.format(n=x))


def write_payload(brightness: Brightness, slot_list: List[Slot], device="/dev/ttyUSB0", baud=1200):
    header = _build_header(brightness, slot_list)
    body = _build_body(slot_list)
    payload = header + body[:16] + bytes([0 for x in range(32)]) + body[16:]
    m18 = serial.Serial(device, baud)
    m18.write(payload)


def main():
    brightness_list = {
        "1": Brightness.DIMMEST,
        "2": Brightness.DIMMER,
        "3": Brightness.BRIGHTER,
        "4": Brightness.BRIGHTEST
    }
    speed_list = {
        "1": Speed.SPEED_0,
        "2": Speed.SPEED_1,
        "3": Speed.SPEED_2,
        "4": Speed.SPEED_3,
        "5": Speed.SPEED_4,
        "6": Speed.SPEED_5,
        "7": Speed.SPEED_6,
        "8": Speed.SPEED_7,
    }
    motion_list = {
        "left": Motion.LEFT,
        "right": Motion.RIGHT,
        "up": Motion.UP,
        "down": Motion.DOWN,
        "freeze": Motion.FREEZE,
        "animation": Motion.ANIMATION,
        "snow": Motion.SNOW,
        "curtain": Motion.CURTAIN,
        "laser": Motion.LASER
    }
    parser = argparse.ArgumentParser(description="USB writer for M1-8 matrix LED name badge.")
    parser.add_argument("paths", metavar="path", type=str, nargs="+",
                        help=f"an image path for bitmap (able to write to slot 1-{SLOT_MAX}).")
    parser.add_argument("-d", "--device", type=str, default="/dev/ttyUSB0",
                        help="tty of LED name badge.")
    parser.add_argument("-b", "--baud", type=int, default=1200,
                        help="baud rate of LED name badge.")
    parser.add_argument("-l", "--lines", type=int, default=12,
                        help="number of lines of LED name badge.")
    parser.add_argument("-w", "--width", type=int, default=48,
                        help="number of columns of LED name badge.")
    parser.add_argument("-t", "--threshold", type=int, default=128,
                        help="threshold of bitmap pixel to light LED.")
    parser.add_argument("--brightness", default="4", choices=brightness_list,
                        help="brightness of LED name badge.")
    parser.add_argument("-p", "--preview", action="store_true",
                        help="save preview of images (skip writing payload).")
    for x in range(SLOT_MAX):
        parser.add_argument(f"--border{x + 1}", action="store_true",
                            help=f"show border on slot 1-{SLOT_MAX}."
                                 if x == 0 else argparse.SUPPRESS)
        parser.add_argument(f"--blink{x + 1}", action="store_true",
                            help=f"blink bitmap on slot 1-{SLOT_MAX}."
                                 if x == 0 else argparse.SUPPRESS)
        parser.add_argument(f"--speed{x + 1}", choices=speed_list,
                            help=f"set speed on slot 1-{SLOT_MAX}."
                                 if x == 0 else argparse.SUPPRESS)
        parser.add_argument(f"--motion{x + 1}", choices=motion_list,
                            help=f"set motion on slot 1-{SLOT_MAX}."
                                 if x == 0 else argparse.SUPPRESS)
        parser.add_argument(f"--savepath{x + 1}", type=str, default=f"preview_{x + 1}_{{n}}.png",
                            help=f"path to save preview of image 1-{SLOT_MAX}."
                                 if x == 0 else argparse.SUPPRESS)

    args = parser.parse_args()
    if not args.preview:
        slot_list = [
            load_image(
                x, args.lines, args.threshold,
                **{k: v for k, v in{
                    "border": getattr(args, f"border{i + 1}"),
                    "blink": getattr(args, f"blink{i + 1}"),
                    "speed": speed_list.get(getattr(args, f"speed{i + 1}")),
                    "motion": motion_list.get(getattr(args, f"motion{i + 1}"))
                }.items() if v is not None}
            )
            for i, x in enumerate(args.paths[:SLOT_MAX])
        ]
        write_payload(brightness_list[args.brightness], slot_list)
    else:
        for i, p in enumerate(args.paths):
            save_preview(p, args.lines, args.width, getattr(args, f"savepath{i + 1}"))


if __name__ == "__main__":
    import doctest
    doctest.testmod()
    main()
