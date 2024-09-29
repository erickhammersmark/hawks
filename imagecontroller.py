#!/usr/bin/env python3

import disc
import io
import json
import math
import os
import requests
import sys
import tempfile
import time
from base import Base
from copy import copy
from math import pi, sin
from matrixcontroller import MatrixController
from PIL import Image, ImageDraw, ImageFont, ImageColor, GifImagePlugin, UnidentifiedImageError
from random import randint, choice
from threading import Timer
from urllib.parse import unquote


class ImageController(Base):
    """
    Image Controller renders a list of tuples of RGB PIL.Image objects and
    durations in ms. Configure it with a reference to a Matrix Controller that
    provides the properties() method, so that the Image Controller can learn
    the properties of the display (width, height). Matrix Controller should also
    offer a brightness_mask() method, allowing the Image Controller to pass in a
    list of integers representing an image bitmask. Where the brightness mask is
    non-negative, the matrix must leave pixels at the specified brightness.
    """

    def __init__(self, frame_queue, settings):
        """
        ImageController objects should not pre-render images in __init__, as
        some properties of the ImageController will be assigned by the
        MatrixController. MatrixController will only call ImageController.render()
        at MatrixController.show() time, which is infrequent. It is OK to to
        expensive calculations in render().
        """

        self.frame_queue = frame_queue
        self.settings = settings
        self.hawks = self.settings.hawks
        self.static_frames = []
        self.bright_frames = []

        self.cols = 32
        self.rows = 32
        self.brightness = 255
        self.brightness_mask = None
        self.transpose = "none"
        self.rotate = 0
        self.zoom = False
        self.direction = 1
        self.back_and_forth = False
        self.zoom_level = 1.0
        self.zoom_center = True
        self.x = 0
        self.y = 0
        self.fit = False
        self.debug = False
        self.render_state = {"callback": None}
        self.period = 1000
        self.fps = 16
        self.amplitude = 1
        self.animation = None
        self.filter = None
        self.queue_target_depth = 20
        self.render_calls = 0
        self.go = True
        self.img_ctrl = None
        self.underscan = 0
        self.noloop = False
        self.slideshow_directory = "img"
        self.slideshow_hold_sec = 15.0
        self.transition = None
        self.transition_duration_ms = 250
        self.transition_frames_max = 18


        # render state
        self.frame_no = 0
        self.direction = 1

        for (k, v) in self.settings:
            setattr(self, k, v)
        super().__init__()

        self.active_cols = self.cols - self.underscan * 2
        self.active_rows = self.rows - self.underscan * 2

    def drain_queue(self):
        while not self.frame_queue.empty():
            self.frame_queue.get()

    def show(self, mode):
        self.go = True
        img_ctrl = None
        if mode == "url":
            if self.url == "":
                self.url = self.urls
            img_ctrl = URLImageController(self.settings)
        elif mode == "file" and self.filename != "none":
            img_ctrl = FileImageController(self.settings)
        elif mode == "network_weather":
            img_ctrl = NetworkWeatherImageController(self.settings)
        elif mode == "disc_animations":
            self.static_frames = []
            #self.ctrl.disc_animations()
            img_ctrl = DiscAnimationsImageController(self.settings)
        elif mode == "slideshow":
            img_ctrl = SlideshowImageController(self.settings)
        else:
            img_ctrl = TextImageController(self.settings)

        if img_ctrl:
            self.img_ctrl = img_ctrl
            frames = img_ctrl.render()
            if type(frames) == list:
                # Assume this list is a set of static frames

                if self.filter and self.filter != "none":
                    frames = getattr(img_ctrl, "filter_" + self.filter)(frames)

                self.static_frames, self.bright_frames = self.transform(frames)
                self.frame_no = -1
                self.direction = 1
        if self.static_frames:
            prev_frame = self.hawks.ctrl.frame
            next_frame = self.static_frames[0]
            if self.transition:
                # some function that shoves frames into the queue, < the queue depth
                self.do_transition(prev_frame, next_frame)
        self.render()

    def stop(self):
        self.go = False
        if getattr(self, "timer", None):
            self.timer.cancel()

    def next_static_frame(self):
        self.frame_no += self.direction
        if self.frame_no >= len(self.static_frames):
            if self.noloop or len(self.static_frames) == 1:
                return None
            if self.back_and_forth:
                self.direction = -1
                self.frame_no += self.direction
            else:
                self.frame_no = 0
        elif self.frame_no < 0:
            self.direction = 1
            self.frame_no = 0
        return self.static_frames[self.frame_no]

    def render(self):
        #self.render_calls += 1
        #print(f"{self.render_calls}, {self.frame_queue.qsize()}")
        if getattr(self, "timer", None):
            self.timer.cancel()
        if not self.go:
            return
        if not self.static_frames and not self.img_ctrl:
            return
        while self.frame_queue.qsize() < self.queue_target_depth:
            if self.static_frames:
                frame = self.next_static_frame()
            elif self.img_ctrl:
                frame = self.img_ctrl.render()
            else:
                break
            if not frame:
                return
            self.frame_queue.put(frame)
        self.timer = Timer(0.100, self.render)
        self.timer.start()

    def transform(self, static_frames):
        """
            transformed_frames will include all of the user-requested transformations,
            such as rotations, brightness, or mirroring.
        """
        transformed_frames = []
        bright_frames = []
        for img, duration in static_frames:
            image, bright_image = self.apply_transformations(img)
            transformed_frames.append((image, duration))
            bright_frames.append((bright_image, duration))
        return transformed_frames, bright_frames

    def shift_column(self, image, column, delta):
        rows = self.active_rows
        if delta == 0:
            return image
        if delta > 0:
            # positive == up
            # from 0 to rows-delta, pull from row+delta.
            # from rows-delta to rows-1, black
            for n in range(0, rows - delta):
                image.putpixel((column, n), image.getpixel((column, n + delta)))
            for n in range(rows - delta, rows):
                image.putpixel((column, n), (0, 0, 0))
        else:
            # negative == down
            # make delta positive
            # from rows-1 to delta, pull from row-delta
            # from delta to 0, black
            delta = 0 - delta
            for n in range(rows - 1, delta, -1):
                image.putpixel((column, n), image.getpixel((column, n - delta)))
            for n in range(0, delta):
                image.putpixel((column, n), (0, 0, 0))

    def frames_equal(self, one, two):
        if not one or not two:
            return False
        for o, t in zip(one.getdata(), two.getdata()):
            if o != t:
                return False
        return True

    def multiply_pixel(self, pixel, value):
        return tuple([int(c * value) for c in pixel])

    def average_anim_frames(self, group):
        """
        group is a list of indices of self.frames
        The frames should represent repetitions of the first image
        and one instnace of the next image, a set of duplicate
        frames and one instance of what the next frame will be.  This
        method should leave the first and last frames untouched and
        replace each of the intermediate frames with a combination of the two.
        """

        if not group:
            return
        num_frames = len(group)
        if num_frames <= 2:
            return
        num_frames -= 1

        saf = self.frames
        # we can redo this to only fetch the first and last.  we compute the ones in the middle.
        group_data = [saf[n].getdata() for n in group]
        new_data = [[] for n in group]
        num_pixels = len(list(group_data[0]))

        for pixel_no in range(0, num_pixels):
            first = group_data[0][pixel_no]
            last = group_data[-1][pixel_no]
            for idx, frame_no in enumerate(group):
                left = self.multiply_pixel(
                    group_data[0][pixel_no], float(num_frames - idx) / num_frames
                )
                right = self.multiply_pixel(
                    group_data[-1][pixel_no], float(idx) / num_frames
                )
                new_data[idx].append(tuple([l + r for l, r in zip(left, right)]))
        for idx, frame_no in enumerate(group):
            if idx == 0 or idx == num_frames:
                continue
            saf[frame_no].putdata(new_data[idx])

    def do_transition(self, prev_frame, next_frame):
        if self.transition == "fade":
            return self.transition_fade(prev_frame, next_frame)
        if "wipe" in self.transition:
            return self.transition_wipe(prev_frame, next_frame)

    def transition_fade(self, prev_frame, next_frame):
        duration = self.transition_duration_ms / self.transition_frames_max
        for n in range(1, self.transition_frames_max):
            next_pct = float(n) / self.transition_frames_max
            image = Image.blend(prev_frame[0], next_frame[0], next_pct)
            self.frame_queue.put((image, duration))

    def transition_wipe(self, prev_frame, next_frame):
        duration = self.transition_duration_ms / self.transition_frames_max
        delta_c = prev_frame[0].width / self.transition_frames_max
        delta_r = prev_frame[0].height / self.transition_frames_max
        sz = prev_frame[0].size # tuple. 0 is width/cols, 1 is height/rows
        for n in range(1, self.transition_frames_max):
            image = Image.new("RGB", sz)
            image.paste(prev_frame[0], (0, 0))
            nc = int(n * delta_c)
            nr = int(n * delta_r)
            if self.transition == "wiperight":
                box = (0, 0, nc, sz[1])
                pos = (0, 0)
            elif self.transition == "wipedown":
                box = (0, 0, sz[0], nr)
                pos = (0, 0)
            elif self.transition == "wipeup":
                y = sz[1] - nr
                box = (0, y, sz[0], sz[1])
                pos = (0, y)
            else: # "wipe", "wipeleft"
                x = sz[0] - nc
                box = (x, 0, sz[0], sz[1])
                pos = (x, 0)
            image.paste(next_frame[0].crop(box), pos)
            self.frame_queue.put((image, duration))


    def rainbow_color_from_value(self, value):
        border = 0
        num_buckets = 6
        max_value = 1024 # implicit min value of 0
        bucket = (max_value - border * 2) / num_buckets
        value = min(value, bucket * num_buckets) # bucket * num_buckets is the actual max value
        r = 0
        g = 0
        b = 0
        bright = 255

        if value < border:
            # red
            r = bright
            g = 0
            b = 0
        elif value < border + bucket * 1:
            # red + increasing green
            value -= border + bucket * 0
            value = (value * bright) / bucket
            r = bright
            g = value
            b = 0
        elif value < border + bucket * 2:
            # green + decreasing red
            value -= border + bucket * 1
            value = bucket - value
            value = (value * bright) / bucket
            r = value
            g = bright
            b = 0
        elif value < border + bucket * 3:
            # green + increasing blue
            value -= border + bucket * 2
            value = (value * bright) / bucket
            r = 0
            g = bright
            b = value
        elif value < border + bucket * 4:
            # blue + decreasing green
            value -= border + bucket * 3
            value = bucket - value
            value = (value * bright) / bucket
            r = 0
            g = value
            b = bright
        elif value < border + bucket * 5:
            # blue + increasing red
            value -= border + bucket * 4
            value = (value * bright) / bucket
            r = value
            g = 0
            b = bright
        else:
            # red + decreasing blue
            value -= border + bucket * 5
            value = bucket - value
            value = (value * bright) / bucket
            r = bright
            g = 0
            b = value
        return (int(g), int(r), int(b))


    def init_anim_frames(self, image, count=None):
        if count is None:
            count = self.fps
        return [image.copy() for n in range(0, count)]

    def glitch_effect_flicker(self, image, color="black"):
        blank = Image.new("RGB", (self.active_cols, self.active_rows), color)
        return [(blank, randint(10, 50))]

    def glitch_effect_shift(self, image, color="black"):
        blank = Image.new("RGB", (self.active_cols, self.active_rows), color)
        blank.paste(image, (randint(1, self.active_cols), randint(1, self.active_rows)))
        return [(blank, randint(10, 50))]

    def generate_glitch_frames(self, image, glitchiness=5):
        """
        glitchiness is the chance out of 100 that any given frame is going to be a glitch.
        """
        glitch_functions = [
            self.glitch_effect_flicker,
            self.glitch_effect_shift,
        ]
        count = randint(self.fps, 4*self.fps)
        frames = []
        for frame in range(count):
            if randint(1, 100) <= glitchiness:
                frames.extend(choice(glitch_functions)(image))
            else:
                frames.append((image, 500))
        return frames

    def generate_waving_frames(self, image):
        cols = self.active_cols
        frames = self.init_anim_frames(image)
        ms_per_frame = self.period / self.fps
        wavelength_radians = math.pi * 2.0
        phase_step_per_frame = wavelength_radians / self.fps
        radians_per_pixel = wavelength_radians / cols
        phase = 0.0
        amplitude = self.amplitude
        # first pass
        for n in range(0, self.fps):
            for c in range(0, cols):
                radians = radians_per_pixel * c + phase
                delta_y = int(
                    round((math.sin(radians) * amplitude) / radians_per_pixel)
                )  # assumes rows == cols!
                self.shift_column(frames[n], c, delta_y)
            phase -= phase_step_per_frame
        # second pass
        group = []
        for n in range(0, self.fps):
            group.append(n)
            if not self.frames_equal(frames[group[0]], frames[n]):
                self.average_anim_frames(group)
                group = [n]
        frame_times = [ms_per_frame for frame in frames]
        return list(zip(frames, frame_times))

    def generate_rainbow_frames(self, image):
        frames = self.init_anim_frames(image)
        color_delta = 1024.0 / (self.active_cols * self.active_rows)
        bg_rgb = ImageColor.getrgb(self.bgcolor)
        color_value = 0.0
        for idx, frame in enumerate(frames):
            color_value = 1024.0 * idx / len(frames)
            pixels = frame.getdata()
            new_pixels = []
            for pixel in pixels:
                if pixel == bg_rgb:
                    new_pixel = self.rainbow_color_from_value(int(color_value))
                    if self.brightness < 255:
                        new_pixel = tuple([int(float(p)*float(self.brightness)/255) for p in new_pixel])   
                    new_pixels.append(new_pixel)
                else:
                    new_pixels.append(pixel)
                color_value += color_delta
                if color_value > 1024:
                    color_value -= 1024
            frame.putdata(new_pixels)
        return list(zip(frames, [50 for frame in frames]))

    def filter_halloween(self, frames):
        spooky = (255, 127, 00)
        for frame in frames:
            new_frame = []
            for pixel in list(frame[0].getdata()):
                pixel_brightness = (pixel[0] + pixel[1] + pixel[2]) / (255 * 3)
                new_frame.append(tuple([int(c * pixel_brightness) for c in spooky]))
            frame[0].putdata(new_frame)
        return frames

    def filter_christmas(self, frames):
        for frame in frames:
            new_frame = []
            for pixel in list(frame[0].getdata()):
                new_pixel = [max(255, pixel[0] * 2), pixel[1] * 2, int(pixel[2] / 4)]
                if new_pixel[0] > new_pixel[1]:
                    new_pixel[1] = int(new_pixel[1] / 4)
                else:
                    new_pixel[0] = int(new_pixel[0] / 4)
                new_frame.append(tuple(new_pixel))
            frame[0].putdata(new_frame)
        return frames

    def fill_out(self, image):
        """
        If an image doesn't have enough rows or columns to fill the matrix,
        fill it in with black rows or columns.
        """
        cols, rows = image.size
        if cols >= self.active_cols and rows >= self.active_rows:
            return image

        new_image = Image.new("RGB", (self.active_cols, self.active_rows), "black")
        x = int((self.active_cols - cols) / 2)
        y = int((self.active_rows - rows) / 2)

        data = list(image.getdata())
        new_data = list(new_image.getdata())
        old_pixels = cols * rows
        new_pixels = self.active_cols * self.active_rows
        pos = 0
        new_pos = self.active_cols * y + x
        while new_pos < new_pixels and pos < old_pixels:
            new_data[new_pos : new_pos + cols] = data[pos : pos + cols]
            pos += cols
            new_pos += self.active_cols
        new_image.putdata(new_data)
        return new_image

    def resize_image(self, image, cols, rows):
        orig_image_c, orig_image_r = image.size
        panel_c, panel_r = cols, rows
        new_c, new_r = panel_c, panel_r
        left, right, top, bottom = 0, orig_image_c - 1, 0, orig_image_r - 1

        # all of the manipulations are in image pixel space
        # the image is not scaled into panel space until the call to image.resize() at the end
        if self.zoom:
            image_c, image_r = image.size
            # zoom in on a pixel position in the image
            # calculate how much the image we are keeping in each dimension
            # bring bottom and right in total - that much
            zoomed_r = image_r / self.zoom_level
            zoomed_c = image_c / self.zoom_level
            if self.zoom_center:
                left = (image_c - zoomed_c) / 2
                right = image_c - left
                top = (image_r - zoomed_r) / 2
                bottom = image_r - top
            else:
                left = self.x
                right = left + zoomed_c
                top = self.y
                bottom = self.y + zoomed_r
            image = image.crop((left, top, right, bottom))
        if self.fit:
            # crop the image to be square, preserving all of one dimension
            image_c, image_r = image.size
            left, right, top, bottom = 0, image_c - 1, 0, image_r - 1
            if image_r > image_c:
                delta = image_r - image_c
                top = delta / 2
                bottom -= (delta - top)
            elif image_c > image_r:
                delta = image_c - image_r
                left = delta / 2
                right -= (delta - left)
            image = image.crop((left, top, right, bottom))
        else:
            # scale such that the longest dimension of the image fits on the panel
            # default is to scale to the size (panel_c, panel_r)
            # if one dimension is longer than the other, scale the shorter one
            # to less than panel_c or panel_r to preserve aspect ratio
            image_c, image_r = image.size
            if image_c > image_r:
                new_r = panel_r * float(image_r) / image_c
            elif image_r > image_c:
                new_c = panel_c * float(image_c) / image_r
        image = image.resize((int(new_c), int(new_r)))
        if new_c < self.active_cols or new_r < self.active_rows:
            image = self.fill_out(image)
        return image

    def brighten(self, image):
        """
        Fun fact: this will only ever darken.
        """
        if self.brightness == 255:
            return image

        data = list(image.getdata())
        newdata = []
        for idx, pixel in enumerate(data):
            brt = self.brightness
            if self.brightness_mask:
                brt = self.brightness_mask[idx]
                if brt < 0:
                    brt = self.brightness
            newdata.append(tuple(int(c * brt / 255) for c in pixel))
        image.putdata(newdata)
        return image

    def make_png(self, image):
        with io.BytesIO() as output:
            image.save(output, format="PNG")
            return output.getvalue()

    def make_gif(self, frames):
        image = frames[0][0]
        append_images = [frame[0] for frame in frames[1:]]
        durations = [frame[1] for frame in frames]
        if self.back_and_forth:
            for frameno in range(len(append_images) - 2, -1, -1):
                append_images.append(append_images[frameno])
                durations.append(durations[frameno])
        with io.BytesIO() as output:
            image.save(output, format="GIF", save_all=True, append_images=append_images, duration=durations, loop=0, disposal=1)
            return output.getvalue()

    def screenshot(self):
        if self.bright_frames:
            if len(self.bright_frames) == 1:
                return self.make_png(self.bright_frames[0][0])
            else:
                return self.make_gif(self.bright_frames)
        return self.make_png(Image.new("RGB", (self.active_cols, self.active_rows), "black"))

    def apply_transformations(self, image, max_brightness=False):
        if not getattr(self, "disc", None):
            image = self.resize_image(image, self.active_cols, self.active_rows)

        if self.transpose != "none":
            operation = getattr(Image, self.transpose.upper(), None)
            if operation != None:
                image = image.transpose(operation)

        if self.rotate != 0:
            image = image.rotate(self.rotate)

        bright_image = copy(image)
        if self.brightness != 255 and not max_brightness:
            image = self.brighten(image)

        if self.underscan:
            new_image = Image.new("RGB", (self.cols, self.rows), "black")
            new_image.paste(image, (self.underscan, self.underscan))
            image = new_image

        return (image, bright_image)

    """
    def skew_image(self, image, start_row=0, end_row=None, start_radians=0, end_radians=2*pi, skew_depth=None):
        if end_row is None:
            end_row = self.rows
        if skew_depth is None:
            skew_depth = randint(int(self.cols/20), int(self.cols/4))
        skewed_image = Image.new("RGB", (self.cols, self.rows), "black")
        radian_delta = float(end_row - start_row) / (end_radians - start_radians)
        angle = start_radians
        new_pixels = []
        cur_row = 0
        row_pixels = []
        for idx, pixel in enumerate(image.getdata()):
            row = int(idx / self.cols)
            if row != cur_row:
                if row >= start_row and row < end_row:
                    new_left_col = int(sin(angle) * skew_depth)
                    angle += radian_delta
                    if new_left_col < 0:
                        new_left_col += self.cols
                    skewed_row_pixels = row_pixels[new_left_col:-1] + row_pixels[0:new_left_col]
                    row_pixels = skewed_row_pixels
                new_pixels.extend(row_pixels)
                row_pixels = []
                cur_row = row
            row_pixels.append(pixel)
        if cur_row >= start_row and cur_row < end_row:
            new_left_col = int(sin(angle) * skew_depth)
            angle += radian_delta
            if new_left_col < 0:
                new_left_col += self.cols
            skewed_row_pixels = row_pixels[new_left_col:-1] + row_pixels[0:new_left_col]
            new_pixels.extend(skewed_row_pixels)
        else:
            new_pixels.extend(row_pixels)
        skewed_image.putdata(new_pixels)
        return skewed_image
    """

    """
    def render_glitch(self, frame):
        next_glitch_time = self.render_state.get("next_glitch_time", time.time())
        if time.time() >= next_glitch_time:
            self.render_state["next_glitch_time"] = next_glitch_time + randint(1000, 15000) / 1000.0
        else:
            return iter([frame])

        glitch_mode = choice(["flicker", "skew", "flash_image"])
        print(f"{time.time()} {glitch_mode}")

        if glitch_mode == "flicker":
            off_frames = randint(2, 12)
            rendered_frames = []
            for x in range(0, off_frames):
                rendered_frames.append((self.blank, randint(10, 30)))
            return iter(self.transform_and_reshape(rendered_frames)[1])

        if glitch_mode == "skew":
            skew_depth = randint(0 - self.cols, self.cols)
            skew_duration = randint(400, 1000)
            return iter(self.transform_and_reshape([(self.skew_image(frame[0]), skew_duration)])[1])

        if glitch_mode == "flash_image":
            flash_duration = randint(1000, 3000)
            print(self.render_state["flash_image"])
            return iter(self.transform_and_reshape([(self.render_state["flash_image"], flash_duration)])[1])
    """


    """
    def disc_animations(self):
      
        circle_colors = []
        color = 100
        for circle in self._disc.circles:
            circle_colors.append(color)
            color += 100

        def rainbow_color_from_value(value):
          border = 0
          num_buckets = 6
          max_value = 1024 # implicit min value of 0
          bucket = (max_value - border * 2) / num_buckets
          value = min(value, bucket * num_buckets) # bucket * num_buckets is the actual max value
          r = 0
          g = 0
          b = 0
          bright = self.brightness
      
          if value < border:
            # red
            r = bright
            g = 0
            b = 0
          elif value < border + bucket * 1:
            # red + increasing green
            value -= border + bucket * 0
            value = (value * bright) / bucket
            r = bright
            g = value
            b = 0
          elif value < border + bucket * 2:
            # green + decreasing red
            value -= border + bucket * 1
            value = bucket - value
            value = (value * bright) / bucket
            r = value
            g = bright
            b = 0
          elif value < border + bucket * 3:
            # green + increasing blue
            value -= border + bucket * 2
            value = (value * bright) / bucket
            r = 0
            g = bright
            b = value
          elif value < border + bucket * 4:
            # blue + decreasing green
            value -= border + bucket * 3
            value = bucket - value
            value = (value * bright) / bucket
            r = 0
            g = value
            b = bright
          elif value < border + bucket * 5:
            # blue + increasing red
            value -= border + bucket * 4
            value = (value * bright) / bucket
            r = value
            g = 0
            b = bright
          else:
            # red + decreasing blue
            value -= border + bucket * 5
            value = bucket - value
            value = (value * bright) / bucket
            r = bright
            g = 0
            b = value
          return (int(g), int(r), int(b))
      
        while True:
            p = 0
            for idx, circle in enumerate(self._disc.circles):
                color = rainbow_color_from_value(circle_colors[idx])
                for n in range(0, circle[1]):
                    self._disc.dots[p] = color
                    p += 1
                circle_colors[idx] += 7
                if circle_colors[idx] >= 1024:
                    circle_colors[idx] = 0
            self._disc.show()
    """


