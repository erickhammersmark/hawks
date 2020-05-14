#!/usr/bin/env python3

import disc
import io
import json
import math
import os
import requests
import sample
import sys
import time
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont, ImageColor, GifImagePlugin
from sign import MatrixController, TextImageController, FileImageController, GifFileImageController, NetworkWeatherImageController
from threading import Timer
from urllib.parse import unquote

try:
  from rgbmatrix import RGBMatrix, RGBMatrixOptions
except ImportError:
  from mock import RGBMatrix, RGBMatrixOptions

class Settings(object):
  def __init__(self, *args, **kwargs):
    self.helptext = {}
    for k,v in kwargs.items():
      self.set(k, v)

  def __contains__(self, name):
    return name in self.__dict__

  def set(self, name, value, helptext=None):
    if helptext:
      self.helptext[name] = helptext
    existing = self.get(name)
    if type(existing) == int:
      try:
        value = int(value)
      except:
        pass
    elif type(existing) == float:
      try:
        value = float(value)
      except:
        pass
    setattr(self, name, value)

  def get(self, name):
    if name in self.__dict__:
      return self.__dict__[name]
    return None

DEBUG = False
def db(*args):
  if DEBUG:
    sys.stderr.write(' '.join([str(arg) for arg in args]) + '\n')


class HawksSettings(Settings):
  def __init__(self):
    super().__init__(self)
    self.controller = None
    self.set("bgcolor", "blue", helptext="Background color when rendering text")
    self.set("outercolor", "black", helptext="Outer color of rendered text")
    self.set("innercolor", "green", helptext="Inner color of rendered text")
    self.set("font", "FreeSansBold", helptext="Font to use when rendering text")
    self.set("x", 0)
    self.set("y", 0)
    self.set("rows", 32, helptext="Image height")
    self.set("cols", 32, helptext="Image width")
    self.set("decompose", False, helptext="Display is a chain of two 64x32 RGB LED matrices arranged to form a big square")
    self.set("text", "12", helptext="Text to render (if filename is \"none\")")
    self.set("textsize", 27)
    self.set("thickness", 1, helptext="Thickness of outercolor border around text")
    self.set("animation", "none", helptext="Options are \"waving\" or \"none\"")
    self.set("amplitude", 0.4, helptext="Amplitude of waving animation")
    self.set("fps", 16, helptext="FPS of waving animation")
    self.set("period", 2000, helptext="Period of waving animation")
    self.set("filename", "none", helptext="Image file to display (or \"none\")")
    self.set("autosize", True)
    self.set("margin", 2, helptext="Margin of background color around text")
    self.set("brightness", 255, helptext="Image brighness, full bright = 255")
    self.set("disc", False, helptext="Display is a 255-element DotStar disc")
    self.set("transpose", "none", helptext="PIL transpose operations are supported")
    self.set("rotate", 0, helptext="Rotation in degrees")
    self.set("mock", False, helptext="Display is mock rgbmatrix")
    self.set("mode", "text", helptext="Valid modes are 'text', 'file', and 'network_weather'")

  def set(self, name, value, **kwargs):
    super().set(name, value, **kwargs)
    if self.controller:
      self.controller.set(name, self.get(name))

  def render(self, names):
    """
    Renders the named stats only
    """

    return dict((name, self.get(name)) for name in names)


class Hawks(object):
  """
  A shim layer providing the old library's interface but implemented with the new library.
  """

  PRESETS = {
      "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
      "bright": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
      "blue_on_green": {"bgcolor": "green", "innercolor": "blue", "outercolor": "black"},
      "green_on_blue": {"bgcolor": "blue", "innercolor": "green", "outercolor": "black"},
      "christmas": {"bgcolor": "green", "innercolor": "red", "outercolor": "black", "text": "12", "textsize": 27, "x": 0, "y": 2, "animation": "none", "thickness": 1},
      "none": {},
  }

  ANIMATIONS = [ "waving" ]

  def __init__(self, *args, **kwargs):
    self.settings = HawksSettings()
    self.port = 1212
    self.debug = False
    self.timer = None
    self.dots = None
    self.gif = None

    preset = None

    for k,v in kwargs.items():
      if k in self.settings:
        self.settings.set(k, v)
      elif k == "preset":
        preset = v
      else:
        setattr(self, k, v)

    self.ctrl = MatrixController(**self.settings.render(MatrixController.settings))
    self.settings.controller = self.ctrl

    if preset:
      self.apply_preset(preset)

  def apply_preset(self, preset):
    if preset in Hawks.PRESETS:
      for k,v in Hawks.PRESETS[preset].items():
        self.settings.set(k, v)
      self.draw_text()
      return True
    return False

  def draw_text(self, return_image=False):
    if self.settings.mode == "file" and self.settings.filename != "none":
      if self.settings.filename.lower().endswith(".gif"):
        self.ctrl.image_controller = GifFileImageController(**self.settings.render(GifFileImageController.settings))
      else:
        self.ctrl.image_controller = FileImageController(**self.settings.render(FileImageController.settings))
    elif self.settings.mode == "network_weather":
        self.ctrl.image_controller = NetworkWeatherImageController(**self.settings.render(NetworkWeatherImageController.settings))
    else:
      self.ctrl.image_controller = TextImageController(**self.settings.render(TextImageController.settings))
      
    return self.ctrl.show(return_image=return_image)


def main():
  h = Hawks()
  h.debug = True
  h.settings.decompose = True
  if len(sys.argv) > 1:
    h.settings.filename = sys.argv[1]
  h.draw_text()

if __name__ == '__main__':
  main()

