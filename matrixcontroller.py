#!/usr/bin/env python3

import time
from base import Base
from PIL import Image
from threading import Timer


class MatrixController(Base):
    """
    Implements an RGB Matrix and Dotstar Disc controller
    """

    settings = [
        "rows",
        "cols",
        "p_rows",
        "p_cols",
        "decompose",
        "disc",
        "mock",
        "nodisplay",
        "row_address_type",
        "debug",
    ]

    def __init__(self, frame_queue, *args, **kwargs):
        self.rows = 32
        self.cols = 32
        self.p_rows = 32
        self.p_cols = 32
        self.decompose = False
        self.disc = False
        self._disc = None
        self.mock = False
        self.debug = False
        self.frames = []
        self.dot_frames = []
        self.next_time = 0
        self.timer = None
        self.go = True
        self.frame_queue = frame_queue
        self.img_ctrl = None

        for (k, v) in kwargs.items():
            setattr(self, k, v)

        self.blank = Image.new("RGB", (self.cols, self.rows), "black")
        self.frame = (self.blank, 0)

        self.init_matrix()

    def init_matrix(self):
        """
        The Matrix has you
        """

        self.db("Initializing matrix")

        if self.disc:
            import disc
            self._disc = disc.Disc(mock=self.mock)
            self.dot_frames = [(self._disc.sample_image(self.blank), 0)]
        else:
            if self.mock:
                from mock import RGBMatrix, RGBMatrixOptions
            else:
                from rgbmatrix import RGBMatrix, RGBMatrixOptions

            options = RGBMatrixOptions()
            options.row_address_type = self.row_address_type

            options.cols = self.p_cols
            options.rows = self.p_rows
            options.chain_length = 1
            if self.decompose:
                options.chain_length = int(self.rows / self.p_rows)
            options.parallel = 1
            options.gpio_slowdown = 4
            options.hardware_mapping = (
                "adafruit-hat"  # If you have an Adafruit HAT: "adafruit-hat" or "adafruit-hat-pwm"
                                    # https://github.com/hzeller/rpi-rgb-led-matrix#troubleshooting
            )
            self.matrix = RGBMatrix(options=options)

        self.show()

    def set_img_ctrl(self, img_ctrl):
        self.img_ctrl = img_ctrl

    def reshape(self, image):
        """
        Map image of size self.rows x self.cols to fit a
        p_rows x p_cols display. For example:

        rows = 64           AAAAAAAA  |-->
        cols = 96           AAAAAAAA  |-->  AAAAAAAABBBBBBBBCCCCCCCC
        panel_rows = 32     AAAAAAAA  |-->  AAAAAAAABBBBBBBBCCCCCCCC
        panel_cols = 192    BBBBBBBB  |-->  AAAAAAAABBBBBBBBCCCCCCCC
                            BBBBBBBB  |-->
                            BBBBBBBB  |-->
                            CCCCCCCC  |-->
                            CCCCCCCC  |-->
                            CCCCCCCC  |-->

        Build a new Image of panel_rows x panel_cols.
        """

        rows, cols = self.rows, self.cols
        p_rows, p_cols = self.p_rows, self.p_cols

        if rows * cols != p_rows * p_cols:
            rows -= rows % p_rows
            cols -= p_cols % cols

        img = Image.new("RGB", (p_cols, p_rows), "black")
        orig_data = list(image.getdata())

        n_panels = int(rows / p_rows)
        if n_panels == 1:
            img.putdata(orig_data)
            return img

        img_data = []
        for row in range(0, p_rows):
            for panel_no in range(0, n_panels):
                r = row * cols + cols * p_rows * panel_no
                img_data.extend(orig_data[r:r+cols])
        img.putdata(img_data[:p_cols*p_rows])
        return img

    def shape_one_for_display(self, frame):
        """
            apply the hardware-specific changes to one frame,
            such as rendering for the dotstar disc or a chain of
            LED matrix panels.

            Consider some kind of cache for this.
        """
        if self.disc:
            return (self._disc.sample_image(frame[0]), frame[1])
        else:
            if self.decompose:
                if self.mock:
                    return frame
                else:
                    return (self.reshape(frame[0]), frame[1])
            return frame

    def shape_for_display(self, frames):
        if self.disc:
            self.db("Sampling frames for disc")
        return [self.shape_one_for_display(frame) for frame in frames]

    def SetFrame(self, frame):
        """
        Use instead of matrix.SetImage
        This will write to the disc or to an rgb matrix
        Input is a tuple where the first element is an Image
        """
        self.db(f"SetFrame({frame})")
        image = frame[0]
        if self.nodisplay:
            return

        if self.disc:
            self.db("setting disc image")
            return self._disc.set_image(image)

        self.db("setting matrix image")
        self.matrix.SetImage(image)

    def render(self):
        self.db("render()")

        # If we have a frame update pending, cancel it
        if self.timer:
            self.timer.cancel()
            self.timer = None

        # self.show() sets self.go to true, but hawks.show() will set it to false so
        # that we stop spending time drawing animations while it renders new frames.
        # Also used by hawks.show() to make this ImageController exit so a new one
        # can be the only thing writing to the frame queue.
        if not self.go:
            return

        # draw this frame on the hardware thingy (or the mock)
        if self.frame and self.frame_queue.empty():
            # we were showing something and have nothing: leave it up for another duration ms
            pass
        elif not self.frame_queue.empty():
            # it's time for a new one and there's something in the queue. get it.
            self.frame = self.shape_one_for_display(self.frame_queue.get())
        if not self.frame:
            # if it's time for a new frame and we don't have one at all,
            # blank for 100ms, then try again
            self.frame=(self.blank, 100)

        self.SetFrame(self.frame)

        duration = self.frame[1]

        if duration:
            # duration is in ms
            self.next_time = self.next_time + duration / 1000.0
            frame_interval = self.next_time - time.time()
            self.timer = Timer(frame_interval, self.render)
            self.timer.start()

    def show(self):
        """
        This is called every time something changes, like run_sign starting or
        a settings change via the API.  This is what the API calls to ensure
        that the changes it just set are acted upon.
        """

        self.db(f"show()")

        self.db("transforming frames")

        self.next_time = time.time()
        self.frame = None
        self.go = True
        self.render()

    def stop(self):
        """
        Stop displaying new frames.
        """
        self.go = False
        if getattr(self, "timer", None):
            self.timer.cancel()

    def start(self):
        """
        Resume displaying new frames.
        """
        self.go = True


def main():
    ctrl = MatrixController(mock=True)
    ctrl.set_image(Image.open("img/hawks.png").convert("RGB"))
    ctrl.show()
    while True:
        time.sleep(1000)


if __name__ == "__main__":
    main()
