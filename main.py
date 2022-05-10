import os
import sys
import yaml
import argparse

from loguru import logger
from datetime import datetime
from mutation.genetic_algorithm import GeneticMutator
from simulation.run_parse import Runner

level = "INFO"
logger.configure(handlers=[{"sink": sys.stderr, "level": level}]) # TODO: fix file output

class Fuzzer(object):

    def __init__(self, cfgs):
        now = datetime.now()
        date_time = now.strftime("%m-%d-%Y-%H-%M-%S")

        self.cfgs = cfgs
        cfgs['output_path'] = cfgs['output_path'] + '-at-' + date_time
        self.output_path = cfgs['output_path']
        self.scenario_name = os.path.basename(cfgs['scenario_env_json']).split('.')[0]

        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        log_file = os.path.join(self.output_path, 'logs/system.log')
        if os.path.exists(log_file):
            os.remove(log_file)
        logger.add(log_file, level=level)
        self.record_cfgs()

        self.runner = Runner(cfgs['scenario_env_json'],
                             self.output_path,
                             self.cfgs['total_sim_time'],
                             self.cfgs['default_record_folder'],
                             self.cfgs['lgsvl_map'],
                             self.cfgs['apollo_map'])
        self.mutation_runner = GeneticMutator(self.runner, self.cfgs['selection'], self.output_path, self.scenario_name, cfgs['bounds'], cfgs['p_mutation'], cfgs['p_crossover'], cfgs['pop_size'], cfgs['npc_size'], cfgs['time_size'], cfgs['max_gen'])
        self.mutation_runner.init_pop()
        logger.info('Initilized Genetic Mutator.')

    def loop(self):
        self.mutation_runner.process()

    def record_cfgs(self):
        logger.info('Record fuzzer configs:')
        for k, v in self.cfgs.items():
            logger.info(str(k) + ' : ' + str(v))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Apollo AV-Fuzzer Testing.')
    parser.add_argument('--config', type=str, help='Test config yaml file.', default='configs/config_ds_1.yaml')
    args = parser.parse_args()

    yaml_file = args.config
    with open(yaml_file, 'r') as f:
        params = yaml.safe_load(f)

    fuzzer = Fuzzer(params)
    fuzzer.loop()