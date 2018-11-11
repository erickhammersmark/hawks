#!/usr/bin/env python

import argparse
import BaseHTTPServer
import sys
import time
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw, ImageFont

global matrix

PRESETS = {
    "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
    "bright": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
    "blue_on_green": {"bgcolor": "green", "innercolor": "blue", "outercolor": "black"},
}

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
  parser.add_argument("--preset", default=None, choices=PRESETS.keys())
  parser.add_argument("--port", type=int, default=1212)
  return parser.parse_args()
  return args

def init_matrix(args):
  # Configuration for the matrix
  options = RGBMatrixOptions()
  options.rows = args.rows
  options.chain_length = 1
  options.parallel = 1
  options.hardware_mapping = 'adafruit-hat'  # If you have an Adafruit HAT: 'adafruit-hat'
  matrix = RGBMatrix(options = options)
  matrix.SetImage(Image.new("RGB", (args.cols, args.rows), "black"))
  return matrix

def draw_text(args):
  global matrix

  if args.preset:
    for k,v in PRESETS[args.preset].iteritems():
      setattr(args, k, v)

  image = Image.new("RGB", (args.cols, args.rows), args.bgcolor)
  draw = ImageDraw.Draw(image)
  font = ImageFont.truetype(args.font, args.textsize)

  (x, y, z) = (args.x, args.y, args.thickness)

  draw.text((x-z, y-z), args.text, fill=args.outercolor, font=font)
  draw.text((x+z, y-z), args.text, fill=args.outercolor, font=font)
  draw.text((x-z, y+z), args.text, fill=args.outercolor, font=font)
  draw.text((x+z, y+z), args.text, fill=args.outercolor, font=font)

  draw.text((x, y), args.text, fill=args.innercolor, font=font)

  matrix.SetImage(image)

def main():
  global matrix
  args = parse_args()
  matrix = init_matrix(args)
  draw_text(args)

  class HawksRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def __init__(self, *a, **kw):
      self.args = args
      return BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, *a, **kw)

    def send(self, code):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()

    def do_GET(self):
      if self.path == '/':
        return self.send(400)
      if self.path == "/exit":
        sys.exit(0)
      parts = self.path.split('/')
      key = parts[1]
      value = parts[2]
      if hasattr(self.args, key):
        if type(getattr(self.args, key)) is int:
          value = int(value)
        setattr(self.args, key, value)
        print(args.preset)
        draw_text(self.args)
        return self.send(200)
      self.send(404)

  httpd = BaseHTTPServer.HTTPServer(('', args.port), HawksRequestHandler)
  httpd.serve_forever()

if __name__ == '__main__':
  main()