class TextImageController(ImageController):
    def __init__(self, settings):
        self.settings = settings

        self.bgcolor = "blue"
        self.outercolor = "black"
        self.innercolor = "white"
        self.bgrainbow = False
        self.font = "FreeSansBold"
        self.text = "12"
        self.textsize = 27
        self.thickness = 1
        self.autosize = True
        self.text_margin = 2
        self.x = 0
        self.y = 0
        super().__init__(None, settings)
        self.rows = self.active_rows
        self.cols = self.active_cols

    def render(self, autosize=True, ignore_animation=False):
        image = Image.new("RGB", (self.cols, self.rows), self.bgcolor)
        draw = ImageDraw.Draw(image)
        text = unquote(self.text.upper())
        font = ImageFont.truetype(self.font, self.textsize)

        if autosize and self.autosize:
            self._autosize()

        font = ImageFont.truetype(self.font, self.textsize)

        x = self.x
        y = self.y

        for dx in range(0 - self.thickness, self.thickness + 1):
            for dy in range(0 - self.thickness, self.thickness + 1):
                draw.text((x - dx, y - dy), text, fill=self.outercolor, font=font)
                draw.text((x + dx, y - dy), text, fill=self.outercolor, font=font)
                draw.text((x - dx, y + dy), text, fill=self.outercolor, font=font)
                draw.text((x + dx, y + dy), text, fill=self.outercolor, font=font)

        draw.text((x, y), text, fill=self.innercolor, font=font)

        if not ignore_animation:
            if self.animation == "waving":
                return self.generate_waving_frames(image)
            elif self.animation == "glitch":
                return self.generate_glitch_frames(image)
            elif self.animation == "rainbow":
                return self.generate_rainbow_frames(image)

        return [(image, 0)]

    def col_only_bgcolor(self, image_data, col):
        if col < 0 or col >= self.cols:
            raise Exception(
                "Column {0} is out of bounds (0, {1})".format(col, self.cols)
            )

        bgcolor = ImageColor.getrgb(self.bgcolor)
        px_no = col
        while px_no < len(image_data):
            if image_data[px_no] != bgcolor:
                return False
            px_no += self.cols
        return True

    def row_only_bgcolor(self, image_data, row):
        if row < 0 or row >= self.rows:
            raise Exception(
                "Column {0} is out of bounds (0, {1})".format(row, self.rows)
            )

        bgcolor = ImageColor.getrgb(self.bgcolor)
        px_no = row * self.cols
        while px_no < (row + 1) * self.cols and px_no < len(image_data):
            if image_data[px_no] != bgcolor:
                return False
            px_no += 1
        return True

    def measure_left_margin(self, image_data):
        col = 0
        while col < self.cols and self.col_only_bgcolor(image_data, col):
            col += 1
        return col

    def measure_right_margin(self, image_data):
        col = self.cols - 1
        while col >= 0 and self.col_only_bgcolor(image_data, col):
            col -= 1
        return (self.cols - 1) - col

    def measure_top_margin(self, image_data):
        row = 0
        while row < self.rows and self.row_only_bgcolor(image_data, row):
            row += 1
        return row

    def measure_bottom_margin(self, image_data):
        row = self.rows - 1
        while row >= 0 and self.row_only_bgcolor(image_data, row):
            row -= 1
        return (self.rows - 1) - row

    def align_and_measure(self):
        image_data = self.render(autosize=False, ignore_animation=True)[0][0].getdata()

        left_margin = self.measure_left_margin(image_data)
        self.x = 0

        top_margin = self.measure_top_margin(image_data)
        self.y = 0

        if self.text_margin != left_margin or self.text_margin != top_margin:
            image = self.render(autosize=False, ignore_animation=True)
            image_data = image[0][0].getdata()

        left_margin = self.measure_left_margin(image_data)
        top_margin = self.measure_top_margin(image_data)
        right_margin = self.measure_right_margin(image_data)
        bottom_margin = self.measure_bottom_margin(image_data)

        return (left_margin, right_margin, top_margin, bottom_margin)

    def _autosize(self):
        self.x = 0
        self.y = 0
        self.textsize = 10

        left_margin, right_margin, top_margin, bottom_margin = self.align_and_measure()

        # make the text big enough
        count = 0
        while right_margin > self.text_margin and bottom_margin > self.text_margin:
            self.textsize += 1
            (
                left_margin,
                right_margin,
                top_margin,
                bottom_margin,
            ) = self.align_and_measure()
            count += 1

        # make sure it is not too big
        while (
            right_margin < self.text_margin or bottom_margin < self.text_margin
        ) and self.textsize > 0:
            self.textsize -= 1
            (
                left_margin,
                right_margin,
                top_margin,
                bottom_margin,
            ) = self.align_and_measure()

        # center the text in both dimensions
        self.x += int((right_margin - left_margin) / 2)
        self.y += int((bottom_margin - top_margin) / 2)


