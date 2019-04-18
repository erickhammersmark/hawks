#!/usr/bin/env python

import api_server
import BaseHTTPServer
import json

def run_api(ip, port, hawks):
  api = api_server.Api(prefix="/api")

  def tups(parts):
    return ((parts[2*n], parts[2*n+1]) for n in range(0, len(parts)/2))

  def ci_dict_get(dictionary, key):
    if key in dictionary:
      return dictionary.get(key)
    for d_key in dictionary:
      if key.lower() == d_key.lower():
        return dictionary.get(d_key)
    return None

  def api_get(req, parts):
    if not parts:
      return req.send(200, body=json.dumps(hawks.settings.__dict__))
    if parts[0] == "presets":
      return req.send(200, body=json.dumps(hawks.PRESETS.keys()))
    if parts[0] == "image":
      return self.send(200, body=hawks.get_image(), content_type="image/png")
    return req.send(404)

  def api_set(req, parts):
    for key,value in parts.iteritems():
      _val = hawks.settings.get(key)
      if _val is not None:
        if type(_val) is float:
          value = float(value)
        elif type(_val) is int:
          value = int(value)
        else:
          value = value
        hawks.settings.set(key, value)
      else:
        return req.send(404, body="Unknown attribute: {0}".format(key))
    hawks.draw_text()
    return req.send(200)

  def api_do(req, parts):
    if not parts:
      return req.send(400, body="API action 'do' requires at least one command and argument")
    if parts[0] == "preset":
      if parts[1]:
        if hawks.apply_preset(parts[1]):
          return req.send(200)
        return req.send(400, body="Unknown preset: {0}".format(parts[1]))
      else:
        return req.send(400, body="Path must have non-zero, even number of elements")
    else:
      return req.send(404, body="Unknown command: {0}".format(parts[0]))

  def do_GET(req):
    parts = map(str.lower, req.path.strip('/').split('/'))
    if not parts or len(parts) % 2 != 0:
      return req.send(400, body="Path must have non-zero, even number of elements")

    api, action = parts[0:2]

    if api != 'api' or action not in ["get", "set", "do"]:
      return req.send(404, body="Unrecognized path: " + req.path)

    if action == 'set':
      settings = dict(tups(parts[2:]))
      return api_set(req, settings)
    elif action == 'get':
      return api_get(req, parts[2:])
    elif action == 'do':
      return api_do(req, parts[2:])

  def do_POST(req):
    parts = map(str.lower, req.path.strip('/').split('/'))

    if not parts or len(parts) != 2:
      return req.send(404, body="Path {0} not found".format(req.path))

    cl = ci_dict_get(req.headers, 'Content-Length')
    if not cl:
      return req.send(400, body="POST body required")
    body = req.rfile.read(int(cl))

    try:
      settings = json.loads(body)
    except Exception as e:
      return req.send(400, body="Unable to decode POST body:  {0}".format(e))

    if type(settings) != dict:
      return req.send(400, body="JSON body must contain only a map of key, value pairs")

    return api_set(settings)

  api.register_endpoint("/get", do_GET)
  api.register_endpoint("/set", do_GET)
  api.register_endpoint("/do", do_GET)
  api.run(ip, port)
