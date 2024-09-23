#!/usr/bin/env python3

from base import Base
from copy import deepcopy

class Settings(Base):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.helptext = {}
        self.choices = {}
        self.hooks = {}
        self.categories = {}
        self.config_file = ".hawks.json"
        self.configs = {}
        self.internal = set(["helptext", "choices", "internal", "hooks", "categories", "config_file"])

        for k, v in kwargs.items():
            self.set(k, v)

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

    def set(self, name, value, helptext=None, choices=None, hooks=None, category=None):
        if helptext is not None:
            self.helptext[name] = helptext
        if choices is not None:
            self.choices[name] = choices
        if hooks is not None:
            self.hooks[name] = hooks
        if category is not None:
            self.categories[name] = category

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
        if name in self.hooks:
            for hook in self.hooks[name]:
                hook(name, value)

    def list(self):
        return [
            (name, getattr(self, name))
            for name in self.__dict__
            if name not in self.internal
        ]

    def __iter__(self):
        return iter(self.list())

    def get(self, name):
        if hasattr(self, name):
            return getattr(self, name)
        return None

    def list_categories(self):
        cats = list(set(self.categories.values()))
        cats.sort(key=lambda x: {"matrix": 0, "misc": 1, "file": 2, "text": 3}.get(x, 4))
        return cats

    def all_from_category(self, category):
        return (kv for kv in self.list() if self.categories.get(kv[0], None) == category)


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

