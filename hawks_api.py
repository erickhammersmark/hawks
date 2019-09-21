#!/usr/bin/env python3

import api_server
import http.server
import json
import os

def run_api(ip, port, hawks):
  api = api_server.Api(prefix="/api")

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
    body = """
Hawks API usage:
  /api/get                Return current settings
  /api/get/presets/foo    Return a list of presets (last argument must be present and is ignored)
  /api/set/key/value      Modify a current setting

Settings:
  disc                    Display is a 255-element DotStar disc
  big                     Display is a chain of two 64x32 RGB LED matrices arranged to form a big square
  mock_square             Display is a terminal mock up of an RGB LED matrix
  file                    Image file to display (or "none")
  text                    Text to render (if file is "none")
  bgcolor                 Background color when rendering text
  innercolor              Inner color of rendered text
  outercolor              Outer color to use when rendering text
  font                    Font to use when rendering text
  y                       y position of rendered text (if autosize is false)
  x                       x position of rendered text (if autosize is false)
  autosize                When rendering text, automatically size the text to fit the display
  textsize                Size of rendered text (if autosize is false)
  margin                  Empty space to leave at bgcolor when autosizing text
  thickness               The thickness of the outercolor of rendered text
  animation               "none" or "waving"
  fps                     How many frames per second of animation to render
  period                  An input to the waving animation
  amplitude               An input to the waving animation

{0}
""".format(msg)
    return req.send(200, body=body)

  def write_file(name, body, hawks):
    with open(os.path.join(hawks.settings.file_path, name), 'wb') as FILE:
      FILE.write(body)

  def api_get(req):
    parts = req.parts[2:]
    if not parts:
      return req.send(200, body=json.dumps(hawks.settings.__dict__))
    if parts[0] == "presets":
      return req.send(200, body=json.dumps(list(hawks.PRESETS.keys())))
    if parts[0] == "image":
      return req.send(200, body=hawks.get_image(), content_type="image/png")
    return usage(req)

  def api_set(req):
    parts = dict(tups(req.parts[2:]))
    for key,value in parts.items():
      if key == "file_path":
        continue
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
        else:
          value = value
        hawks.settings.set(key, value)
      else:
        return req.send(404, body="Unknown attribute: {0}".format(key))
    hawks.draw_text()
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
    else:
      return usage(req, msg=="Unknown command: {0}".format(parts[0]))

  def api_put(req):
    parts = list(map(str.lower, req.path.strip('/').split('/')))

    if not parts or len(parts) < 4:
      return usage(req, msg="PUT request must use path /api/put/file/filename")

    api, action, _file, target = parts[0:4]

    if api != "api" or action != "put" or _file != "file":
      return usage(req, msg="PUT request must use path /api/put/file/filename")

    cl = ci_dict_get(req.headers, 'Content-Length')
    if not cl:
      return req.send(400, body="POST body required")
    body = req.rfile.read(int(cl))
    write_file(target, body, hawks)
    req.send(200)
    

  api.register_endpoint("default", usage)
  api.register_endpoint("/get", api_get)
  api.register_endpoint("/set", api_set)
  api.register_endpoint("/do", api_do)
  api.register_endpoint("/put", api_put)
  api.run(ip, port)
