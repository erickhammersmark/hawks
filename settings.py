#!/usr/bin/env python3

from base import Base
from copy import deepcopy

class Settings(Base):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.helptext = {}
        self.choices = {}
        self.categories = {}
        self.tags = {}
        self.config_file = ".hawks.json"
        self.configs = {}
        self.read_only = set(["configs"])
        self.internal = set(["helptext", "choices", "internal", "categories", "config_file", "tags", "read_only"])

        for k, v in kwargs.items():
            self.set(k, v)

    def dump(self):
        conf = {}
        for k, v in self:
            conf[k] = {}
            conf[k]["value"] = v
            conf[k]["helptext"] = self.helptext.get(k, "")
            conf[k]["choices"] = self.choices.get(k, [])
            conf[k]["categories"] = self.categories.get(k, [])
            conf[k]["tags"] = self.tags.get(k, [])
        return conf

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
        _config = deepcopy(dict(filter(self.nondefault, dict(self).items())))
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
        return name in self.__dict__

    def set(self, name, value, helptext=None, choices=None, categories=None, tags=None, read_only=False):
        if helptext is not None:
            self.helptext[name] = helptext
        if choices is not None:
            self.choices[name] = choices
        if categories is not None:
            self.categories[name] = categories
        if tags is not None:
            self.tags[name] = tags
        if read_only:
            self.read_only.add(name)

        existing = self.get(name)
        if type(existing) == int:
            try:
                value = int(value)
            except:
                pass
        elif type(existing) == float:
            try:
                value = float(value)
            except:
                pass
        setattr(self, name, value)

    def list(self):
        return [
            (name, getattr(self, name))
            for name in self.__dict__
            if name not in self.internal
        ]

    def __iter__(self):
        return iter(self.list())

    def get(self, name, default=None):
        if hasattr(self, name):
            return getattr(self, name)
        return default

    def list_categories(self):
        cats = set()
        for vals in self.categories.values():
            cats.update(set(vals))
        cats = list(cats)
        cats.sort(key=lambda x: {"matrix": 0, "misc": 1, "file": 2, "slideshow": 3, "text": 4}.get(x, 4))
        return cats

    def all_from_category(self, category):
        return (kv for kv in self.list() if category in self.categories.get(kv[0], []))

    def get_tags(self, name):
        return self.tags.get(name, [])


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
#!/usr/bin/env python3

import json
from base import Base

class HawksConfig(Base):
    def __init__(self, filename):
        self.filename = filename
        self.config = {"urls": [], "saved": {}}
        super().__init__()

