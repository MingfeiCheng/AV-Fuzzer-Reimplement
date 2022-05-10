import os
import copy
import random
import pickle
import shutil

from datetime import datetime
from loguru import logger
from mutation import restart

class LocalGeneticMutator(object):
    def __init__(self, runner, selection, output_path, global_iter, ga_logger, progress_logger, scenario_name, bounds, pm, pc, pop_size, NPC_size, time_size, max_gen):
        self.pop = []
        self.bounds = bounds                # The value ranges of the inner most elements
        self.pm = pm
        self.pc = pc
        self.pop_size = pop_size            # Number of scenarios in the population
        self.NPC_size = NPC_size            # Number of NPC in each scenario
        self.time_size = time_size          # Number of time slides in each NPC
        self.max_gen = max_gen
        self.bests = [0] * max_gen
        self.bestIndex = 0
        self.g_best = None
        self.touched_chs = []             # Record which chromosomes have been touched in each generation

        self.minLisGen = 2                  # Min gen to start LIS
        self.numOfGenInLis = 5              # Number of gens in LIS
        self.hasRestarted = False
        self.lastRestartGen = 0
        self.bestYAfterRestart = 0

        self.runner = runner
        self.selection = selection
        self.scenario_name = scenario_name
        self.output_path = output_path
        self.ga_checkpoints_path = os.path.join(self.output_path, 'logs/checkpoints_ga')

        if os.path.exists(self.ga_checkpoints_path):
            shutil.rmtree(self.ga_checkpoints_path)
        os.makedirs(self.ga_checkpoints_path)
        
        # TODO: add inner log
        self.ga_log = ga_logger
        self.progress_log = progress_logger
        self.global_iter = global_iter

    
    def take_checkpoint(self, obj, ck_name):
        ck_file = os.path.join(self.ga_checkpoints_path, ck_name)
        with open(ck_file, 'wb') as ck_f:
            pickle.dump(obj, ck_f)

    def setLisPop(self, singleChs):
        for i in range(self.pop_size):
            self.pop.append(copy.deepcopy(singleChs))

        # Add some entropy
        tempPm = self.pm
        self.pm = 1
        self.mutation(0)
        self.pm = tempPm
        self.g_best, bestIndex = self.find_best()

    def cross(self):
        # Implementation of random crossover

        for i in range(int(self.pop_size / 2.0)):
            # Check crossover probability
            if self.pc > random.random():
            # randomly select 2 chromosomes(scenarios) in pops
                i = 0
                j = 0
                while i == j:
                    i = random.randint(0, self.pop_size-1)
                    j = random.randint(0, self.pop_size-1)
                pop_i = self.pop[i]
                pop_j = self.pop[j]

                # Record which chromosomes have been touched
                self.touched_chs.append(i)
                self.touched_chs.append(j)

                # Every time we only switch one NPC between scenarios
                # select cross index
                swap_index = random.randint(0, self.NPC_size - 1)

                temp = copy.deepcopy(pop_j.scenario[swap_index])
                pop_j.scenario[swap_index] = copy.deepcopy(pop_i.scenario[swap_index])
                pop_i.scenario[swap_index] = temp
        # cross: generate new elements

    def mutation(self, ga_iter):

        i = 0
        while i < len(self.pop) :
            eachChs = self.pop[i]
            
            if self.pm >= random.random():
                
                beforeMutation = copy.deepcopy(eachChs)
                # select mutation index
                npc_index = random.randint(0, self.NPC_size - 1)
                time_index = random.randint(0, self.time_size - 1)

                # Record which chromosomes have been touched
                self.touched_chs.append(i)
                actionIndex = random.randint(0, 1)
                
                if actionIndex == 0:
                    # Change Speed
                    eachChs.scenario[npc_index][time_index][0] = random.uniform(self.bounds[0][0], self.bounds[0][1])
                elif actionIndex == 1:
                    # Change direction
                    eachChs.scenario[npc_index][time_index][1] = random.randrange(self.bounds[1][0], self.bounds[1][1])
            i += 1
        
        logger.info('Generate ' + str(len(self.touched_chs)) + ' mutated scenarios')
        # Only run simulation for the chromosomes that are touched in this generation
        self.touched_chs = set(self.touched_chs)
        for i in self.touched_chs:
            before_fitness = eachChs.fitness
            eachChs = self.pop[i]
            fitness, scenario_id = self.runner.run(eachChs.scenario)
            # 2. creat new elements or update fitness_score and coverage feat
            eachChs.fitness = fitness
            eachChs.scenario_id = scenario_id
            after_fitness = eachChs.fitness

            with open(self.ga_log, 'a') as f:
                f.write('global_' + str(self.global_iter) + '_local_' + str(ga_iter))
                f.write(',')
                f.write(scenario_id)
                f.write(',')
                f.write('before run:' + str(before_fitness))
                f.write(',')
                f.write('after run:' + str(after_fitness))
                f.write('\n')
    
    def select_roulette(self):

        sum_f = 0
        for i in range(0, self.pop_size):
            if self.pop[i].fitness == 0:
                self.pop[i].fitness = 0.001

        ############################################################
        min_fitness = self.pop[0].fitness
        for k in range(0, self.pop_size):
            if self.pop[k].fitness < min_fitness:
                min_fitness = self.pop[k].fitness
        if min_fitness < 0:
            for l in range(0, self.pop_size):
                self.pop[l].fitness = self.pop[l].fitness + (-1) * min_fitness

        # roulette
        for i in range(0, self.pop_size):
            sum_f += self.pop[i].fitness
        p = [0] * self.pop_size
        for i in range(0, self.pop_size):
            if sum_f == 0:
                sum_f = 1
            p[i] = self.pop[i].fitness / sum_f
        q = [0] * self.pop_size
        q[0] = 0
        for i in range(0, self.pop_size):
            s = 0
            for j in range(0, i+1):
                s += p[j]
            q[i] = s

        # start roulette
        v = []
        for i in range(0, self.pop_size):
            r = random.random()
            if r < q[0]:
                v.append(copy.deepcopy(self.pop[0]))
            for j in range(1, self.pop_size):
                if q[j - 1] < r <= q[j]:
                    v.append(copy.deepcopy(self.pop[j]))
        self.pop = copy.deepcopy(v)

    def select_top2(self):
        maxFitness = 0
        v = []
        for i in range(0, self.pop_size):
            if self.pop[i].fitness > maxFitness:
                maxFitness = self.pop[i].fitness

        for i in range(0, self.pop_size):
            if self.pop[i].fitness == maxFitness:
                for j in range(int(self.pop_size / 2.0)):
                    v.append(copy.deepcopy(self.pop[i]))
                break

        max2Fitness = 0
        for i in range(0, self.pop_size):
            if self.pop[i].fitness > max2Fitness and self.pop[i].fitness != maxFitness:
                max2Fitness = self.pop[i].fitness

        for i in range(0, self.pop_size):
            if self.pop[i].fitness == max2Fitness:
                for j in range(int(self.pop_size / 2.0)):
                    v.append(copy.deepcopy(self.pop[i]))
                break

        self.pop = copy.deepcopy(v)

    def find_best(self):
        best = copy.deepcopy(self.pop[0]) # element object
        bestIndex = 0
        for i in range(self.pop_size):
            if best.fitness < self.pop[i].fitness:
                best = copy.deepcopy(self.pop[i])
                bestIndex = i
        return best, bestIndex
    
    def process(self, global_generation_id):
        
        best, bestIndex = self.find_best()
        self.g_best = copy.deepcopy(best)

        # Start evolution
        for i in range(self.max_gen):                       # i th generation.

            logger.info("Local Generation of " + str(global_generation_id) + ": * " + str(i) + "th generation *")
            
            # Make sure we clear touched_chs history book every gen
            self.touched_chs = []
            self.cross()
            self.mutation(i)
            if self.selection == 'top':
                self.select_top2()
            elif self.selection == 'roulette':
                self.select_roulette()
            else:
                raise RuntimeError('Selection methods require: top or roulette.')      

            best, bestIndex = self.find_best()                     # Find the scenario with the best fitness score in current generation 
            self.bests[i] = best                        # Record the scenario with the best fitness score in i th generation

            if self.g_best.fitness < best.fitness:                  # Record the best fitness score across all generations
                self.g_best = copy.deepcopy(best)

            N_generation = self.pop
            N_b = self.g_best                           # Record the scenario with the best score over all generations

            # Update the checkpoint of the best scenario so far
            self.take_checkpoint(N_b, 'best_scenario.obj')                       

            # Checkpoint this generation
            self.take_checkpoint(N_generation, 'last_gen.obj')

            # Checkpoint every generation
            now = datetime.now()
            date_time = now.strftime("%m-%d-%Y-%H-%M-%S")
            self.take_checkpoint(N_generation, 'generation-' + str(i) + '-at-' + date_time)

            if os.path.exists(self.ga_checkpoints_path) == True:
                prePopPool = restart.get_all_checkpoints(self.ga_checkpoints_path) 
                simiSum = 0
                for eachChs in self.pop:
                    eachSimilarity =  restart.get_similarity_scenario_vs_pre_pop(eachChs, prePopPool)
                    simiSum += eachSimilarity
                # util.print_debug(" ==== Similarity compared with all prior generations: " + str(simiSum/float(self.pop_size)))

            # Log fitness etc
            with open(self.progress_log, 'a') as f:
                f.write('global_' + str(self.global_iter) + '_local_' + str(i) + " " + str(best.fitness) + " " + str(self.g_best.fitness) + " " + str(simiSum/float(self.pop_size)) + " " + date_time + "\n")

        return self.g_best
 