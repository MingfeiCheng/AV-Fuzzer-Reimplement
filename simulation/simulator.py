import os
import lgsvl
import time
import json

import simulation.utils as util
import simulation.liability as liability

from datetime import datetime
from loguru import logger

EGO_VEHICLE_ID = '2e966a70-4a19-44b5-a5e7-64e00a7bc5de'

class Simulator(object):

    def __init__(self, default_record_folder, target_record_folder, total_sim_time, lgsvl_map = 'SanFrancisco_correct', apollo_map = 'SanFrancisco'):
        
        self.default_record_folder = default_record_folder
        self.target_record_folder = target_record_folder
        ################################################################
        self.total_sim_time = total_sim_time
        self.destination = None
        ################################################################
        self.sim = None
        self.data_prime = None
        self.dv = None
        self.lgsvl_map = lgsvl_map
        self.apollo_map = apollo_map
        self.ego = None
        self.mutated_npc_list = [] # The list contains all the npc added
        self.fixed_npc_list = []
        self.yellow_lines = None
        self.cross_lines = None
        self.edge_lines = None

        self.connect_lgsvl()
        self.load_map(self.lgsvl_map)
        self.isEgoFault = False
        self.isHit = False
        self.maxint = 130
        self.egoFaultDeltaD = 0

        self.modules = [
            'Localization',
            'Transform',
            'Routing',
            'Prediction',
            'Planning',
            'Control',
            'Storytelling',
        ]
        self.dy_modules = [
            'Recorder',
        ]

    def connect_lgsvl(self):
        try:
            sim = lgsvl.Simulator(os.environ.get("SIMULATOR_HOST", "127.0.0.1"), 8181) 
            self.sim = sim
        except Exception as e:
            logger.error('Connect LGSVL wrong: ' + '127.0.0.1:8181')
            logger.error(e.message)
        logger.info('Connected LGSVL 127.0.0.1:8181')

    def load_map(self, mapName="SanFrancisco_correct"):
        if self.sim.current_scene == mapName:
           self.sim.reset()
        else:
           self.sim.load(mapName)
        logger.info('Loaded map: ' + mapName)
    
    def load_json(self, json_file):
        self.data_prime = json.load(open(json_file))
        if not self.data_prime.get('environment'):
            self.data_prime['environment'] = dict()
            self.data_prime['environment'] = {
                    'rain': 0,
                    'fog':  0,
                    'wetness':  0,
                    'cloudiness':  0,
                    'damage': 0,
                    'time':0,
                }

    def init_environment(self, json_file):
        """

        Args:
            json_file: contains env configs
                must: car position
                ego - destination (forward, right) or (x, y, z)
        Returns:

        """

        self.isEgoFault = False
        self.isHit = False
        self.mutated_npc_list = []
        self.fixed_npc_list = []

        self.load_json(json_file)

        # load ego car
        ego_data = self.data_prime['agents']['ego']
        ego_position = ego_data['position']
        ego_pos_vector = lgsvl.Vector(x=ego_position['x'], y=ego_position['y'], z=ego_position['z'])
        ego_state = lgsvl.AgentState()
        ego_state.transform = self.sim.map_point_on_lane(ego_pos_vector)
        self.ego = self.sim.add_agent(EGO_VEHICLE_ID, lgsvl.AgentType.EGO, ego_state)
        ## ego destination
        des_method = ego_data['destination']['method']
        if des_method == 'forward_right':
            des_forward = ego_data['destination']['value']['v1']
            des_right = ego_data['destination']['value']['v2']
            forward = lgsvl.utils.transform_to_forward(ego_state.transform)
            right = lgsvl.utils.transform_to_right(ego_state.transform)
            self.destination = ego_state.position + des_forward * forward + des_right * right
        elif des_method == 'xyz':
            x = ego_data['destination']['value']['v1']
            y = ego_data['destination']['value']['v2']
            z = ego_data['destination']['value']['v3']
            self.destination = lgsvl.Vector(x, y, z)
        else:
            raise RuntimeError('Unmatched destination method')

        # load mutated npc
        npcs = self.data_prime['agents']['npcs']
        for m_npc in npcs:
            npc_type = m_npc['type']
            npc_goal = m_npc['goal']
            npc_pos_x = m_npc['position']['x']
            npc_pos_y = m_npc['position']['y']
            npc_pos_z = m_npc['position']['z']
            npc_pos = lgsvl.Vector(x=npc_pos_x, y=npc_pos_y, z=npc_pos_z)
            npc_state = lgsvl.AgentState()
            npc_state.transform = self.sim.map_point_on_lane(npc_pos)
            npc = self.sim.add_agent(npc_type, lgsvl.AgentType.NPC, npc_state)
            if npc_goal == 'fixed':
                self.fixed_npc_list.append(npc)
            elif npc_goal == 'mutated':
                self.mutated_npc_list.append(npc)
            else:
                raise RuntimeError('Wrong npc goal. Only support fixed or mutated.')

        # load environments
        self.sim.weather = lgsvl.WeatherState(
            rain=self.data_prime['environment']['rain'],
            fog=self.data_prime['environment']['fog'],
            wetness=self.data_prime['environment']['wetness'],
            cloudiness=self.data_prime['environment']['cloudiness'],
            damage=self.data_prime['environment']['damage']
        )
        self.sim.set_time_of_day(self.data_prime['environment']['time'])

         # load lines
        # yellow line
        self.yellow_lines = self.data_prime['lines']['yellow_lines']
        self.cross_lines = self.data_prime['lines']['cross_lines']
        self.edge_lines = self.data_prime['lines']['edge_lines']

    def runSimulation(self, scenario_obj, json_file, case_id):

        #exit_handler()
        now = datetime.now()
        date_time = now.strftime("%m-%d-%Y-%H-%M-%S")
        logger.info(' === Simulation Start:  ['  + date_time + '] ===')

        self.sim.reset()
        self.init_environment(json_file)

        time_slice_size = len(scenario_obj[0])
        mutated_npc_num = len(scenario_obj)

        assert mutated_npc_num == len(self.mutated_npc_list)

        # simulation info
        simulation_recording = {
            'bbox': {
                'ego' : self.ego.bounding_box
            },
            'frames': {

            }
        }
        for npc_i in range(mutated_npc_num):
            simulation_recording['bbox']['npc_' + str(npc_i)] = self.mutated_npc_list[npc_i].bounding_box
        
        global collision_info
        global accident_happen
        global time_index
        
        collision_info = None
        accident_happen = False

        def on_collision(agent1, agent2, contact):
            global accident_happen
            global collision_info
            global time_index

            accident_happen = True
            collision_info = {}

            name1 = "STATIC OBSTACLE" if agent1 is None else agent1.name
            name2 = "STATIC OBSTACLE" if agent2 is None else agent2.name
            logger.error(str(name1) + " collided with " + str(name2) + " at " + str(contact))

            agent1_info = [agent1.state, agent1.bounding_box]
                        
            if not agent2:
                agent2_info = [None, None]
            else:
                agent2_info = [agent2.state, agent2.bounding_box]
            
            if contact:
                contact_loc = [contact.x, contact.y, contact.z]
            
            collision_info['time'] = time_index
            collision_info['ego'] = agent1_info
            collision_info['npc'] = agent2_info
            collision_info['contact'] = contact_loc

            self.sim.stop()
        
        # INIT apollo      
        self.ego.connect_bridge(address='127.0.0.1', port=9090) #address, port
        self.ego.on_collision(on_collision)
        
        times = 0
        success = False
        while times < 3:
            try:
                dv = lgsvl.dreamview.Connection(self.sim, self.ego, os.environ.get("BRIDGE_HOST", "127.0.0.1"))
                dv.set_hd_map(self.apollo_map)
                dv.set_vehicle('Lincoln2017MKZ_LGSVL')
                dv.setup_apollo(self.destination.x, self.destination.z, self.modules, default_timeout=30)
                success = True
                break
            except:
                logger.warning('Fail to spin up apollo, try again!')
                times += 1
        if not success:
            raise RuntimeError('Fail to spin up apollo')

        if self.default_record_folder:
            util.disnable_modules(dv, self.dy_modules)
            time.sleep(1)
            util.enable_modules(dv, self.dy_modules)
        
        dv.set_destination(self.destination.x, self.destination.z)
        logger.info(' --- destination: ' + str(self.destination.x) + ',' + str(self.destination.z))
        
        delay_t = 5
        time.sleep(delay_t)

        for npc in self.mutated_npc_list:
            npc.follow_closest_lane(True, 0)

        for npc in self.fixed_npc_list:
            npc.follow_closest_lane(True, 13.4)

        # Frequency of action change of NPCs
        total_sim_time = self.total_sim_time
        action_change_freq = total_sim_time / time_slice_size
        time_index = 0
        
        # record start
        simulation_recording['frames'][time_index] = {
            'ego': self.ego.state
        }

        for npc_i in range(mutated_npc_num):
            simulation_recording['frames'][time_index]['npc_' + str(npc_i)] = self.mutated_npc_list[npc_i].state
        
        for t in range(0, int(time_slice_size)):
            # check module states
            
            
                    
            # actionChangeFreq seconds
            # For every npc
            i = 0
            for npc in self.mutated_npc_list:
                npc.follow_closest_lane(True, scenario_obj[i][t][0])
                turn_command = scenario_obj[i][t][1]

                #<0: no turn; 1: left; 2: right>
                if turn_command == 1:
                    #direction = "LEFT"
                    npc.change_lane(True)
                    
                elif turn_command == 2:
                    #direction = "RIGHT"
                    npc.change_lane(False)
                    
                i += 1        

            for j in range(0, int(action_change_freq) * 10):
                module_status_mark = True
                while module_status_mark:
                    module_status_mark = False
                    module_status = dv.get_module_status()
                    for module, status in module_status.items():
                        if (not status) and (module in self.modules):
                            logger.warning('$$Simulator$$ Module is closed: ' + module + ' ==> restart')
                            dv.enable_module(module)
                            time.sleep(0.5)
                            module_status_mark = True
                time_index += 1

                self.sim.run(0.1)

                simulation_recording['frames'][time_index] = {
                    'ego': self.ego.state
                }

                for npc_i in range(len(self.mutated_npc_list)):
                    simulation_recording['frames'][time_index]['npc_' + str(npc_i)] = self.mutated_npc_list[npc_i].state

    
        if self.default_record_folder:
            util.disnable_modules(dv, self.dy_modules)
            time.sleep(0.5)

        # check new folder and move -> save folder
        if self.default_record_folder:
            util.check_rename_record(self.default_record_folder, self.target_record_folder, case_id)

        
        # compute fitness score & check other bugs such as line cross or else
        '''
        

        global collision_info
        global accident_happen
        
        collision_info = None
        accident_happen = False
        
        '''
        # Step 1 obtain time
        simulation_slices = max(simulation_recording['frames'].keys())

        '''
        simulation_recording[time_index] = {
                    'ego': self.ego.transform,
                    'npc': []
                }
        '''
        fault = []
        max_fitness = -1111
        # Step 2 compute distance and check line error and filter npc_fault
        for t in range(simulation_slices):
            simulation_frame = simulation_recording['frames'][t]
            ego_info = {
                'state': simulation_frame['ego'],
                'bbox': simulation_recording['bbox']['ego']
            }            
            # compute distance
            for npc_i in range(len(self.mutated_npc_list)):
                npc_id = 'npc_' + str(npc_i)
                npc_info = {
                    'state': simulation_frame[npc_id],
                    'bbox': simulation_recording['bbox'][npc_id]
                }
                
                npc_ego_fitness = liability.compute_danger_fitness(ego_info, npc_info, False)
                
                if npc_ego_fitness > max_fitness:
                    max_fitness = npc_ego_fitness
            
            # check line
            for yellow_line in self.yellow_lines:
                hit_yellow_line = liability.ego_yellow_line_fault(ego_info, yellow_line)
                if hit_yellow_line:
                    fault.append('hit_yellow_line')
            
            for edge_line in self.edge_lines:
                hit_edge_line = liability.ego_edge_line_fault(ego_info, edge_line)
                if hit_edge_line:
                    fault.append('hit_edge_line')
            
        # Step 3 if collision, check is npc fault
        '''
        agent1_info = [agent1.transform, agent1.state]
                        
            if not agent2:
                agent2_info = [None, None]
            else:
                agent2_info = [agent2.transform, agent2.state]
            
            if contact:
                contact_loc = [contact.x, contact.y, contact.z]
            
            collision_info['time'] = time_index
            collision_info['ego'] = agent1_info
            collision_info['npc'] = agent2_info
            collision_info['contact'] = contact_loc

        '''
        if collision_info is not None:
            ego_info = {
                'state': collision_info['ego'][0],
                'bbox': collision_info['ego'][1]
            }

            npc_info = {
                'state': collision_info['npc'][0],
                'bbox': collision_info['npc'][1]
            }
            
            ego_fault = liability.ego_collision_fault(ego_info, npc_info, self.cross_lines)
            if ego_fault:
                fault.append('ego_fault')
            else:
                fault.append('npc_fault')
            
            fitness = liability.compute_danger_fitness(ego_info, npc_info, True)
            if fitness <= max_fitness:
                logger.error('Please increase K in liability.compute_danger_fitness: Collision - ' + str(fitness) + 'No Collision - ' + str(max_fitness))
                raise RuntimeError('liability.compute_danger_fitness parameter setting is not right.')
            else:
                max_fitness = fitness

        if len(fault) == 0:
            fault.append('normal')
        
        #fitness_score = self.findFitness(deltaDList, dList, self.isHit, hit_time)
        
        result_dict = {}
        result_dict['fitness'] = max_fitness
        #(fitness_score + self.maxint) / float(len(self.mutated_npc_list) - 1 ) # Try to make sure it is positive
        result_dict['fault'] = fault
        
        logger.info(' === Simulation End === ')

        return result_dict