class FileImageController(ImageController):
    def __init__(self, settings):
        self.settings = settings
        self.animate_gifs = True
        self.gif_frame_no = 0
        self.gif_speed = 1
        self.gif_loop_delay = 0
        self.no_gif_override_duration_zero = False
        super().__init__(None, settings)
        self.cols = self.active_cols
        self.rows = self.active_rows

    def render(self):
        try:
            image = Image.open(unquote(self.filename))
        except UnidentifiedImageError as e:
            print(f"Unable to open image file {self.filename}: {e}")
            return []

        if hasattr(image, "is_animated") and image.is_animated:
            return GifFileImageController(self.settings).render()

        image = image.convert("RGB")
        return [(image, 0)]


class GifFileImageController(FileImageController):
    def __init__(self, settings):
        self.settings = settings
        super().__init__(settings)
        self.init_frames()

    def init_frames(self):
        self.frames = []
        with Image.open(unquote(self.filename)) as gif:
            for n in range(0, gif.n_frames):
                gif.seek(n)
                image = gif.convert("RGB")
                if self.animate_gifs:
                    duration = int(gif.info["duration"])
                    if duration == 0 and not self.no_gif_override_duration_zero:
                        duration = 100
                    if n == gif.n_frames - 1:
                        duration += self.gif_loop_delay * self.gif_speed  # hack
                else:
                    if n == self.gif_frame_no:
                        duration = 0
                    else:
                        duration = 1
                duration = int(duration * (1 / self.gif_speed))
                self.frames.append((image, duration))
                if not duration:
                    # -0 duration frame will be shown forever, no value in rendering any more
                    return

    def render(self):
        return self.frames


