#!/usr/bin/env python3

import http.server
import json
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
    """
  Create an Api instance with Api(prefix="/whatever"), defaults to "/api/v1".

  This class is opinionated about slashes.  The api prefix will not end with
  one.  The endpoint paths will start with one.  You can do it right or the
  code will make it right, but it WILL be right.  "default" is special-cased, it
  will be used if no other path matches the request.  NB: "default" is distinct
  from "/default".  I am not stealing any paths from you.

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
  """

    def __init__(self, *args, **kwargs):
        self.prefix = "/api/v1"
        self.endpoints = {}
        self.special_paths = ["default"]
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.prefix = self.prefix.rstrip("/")

    def register_endpoint(self, path, callback, methods=["GET"]):
        if not path or not callback:
            raise Exception("register_endpoint(path, callback)")

        if not path.startswith("/") and path not in self.special_paths:
            path = "/" + path

        self.endpoints[path] = {
            "path": path,
            "callback": callback,
            "methods": copy(methods),
        }

    def request_match(self, req):
        if not req.path.startswith(self.prefix):
            return req.send(
                404,
                body="Unrecognized path: {0}. Requests must start with {1}\n".format(
                    req.path, self.prefix
                ),
            )
        path = req.path.replace(self.prefix, "")
        paths = list(self.endpoints.keys())
        paths.sort(key=len)
        paths.reverse()
        for _p in paths:
            if path.startswith(_p):
                return self.endpoints[_p]
        return self.endpoints.get("default", None)

    class RequestHandler(http.server.BaseHTTPRequestHandler):
        def send(self, code, body=None, content_type="text/html"):
            self.send_response(code)
            if body:
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", len(body))
            self.end_headers()
            if body:
                if content_type.startswith("text"):
                    self.wfile.write(body.encode("utf-8"))
                else:
                    self.wfile.write(body)

        def reply(self, message):
            """
      Respond with 200 OK + your message as the text/html body of the response.
      Use send() to send a different response code or content-type.
      """
            self.send(200, body=message)

        def do_POST(self):
            if "Content-Length" in self.headers:
                self.data = self.rfile.read(int(self.headers["Content-Length"]))
            return self.do_ANY()

        def do_GET(self):
            return self.do_ANY()

        def do_ANY(self):
            self.parts = list(self.path.strip("/").split("/"))
            endpoint = self.api.request_match(self)
            if endpoint:
                return endpoint["callback"](self)
            else:
                return self.send(
                    404, body="Unrecognized request: {0}\n".format(self.path)
                )

    def run(self, ip, port):
        api = self

        class ApiRequestHandler(Api.RequestHandler):
            def __init__(self, *a, **kw):
                self.api = api
                Api.RequestHandler.__init__(self, *a, **kw)

        http.server.HTTPServer((ip, port), ApiRequestHandler).serve_forever()


if __name__ == "__main__":
    unittest.main()
