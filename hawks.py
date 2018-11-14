#!/usr/bin/env python

import os
import sys
from PIL import Image, ImageDraw, ImageFont

def running_on_pi():
  return os.uname()[1] == 'raspberrypi'

if running_on_pi():
  from rgbmatrix import RGBMatrix, RGBMatrixOptions
else:
  from mock import RGBMatrix, RGBMatrixOptions

class Hawks(object):
  PRESETS = {
      "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
      "bright": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
      "blue_on_green": {"bgcolor": "green", "innercolor": "blue", "outercolor": "black"},
      "none": {},
  }

  def __init__(self, *args, **kwargs):
    self.bgcolor = "black"
    self.outercolor = "green"
    self.innercolor = "blue"
    self.font = "FreeSansBold"
    self.x = 0
    self.y = 2
    self.rows = 32
    self.cols = 32
    self.text = "12"
    self.textsize=27
    self.thickness = 1
    self.preset = "none"
    self.port = 1212
    self.debug = False

    self.init_matrix()

    for k,v in kwargs.iteritems():
      print(k, v)
      setattr(self, k, v)


  def text_as_color(self, text, rgb):
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

  def print_image(self, image):
    #\033[38;2;255;82;197;48;2;155;106;0mHello
    count = 0
    print
    for px in image.getdata():
      sys.stdout.write(self.text_as_color('  ', px))
      count += 1
      if count % 32 == 0:
        print
    print

  def set_image(self, image):
    if self.debug:
      self.print_image(image)
    self.matrix.SetImage(image)

  def init_matrix(self):
    # Configuration for the matrix
    options = RGBMatrixOptions()
    options.rows = self.rows
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = 'adafruit-hat'  # If you have an Adafruit HAT: 'adafruit-hat'
    self.matrix = RGBMatrix(options = options)
    self.set_image(Image.new("RGB", (self.cols, self.rows), "black"))

  def draw_text(self):
    if self.preset:
      for k,v in Hawks.PRESETS[self.preset].iteritems():
        setattr(self, k, v)

    image = Image.new("RGB", (self.cols, self.rows), self.bgcolor)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(self.font, self.textsize)

    (x, y, z) = (self.x, self.y, self.thickness)

    draw.text((x-z, y-z), self.text, fill=self.outercolor, font=font)
    draw.text((x+z, y-z), self.text, fill=self.outercolor, font=font)
    draw.text((x-z, y+z), self.text, fill=self.outercolor, font=font)
    draw.text((x+z, y+z), self.text, fill=self.outercolor, font=font)

    draw.text((x, y), self.text, fill=self.innercolor, font=font)

    self.set_image(image)

def main():
  h = Hawks()
  h.debug = True
  h.draw_text()

if __name__ == '__main__':
  main()

