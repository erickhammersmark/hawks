#!/usr/bin/env python

import BaseHTTPServer
import json

def run_api(ip, port, hawks):
  class HawksRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def __init__(self, *a, **kw):
      self.hawks = hawks
      return BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, *a, **kw)

    def send(self, code, body=None, content_type="text/html"):
        self.send_response(code)
        if body:
          self.send_header('Content-Type', content_type)
          self.send_header('Content-Length', len(body))
        self.end_headers()
        if body:
          self.wfile.write(body)

    def tups(self, parts):
      return ((parts[2*n], parts[2*n+1]) for n in range(0, len(parts)/2))

    def ci_dict_get(self, dictionary, key):
      if key in dictionary:
        return dictionary.get(key)
      for d_key in dictionary:
        if key.lower() == d_key.lower():
          return dictionary.get(d_key)
      return None

    def api_get(self, parts):
      if not parts:
        return self.send(200, body=json.dumps(hawks.settings.__dict__))
      if parts[0] == "presets":
        return self.send(200, body=json.dumps(hawks.PRESETS.keys()))
      return self.send(404)

    def api_set(self, parts):
      for key,value in parts.iteritems():
        _val = hawks.settings.get(key)
        if _val is not None:
          if type(_val) is float:
            value = float(value)
          elif type(_val) is int:
            value = int(value)
          else:
            value = value
          self.hawks.settings.set(key, value)
        else:
          return self.send(404, body="Unknown attribute: {0}".format(key))
      hawks.draw_text()
      return self.send(200)

    def api_do(self, parts):
      if not parts:
        return self.send(400, body="API action 'do' requires at least one command and argument")
      if parts[0] == "preset":
        if parts[1]:
          if hawks.apply_preset(parts[1]):
            return self.send(200)
          return self.send(400, body="Unknown preset: {0}".format(parts[1]))
        else:
          return self.send(400, body="Path must have non-zero, even number of elements")
      else:
        return self.send(404, body="Unknown command: {0}".format(parts[0]))

    def do_GET(self):
      parts = map(str.lower, self.path.strip('/').split('/'))
      if not parts or len(parts) % 2 != 0:
        return self.send(400, body="Path must have non-zero, even number of elements")

      api, action = parts[0:2]

      if api != 'api' or action not in ["get", "set", "do"]:
        return self.send(404, body="Unrecognized path: self.path")

      if action == 'set':
        settings = dict(self.tups(parts[2:]))
        return self.api_set(settings)
      elif action == 'get':
        return self.api_get(parts[2:])
      elif action == 'do':
        return self.api_do(parts[2:])

    def do_POST(self):
      parts = map(str.lower, self.path.strip('/').split('/'))

      if not parts or len(parts) != 2:
        return self.send(404, body="Path {0} not found".format(self.path))

      cl = self.ci_dict_get(self.headers, 'Content-Length')
      if not cl:
        return self.send(400, body="POST body required")
      body = self.rfile.read(int(cl))

      try:
        settings = json.loads(body)
      except Exception as e:
        return self.send(400, body="Unable to decode POST body:  {0}".format(e))

      if type(settings) != dict:
        return self.send(400, body="JSON body must contain only a map of key, value pairs")

      return self.api_set(settings)

  httpd = BaseHTTPServer.HTTPServer((ip, port), HawksRequestHandler)
  httpd.serve_forever()
