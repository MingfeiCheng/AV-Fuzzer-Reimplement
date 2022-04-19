#! /usr/bin/python3
import os
import collections
import pickle
import random

from corpus.corpus import CorpusElement
from mutation import tools

def get_all_checkpoints(ck_path):
    # ga_checkpoints_path
    only_files = os.listdir(ck_path)

    pre_pop_pool = []

    for i in range(len(only_files)):
        with open(ck_path+'/'+only_files[i], "rb") as f:
            if "generation" not in only_files[i]:
                continue
            try:
                pre_pop = pickle.load(f)
                pre_pop_pool.append(pre_pop)
            except Exception:
                pass

    return pre_pop_pool

def generate_restart_scenarios(runner, ga_logger, global_iter, ck_path, scenario_num, bounds):
	
	pre_pop_pool = get_all_checkpoints(ck_path)			 
	
	new_pop_candidate = []
	new_scenario_list = []
	pop_size = len(pre_pop_pool[0])
	npc_size = len(pre_pop_pool[0][0].scenario)
	time_size = len(pre_pop_pool[0][0].scenario[0])
	scenario_size = len(pre_pop_pool[0])
	pop_pool_size = len(pre_pop_pool)
	scenario_dict = {}

	for i in range(scenario_num):
		# 1. init scenario data (data)
		scenario_data = [[[] for _ in range(time_size)] for _ in range(npc_size)]

		for n_s in range(npc_size):
			for t_s in range(time_size):
				v = random.uniform(bounds[0][0], bounds[0][1]) # velocity
				a = random.randrange(bounds[1][0], bounds[1][1]) # action
				scenario_data[n_s][t_s].append(v)
				scenario_data[n_s][t_s].append(a)

		new_pop_candidate.append(scenario_data)

	# Go through every scenario

	for i in range(scenario_num):
		similarity = 0
		for j in range(pop_pool_size):
			simi_pop = 0
			for k in range(scenario_size):
				# TODO
				scenario1 = new_pop_candidate[i]
				scenario2 = pre_pop_pool[j][k].scenario
				simi = tools.get_similarity_between_scenarios(scenario1, scenario2)
				simi_pop += simi

			simi_pop /= scenario_size + 0.0
			similarity += simi_pop
		similarity /= pop_pool_size + 0.0
		scenario_dict[i] = similarity

	sorted_x = sorted(scenario_dict.items(), key=lambda kv: kv[1], reverse=True)
	sorted_dict = collections.OrderedDict(sorted_x)

	index = sorted_dict.keys()

	j = 0

	for i in index:
		if j == pop_size:
			break
		# run pop
		fitness, scenario_id = runner.run(new_pop_candidate[i])

		new_element = CorpusElement(scenario_id, new_pop_candidate[i], fitness)

		new_scenario_list.append(new_element)
		
		with open(ga_logger, 'a') as f:
			f.write('global_' + str(global_iter) + '_restart_' + str(j))
			f.write(',')
			f.write(scenario_id)
			f.write('\n')
		
		j += 1

	return new_scenario_list

def get_similarity_scenario_vs_pre_pop(scenario, pre_pop_pool):
	
	similarity = 0
	for i in pre_pop_pool:
		pop_similarity = 0
		for j in i:
			simi = tools.get_similarity_between_scenarios(j.scenario, scenario.scenario)
			pop_similarity += simi
		pop_similarity /= len(i)
		similarity += pop_similarity + 0.0
	similarity /= len(pre_pop_pool) + 0.0

	return similarity	