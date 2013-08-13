import cPickle as pickle
import itertools

import numpy as np
import theano
T = theano.tensor
F = theano.function

from pylearn2.costs.autoencoder import MeanBinaryCrossEntropy
from pylearn2.costs.gsn import GSNCost
from pylearn2.corruption import *
from pylearn2.datasets.mnist import MNIST
from pylearn2.distributions.parzen import ParzenWindows
from pylearn2.models.gsn import *
from pylearn2.termination_criteria import EpochCounter
from pylearn2.train import Train
from pylearn2.training_algorithms.sgd import SGD, MonitorBasedLRAdjuster
from pylearn2.utils import image, safe_zip, identity

HIDDEN_SIZE = 1000
SALT_PEPPER_NOISE = 0.4
GAUSSIAN_NOISE = 0.5

WALKBACK = 0

LEARNING_RATE = 0.2
MOMENTUM = 0.5

MAX_EPOCHS = 100
BATCHES_PER_EPOCH = None # covers full training set
BATCH_SIZE = 100

dataset = MNIST(which_set='train', one_hot=True)

layers = [dataset.X.shape[1], HIDDEN_SIZE]

vis_corruptor = SaltPepperCorruptor(SALT_PEPPER_NOISE)
pre_corruptor = GaussianCorruptor(GAUSSIAN_NOISE)
post_corruptor = GaussianCorruptor(GAUSSIAN_NOISE)

mbce = MeanBinaryCrossEntropy()
reconstruction_cost = lambda a, b: mbce.cost(a, b) / 784.0

def test_train_ae():
    gsn = GSN.new_ae(layers, vis_corruptor, pre_corruptor, post_corruptor)
    c = GSNCost([(0, 1.0, reconstruction_cost)], walkback=WALKBACK)
    alg = SGD(LEARNING_RATE, init_momentum=MOMENTUM, cost=c,
              termination_criterion=EpochCounter(5),
              batches_per_iter=BATCHES_PER_EPOCH, batch_size=BATCH_SIZE,
              monitoring_dataset={"test": MNIST(which_set='test')})

    trainer = Train(dataset, gsn, algorithm=alg, save_path="gsn_ae_example.pkl",
                    save_freq=5)
    trainer.main_loop()
    print "done training"

def test_train_supervised():
    raw_class_cost = MeanBinaryCrossEntropy()
    classification_cost = lambda a, b: raw_class_cost.cost(a, b) / 10.0

    """
    gsn = GSN.new(layers + [10], ["sigmoid", "tanh", plushmax],
                  [GaussianCorruptor(0.75), None, GaussianCorruptor(0.75)],
                  [SaltPepperCorruptor(0.3), None, SmoothOneHotCorruptor(0.75)],
                  [BinomialSampler(), None, MultinomialSampler()],
                  tied=False)
    """
    with open("pre_gsn_4.pkl", 'r') as f:
        gsn = pickle.load(f)
    del gsn.monitor


    gsn._layer_samplers = [identity] * 3
    cor = ComposedCorruptor(BinomialCorruptor(0.5), GaussianCorruptor(.75))
    gsn._postact_cors = [cor] * 3

    c = GSNCost(
        [
            (0, 1.0, reconstruction_cost),
            (2, 10.0, classification_cost)
        ],
        walkback=WALKBACK, mode='supervised')

    alg = SGD(LEARNING_RATE, init_momentum=MOMENTUM, cost=c,
              termination_criterion=EpochCounter(MAX_EPOCHS),
              batches_per_iter=BATCHES_PER_EPOCH, batch_size=BATCH_SIZE,
              monitoring_dataset=MNIST(which_set='train', one_hot=True),
              monitoring_batches=10, monitor_iteration_mode="shuffled_sequential"
              )

    trainer = Train(dataset, gsn, algorithm=alg, save_path="gsn_sup_example.pkl",
                    save_freq=5, extensions=[MonitorBasedLRAdjuster()])
    trainer.main_loop()
    print "done training"

def test_sample_ae():
    with open("gsn_ae_example.pkl") as f:
        gsn = pickle.load(f)

    mb_data = MNIST(which_set='test').X[105:106, :]

    history = gsn.get_samples([(0, mb_data)], walkback=1000,
                              symbolic=False, include_first=True)

    history = list(itertools.chain(*history))
    history = np.vstack(history)

    tiled = image.tile_raster_images(history,
                                     img_shape=[28,28],
                                     tile_shape=[50,50],
                                     tile_spacing=(2,2))
    image.save("gsn_ae_example.png", tiled)

    # code to get log likelihood from kernel density estimator
    # this crashed on GPU (out of memory), but works on CPU
    pw = ParzenWindows(MNIST(which_set='test').X, .20)
    print pw.get_ll(history)

def test_sample_supervised():
    with open("gsn_sup_example.pkl") as f:
        gsn = pickle.load(f)

    gsn = JointGSN.convert(gsn, 0, 2)
    gsn._corrupt_switch = False

    ds = MNIST(which_set='test', one_hot=True)
    mb_data = ds.X
    y = ds.y

    for i in xrange(1, 5):
        y_hat = gsn.classify(mb_data, trials=i)
        errors = np.abs(y_hat - y).sum() / 2.0

        print i, errors, errors / 10000.0

def vis_samples(samples):
    images = []
    labels = []
    for step in samples:
        assert len(step) == 2
        images.append(step[0])
        labels.append(np.argmax(step[1], axis=1))
    for i in xrange(len(images)):
        print "Step %s" % i
        print "Label: %s" % labels[i]
        print_char(images[0])
        print "-----------------------------"


# some utility methods for viewing MNIST characters without any GUI
def print_char(A):
    print a_to_s(A.round().reshape((28, 28)))

def a_to_s(A):
    """Prints binary array"""
    strs = []
    for row in A:
        x = [None] * len(row)
        for i, num in enumerate(row):
            if num != 0:
                x[i] = "@"
            else:
                x[i] = " "
        strs.append("".join(x))
    return "\n".join(strs)

if __name__ == '__main__':
    test_sample_supervised()
