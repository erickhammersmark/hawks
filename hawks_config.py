#!/usr/bin/env python3

import json
from base import Base

class HawksConfig(Base):
    def __init__(self, filename):
        self.filename = filename
        self.config = {"urls": [], "saved": {}}
        super().__init__()

    def load(self):
        try:
            with open(self.filename, "r") as CONFIG:
                self.config = json.load(CONFIG)
        except Exception as e:
            self.db("Unable to load config: {}".format(e))
        return self.config

    def save(self):
        try:
            with open(self.filename, "w") as CONFIG:
                json.dump(self.config, CONFIG)
        except Exception as e:
            self.db("Unable to save config: {}".format(e))

