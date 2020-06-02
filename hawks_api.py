#!/usr/bin/env python3

import api_server
import http.server
import json
import os

from urllib.parse import unquote

def run_api(ip, port, hawks):
  api = api_server.Api(prefix="/")

  def tups(parts):
    return ((parts[2*n], parts[2*n+1]) for n in range(0, int(len(parts)/2)))

  def ci_dict_get(dictionary, key):
    if key in dictionary:
      return dictionary.get(key)
    for d_key in dictionary:
      if key.lower() == d_key.lower():
        return dictionary.get(d_key)
    return None

  def usage(req, msg=""):
    settings_help = "\n".join(["  {0}{1}{2}".format(k, " " * (24 - len(k)), v) for k, v in hawks.settings])
    body = """
Hawks API usage:
  /api/get                Return current settings
  /api/get/settings       Return current settings
  /api/get/setting/key    Return the value of one setting (404 on error)
  /api/get/key            Return the value of one setting (200 w/usage on error)
  /api/get/presets        Return a list of presets
  /api/set/key/value      Modify a current setting. /key/value can be repeated.
  /api/do/image           Returns a PNG of the current image
  /api/do/preset/name     Apply the named preset

Settings:
{0}

{1}
""".format(settings_help, msg)
    return req.send(200, body=body)

  def api_get(req):
    parts = req.parts[2:]
    if not parts or parts[0] == "settings":
      # GET /api or /api/settings, return a dump of all of the settings
      return req.send(200, body=json.dumps(dict((k,v) for k,v in hawks.settings if k != "hawks")))
    if parts[0] == "presets":
      # GET /api/presets, dump the list of available presets
      return req.send(200, body=json.dumps(list(hawks.PRESETS.keys())))
    if parts[0] == "setting":
      # GET /api/setting/foo, return setting foo or 404 if setting foo does not exist
      # use this instead of GET /api/foo if you want a 404 when you screw up
      if hawks.settings.get(parts[1]):
        return req.send(200, body=json.dumps(hawks.settings.get(parts[1])))
      return req.send(404, body="No such setting {}".format(parts[1]))
    if hawks.settings.get(parts[0]):
      # GET /api/foo, return setting foo if it exists, otherwise, fall through to a 200 from usage()
      # use this when you want the get/set sematics to be the same and you don't care about getting
      # a 404 when you screw up
      return req.send(200, body=json.dumps(hawks.settings.get(parts[0])))
    return usage(req)

  def api_set(req, msg=None):
    parts = dict(tups(req.parts[2:]))
    for key,value in parts.items():
      if key == "filename":
        if not only_alpha(value):
          continue
      if key == "text":
        value = unquote(value)
      _val = hawks.settings.get(key)
      if _val is not None:
        if type(_val) is float:
          try:
            value = float(value)
          except:
            return req.send(400, body="Value for key {0} must be of type float".format(key))
        elif type(_val) is int:
          try:
            value = int(value)
          except:
            return req.send(400, body="Value for key {0} must be of type int".format(key))
        elif type(_val) is bool:
            try:
              value = bool(value)
            except:
              return req.send(400, body="Value for key {0} must be of type bool".format(key))
        else:
          value = value
        hawks.settings.set(key, value, show=False)
      else:
        return req.send(404, body="Unknown attribute: {0}".format(key))
    hawks.show()
    if msg:
      return req.send(200, msg)
    return req.send(200)

  def api_do(req):
    parts = req.parts[2:]
    if not parts:
      return req.send(400, body="API action 'do' requires at least one command and argument")
    if parts[0] == "preset":
      if parts[1]:
        if hawks.apply_preset(parts[1]):
          return req.send(200)
        return req.send(400, body="Unknown preset: {0}".format(parts[1]))
      else:
        return usage(req, msg="Path must have non-zero, even number of elements")
    elif parts[0] == "image":
      return req.send(200, body=hawks.show(return_image=True), content_type="image/png")
    else:
      return usage(req, msg=="Unknown command: {0}".format(parts[0]))

  def only_alpha(name):
    name = unquote(name)
    if name.startswith("/"):
      return False
    if ".." in name:
      return False
    for c in name:
      if c not in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-_/":
        return False
    return True

  def webui_form(req):
    body = "<html><head>Hawks UI</head><body><H1>Hawks UI</H1>"
    body = body + '<form method="get" action="/submit"><table>'
    for setting, value in hawks.settings:
      if setting != "hawks":
        body = body + "<tr><td>{0}</td><td><input name={0} value={1} type=text></input></td></tr>".format(setting, value)
    body = body + "</table><br><input type=submit>"
    body = body + "</form></body></html>"
    req.send(200, body=body)
    
  def webui_submit(req):
    req.parts = ['api', 'set'] 
    parts = req.path.split("?")[1].split("&")
    for part in parts:
      key, value = part.split("=")
      if value in ["True", "true"]:
        value = True
      elif value in ["False", "false"]:
        value = False
      req.parts.extend([key, value])
    return api_set(req, msg="Settings accepted")

  def api_help(req):
    usage(req)

  api.register_endpoint("default", usage)
  api.register_endpoint("/api/get", api_get)
  api.register_endpoint("/api/set", api_set)
  api.register_endpoint("/api/do", api_do)
  api.register_endpoint("/help", api_help)
  api.register_endpoint("/api/help", api_help)
  api.register_endpoint("/", webui_form)
  api.register_endpoint("/submit", webui_submit)
  api.run(ip, port)
