#!/usr/bin/env python3

import time
from settings import Settings
from matrixcontroller import MatrixController
from imagecontroller import (
    TextImageController,
    FileImageController,
    NetworkWeatherImageController,
)


class HawksSettings(Settings):
    def __init__(self):
        super().__init__(self)
        self.hawks = None
        self.set("bgcolor", "blue", helptext="Background color when rendering text")
        self.set("outercolor", "black", helptext="Outer color of rendered text")
        self.set("innercolor", "green", helptext="Inner color of rendered text")
        self.set("font", "FreeSansBold", helptext="Font to use when rendering text")
        self.set("x", 0)
        self.set("y", 0)
        self.set("rows", 32, helptext="Image height")
        self.set("cols", 32, helptext="Image width")
        self.set(
            "decompose",
            False,
            helptext="Display is a chain of two 64x32 RGB LED matrices arranged to form a big square",
        )
        self.set("text", "12", helptext='Text to render (if filename is "none")')
        self.set("textsize", 27)
        self.set("thickness", 1, helptext="Thickness of outercolor border around text")
        self.set("animation", "none", helptext='Options are "waving" or "none"')
        self.set("amplitude", 0.4, helptext="Amplitude of waving animation")
        self.set("fps", 16, helptext="FPS of waving animation")
        self.set("period", 2000, helptext="Period of waving animation")
        self.set("filename", "none", helptext='Image file to display (or "none")')
        self.set("autosize", True)
        self.set("margin", 2, helptext="Margin of background color around text")
        self.set("brightness", 255, helptext="Image brighness, full bright = 255")
        self.set("disc", False, helptext="Display is a 255-element DotStar disc")
        self.set("transpose", "none", helptext="PIL transpose operations are supported")
        self.set("rotate", 0, helptext="Rotation in degrees")
        self.set("mock", False, helptext="Display is mock rgbmatrix")
        self.set(
            "mode",
            "text",
            helptext="Valid modes are 'text', 'file', and 'network_weather'",
        )

    def set(self, name, value, show=True, **kwargs):
        """
    Write the value to ourself.
    If we are configured with a reference to a Hawks object, check the settings of its
    MatrixController. If the MatrixController has this setting, write it there, too.
    Some of our settings are intended for ImageControllers, but since ImageControllers are not
    persistent, we have nowhere to write to them at this time.  We interrogate the ImageController
    classes at create time to understand which settings to pass to their constructors.
    """

        super().set(name, value, **kwargs)
        if self.hawks:
            if name in self.hawks.ctrl.settings:
                setattr(self.hawks.ctrl, name, self.get(name))
            if show:
                self.hawks.show()

    def render(self, names):
        """
    Renders the named settings only. This is used to pass only the relevant settings to the
    constructors of Controllers.
    """

        return dict((name, self.get(name)) for name in names)


class Hawks(object):
    """
  Implements the base logic of the sign. Passes the right parameters to the ImageController's constrctor,
  interprets the settings enough to understand which ImageController to use and which settings to
  pass it.
  """

    PRESETS = {
        "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
        "bright": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
        "blue_on_green": {
            "bgcolor": "green",
            "innercolor": "blue",
            "outercolor": "black",
        },
        "green_on_blue": {
            "bgcolor": "blue",
            "innercolor": "green",
            "outercolor": "black",
        },
        "christmas": {
            "bgcolor": "green",
            "innercolor": "red",
            "outercolor": "black",
            "text": "12",
            "textsize": 27,
            "x": 0,
            "y": 2,
            "animation": "none",
            "thickness": 1,
        },
        "none": {},
    }

    ANIMATIONS = ["waving"]

    def __init__(self, *args, **kwargs):
        self.settings = HawksSettings()

        preset = None

        for k, v in kwargs.items():
            if k in self.settings:
                self.settings.set(k, v)
            elif k == "preset":
                preset = v
            else:
                setattr(self, k, v)

        self.ctrl = MatrixController(**self.settings.render(MatrixController.settings))
        self.settings.hawks = self

        if preset:
            self.apply_preset(preset)

    def apply_preset(self, preset):
        if preset in Hawks.PRESETS:
            for k, v in Hawks.PRESETS[preset].items():
                self.settings.set(k, v, show=False)
            self.show()
            return True
        return False

    def show(self, return_image=False):
        img_ctrl = None
        if self.settings.mode == "file" and self.settings.filename != "none":
            img_ctrl = FileImageController(
                **self.settings.render(FileImageController.settings)
            )
        elif self.settings.mode == "network_weather":
            img_ctrl = NetworkWeatherImageController(
                **self.settings.render(NetworkWeatherImageController.settings)
            )
        else:
            img_ctrl = TextImageController(
                **self.settings.render(TextImageController.settings)
            )

        if img_ctrl:
            self.ctrl.set_frames(img_ctrl.render())

        return self.ctrl.show(return_image=return_image)
