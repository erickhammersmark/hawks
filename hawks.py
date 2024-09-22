#!/usr/bin/env python3

import os
import time
from base import Base
from settings import Settings
from matrixcontroller import MatrixController
from imagecontroller import ImageController
from queue import Queue
from threading import Thread


class HawksSettings(Settings):
    def __init__(self):
        super().__init__(self)
        self.load_from_file()
        self.hawks = None
        self.internal.add("hawks")
        self.internal.add("filepath")
        self.internal.add("debug")
        self.set("filepath", "")
        self.set("debug", False)
        self.set("bgcolor", "blue", helptext="Background color when rendering text")
        self.set("outercolor", "black", helptext="Outer color of rendered text")
        self.set("innercolor", "green", helptext="Inner color of rendered text")
        self.set("bgbrightness", 0, helptext="background brightness of rainbow background")
        self.set("font", "FreeSansBold", helptext="Font to use when rendering text")
        self.set("x", 0)
        self.set("y", 0)
        self.set("rows", 32, helptext="Image height", choices=[32, 64, 128])
        self.set("cols", 32, helptext="Image width", choices=[32, 64, 128])
        self.set("p_rows", 32, helptext="Matrix height", choices=[32, 64, 128])
        self.set("p_cols", 32, helptext="Matrix width", choices=[32, 64, 128, 256])
        self.set(
            "decompose",
            False,
            helptext="Display is a chain of two 64x32 RGB LED matrices arranged to form a big square",
            choices=[False, True],
        )
        self.set(
            "row_address_type",
            0,
            helptext="rpi-rgb-led-matrix option led-row-addr-type, default 0",
            choices=[0, 1, 2, 3, 4],
        )
        self.set("text", "12", helptext='Text to render (if filename is "none")')
        self.set("textsize", 27)
        self.set("thickness", 1, helptext="Thickness of outercolor border around text")
        self.set(
            "animation",
            "none",
            helptext='Options are "waving" or "none"',
            choices=["none", "waving", "disc_animations", "glitch"],
        )
        self.set("amplitude", 0.4, helptext="Amplitude of waving animation")
        self.set("fps", 16, helptext="FPS of waving animation")
        self.set("period", 2000, helptext="Period of waving animation")
        self.set("filename", "none", helptext='Image file to display (or "none")')
        self.set("autosize", True, choices=[True, False])
        self.set("text_margin", 2, helptext="Margin of background color around text")
        self.set("brightness", 255, helptext="Image brighness, full bright = 255")
        self.set("back_and_forth", False, helptext="Loop GIF back and forth", choices=[False, True])
        self.set("url", "", helptext="Fetch image from url")
        self.set("urls", "", choices=[])
        self.set("urls_file", "", helptext="File containing image urls, one url per line")
        self.set("config_file", ".hawks.json", helptext="Hawks config file for image urls and saved configs (JSON)")
        self.set(
            "disc",
            False,
            helptext="Display is a 255-element DotStar disc",
            choices=[False, True],
        )
        self.set(
            "transpose",
            "none",
            helptext="PIL transpose operations are supported",
            choices=[
                "none",
                "FLIP_LEFT_RIGHT",
                "FLIP_TOP_BOTTOM",
                "ROTATE_90",
                "ROTATE_180",
                "ROTATE_270",
                "TRANSPOSE",
            ],
        )
        self.set("rotate", 0, helptext="Rotation in degrees")
        self.set(
            "mock", False, helptext="Display is mock rgbmatrix", choices=[False, True]
        )
        self.set(
            "nodisplay", False, helptext="Do not output to a display, including the mock", choices=[False, True]
        )
        self.set(
            "mode",
            "text",
            helptext="Valid modes are 'text', 'file', 'url', and 'network_weather'",
            choices=["text", "file", "url", "network_weather", "disc_animations"],
        )
        self.set("gif_frame_no", 0, helptext="Frame number of gif to statically display (when not animating)")
        self.set("gif_speed", 1.0, helptext="Multiplier for gif animation speed")
        self.set("gif_loop_delay", 0, helptext="Delay (ms) between repeatations of an animated gif")
        self.set("no_gif_override_duration_zero", False, helptext="Don't use 100ms frame time instead of 0", choices=[True, False])
        self.set("animate_gifs", True, choices=[True, False], helptext="Animate animated GIFs")
        self.set("zoom", False, choices=[True, False], helptext="Crop images to fill screen")
        self.set("zoom_center", True, choices=[True, False], helptext="When zooming, zoom into center of image")
        self.set("zoom_level", 1.0, helptext="Custom zoom level")
        self.set("fit", False, choices=[True, False], helptext="Fit image to display")
        self.set("filter", "none", choices=["none", "halloween"], helptext="Filter to apply to image")
        self.set("underscan", 0, helptext="Number of border rows and columns to leave blank")
        self.set("noloop", True, choices=[True, False], helptext="Do not loop animated GIFs")
        self.set("slideshow_directory", "img", helptext="directory full of images for slideshow")
        self.set("slideshow_hold_sec", 10.0, helptext="length of time to display each image in a slideshow")
        self.set("transition", "none", choices=["none", "fade", "wipe"], helptext="Slideshow transition")
        self.set("transition_duration_ms", 250, helptext="Slideshow transition duration in ms")
        self.set("transition_frames_max", 18, helptext="Max number of frames to render for slideshow transition")
        

    def set(self, name, value, **kwargs):
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
            if name in self.hawks.img_ctrl.settings:
                setattr(self.hawks.img_ctrl, name, self.get(name))

    def render(self, names):
        """
        Renders the named settings only. This is used to pass only the relevant settings to the
        constructors of Controllers.
        """

        return dict((name, self.get(name)) for name in names)


class Hawks(Base):
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
        self.settings.save("defaults")

        self.debug_file = open(f"/tmp/{os.getpid()}", "w")

        preset = None

        for k, v in kwargs.items():
            if k in self.settings:
                self.settings.set(k, v)
            elif k == "preset":
                preset = v
            else:
                setattr(self, k, v)

        self.frame_queue = Queue()

        self.ctrl = MatrixController(self.frame_queue, **self.settings.render(MatrixController.settings))
        self.img_ctrl = ImageController(self.frame_queue, **self.settings.render(ImageController.settings))
        self.settings.hawks = self

        if preset and preset != "none":
            self.apply_preset(preset)

    def db(self, msg):
        self.debug_file.write(f"{msg}\n")

    def apply_preset(self, preset):
        if preset in Hawks.PRESETS:
            for k, v in Hawks.PRESETS[preset].items():
                self.settings.set(k, v)
            return True
        return False

    def show(self):
        self.db(time.time())
        self.stop()
        self.img_ctrl = ImageController(self.frame_queue, **self.settings.render(ImageController.settings))
        self.img_ctrl.show(self.settings.mode)
        self.img_ctrl_render_thread = Thread(target=self.img_ctrl.render)
        self.img_ctrl_render_thread.start()
        return self.ctrl.show()

    def screenshot(self):
        return self.img_ctrl.screenshot()

    def stop(self):
        self.img_ctrl.stop()
        self.ctrl.stop()
        while not self.frame_queue.empty():
            self.frame_queue.get()

    def start(self):
        return self.ctrl.start()
