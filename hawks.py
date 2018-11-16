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

class HawksSettings(object):
  def __init__(self, *args, **kwargs):
    self.set("bgcolor", "black")
    self.set("outercolor", "green")
    self.set("innercolor", "blue")
    self.set("font", "FreeSansBold")
    self.set("x", 0)
    self.set("y", 2)
    self.set("rows", 32)
    self.set("cols", 32)
    self.set("text", "12")
    self.set("textsize", 27)
    self.set("thickness", 1)
    self.set("preset", "none")
    for k,v in kwargs.iteritems():
      self.set(k, v)

  def __contains__(self, name):
    return name in self.__dict__

  def set(self, name, value):
    setattr(self, name, value)

class Hawks(object):
  PRESETS = {
      "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
      "bright": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
      "blue_on_green": {"bgcolor": "green", "innercolor": "blue", "outercolor": "black"},
      "none": {},
  }

  def __init__(self, *args, **kwargs):
    self.settings = HawksSettings()
    self.port = 1212
    self.debug = False

    self.init_matrix()

    for k,v in kwargs.iteritems():
      if k in self.settings:
        self.settings.set(k, v)
      else:
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
    self.matrix.SetImage(image)

  def init_matrix(self):
    # Configuration for the matrix
    options = RGBMatrixOptions()
    options.rows = self.settings.rows
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = 'adafruit-hat'  # If you have an Adafruit HAT: 'adafruit-hat'
    self.matrix = RGBMatrix(options = options)
    self.set_image(Image.new("RGB", (self.settings.cols, self.settings.rows), "black"))

  def draw_text(self):
    if self.settings.preset:
      for k,v in Hawks.PRESETS[self.settings.preset].iteritems():
        setattr(self, k, v)

    image = Image.new("RGB", (self.settings.cols, self.settings.rows), self.settings.bgcolor)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(self.settings.font, self.settings.textsize)

    (x, y) = (self.settings.x, self.settings.y)

    for dx in range(0 - self.settings.thickness, self.settings.thickness + 1):
      for dy in range(0 - self.settings.thickness, self.settings.thickness + 1):
        draw.text((x-dx, y-dy), self.settings.text, fill=self.settings.outercolor, font=font)
        draw.text((x+dx, y-dy), self.settings.text, fill=self.settings.outercolor, font=font)
        draw.text((x-dx, y+dy), self.settings.text, fill=self.settings.outercolor, font=font)
        draw.text((x+dx, y+dy), self.settings.text, fill=self.settings.outercolor, font=font)

    draw.text((x, y), self.settings.text, fill=self.settings.innercolor, font=font)

    self.set_image(image)

def main():
  h = Hawks()
  h.debug = True
  h.draw_text()

if __name__ == '__main__':
  main()

