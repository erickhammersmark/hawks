#!/usr/bin/env python3

import argparse
import time

from sign import MatrixController, TextImageController, FileImageController, GifFileImageController, NetworkWeatherImageController

def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("--rows", type=int, default=32)
  parser.add_argument("--cols", type=int, default=32)
  parser.add_argument("--decompose", action="store_true", help="Include this flag if you have two 64x32 panels arranged as a square")
  parser.add_argument("--mode", default="text", choices=["text", "file"])
  parser.add_argument("--mock", action="store_true")
  text_group = parser.add_argument_group("text")
  text_group.add_argument("--text", default="")
  text_group.add_argument("--bgcolor", default="blue")
  text_group.add_argument("--outercolor", default="black")
  text_group.add_argument("--innercolor", default="white")
  file_group = parser.add_argument_group("file")
  file_group.add_argument("--filename", default="")
  return parser.parse_args()
  
class HawksSign(object):
  def __init__(self, *args, **kwargs):
    self.rows = 0
    self.cols = 0
    self.decompose = False
    self.text = ""
    self.bgcolor = "black"
    self.innercolor = "black"
    self.outercolor = "black"
    self.filename = ""

    for (k, v) in kwargs.items():
      setattr(self, k, v)

    self.ctrl = MatrixController(rows=self.rows, cols=self.cols, decompose=self.decompose, mock=self.mock)
    if self.filename:
      if self.filename.lower().endswith(".gif"):
        self.ctrl.image_controller = GifFileImageController(self.filename)
      else:
        self.ctrl.image_controller = FileImageController(self.filename)
    elif self.text:
      self.ctrl.image_controller = TextImageController(text=self.text, bgcolor=self.bgcolor, outercolor=self.outercolor, innercolor=self.innercolor)

    while True:
      time.sleep(1000)
    
def main():
  args = parse_args()
  hawks = HawksSign(**args.__dict__)
  

if __name__ == "__main__":
  main()
