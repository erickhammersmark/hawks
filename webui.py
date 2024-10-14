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

        var add_category_hiders = function(value) {{
            var adv_checkbox = document.getElementById("advanced");
            var categories = document.getElementsByClassName("category");
            for (let c = 0; c < categories.length; c++) {{
                window.l.categories[categories[c].title] = true;
            }}
            for (let n = 0; n < categories.length; n++) {{

                let settings_toggler = function() {{
                    let cat_title = categories[n].title;
                    if (window.l.categories[cat_title] == false) {{
                        window.l.categories[cat_title] = true;
                    }} else {{
                        window.l.categories[cat_title] = false;
                    }}
                    let settings = document.getElementsByClassName(cat_title);
                    for (let s = 0; s < settings.length; s++) {{
                        if (window.l.categories[cat_title] == true) {{
                            if (settings[s].classList.contains("advanced")) {{
                                if (adv_checkbox.checked) {{
                                    settings[s].style.display = 'table-row';
                                }} else {{
                                    settings[s].style.display = 'none';
                                }}
                            }} else {{ 
                                settings[s].style.display = 'table-row';
                            }}
                        }} else {{
                            settings[s].style.display = 'none';
                        }}
                    }}
                }}

                categories[n].addEventListener('click', settings_toggler);
                window.l.togglers[categories[n].title] = settings_toggler;
            }}

            let advanced_toggler = function() {{
                var adv_checkbox = document.getElementById("advanced");
                let settings = document.getElementsByClassName("advanced");
                for (let s = 0; s < settings.length; s++) {{
                    s_cls = settings[s].classList[0];
                    if (window.l.categories[s_cls] == false) {{
                        continue;
                    }}
                    if (adv_checkbox.checked) {{
                        settings[s].style.display = 'table-row';
                    }} else {{
                        settings[s].style.display = 'none';
                    }}
                }}
            }}
            adv_checkbox.addEventListener('change', advanced_toggler);
            if ("{self.hawks.settings.advanced}" == "False") {{
                advanced_toggler();
            }}
        }}

        var one_mode_only = function(mode) {{
            if ("{self.hawks.settings.no_webui_one_mode_only}" == "True") {{
                return;
            }}
            var categories = document.getElementsByClassName("category");
            for (let c = 0; c < categories.length; c++) {{
                if (categories[c].title == "matrix") {{
                    continue;
                }}
                if (categories[c].title == mode) {{
                    if (window.l.categories[categories[c].title] == false) {{
                        window.l.togglers[categories[c].title]();
                    }}
                    continue;
                }}
                if (window.l.categories[categories[c].title] == true) {{
                    window.l.togglers[categories[c].title]();
                }}
            }}
        }}

        var add_hiders = function(value) {{
            window.l = {{ categories: {{ }}, togglers: {{ }} }};
            add_category_hiders();
            one_mode_only("{self.hawks.settings.mode}");
        }}

        window.onload = add_hiders;
        
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
        body.append(f'<tr><td><input label="Advanced" type="checkbox" name="advanced" id="advanced" {"checked" if self.hawks.settings.get("advanced") else ""} />Advanced</td><td></td><td rowspan=4><img height="64" src="/api/do/image"></img></td></tr>')
        categories = self.hawks.settings.list_categories()
        for category in categories:
            body.append(f"<tr class=\"category\" title=\"{category}\"><td><strong>{category} settings</strong></td></tr>")
            cat_settings = list(self.hawks.settings.all_from_category(category))
            cat_settings.sort(key=lambda x: 1 if "advanced" in self.hawks.settings.get_tags(x[0]) else 0)
            for setting, value in cat_settings:
                setting_class = category
                if "advanced" in self.hawks.settings.get_tags(setting):
                    setting_class += " advanced"
                body.append(f"<tr class=\"{setting_class}\">")
                if setting == "filename":
                    value = unquote(value).replace(f"{filepath}/", "")
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
                    elif setting == "mode":
                        body.append(f'<select name={setting} value={value} oninput="one_mode_only(this.value)">')
                        choices.sort(key=lambda x: x != value)
                        for choice in choices:
                            body.append(f'<option value="{choice}">{choice}</option>')
                        body.append("</select>")
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
                body.append("</td>")
                body.append("</tr>")
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
        if "advanced" not in req.parts:
            req.parts.extend(["advanced", False])
        code, message = self.api_set(req, msg="Settings accepted", respond=False)
        return message

