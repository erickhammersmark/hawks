#!/usr/bin/env python3

from base import Base
from copy import deepcopy

class Settings(Base):
    def __init__(self, *args, **kwargs):
        super().__setattr__("S", {}) # this MUST remain the first statement
        super().__init__()
        self.config_file = ".hawks.json"
        self.configs = {}
        self.read_only = set(["configs"])
        self.internal = set(["internal", "config_file", "read_only"])

        for k, v in kwargs.items():
            self.set(k, v)

    def dump(self):
        return self.S

    def apply_dict(self, data):
        for k, v in data.items():
            self.set(k, v)

    def load(self, config_name):
        if name in self.configs:
            self.apply_dict(self.configs[name])

    def nondefault(self, kv):
        if "defaults" not in self.configs:
            return True
        if kv[0] in self.configs["defaults"] and kv[1] != self.configs["defaults"][kv[0]]:
            return True
        return False

    def save(self, config_name):
        _config = deepcopy(dict(filter(self.nondefault, self.S.items())))
        if "configs" in _config:
            del(_config["configs"])
        self.configs[config_name] = _config

    def load_from_file(self):
        try:
            with open(self.config_file, "r") as CONFIG:
                self.apply_dict(json.load(CONFIG))
        except Exception as e:
            self.db("Unable to load config: {}".format(e))
        return self

    def save_to_file(self):
        try:
            with open(self.config_file, "w") as CONFIG:
                json.dump(dict(self), CONFIG)
        except Exception as e:
            self.db("Unable to save config: {}".format(e))

    def __contains__(self, name):
        return name in self.S

    def coerce(self, value, existing_value):
        if type(existing_value) == int:
            try:
                value = int(value)
            except:
                pass
        elif type(existing_value) == float:
            try:
                value = float(value)
            except:
                pass
        return value

    def set(self, name, value, helptext=None, choices=None, categories=None, tags=None, read_only=False):
        existing_setting = self.S.get(name, {})
        if existing_setting:
            value = self.coerce(value, existing_setting["value"])

        self.S[name] = {
            "value": value,
            "helptext": helptext or existing_setting.get("helptext", ""),
            "choices": choices or existing_setting.get("choices", []),
            "categories": categories or existing_setting.get("categories", []),
            "tags": tags or existing_setting.get("tags", []),
            "read_only": read_only,
        }

    def list(self):
        return [(k, s["value"]) for k, s in self.S.items() if k not in self.internal]

    def __iter__(self):
        return iter(self.list())

    def get(self, name, default=None):
        return self.S.get(name, {}).get("value", default)

    def get_tags(self, name):
        return self.S.get(name, {}).get("tags", [])

    def get_helptext(self, name, default=""):
        return self.S.get(name, {}).get("helptext", default)

    def get_choices(self, name, default=[]):
        return self.S.get(name, {}).get("choices", default)

    def set_choices(self, name, value):
        self.S.get(name, {})["choices"] = value

    def add_choice(self, name, value):
        if name not in self.S:
            return
        if type(self.S[name]["choices"]) != list:
            self.S[name]["choices"] = []
        self.S[name]["choices"].append(value)

    def list_categories(self):
        cats = set()
        for name, setting in self.S.items():
            if "categories" in setting:
                cats.update(set(setting["categories"]))
        cats = list(cats)
        # why are we doing webui's work in settings?
        cats.sort(key=lambda x: {"matrix": 0, "misc": 1, "file": 2, "slideshow": 3, "text": 4}.get(x, 4))
        return cats

    def all_from_category(self, category):
        return ((k, s["value"]) for k, s in self.S.items() if category in s["categories"])

    def __getattr__(self, name, default=None):
        """
        self.__getattr__ only gets called when self.__getattribute__ doesn't find the attribute
        which is perfect, because this is just intended as an access method for self.S[name]["value"]

        NB: it is _very important_ that super().__setattr__("S", {}) remains
        the very first statement in Settings.__init__.
        """
        if name in self.S:
            return self.S[name]["value"]
        try:
            return self.__getattribute__(name)
        except AttributeError:
            pass
        return default

    def __setattr__(self, name, value):
        """
        self.__setattr__ is called every time any attribute is set
        on this object. If this isn't in self.S, call super().__setattr__.
        Do not use dot-notation attribute assignment to create a new
        setting, it will not work.

        NB: it is _very important_ that super().__setattr__("S", {}) remains
        the very first statement in Settings.__init__.
        """
        if name in self.S:
            self.S[name]["value"] = self.coerce(value, self.S[name]["value"])
        else:
            super().__setattr__(name, value)


if __name__ == "__main__":
    s = Settings()
    s.set("foo", 27, helptext="twentyseven", choices=[27, 42, 69])
    s.set(
        "bar",
        "The Horrible Revelation",
        helptext="place for booze",
        choices=["The Horrible Revelation", "Cheers"],
    )

    for name in s:
        print(name)
        # print(name, getattr(s, name))
