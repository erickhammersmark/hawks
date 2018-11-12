#!/usr/bin/env python

import argparse
import BaseHTTPServer
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

nodename = os.uname()[1]
if nodename == 'raspberrypi':
  from rgbmatrix import RGBMatrix, RGBMatrixOptions
else:
  from mock import RGBMatrix, RGBMatrixOptions

global matrix

PRESETS = {
    "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
    "bright": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
    "blue_on_green": {"bgcolor": "green", "innercolor": "blue", "outercolor": "black"},
    "none": {},
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
  parser.add_argument("--debug", action="store_true", default=False)
  return parser.parse_args()
  return args

def text_as_color(text, rgb):
  '''
  Return string with text prefixed by ANSI escape
  code to set the backgorund to the color specified
  by 'rgb' (a tuple of r, g, b bytes).  The string
  also include the escape sequence to set the terminal
  back to its default colors.
  '''
  escape_seq = '\033[48;2;{0};{1};{2}m{3}\033[10;m'
  r, g, b = rgb
  return escape_seq.format(r, g, b, text)

def print_image(image):
  #\033[38;2;255;82;197;48;2;155;106;0mHello
  count = 0
  print
  for px in image.getdata():
    sys.stdout.write(text_as_color('  ', px))
    count += 1
    if count % 32 == 0:
      print
  print

def set_image(args, matrix, image):
  if args.debug:
    print_image(image)
  matrix.SetImage(image)

def init_matrix(args):
  # Configuration for the matrix
  options = RGBMatrixOptions()
  options.rows = args.rows
  options.chain_length = 1
  options.parallel = 1
  options.hardware_mapping = 'adafruit-hat'  # If you have an Adafruit HAT: 'adafruit-hat'
  matrix = RGBMatrix(options = options)
  #matrix.SetImage(Image.new("RGB", (args.cols, args.rows), "black"))
  set_image(args, matrix, Image.new("RGB", (args.cols, args.rows), "black"))
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

  #matrix.SetImage(image)
  set_image(args, matrix, image)

  return image

def run_api_forever(args):
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
      if len(parts) < 3:
        return self.send(404)
      key = parts[1]
      value = parts[2]
      if hasattr(self.args, key):
        if type(getattr(self.args, key)) is int:
          value = int(value)
        setattr(self.args, key, value)
        print(args.preset)
        image = draw_text(self.args)
        return self.send(200)
      self.send(404)

  httpd = BaseHTTPServer.HTTPServer(('', args.port), HawksRequestHandler)
  httpd.serve_forever()

def main():
  global matrix
  args = parse_args()
  matrix = init_matrix(args)
  draw_text(args)
  run_api_forever(args)


if __name__ == '__main__':
  main()
