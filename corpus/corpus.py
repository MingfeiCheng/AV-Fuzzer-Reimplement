# Copyright 2018 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Defines a set of objects that together describe the fuzzing input corpus."""

# pylint: disable=too-few-public-methods
class CorpusElement(object):
    """Class representing a single element of a corpus."""

    def __init__(self, scenario_id, scenario, fitness):
        """Inits the object. scenario - level, output contains multi trajs, each traj has one global index
        Args:
            scenario: a list of numpy arrays representing the mutated data.
            fitness: arbitrary python object to be used by the fuzzer for e.g. computing the objective function during the fuzzing loop.
            feat: an arbitrary hashable python object that guides fuzzing process. record path
        Returns:
          Initialized object.
        """
        self.scenario = scenario # input data
        self.fitness = fitness # simulator output - fitness score or others
        self.parent = None
        self.scenario_id = scenario_id

    def set_parent(self, parent):
        self.parent = parent

    def oldest_ancestor(self):
        """Returns the least recently created ancestor of this corpus item."""
        current_element = self
        generations = 0
        while current_element.parent is not None:
            current_element = current_element.parent
            generations += 1
        return current_element, generations
    
    # def rand_init(self, npc_size, time_size, bounds):
    #     for i in range(npc_size):        # For every NPC
    #         for j in range(time_size):    # For every time slice
    #             v = random.uniform(bounds[0][0], bounds[0][1])        # Init velocity
    #             a = random.randrange(bounds[1][0], bounds[1][1])      # Init action
    #             self.scenario[i][j].append(v)
    #             self.scenario[i][j].append(a)