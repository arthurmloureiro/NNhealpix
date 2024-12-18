# -*- encoding: utf-8 -*-

import numpy as np
import os.path
from tensorflow.keras.layers import Conv1D
import tensorflow.keras.backend as K
from tensorflow.keras.layers import Layer
import tensorflow as tf
import nnhealpix as nnh


class OrderMap(Layer):
    def __init__(self, indices, **kwargs):
        self.input_indices = np.array(indices, dtype="int32")
        
        # Validate indices during initialization and store for runtime clamping
        self.max_index = np.max(self.input_indices)
        self.min_index = np.min(self.input_indices)
        Kindices = K.variable(self.input_indices, dtype="int32")
        self.indices = K.stop_gradient(Kindices)
        super(OrderMap, self).__init__(**kwargs)

    def build(self, input_shape):
        """Create the weights for the layer"""
        self.in_shape = input_shape
        super(OrderMap, self).build(input_shape)

    def call(self, x):
        """Implement the layer's logic"""
        x = tf.cast(x, dtype=tf.float32)

        # Clamp indices dynamically to valid range
        n_pixels = tf.shape(x)[1]  # Number of pixels in the input
        clamped_indices = tf.clip_by_value(self.indices, 0, n_pixels - 1)

        # Add an extra row of zeros for out-of-bounds indices
        zero = tf.fill([tf.shape(x)[0], 1, tf.shape(x)[2]], 0.0)
        x1 = tf.concat([x, zero], axis=1)

        # Use clamped indices for reordering
        reordered = tf.gather(x1, clamped_indices, axis=1)
        return reordered

    def compute_output_shape(self, input_shape):
        """Compute the shape of the layer's output."""
        batch_size = input_shape[0]
        num_pixels = self.indices.shape[0]
        num_channels = input_shape[2]
        return (batch_size, num_pixels, num_channels)

    def get_config(self):
        """Return a dictionary containing the configuration for the layer."""
        config = super(OrderMap, self).get_config()
        config.update({"indices": self.input_indices})
        return config


def Dgrade(nside_in, nside_out):
    """Keras layer performing a downgrade of input maps

    Parameters
    ----------
    nside_in : integer
        Nside parameter for the input maps.
        Must be a valid healpix Nside value
    nside_out: integer
        Nside parameter for the output maps.
        Must be a valid healpix Nside value
    """

    file_in = os.path.join(
        os.path.dirname(__file__),
        "..",
        "ancillary_files",
        "dgrade_from{}_to{}.npy".format(nside_in, nside_out),
    )
    try:
        pixel_indices = np.load(file_in)
    except:
        pixel_indices = nnh.dgrade(nside_in, nside_out)

    def f(x):
        y = OrderMap(pixel_indices)(x)
        pool_size = int((nside_in / nside_out) ** 2.0)
        y = tf.keras.layers.AveragePooling1D(pool_size=pool_size)(y)
        return y

    return f

def Upsample(nside_in, factor):
    """Keras layer performing an upsampling of input HEALPix maps.

    Args:
        nside_in (integer): `NSIDE` parameter for the input maps.
        factor (integer): Upsampling factor (e.g., 2 to double the resolution).

    Returns:
        A Keras-compatible layer function for upsampling.
    """
    nside_out = nside_in * factor  # New NSIDE after upsampling

    file_in = os.path.join(
        os.path.dirname(__file__),
        "..",
        "ancillary_files",
        "upgrade_from{}_to{}.npy".format(nside_in, nside_out),
    )
    try:
        pixel_indices = np.load(file_in)
    except:
        pixel_indices = nnh.upgrade(nside_in, nside_out)

    def f(x):
        # Reorder the pixels to the upgraded resolution
        y = OrderMap(pixel_indices)(x)
        return y

    return f

