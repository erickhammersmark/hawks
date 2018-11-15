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

    def do_GET(self):
      parts = map(str.lower, self.path.strip('/').split('/'))
      if not parts or len(parts) % 2 != 0:
        return self.send(400, body="Path must have non-zero, even number of elements")

      api, action = parts[0:2]

      if api != 'api' or action not in ["get", "set"]:
        return self.send(404, body="Unrecognized path: self.path")

      if action == 'set':
        for key,value in self.tups(parts[2:]):
          if hasattr(self.hawks, key):
            if type(getattr(self.hawks, key)) is int:
              value = int(value)
            setattr(self.hawks, key, value)
          else:
            return self.send(404, body="Unknown attribute: {0}".format(key))
        hawks.draw_text()
        return self.send(200)
      elif action == 'get':
        settings = {}
        blacklist = ['matrix']
        for k,v in self.hawks.__dict__.iteritems():
          if k not in blacklist:
            settings[k] = v
        return self.send(200, body=json.dumps(settings))

  httpd = BaseHTTPServer.HTTPServer((ip, port), HawksRequestHandler)
  httpd.serve_forever()
