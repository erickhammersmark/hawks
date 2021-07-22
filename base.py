#!/usr/env/bin python3

import sys

class Base(object):
  def __init__(self):
    self.debug = False

  def db(self, msg):
    if self.debug:
      sys.stderr.write(str(msg) + "\n")