class URLImageController(FileImageController):
    def __init__(self, settings):
        self.settings = settings
        super().__init__(settings)
        self.cols = self.active_cols
        self.rows = self.active_rows
        self.filename = tempfile.mktemp()
        self.settings.filename = self.filename
        self.fetch_image()

    def fetch_image(self):
        response = requests.get(self.url)
        if response.status_code != 200:
            raise Exception("Error fetching {}: status code {}".format(self.url, response.status_code))
        with open(self.filename, "wb") as TMPFILE:
            TMPFILE.write(response.content)

    def render(self):
        frames = FileImageController(self.settings).render()
        os.unlink(self.filename)
        return frames


class SlideshowImageController(ImageController):
    # FIXME: slideshow works by itself calling this function against each of the
    # images in this directory, each on a new instance of ImageController.
    # Once it has called show() on the MatrixController for each image,
    # it sets a timer, after which it will loop again, stop the old
    # ImageController and make a new one. If the file being shown has a total
    # duration longer than the slideshow hold time, that timer will adjust to
    # let the file play at least one time through. Animations shorter than the
    # hold time can loop.

    def __init__(self, settings):
        super().__init__(None, settings)
        self.files = os.listdir(self.slideshow_directory)
        self.fileno = 0
        self.static_frames = []
        self.frameno = 0
        self.hold_time_ms = self.slideshow_hold_sec * 1000
        self.next_render_time_sec = time.time()

    def next_filename(self, recursion_count=0):
        fullpath = os.path.join(self.slideshow_directory, self.files[self.fileno])
        self.fileno += 1
        if self.fileno >= len(self.files):
            self.fileno = 0
        if os.path.isdir(fullpath):
            if recursion_count >= len(self.files):
                raise Exception(f"Path contains only directories: {self.slideshow_directory}")
            return self.next_filename(recursion_count=recursion_count+1)
        return fullpath

    def render(self):
        if time.time() >= self.next_render_time_sec:
            fullpath = self.next_filename()
            settings = copy(self.settings)
            settings.set("filename", fullpath, propagate=False)
            img_ctrl = FileImageController(settings)
            if img_ctrl:
                frames = img_ctrl.render()
                if self.filter and self.filter != "none":
                    frames = getattr(img_ctrl, "filter_" + self.filter)(frames)
                self.static_frames, self.bright_frames = self.transform(frames)
                self.frameno = 0
                #print(f"rendering {self.files[self.fileno]} at {time.time()}, got {len(self.static_frames)} frames")
                duration = sum(f[1] for f in self.static_frames)
                hold_time_ms = self.hold_time_ms
                if duration > hold_time_ms:
                    hold_time_ms = duration
                self.next_render_time_sec = time.time() + hold_time_ms / 1000.0

        if self.static_frames:
            frame = self.static_frames[self.frameno]
            if self.frameno < len(self.static_frames) - 1:
                self.frameno += 1
            elif not self.noloop:
                self.frameno = 0
            if frame[1] == 0:
                frame = (frame[0], 100)
            #print(f"returning frame {frame}")
            return frame  

        #print("returning blank")
        return (self.blank, 100)


