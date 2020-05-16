#!/usr/bin/env python3

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