def Pooling(nside_in, nside_out, layer1D, *args, **kwargs):
    """Keras layer performing a downgrade+custom pooling of input maps

    Args:
        * nside_in (integer): ``NSIDE`` parameter for the input maps.
        * nside_out (integer): ``NSIDE`` parameter for the output maps.
        * layer1D (layer object): a 1-D layer operation, like
          :code:`keras.layers.MaxPooling1D`
        * args (any): Positional arguments to be passed to :code:`layer1D`
        * kwargs: keyword arguments to be passed to
          :code:`layer1D`. The keyword :code:`pool_size` should not be
          included, as it is handled automatically.
    """

    file_in = os.path.join(
        os.path.dirname(__file__),
        "..",
        "ancillary_files",
        "dgrade_from{}_to{}.npy".format(nside_in, nside_out),
    )
    try:
        pixel_indices = np.load(file_in)
    except:
        pixel_indices = nnh.dgrade(nside_in, nside_out)

    def f(x):
        y = OrderMap(pixel_indices)(x)
        pool_size = int((nside_in / nside_out) ** 2.0)
        kwargs["pool_size"] = pool_size
        y = layer1D(*args, **kwargs)(y)
        return y

    return f


def MaxPooling(nside_in, nside_out):
    """Keras layer performing a downgrading+maxpooling of input maps

    Args:
        * nside_in (integer): ``NSIDE`` parameter for the input maps.
        * nside_out (integer): ``NSIDE`` parameter for the output maps.
    """

    return Pooling(nside_in, nside_out, tf.keras.layers.MaxPooling1D)


def AveragePooling(nside_in, nside_out):
    """Keras layer performing a downgrading+averaging of input maps

    Args:
        * nside_in (integer): ``NSIDE`` parameter for the input maps.
        * nside_out (integer): ``NSIDE`` parameter for the output maps.
    """

    return Pooling(nside_in, nside_out, tf.keras.layers.AveragePooling1D)


def DegradeAndConvNeighbours(
        nside_in, nside_out, filters, use_bias=False, trainable=True
):
    """Keras layer performing a downgrading and convolution of input maps.

    Args:
        * nside_in (integer): ``NSIDE`` parameter for the input maps.
        * nside_out (integer): ``NSIDE`` parameter for the output maps.
        * filters (integer): Number of filters to use in the
          convolution
        * use_bias (bool): Whether the layer uses a bias vector or
          not. Default is ``False``.
        * trainable (bool): Wheter this is a trainable layer or
          not. Default is ``True``.

    """

    file_in = os.path.join(
        os.path.dirname(__file__),
        "..",
        "ancillary_files",
        "dgrade_from{}_to{}.npy".format(nside_in, nside_out),
    )
    try:
        pixel_indices = np.load(file_in)
    except:
        pixel_indices = nnh.dgrade(nside_in, nside_out)

    def f(x):
        y = OrderMap(pixel_indices)(x)
        kernel_size = int((nside_in / nside_out) ** 2.0)
        y = Conv1D(
            filters,
            kernel_size=kernel_size,
            strides=kernel_size,
            use_bias=use_bias,
            trainable=trainable,
            kernel_initializer="random_uniform",
        )(y)
        return y

    return f


def ConvNeighbours(nside, kernel_size, filters, use_bias=False, trainable=True):
    """Keras layer to perform pixel neighbour convolution.

    Args:
        * nside(integer): ``NSIDE`` parameter for the input maps.
        * kernel_size(integer): Dimension of the kernel. Currently,
          NNhealpix only supports ``kernelsize = 9`` (first-order
          convolution).
        * filters(integer): Number of filters to use in the
          convolution
        * use_bias(bool): Whether the layer uses a bias vector or
          not. Default is ``False``.
        * trainable(bool): Wheter this is a trainable layer or
          not. Default is ``True``.

    """

    if kernel_size != 9:
        raise ValueError("kernel size must be 9")

    file_in = nnh.filter_file_name(nside, kernel_size)
    try:
        pixel_indices = np.load(file_in)
    except:
        pixel_indices = nnh.filter(nside)

    def f(x):
        y = OrderMap(pixel_indices)(x)
        y = Conv1D(
            filters,
            kernel_size=kernel_size,
            strides=kernel_size,
            use_bias=use_bias,
            trainable=trainable,
        )(y)
        return y

    return f