class NetworkWeatherImageController(ImageController):
    """
    WIP
    """

    def __init__(self, settings):
        self.settings = settings
        super().__init__(None, settings)
        self.cols = self.active_cols
        self.rows = self.active_rows
        self.network_weather_data = None
        self.network_weather_image = Image.new("RGB", (self.cols, self.rows), "black")

        #
        # on a 32x32 6mm pitch LED matrix
        # if you happen to have a 5 7/8" wide Google Cloud Platform plexiglass logo
        # if you center it horizontally and align its top with the top of the panel
        # these are the lights that it will cover.
        #
        # no one else will use this EVER
        #
        # fmt: off
        self.gcp_logo_pixels = [
                                                      14, 15, 16, 17,

                                          43, 44, 45, 46, 47, 48, 49, 50, 51, 52,

                                     74,  75,  76,  77,  78,  79,  80,  81,  82,  83,  84,  85,

                               105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118,

                          136, 137, 138, 139, 140, 141,                          147, 148, 149, 150, 151,

                          168, 169, 170, 171,                                              181, 182, 183, 184,

                     199, 200, 201, 202, 203, 204,                                         213, 214, 215, 216,

                230, 231, 232, 233, 234, 235, 236, 237, 238,                               245, 246, 247, 248,

                262, 263, 264, 265, 266, 267, 268, 269, 270, 271,                               278, 279, 280, 281,

           293, 294, 295, 296, 297, 298, 299, 300, 301, 302,                                    310, 311, 312, 313, 314,

      324, 325, 326, 327, 328,                     332, 333,                                         343, 344, 345, 346, 347,

      356, 357, 358, 359,                                                                                 376, 377, 378, 379,

      388, 389, 390, 391,                                                                                 408, 409, 410, 411,

      420, 421, 422, 423,                                                                                 440, 441, 442, 443,

      452, 453, 454, 455,                                                                                 472, 473, 474, 475,

      484, 485, 486, 487, 488,                                                                       503, 504, 505, 506, 507,

           517, 518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 530, 531, 532, 533, 534, 535, 536, 537, 538,

                550, 551, 552, 553, 554, 555, 556, 557, 558, 559, 560, 561, 562, 563, 564, 565, 566, 567, 568, 569,

                     583, 584, 585, 586, 587, 588, 589, 590, 591, 592, 593, 594, 595, 596, 597, 598, 599, 600,

                               617, 618, 619, 620, 621, 622, 623, 624, 625, 626, 627, 628, 629, 630

        ]
        # fmt: on

        self.gcp_logo_pixels.sort()

        # ImageControllers shouldn't render things in __init__, but the gcp
        # logo pixels only work for 32x32, so nothing the MatrixController
        # sets later is going to change this.

        n = 0
        p = 0
        self.brightness_mask = []
        self.not_gcp_logo_pixels = []
        while n < 32 * 32:
            if self.gcp_logo_pixels[p] == n:
                p += 1
                self.brightness_mask.append(255)
            else:
                self.brightness_mask.append(-1)
                self.not_gcp_logo_pixels.append(n)
            n += 1

        super().__init__(None, *args, **kwargs)

    def render(self):
        self.network_color = "black"
        img = Image.new("RGB", (self.cols, self.rows), self.network_color)
        img_data = list(img.getdata())
        for p in self.not_gcp_logo_pixels:
            img_data[p] = (255, 0, 0)
        for p in self.gcp_logo_pixels:
            img_data[p] = (255, 255, 255)

        self.network_weather_image.putdata(img_data)
        return [(self.network_weather_image, 0)]

    def network_weather_update(self):
        """
        Fetch the data needed to render the network weather.
        If the data has changed, call network_weather_anim_setup()
        """
        try:
            response = requests.get("https://status.cloud.google.com/incidents.json")
            if response.status_code == 200:
                new_network_weather_data = json.loads(response.text)
                if new_network_weather_data != self.network_weather_data:
                    self.network_weather_data = new_network_weather_data
        except ConnectionError as e:
            # Couldn't connect, try again next time
            pass


