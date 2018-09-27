import numpy as np
import keras
import os.path
from keras.layers import Conv1D
import keras.backend as K
from keras.engine.topology import Layer
import tensorflow as tf
import nnhealpix.map_ordering


class OrderMap(Layer):
    def __init__(self, indices, **kwargs):
        Kindices = K.variable(indices, dtype='int32')
        self.indices = Kindices
        super(OrderMap, self).__init__(**kwargs)
    def build(self, input_shape):
        self.in_shape = input_shape
        super(OrderMap, self).build(input_shape)
    def call(self, x):
        x = tf.to_float(x)
        zero = tf.fill([tf.shape(x)[0], 1, tf.shape(x)[2]], 0.)
        x1 = tf.concat([x, zero], axis=1)
        reordered = tf.gather(x1, self.indices, axis=1)
        self.output_dim = reordered.shape
        return reordered
    def compute_output_shape(self, input_shape):
        return (
            input_shape[0], int(self.output_dim[1]), int(self.output_dim[2]))

def Dgrade(nside_in, nside_out):
    file_in = os.path.join(
        os.path.dirname(__file__),
        '../ancillary_files/dgrade_from{}_to{}'.format(nside_in, nside_out))
    try:
        pixel_indices = np.load(file_in)
    except:
        pixel_indices = nnhealpix.map_ordering.dgrade(nside_in, nside_out)
    def f(x):
        y = OrderMap(pixel_indices)(x)
        pool_size=int((nside_in/nside_out)**2.)
        y = keras.layers.AveragePooling1D(pool_size=pool_size)(y)
        return y
    return f

def ConvPixel(nside_in, nside_out, filters, use_bias=False, trainable=True):
    file_in = os.path.join(
        os.path.dirname(__file__),
        '../ancillary_files/dgrade_from{}_to{}'.format(nside_in, nside_out))
    try:
        pixel_indices = np.load(file_in)
    except:
        pixel_indices = nnhealpix.map_ordering.dgrade(nside_in, nside_out)
    def f(x):
        y = OrderMap(pixel_indices)(x)
        kernel_size = (nside_in/nside_out)**2.
        y = keras.layers.Conv1D(
            filters, kernel_size=kernel_size, strides=kernel_size,
            use_bias=use_bias, trainable=trainable)(y)
        return y
    return f

def ConvNeighbours(nside, kernel_size, filters, use_bias=False, trainable=True):
    if kernel_size!=9:
        raise ValueError('kernel size must be 9')
    file_in = os.path.join(
        os.path.dirname(__file__),
        '../ancillary_files/filter{}_nside{}.npy'.format(kernel_size, nside))
    try:
        pixel_indices = np.load(file_in)
    except:
        pixel_indices = nnhealpix.map_ordering.filter9(nside)
    def f(x):
        y = OrderMap(pixel_indices)(x)
        y = keras.layers.Conv1D(
            filters, kernel_size=kernel_size, strides=kernel_size,
            use_bias=use_bias, trainable=trainable)(y)
        return y
    return f