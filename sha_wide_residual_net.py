import six
import chainer
import numpy as np
import chainer.links as L
import chainer.functions as F
import nutszebra_chainer
import functools
from collections import defaultdict


class Conv(nutszebra_chainer.Model):

    def __init__(self, in_channel, out_channel, filter_size=(3, 3), stride=(1, 1), pad=(1, 1)):
        super(Conv, self).__init__(
            conv=L.Convolution2D(in_channel, out_channel, filter_size, stride, pad),
        )

    def weight_initialization(self):
        self.conv.W.data = self.weight_relu_initialization(self.conv)
        self.conv.b.data = self.bias_initialization(self.conv, constant=0)

    def __call__(self, x, train=False):
        return self.conv(x)

    def count_parameters(self):
        return functools.reduce(lambda a, b: a * b, self.conv.W.data.shape)


class BN_ReLU_Conv(nutszebra_chainer.Model):

    def __init__(self, in_channel=None, out_channel=None, filter_size=(3, 3), stride=(1, 1), pad=(1, 1), conv=None):
        super(BN_ReLU_Conv, self).__init__()
        modules = []
        if conv is None:
            modules += [('conv', L.Convolution2D(in_channel, out_channel, filter_size, stride, pad))]
            modules += [('bn', L.BatchNormalization(in_channel))]
        else:
            self.conv = conv
            modules += [('bn', L.BatchNormalization(conv.W.data.shape[1]))]
        # register layers
        [self.add_link(*link) for link in modules]
        self.modules = modules
        self.conv_flag = False if conv is None else True

    def weight_initialization(self):
        if self.conv_flag is False:
            self.conv.W.data = self.weight_relu_initialization(self.conv)
            self.conv.b.data = self.bias_initialization(self.conv, constant=0)

    def __call__(self, x, train=False):
        return self.conv(F.relu(self.bn(x, test=not train)))

    def count_parameters(self):
        if self.conv_flag is True:
            return 0
        else:
            return functools.reduce(lambda a, b: a * b, self.conv.W.data.shape)


class ShaWideResBlock(nutszebra_chainer.Model):

    def __init__(self, in_channel, out_channel, n=13, stride_at_first_layer=2):
        super(ShaWideResBlock, self).__init__()
        shared_conv = Conv(out_channel, out_channel)
        modules = []
        modules += [('shared_conv', shared_conv)]
        modules += [('bn_relu_conv1_1', BN_ReLU_Conv(in_channel, out_channel, 3, stride_at_first_layer, 1))]
        modules += [('bn_relu_conv2_1', BN_ReLU_Conv(conv=shared_conv.conv))]
        for i in six.moves.range(2, n + 1):
            modules.append(('bn_relu_conv1_{}'.format(i), BN_ReLU_Conv(out_channel, out_channel)))
            modules.append(('bn_relu_conv2_{}'.format(i), BN_ReLU_Conv(conv=shared_conv.conv)))
        # register layers
        [self.add_link(*link) for link in modules]
        self.modules = modules
        self.in_channel = in_channel
        self.out_channel = out_channel
        self.n = n
        self.stride_at_first_layer = stride_at_first_layer

    def weight_initialization(self):
        [link.weight_initialization() for _, link in self.modules]

    def count_parameters(self):
        return int(np.sum([link.count_parameters() for _, link in self.modules]))

    @staticmethod
    def concatenate_zero_pad(x, h_shape, volatile, h_type):
        _, x_channel, _, _ = x.data.shape
        batch, h_channel, h_y, h_x = h_shape
        if x_channel == h_channel:
            return x
        pad = chainer.Variable(np.zeros((batch, h_channel - x_channel, h_y, h_x), dtype=np.float32), volatile=volatile)
        if h_type is not np.ndarray:
            pad.to_gpu()
        return F.concat((x, pad))

    def maybe_pooling(self, x):
        if self.stride_at_first_layer == 2:
            return F.average_pooling_2d(x, 1, 2, 0)
        return x

    def __call__(self, x, train=False):
        h = self['bn_relu_conv1_1'](x, train=train)
        h = self['bn_relu_conv2_1'](h, train=train)
        x = h + ShaWideResBlock.concatenate_zero_pad(self.maybe_pooling(x), h.data.shape, h.volatile, type(h.data))
        for i in six.moves.range(2, self.n + 1):
            h = self['bn_relu_conv1_{}'.format(i)](x, train=train)
            x = self['bn_relu_conv2_{}'.format(i)](h, train=train) + x
        return x


class ShaWideResidualNetwork(nutszebra_chainer.Model):

    def __init__(self, category_num, block_num=3, out_channels=(16 * 4, 32 * 4, 64 * 4), N=(13, 13, 13)):
        super(ShaWideResidualNetwork, self).__init__()
        # conv
        modules = [('conv1', L.Convolution2D(3, 16, 3, 1, 1))]
        in_channel = 16
        strides = [1] + [2] * (block_num - 1)
        for i, out_channel, n, stride in six.moves.zip(six.moves.range(1, block_num + 1), out_channels, N, strides):
            modules.append(('wide_res_block{}'.format(i), ShaWideResBlock(in_channel, out_channel, n=n, stride_at_first_layer=stride)))
            in_channel = out_channel
        modules.append(('bn_relu_conv', BN_ReLU_Conv(in_channel, category_num, filter_size=(1, 1), stride=(1, 1), pad=(0, 0))))
        # register layers
        [self.add_link(*link) for link in modules]
        self.modules = modules
        self.category_num = category_num
        self.block_num = block_num
        self.out_channels = out_channels
        self.N = N
        self.name = 'wide_residual_network_{}_{}_{}_{}'.format(category_num, block_num, out_channels, N)

    def weight_initialization(self):
        self.conv1.W.data = self.weight_relu_initialization(self.conv1)
        self.conv1.b.data = self.bias_initialization(self.conv1, constant=0)
        for i in six.moves.range(1, self.block_num + 1):
            self['wide_res_block{}'.format(i)].weight_initialization()
        self.bn_relu_conv.weight_initialization()

    def __call__(self, x, train=False):
        h = self.conv1(x)
        for i in six.moves.range(1, self.block_num + 1):
            h = self['wide_res_block{}'.format(i)](h, train=train)
        h = self.bn_relu_conv(h, train=train)
        num, categories, y, x = h.data.shape
        h = F.reshape(F.average_pooling_2d(h, (y, x)), (num, categories))
        return h

    def count_parameters(self):
        count = 0
        count += functools.reduce(lambda a, b: a * b, self.conv1.W.data.shape)
        for i in six.moves.range(1, self.block_num + 1):
            count = count + self['wide_res_block{}'.format(i)].count_parameters()
        count += self.bn_relu_conv.count_parameters()
        return count

    def calc_loss(self, y, t):
        loss = F.softmax_cross_entropy(y, t)
        return loss

    def accuracy(self, y, t, xp=np):
        y.to_cpu()
        t.to_cpu()
        indices = np.where((t.data == np.argmax(y.data, axis=1)) == True)[0]
        accuracy = defaultdict(int)
        for i in indices:
            accuracy[t.data[i]] += 1
        indices = np.where((t.data == np.argmax(y.data, axis=1)) == False)[0]
        false_accuracy = defaultdict(int)
        false_y = np.argmax(y.data, axis=1)
        for i in indices:
            false_accuracy[(t.data[i], false_y[i])] += 1
        return accuracy, false_accuracy
