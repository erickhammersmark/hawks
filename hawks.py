#!/usr/bin/env python

import argparse
import BaseHTTPServer
import sys
import time
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw, ImageFont

PRESETS = {
    "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
    "daylight": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
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
  args = parser.parse_args()
  if args.preset:
    for k,v in PRESETS[args.preset].iteritems():
      setattr(args, k, v)
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
  matrix = init_matrix(args)

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
  args = parse_args()
  draw_text(args)

  class HawksRequestHandler(BaseHTTPServer.BaseHTTPRequestHanlder):
    def __init__(self, *a, **kw):
      self.args = args
      super(HawksRequestHandler, self).__init__(self, *a, **kw)

    def send(self, code):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()

    def do_GET(self, req):
      if !req or req.path == '/':
        return self.send(400)
      if req.path == "/exit":
        sys.exit(0)
      parts = req.path.split('/')
      key = parts[1]
      value = parts[2]
      if hasattr(args, key):
        if type(getattr(args, key) == int):
          value = int(value)
        args.key = value
        draw_text(args)
        return self.send(200)
      self.send(404)

  httpd = BaseHttpServer(('', args.port), HawksRequestHandler)
  httpd.serve_forever()

if __name__ == '__main__':
  main()
