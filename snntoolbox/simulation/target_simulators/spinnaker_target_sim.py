# -*- coding: utf-8 -*-
"""
Building and simulating spiking neural networks using
`pyNN <http://neuralensemble.org/docs/PyNN/>`_.

# http://spinnakermanchester.github.io/development/devenv.html
# you have to install this version of spynnaker above for the script to work (please note that some changes
#have to be made in spynnaker script due to compatibilty)
# modified /bin/utils.py to add in spynnaker8 as a simulator and add in config.defaults as one of the simulators.

@author: piewchee, rbodo
"""

from __future__ import division, absolute_import
from __future__ import print_function, unicode_literals

import os
import warnings
import csv
import json

import numpy as np
from future import standard_library
from six.moves import cPickle

from snntoolbox.utils.utils import confirm_overwrite
from snntoolbox.simulation.utils import AbstractSNN
from pyNN.utility.plotting import Figure, Panel
import matplotlib.pyplot as plt


standard_library.install_aliases()


cellparams_pyNN = {'v_thresh', 'v_reset', 'v_rest', 'e_rev_E', 'e_rev_I', 'cm',
                   'i_offset', 'tau_refrac', 'tau_m', 'tau_syn_E', 'tau_syn_I'}


class SNN(AbstractSNN):
    """Class to hold the compiled spiking neural network.

    Represents the compiled spiking neural network, ready for testing in a
    spiking simulator.

    Attributes
    ----------

    layers: list[pyNN.Population]
        Each entry represents a layer, i.e. a population of neurons, in form of
        pyNN ``Population`` objects.

    connections: list[pyNN.Projection]
        pyNN ``Projection`` objects representing the connections between
        individual layers.

    cellparams: dict
        Neuron cell parameters determining properties of the spiking neurons in
        pyNN simulators.
    """

    def __init__(self, config, queue=None):

        AbstractSNN.__init__(self, config, queue)

        self.layers = []
        self._conns = []  # Temporary container for layer connections (excitatory neuron).
        self._inconns = [] # Temporary container for layer connections (inhibitory neuron). 
        self._con_exconns = [] # Temporary container for convolution layer connections (excitatory neuron).
        self._con_inconns = [] # Temporary container for  convolution layer connections (inhibitory neuron).
        self._biases = []  # Temporary container for layer biases.
        self.connections = []  # Final container for all layers.
        self.cellparams = {key: config.getfloat('cell', key) for key in
                           cellparams_pyNN}

    @property
    def is_parallelizable(self):
        return False
  
    def input_spike(self):
        with  open('/media/mikat3/92d61e88-74ff-49dd-8e8b-5f1ea9ec3eb7/home/mikat2/snn_toolbox/1.txt', 'r') as f:
              data = f.read()
              data = json.loads(data)
              #print('json',data)
              spiketrains=data

        return spiketrains


    def add_input_layer(self, input_shape):

        #self.sim.set_number_of_neurons_per_core(self.sim.SpikeSourcePoisson, 100) # limit number of neurons per core for input spike source 

   
        self.layers.append(self.sim.Population(
            np.asscalar(np.prod(input_shape[1:], dtype=np.int)),
            self.sim.SpikeSourcePoisson(), label='InputLayer'))


    def add_layer(self, layer):

        if 'Flatten' in layer.__class__.__name__:
            return

        self._conns = []
        self.sim.set_number_of_neurons_per_core(self.sim.IF_cond_exp, 140) # limit number of neurons per core
        self.layers.append(self.sim.Population(
            np.asscalar(np.prod(layer.output_shape[1:], dtype=np.int)),
            self.sim.IF_cond_exp, self.cellparams, label=layer.name))


    def build_dense(self, layer):
        """

        Parameters
        ----------
        layer : keras.layers.Dense

        Returns
        -------

        """

        if layer.activation.__name__ == 'softmax':
            warnings.warn("Activation 'softmax' not implemented. Using 'relu' "
                          "activation instead.", RuntimeWarning)

        weights, biases = layer.get_weights()
        self._biases = np.array(biases, 'float64')
        self.set_biases()
        delay = self.config.getfloat('cell', 'delay')

        for i in range(weights.shape[0]):
           for j in range(weights.shape[1]):
               if weights[i,j] >= 0:
                   self._conns.append((i, j, weights[i, j], delay))
               else:
                   self._inconns.append((i, j, weights[i, j], delay))

        print("layer name {}".format(layer.name))

        #self.connections.append(self.sim.Projection(
        #    self.layers[-2], self.layers[-1],
        #    self.sim.FromListConnector(self._conns, ['weight', 'delay'])))
  
        self.proj_ex=self.sim.Projection(
           self.layers[-2], self.layers[-1],
           self.sim.FromListConnector(self._conns, ['weight', 'delay']), receptor_type='excitatory')
         
        self.connections.append(self.proj_ex) 

        self.proj_in=self.sim.Projection(
           self.layers[-2], self.layers[-1],
           self.sim.FromListConnector(self._inconns, ['weight', 'delay']), receptor_type='inhibitory')

        self.connections.append(self.proj_in) 



    def build_convolution(self, layer):
        from snntoolbox.simulation.utils import build_convolution

        delay = self.config.getfloat('cell', 'delay')
        transpose_kernel = \
            self.config.get('simulation', 'keras_backend') == 'tensorflow'
        self._conns, self._biases = build_convolution(layer, delay,
                                                      transpose_kernel)
        print("layer name {}".format(layer.name))
    
        weights= self._conns
        for i, w in enumerate(weights):
            if w[2] >=0:
               self._con_exconns.append(w)
            else:
               self._con_inconns.append(w)

        self.set_biases()
        #self.connections.append(self.sim.Projection(
        #   self.layers[-2], self.layers[-1],
        #   self.sim.FromListConnector(self._conns, ['weight', 'delay'])))

        self.proj_excon=self.sim.Projection(
           self.layers[-2], self.layers[-1],
           self.sim.FromListConnector(self._con_exconns, ['weight', 'delay']), receptor_type='excitatory')
  
        self.connections.append(self.proj_excon) 

        self.proj_incon=self.sim.Projection(
           self.layers[-2], self.layers[-1],
           self.sim.FromListConnector(self._con_inconns, ['weight', 'delay']), receptor_type='inhibitory')
 
        self.connections.append(self.proj_incon)


    def build_pooling(self, layer):
        from snntoolbox.simulation.utils import build_pooling

        delay = self.config.getfloat('cell', 'delay')
        self._conns = build_pooling(layer, delay)
        print("layer name {}".format(layer.name))

        self.connections.append(self.sim.Projection(
            self.layers[-2], self.layers[-1],
            self.sim.FromListConnector(self._conns, ['weight', 'delay'])))

        #self.proj=self.sim.Projection(
        #  self.layers[-2], self.layers[-1],
        #  self.sim.FromListConnector(self._conns, ['weight', 'delay']))


    def compile(self):

        pass

    def simulate(self, **kwargs):

        if self._poisson_input:
            rates = kwargs[str('x_b_l')].flatten()
            spiketrains = []
            spiketrains = list(rates*500)
            #for neuron_idx, neuron in enumerate(self.layers[0]):
                #neuron._rate= rates[neuron_idx]  / self.rescale_fac*1000 
                #self.layers[0].set(rate=neuron._rate) #rates[neuron_idx]  / self.rescale_fac*1000)
                #spiketrains =neuron._rate
            #spiketrains = list(neuron._rate) 

            self.layers[0].set(rate=spiketrains)

        elif self._dataset_format == 'aedat':
            raise NotImplementedError
        else:
            constant_input_currents = kwargs[str('x_b_l')].flatten()
            try:
                for neuron_idx, neuron in enumerate(self.layers[0]):
                    # TODO: Implement constant input currents.
                    neuron.current = constant_input_currents[neuron_idx]
            except AttributeError:
                raise NotImplementedError

        def get_spiketrains_nest():
            shape = list(self.parsed_model.input_shape) + [self._num_timesteps]
            spiketrains_b_l_t_nest = self.reshape_flattened_spiketrains(spiketrains_flat_nest,
                                                               shape)
            return spiketrains_b_l_t_nest


        self.sim.run(self._duration) # - self._dt)
       
        self.layers[0].record(['spikes'])


        layer = self.layers[0]

        spikes = layer.get_data('spikes')

        output_b_l_t = self.get_recorded_vars(self.layers)
        print('output spike no.', output_b_l_t)
        return output_b_l_t

    def reset(self, sample_idx):
         
        mod = self.config.getint('simulation', 'reset_between_nth_sample')
        mod = mod if mod else sample_idx + 1
        if sample_idx % mod == 0:
            print("Resetting simulator...")
            self.sim.reset()
            print("Done.")

    def end_sim(self):

        self.sim.end()
    
    def save(self, path, filename):

        print("Saving model to {}...".format(path))
        self.save_assembly(path, filename)
        #self.save_connections(path) # disabled "save connections due to syntax error".
        print("Done.\n")

    def load(self, path, filename):

        self.layers = self.load_assembly(path, filename)
        for i in range(len(self.layers)-1):
            filepath = os.path.join(path, self.layers[i+1].label)
            assert os.path.isfile(filepath), \
                "Connections were not found at specified location."
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                warnings.warn('deprecated', UserWarning)
                self.sim.Projection(self.layers[i], self.layers[i+1],
                                    self.sim.FromFileConnector(filepath))

    def init_cells(self):

        vars_to_record = self.get_vars_to_record()

        if 'spikes' in vars_to_record:
            self.layers[0].record([str('spikes')])  # Input layer has no 'v'

        for layer in self.layers[1:]:
            layer.set(**self.cellparams)
            layer.initialize(v=layer.get('v_rest')) 
            layer.record(vars_to_record)

        # The spikes of the last layer are recorded by default because they
        # contain the networks output (classification guess).
        if 'spikes' not in vars_to_record:
            vars_to_record.append(str('spikes'))
            self.layers[-1].record(vars_to_record)

    def set_biases(self):
        """Set biases.

        Notes
        -----

        This has not been tested yet.
        """

        if not np.any(self._biases):
            return

        warnings.warn("Biases are implemented but might have no effect. "
                      "Please check!", RuntimeWarning)
        self.layers[-1].set(i_offset=self._biases * self._dt)

    def get_vars_to_record(self):
        """Get variables to record during simulation.

        Returns
        -------

        vars_to_record: list[str]
            The names of variables to record during simulation.
        """

        vars_to_record = []

        if any({'spiketrains', 'spikerates', 'correlation', 'spikecounts',
                'hist_spikerates_activations'} & self._plot_keys) \
                or 'spiketrains_n_b_l_t' in self._log_keys:
            vars_to_record.append(str('spikes'))

        if 'mem_n_b_l_t' in self._log_keys or 'v_mem' in self._plot_keys:
            vars_to_record.append(str('v'))

        return vars_to_record

    def get_spiketrains(self, **kwargs):
        j = self._spiketrains_container_counter
        if self.spiketrains_n_b_l_t is None \
                or j >= len(self.spiketrains_n_b_l_t):
            return None

        shape = self.spiketrains_n_b_l_t[j][0].shape

        # Outer for-loop that calls this function starts with
        # 'monitor_index' = 0, but this is reserved for the input and handled by
        # `get_spiketrains_input()`.
        i = len(self.layers) - 1 if kwargs[str('monitor_index')] == -1 else \
            kwargs[str('monitor_index')] + 1
        spiketrains_flat = self.layers[i].get_data().segments[-1].spiketrains
        counts=0

        spiketrains_b_l_t = self.reshape_flattened_spiketrains(spiketrains_flat,
                                                               shape)
        return spiketrains_b_l_t

    def get_spiketrains_input(self):
        shape = list(self.parsed_model.input_shape) + [self._num_timesteps]
        spiketrains_flat = self.layers[0].get_data().segments[-1].spiketrains
        spiketrains_b_l_t = self.reshape_flattened_spiketrains(spiketrains_flat,
                                                               shape)
        return spiketrains_b_l_t

    def get_spiketrains_output(self):
        shape = [self.batch_size, self.num_classes, self._num_timesteps]
        spiketrains_flat = self.layers[-1].get_data().segments[-1].spiketrains
        spiketrains_b_l_t = self.reshape_flattened_spiketrains(spiketrains_flat,
                                                               shape)
        return spiketrains_b_l_t

    def get_vmem(self, **kwargs):
        vs = kwargs[str('layer')].get_data().segments[-1].analogsignals
        #print('Spike_Voltage', vs)
        if len(vs) > 0:

            return np.array([np.swapaxes(v, 0, 1) for v in vs])

    def save_assembly(self, path, filename):
        """Write layers of neural network to disk.

        The size, structure, labels of all the population of an assembly are
        stored in a dictionary such that one can load them again using the
        `load_assembly` function.

        The term "assembly" refers to pyNN internal nomenclature, where
        ``Assembly`` is a collection of layers (``Populations``), which in turn
        consist of a number of neurons (``cells``).

        Parameters
        ----------

        path: str
            Path to directory where to save layers.

        filename: str
            Name of file to write layers to.
        """

        filepath = os.path.join(path, filename)

        if not (self.config.getboolean('output', 'overwrite') or
                confirm_overwrite(filepath)):
            return

        print("Saving assembly...")

        s = {}
        labels = []
        variables = ['size', 'structure', 'label']
        for population in self.layers:
            labels.append(population.label)
            data = {}
            for variable in variables:
                data[variable] = getattr(population, variable)
            data['celltype'] = population.celltype.describe()
            if population.label != 'InputLayer':
                data['i_offset'] = population.get('i_offset')
            s[population.label] = data
        s['labels'] = labels  # List of population labels describing the net.
        s['variables'] = variables  # List of variable names.
        s['size'] = len(self.layers)  # Number of populations in assembly.
        cPickle.dump(s, open(filepath, 'wb'), -1) 

    def save_connections(self, path):
        """Write parameters of a neural network to disk.

        The parameters between two layers are saved in a text file.
        They can then be used to connect pyNN populations e.g. with
        ``sim.Projection(layer1, layer2, sim.FromListConnector(filename))``,
        where ``sim`` is a simulator supported by pyNN, e.g. Brian, NEURON, or
        NEST.

        Parameters
        ----------

        path: str
            Path to directory where connections are saved.

        Return
        ------

            Text files containing the layer connections. Each file is named
            after the layer it connects to, e.g. ``layer2.txt`` if connecting
            layer1 to layer2.
        """

        print("Saving connections...")

        # Iterate over layers to save each projection in a separate txt file.
        for i,  projection in enumerate(self.connections):
            filepath = os.path.join(path,self.layers[i+1].label) 
            print('chee', filepath)
           # filepath = os.path.join(path, projection.label.partition('→')[-1])
            #print('i=', i)
            #if hasattr(projection, 'label'):
            #      filename = projection.label.partition('→')[-1] # if hasattr(projection, 'label')
            #else: filename= 'layer_'+ str(i)
            #filepath =  os.path.join(path, filename)
            #print('filepath=', filepath)

            if self.config.getboolean('output', 'overwrite') or \
                    confirm_overwrite(filepath):
                projection.save('connections', filepath)

    def load_assembly(self, path, filename):
        """Load the populations in an assembly.

        Loads the populations in an assembly that was saved with the
        `save_assembly` function.

        The term "assembly" refers to pyNN internal nomenclature, where
        ``Assembly`` is a collection of layers (``Populations``), which in turn
        consist of a number of neurons (``cells``).

        Parameters
        ----------

        path: str
            Path to directory where to load model from.

        filename: str
            Name of file to load model from.

        Returns
        -------

        layers: list[pyNN.Population]
            List of pyNN ``Population`` objects.
        """

        import sys

        filepath = os.path.join(path, filename)
        assert os.path.isfile(filepath), \
            "Spiking neuron layers were not found at specified location."
        if sys.version_info < (3,):
            s = cPickle.load(open(filepath, 'rb'))
        else:
            s = cPickle.load(open(filepath, 'rb'), encoding='bytes')

        # Iterate over populations in assembly
        layers = []
        for label in s['labels']:
            celltype = getattr(self.sim, s[label]['celltype'])
            population = self.sim.Population(s[label]['size'], celltype,
                                             celltype.default_parameters,
                                             structure=s[label]['structure'],
                                             label=label)
            # Set the rest of the specified variables, if any.
            for variable in s['variables']:
                if getattr(population, variable, None) is None:
                    setattr(population, variable, s[label][variable])
            if label != 'InputLayer':
                population.set(i_offset=s[label]['i_offset'])
            layers.append(population)

        return layers

    def set_spiketrain_stats_input(self):
        AbstractSNN.set_spiketrain_stats_input(self)
