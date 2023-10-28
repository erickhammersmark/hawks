# hawks

hawks, a system for running an electronic sign on an RGB LED matrix.

## Setup and installation
You can find information about building the hardware for this project at https://ninetypercentfinished.com/2019/10/29/12-sign-redux/.

Depends on PIL (Python Image Library), which you may need to install via your OS's package manager.  python3-pil 

Also depends on the FreeFonts TrueType package, which you may also need to install.  fonts-freefont-ttf 

You can find installation instructions for the Adafruit RGBMatrix library here:  https://learn.adafruit.com/adafruit-rgb-matrix-plus-real-time-clock-hat-for-raspberry-pi

## Examples

All you need to get started is to call `run_sign` and tell it to write to a mock rgbmatrix (your terminal).

`./run_sign --mock`

This should display a white-on-blue 12 in your terminal. You can now point a web browser at `http://localhost/` to adjust the settings, or hit the API endpoint. Try `http://localhost/api/help` to get started. You can also try `./run_sign --help` to see some of the settings you can change.

## Components

`matrixcontroller.MatrixController` runs the hardware: an RGBMatrix, a Dotstar Disc, or a mock matrix that outputs to the terminal. It has a property .settings with a list of the attributes you can set. You can set a brightness and a brightness_mask; every color of every pixel will be multiplied by brightness/255.0, but if brighness_mask exists, it will be assumed to be a list the same length as the number of pixels in the image, and each value will contain the brightness for that pixel. A brightness_mask value of -1 indicates that the configured system brightness should be used for that pixel. Call .set_frames() with a list of tuples of PIL.Image images and durations in ms. Call .set_image() with a single PIL.Image object.

`imagecontroller.ImageController` turns configuration into a set of frames for MatrixController. ImageController and all of its subclasses offer a .settings property that lists all the settings you can use to configure its behavior.
   * TextImageController renders text full-frame in the image.
   * FileImageController loads an image file
   * GifFileImageController loads an animated GIF file
   * NetworkWeatherImageController implements a "network weather" display.

`api_server.ApiServer` implements an API server. Configure it by calling .register_endpoint() with a path, a callback, and an optional list of methods. Launch it with .run(ip, port).

`disc.Disc` implements the logic to map the points on a DotStart disc to the points in a rectangular image.

`sample.py` is generic image sampling logic, consumed by Disc

`settings.Settings` is a simple key value store

`img_viewer.py` is a simple rgbmatrix image viewer

`hawks.Hawks` implements most of the logic of the sign

`mock.py` provides mock RGBMatrix and RGBMatrixOptions objects. The fake matrix will draw pixels in your terminal.

`hawks_api.py` consumes ApiServer and provides a hawks-sign specific set of API behaviors.

`run_sign` is the main executable for the hawks sign. Its arguments represent a subset of what you can configure with hawks_api.
