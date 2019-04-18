#!/usr/bin/env python

import BaseHTTPServer
import unittest
from copy import copy

class ApiTest(unittest.TestCase):
  def testRegister(self):
    api = Api()
    def foo_callback(bar):
      print(bar)
    api.register_endpoint("/foo", foo_callback)
    self.assertTrue("/foo" in api.endpoints)
    self.assertTrue(api.endpoints["/foo"]["callback"] is foo_callback)

class Api(object):
  '''
  Create an Api instance with Api(prefix="/whatever"), defaults to "/api/v1".

  This class is opinionated about slashes.  The api prefix will not end with
  one.  The endpoint paths will start with one.  You can do it right or the
  code will make it right, but it WILL be right.

  Call Api.register_endpoint(path, callback)
  Optionally, add methods=["GET", "POST", "DUCK"] to register_endpoint()
  Start serving with Api.run(ip, port)

  Your callback will get one argument, a ApiRequestHandler object, a child of
  BaseHTTPRequestHandler.  It has attributes like 'address_string', 'api',
  'client_address', 'close_connection', 'command', 'connection', 'date_time_string',
  'default_request_version', 'disable_nagle_algorithm', 'end_headers',
  'error_content_type', 'error_message_format', 'finish', 'handle',
  'handle_one_request', 'headers', 'log_date_time_string', 'log_error', 'log_message',
  'log_request', 'monthname', 'parse_request', 'path', 'protocol_version',
  'raw_requestline', 'rbufsize', 'request', 'request_version', 'requestline',
  'responses', 'rfile', 'send', 'send_error', 'send_header', 'send_response',
  'server', 'server_version', 'setup', 'sys_version', 'timeout', 'version_string',
  'wbufsize', 'weekdayname', and 'wfile'.
  '''

  def __init__(self, *args, **kwargs):
    self.prefix = "/api/v1"
    self.endpoints = {}
    for k, v in kwargs.iteritems():
      setattr(self, k, v)
    self.prefix = self.prefix.rstrip("/")

  def register_endpoint(self, path, callback, methods=["GET"]):
    if not path or not callback:
      raise Exception("register_endpoint(path, callback)")

    if not path.startswith("/"):
      path = "/" + path

    self.endpoints[path] = {
      "path": path,
      "callback": callback,
      "methods": copy(methods),
    }

  def request_match(self, req):
    if not req.path.startswith(self.prefix):
      return req.send(404, body="Unrecognized path: {0}".format(req.path))
    path = req.path.replace(self.prefix, "")
    paths = self.endpoints.keys()
    paths.sort(lambda x, y: cmp(len(y), len(x)))
    for _p in paths:
      if path.startswith(_p):
        return self.endpoints[_p]
      print("path {0} does not start with endpoint path {1}".format(path, _p))
    return None

  class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def send(self, code, body=None, content_type="text/html"):
      self.send_response(code)
      if body:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
      self.end_headers()
      if body:
        self.wfile.write(body)

    def reply(self, message):
      '''
      Respond with 200 OK + your message as the text/html body of the response.
      Use send() to send a different response code or content-type.
      '''
      self.send(200, body=message)

    def do_GET(self):
      return self.do_ANY()

    def do_ANY(self):
      print(self, dir(self))
      endpoint = self.api.request_match(self)
      if endpoint:
        return endpoint["callback"](self)
      else:
        return self.send(404, body="Unrecognized request: {0}".format(self.path))

  def run(self, ip, port):
    api = self
    class ApiRequestHandler(Api.RequestHandler):
      def __init__(self, *a, **kw):
        self.api =  api
        Api.RequestHandler.__init__(self, *a, **kw)
    BaseHTTPServer.HTTPServer((ip, port), ApiRequestHandler).serve_forever()

if __name__ == '__main__':
  unittest.main()