class DiscAnimationsImageController(ImageController):
    def __init__(self, settings):
        self.settings = settings
        super().__init__(None, settings)
        self.cols = self.active_cols
        self.rows = self.active_rows
        self.circle_colors = []
        color = 100
        for circle in disc.Disc.circles:
            self.circle_colors.append(color)
            color += 100

    def render(self):
        frame = []
        for idx, circle in enumerate(disc.Disc.circles):
            color = self.rainbow_color_from_value(self.circle_colors[idx])
            for n in range(0, circle[1]):
                frame.append(color)
            self.circle_colors[idx] += 7
            if self.circle_colors[idx] >= 1024:
                self.circle_colors[idx] = 0
        return (frame, 50)


def main():
    ctrl = MatrixController((("mock", True)))
    ctrl.debug = True
    if len(sys.argv) > 1:
        if sys.argv[1].endswith(".gif"):
            ctrl.set_frames(GifFileImageController((("filename", sys.argv[1]))).render())
        else:
            ctrl.set_frames(FileImageController((("filename", sys.argv[1]))).render())
    else:
        #ctrl.set_frames(TextImageController(animation="glitch").render())
        print(TextImageController(()).render())
        ctrl.set_frames(TextImageController(()).render())
    ctrl.show()
    while True:
        time.sleep(1000)


if __name__ == "__main__":
    main()

