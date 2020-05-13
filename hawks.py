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
    self.set("bgcolor", "blue", helptext="Background color when rendering text")
    self.set("outercolor", "black", helptext="Outer color of rendered text")
    self.set("innercolor", "green", helptext="Inner color of rendered text")
    self.set("font", "FreeSansBold", helptext="Font to use when rendering text")
    self.set("x", 0)
    self.set("y", 0)
    self.set("rows", 32, helptext="Image height")
    self.set("cols", 32, helptext="Image width")
    self.set("decompose", False, helptext="Display is a chain of two 64x32 RGB LED matrices arranged to form a big square")
    self.set("text", "12", helptext="Text to render (if file is \"none\")")
    self.set("textsize", 27)
    self.set("thickness", 1, helptext="Thickness of outercolor border around text")
    self.set("animation", "none", helptext="Options are \"waving\" or \"none\"")
    self.set("amplitude", 0.4, helptext="Amplitude of waving animation")
    self.set("fps", 16, helptext="FPS of waving animation")
    self.set("period", 2000, helptext="Period of waving animation")
    self.set("file", "none", helptext="Image file to display (or \"none\")")
    self.set("file_path", "img", helptext="Directory in which to find files")
    self.set("autosize", True)
    self.set("margin", 2, helptext="Margin of background color around text")
    self.set("brightness", 255, helptext="Image brighness, full bright = 255")
    self.set("disc", False, helptext="Display is a 255-element DotStar disc")
    self.set("transpose", "none", helptext="PIL transpose operations are supported")
    self.set("rotate", 0, helptext="Rotation in degrees")
    self.set("mock", False, helptext="Display is mock rgbmatrix")
    self.set("mode", "text", helptext="Valid modes are 'text', 'file', and 'network_weather'")

  def render(self, mode=None):
    """
    Renders the HawksSettings in a format that's appropriate for the
    MatrixController or one of the ImageControllers.
    """

    mode = mode or self.mode

    settings = []
    result = {}

    if mode == "ctrl":
      settings.extend([
        "animation",
        "x",
        "y",
        "rows",
        "cols",
        "decompose",
        "file",
        "file_path",
        "brightness",
        "disc",
        "transpose",
        "rotate",
        "mock",
      ])

    elif mode == "file":
      result["filename"] = os.path.join(self.file_path, self.file)

    elif mode == "text":
      settings.extend([
        "text",
        "textsize",
        "bgcolor",
        "innercolor",
        "outercolor",
        "font",
        "thickness",
        "autosize",
        "margin",
        "x",
        "y",
      ])

    elif mode == "network_weather":
      pass

    result.update(dict((k, self.get(k)) for k in settings))

    return result

class AnimState(Settings):
  def __init__(self):
    self.set("animation", None)
    self.set("start_time", None)
    self.set("period", None)
    self.set("next_update_time", None)
    self.set("frames", None)


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

    self.ctrl = MatrixController(**self.settings.render("ctrl"))

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
    if self.settings.mode == "file" and self.settings.file != "none":
      if self.settings.file.lower().endswith(".gif"):
        #self.ctrl.image_controller = GifFileImageController(self.filename, **self.settings.render("file"))
        self.ctrl.image_controller = GifFileImageController(**self.settings.render("file"))
      else:
        self.ctrl.image_controller = FileImageController(**self.settings.render("file"))
    elif self.settings.mode == "network_weather":
        self.ctrl.image_controller = NetworkWeatherImageController(**self.settings.render("network_weather"))
    else:
      #self.ctrl.image_controller = TextImageController(text=self.text, bgcolor=self.bgcolor, outercolor=self.outercolor, innercolor=self.innercolor)
      self.ctrl.image_controller = TextImageController(**self.settings.render("text"))
      
    return self.ctrl.show(return_image=return_image)


def main():
  h = Hawks()
  h.debug = True
  h.settings.decompose = True
  if len(sys.argv) > 1:
    h.settings.file = sys.argv[1]
  h.draw_text()

if __name__ == '__main__':
  main()

