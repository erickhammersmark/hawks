#!/usr/bin/env python3

import os
import time
from urllib.parse import unquote

class Webui(object):
    def __init__(self, hawks, api_set):
        self.hawks = hawks
        self.api_set = api_set

    def webui_form(self, req, message=None):
        if req.command == "POST":
            message = self.webui_submit(req)
        filepath = self.hawks.settings.filepath or "img"
        api_js = f'''
        var update_preview = function(value) {{
            img_tag = document.getElementById("preview")
            img_tag.src="{filepath}/" + value
        }}
        var update_url = function(value) {{
            url_field = document.getElementsByName("url")[0]
            url_field.value = value
            img_tag = document.getElementById("preview")
            img_tag.src = value
        }}
        '''

        try:
            self.hawks.settings.choices["filename"] = [
                #os.path.join(filepath, item) for item in os.listdir(filepath)
                item for item in os.listdir(filepath)
            ]
        except FileNotFoundError:
            self.hawks.settings.choices["filename"] = None

        #self.hawks.settings.set("urls", self.hawks.settings.url, choices=read_urls(self.hawks), show=False)

        body = []
        body.append(f"<html><head><title>Hawks UI</title><script>{api_js}</script></head><body><H1>Hawks UI</H1>")
        if message:
            body.append(f"<h3>{time.asctime()}: {message}</h3>")
        body.append('<form method="post" action="/"><table>')
        body.append('<tr><td></td><td></td><td rowspan=4><img height="64" src="/api/do/image"></img></td></tr>')
        for setting, value in self.hawks.settings:
            if setting == "filename":
                value = unquote(value).replace(f"{filepath}/", "")
            body.append("<tr>")
            if setting in self.hawks.settings.helptext:
                helptext = self.hawks.settings.helptext[setting]
                body.append(f'<td title="{helptext}">')
            else:
                body.append("<td>")
            body.append(f"{setting}</td><td>")
            if setting in self.hawks.settings.choices and self.hawks.settings.choices[setting]:
                choices = self.hawks.settings.choices[setting]
                if setting == "filename":
                    choices.sort()
                    body.append(f'<select name={setting} value={value} size=12 oninput="update_preview(this.value)">')
                    for choice in choices:
                        if choice == value:
                            body.append(f'<option value="{choice}" selected="selected">{choice}</option>')
                        else:
                            body.append(f'<option value="{choice}">{choice}</option>')
                    body.append("</select></td><td rowspan=1><img style=\"max-height: 200px;\" id=\"preview\"</img>")
                elif setting == "urls":
                    choices.sort()
                    body.append(f'<select name={setting} value={value} size=12 oninput="update_url(this.value)">')
                    for choice in choices:
                        if choice == value:
                            body.append(f'<option value="{choice}" selected="selected">{choice}</option>')
                        else:
                            body.append(f'<option value="{choice}">{choice}</option>')
                    body.append("</select></td><td rowspan=1>")
                else:
                    body.append(f"<select name={setting} value={value}>")
                    choices.sort(key=lambda x: x != value)
                    for choice in choices:
                        body.append(f'<option value="{choice}">{choice}</option>')
                    body.append("</select>")
            else:
                if setting == "url":
                    body.append(f'<input name={setting} value="{value}" type=text style="width:100%;box-sizing:border-box;"></input>')
                else:
                    body.append(f"<input name={setting} value=\"{value}\" type=text></input>")
            body.append("</td></tr>")
        body.append("</table><br><input type=submit>")
        body.append("</form></body></html>")
        req.send(200, body="".join(body))

    def webui_submit(self, req):
        req.parts = ["api", "set"]
        filepath = self.hawks.settings.filepath or "img"
        data = req.data.decode()
        for part in data.split("&"):
            key, value = part.split("=")
            #if value in ["True", "true"]:
            #    value = True
            #elif value in ["False", "false"]:
            #    value = False
            if key == "filename":
                value = f"{filepath}/{value}"
            req.parts.extend([key, value])
        code, message = self.api_set(req, msg="Settings accepted", respond=False)
        return message

