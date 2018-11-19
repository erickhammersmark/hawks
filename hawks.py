#!/usr/bin/env python

import math
import os
import sys
import time
from PIL import Image, ImageDraw, ImageFont
from threading import Timer

def running_on_pi():
  return os.uname()[1] == 'raspberrypi'

if running_on_pi():
  from rgbmatrix import RGBMatrix, RGBMatrixOptions
else:
  from mock import RGBMatrix, RGBMatrixOptions

class Settings(object):
  def __init__(self, *args, **kwargs):
    for k,v in kwargs.iteritems():
      self.set(k, v)

  def __contains__(self, name):
    return name in self.__dict__

  def set(self, name, value):
    setattr(self, name, value)

  def get(self, name):
    if name in self.__dict__:
      return self.__dict__[name]
    return None


class HawksSettings(Settings):
  def __init__(self):
    self.set("bgcolor", "blue")
    self.set("outercolor", "black")
    self.set("innercolor", "green")
    self.set("font", "FreeSansBold")
    self.set("x", 0)
    self.set("y", 2)
    self.set("rows", 32)
    self.set("cols", 32)
    self.set("text", "12")
    self.set("textsize", 27)
    self.set("thickness", 1)
    self.set("preset", "none")
    self.set("animation", "")
    self.set("amplitude", 0.4)
    self.set("fps", 16)
    self.set("period", 2000)


class AnimState(Settings):
  def __init__(self):
    self.set("animation", None)
    self.set("start_time", None)
    self.set("period", None)
    self.set("next_updat_time", None)


class Hawks(object):
  PRESETS = {
      "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
      "bright": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
      "blue_on_green": {"bgcolor": "green", "innercolor": "blue", "outercolor": "black"},
      "none": {},
  }

  ANIMATIONS = [ "waving" ]

  def __init__(self, *args, **kwargs):
    self.settings = HawksSettings()
    self.port = 1212
    self.debug = False
    self.timer = None

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
    self.image = image
    if self.settings.animation == "waving":
      self.waving_start()
    else:
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

  def init_anim_frames(self):
    self.anim_state.frames = [self.image.copy() for n in range(0, self.anim_state.fps)]

  def shift_column(self, image, column, delta):
    if delta == 0:
      return image
    if delta > 0:
      # positive == up
      # from 0 to rows-delta, pull from row+delta.
      # from rows-delta to rows-1, black
      for n in range(0, self.settings.rows - delta):
        image.putpixel((column, n), image.getpixel((column, n + delta)))
      for n in range(self.settings.rows - delta, self.settings.rows):
        image.putpixel((column, n), (0, 0, 0))
    else:
      # negative == down
      # make delta positive
      # from rows-1 to delta, pull from row-delta
      # from delta to 0, black
      delta = 0 - delta
      for n in range(self.settings.rows - 1, delta, -1):
        image.putpixel((column, n), image.getpixel((column, n - delta)))
      for n in range(0, delta):
        image.putpixel((column, n), (0, 0, 0))

  def waving_setup(self):
    if self.timer:
      self.timer.cancel()
    self.init_anim_frames()
    self.anim_state.set("ms_per_frame", self.settings.period / self.anim_state.fps)
    wavelength_radians = math.pi * 2.0
    phase_step_per_frame = wavelength_radians / self.anim_state.fps
    radians_per_pixel = wavelength_radians / self.settings.cols
    phase = 0.0
    amplitude = self.settings.amplitude
    for n in range(0, self.anim_state.fps):
      for c in range(0, self.settings.cols):
        radians = radians_per_pixel * c + phase
        delta_y = int(round((math.sin(radians) * amplitude) / radians_per_pixel)) # assumes rows == cols!
        self.shift_column(self.anim_state.frames[n], c, delta_y)
      phase -= phase_step_per_frame
    self.anim_state.set("frame_no", 0)

  def waving_do(self):
    print("waving_do at {0}".format(time.time()))
    if self.settings.animation == "waving" and time.time()*1000 >= self.anim_state.next_update_time:
      print("waving_do {0} is later than {1}".format(time.time()*1000, self.anim_state.next_update_time))
      self.anim_state.next_update_time += self.anim_state.ms_per_frame
      self.matrix.SetImage(self.anim_state.frames[self.anim_state.frame_no])
      self.anim_state.frame_no += 1
      if self.anim_state.frame_no >= len(self.anim_state.frames):
        self.anim_state.frame_no = 0
      print("setting timer for {0} seconds".format(self.anim_state.ms_per_frame / 1000.0))
      if self.timer:
        self.timer.cancel()
      self.timer = Timer(self.anim_state.ms_per_frame / 1000.0, self.waving_do)
      self.timer.start()

  def waving_start(self):
    setattr(self, "anim_state", AnimState())
    self.anim_state.set("start_time", time.time()*1000)
    self.anim_state.set("next_update_time", self.anim_state.start_time)
    self.anim_state.set("fps", self.settings.fps)
    self.waving_setup()
    self.waving_do()

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

