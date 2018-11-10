#!/usr/bin/env python

import argparse
import sys
import time
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw, ImageFont

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bgcolor", default="black")
    parser.add_argument("--outercolor", default="green")
    parser.add_argument("--innercolor", default="blue")
    parser.add_argument("--font", default="FreeSansBold")
    parser.add_argument("--x", type=int, default=0, help="left position of text")
    parser.add_argument("--y", type=int, default=2, help="top position of text")
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--cols", type=int, default=32)
    parser.add_argument("--text", default="12")
    parser.add_argument("--textsize", type=int, default=27)
    parser.add_argument("--thickness", type=int, default=1)
    return parser.parse_args()

args = parse_args()

image = Image.new("RGB", (args.cols, args.rows), args.bgcolor)
draw = ImageDraw.Draw(image)
font = ImageFont.truetype(args.font, args.textsize)

(x, y, z) = (args.x, args.y, args.thickness)

draw.text((x-z, y-z), args.text, fill=args.outercolor, font=font)
draw.text((x+z, y-z), args.text, fill=args.outercolor, font=font)
draw.text((x-z, y+z), args.text, fill=args.outercolor, font=font)
draw.text((x+z, y+z), args.text, fill=args.outercolor, font=font)

draw.text((x, y), args.text, fill=args.innercolor, font=font)

# Configuration for the matrix
options = RGBMatrixOptions()
options.rows = args.rows
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'adafruit-hat'  # If you have an Adafruit HAT: 'adafruit-hat'

matrix = RGBMatrix(options = options)

matrix.SetImage(image.convert('RGB'))

try:
    print("Press CTRL-C to stop.")
    while True:
        time.sleep(100)
except KeyboardInterrupt:
    sys.exit(0)
