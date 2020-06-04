#!/usr/bin/env python3


class SettingsIterator(object):
    def __init__(self, settings):
        self.kvs = settings.list()
        self.pointer = 0

    def __next__(self):
        if self.pointer >= len(self.kvs):
            raise StopIteration
        result = self.kvs[self.pointer]
        self.pointer += 1
        return result


class Settings(object):
    def __init__(self, *args, **kwargs):
        self.helptext = {}
        self.choices = {}
        self.internal = set(["helptext", "choices", "internal"])

        for k, v in kwargs.items():
            self.set(k, v)

    def __contains__(self, name):
        return name in self.__dict__

    def set(self, name, value, helptext=None, choices=None):
        if helptext:
            self.helptext[name] = helptext
        if choices:
            self.choices[name] = choices

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
        return SettingsIterator(self)

    def get(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        return None


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
>>>>>>> overhaul
