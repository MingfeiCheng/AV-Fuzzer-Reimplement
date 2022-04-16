import os
import lgsvl
import time
import json

import simulation.utils as util
import simulation.liability as liability

from datetime import datetime
from loguru import logger

from simulation.dreamview import Connection

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

        self.init_modules = [
            'Localization',
            'Transform',
            'Routing',
            'Prediction',
            'Planning',
            'Control',
            'Storytelling'
        ]
        self.dy_modules = [
            'Recorder',
        ]
        self.dv = Connection(self.sim, '127.0.0.1')
        self.dv.set_hd_map(self.apollo_map)  # SanFrancisco borregas_ave Straight2LaneSame
        self.dv.set_vehicle('Lincoln2017MKZ_LGSVL')
        util.disnable_modules(self.dv, self.init_modules)
        util.disnable_modules(self.dv, self.dy_modules)
        time.sleep(0.5)
        util.enable_modules(self.dv, self.init_modules)
        time.sleep(1)
        module_status = self.dv.get_module_status()
        not_all = False
        for module, status in module_status.items():
            if (not status) and (module in self.init_modules):
                logger.error('$$Simulator$$ Module is closed: ' + module)
                not_all = True
        if not_all:
            exit(-1)

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
        self.mutated_npc_list = []
        self.fixed_npc_list = []
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

    def brakeDist(self, speed):
        dBrake = 0.0467 * pow(speed, 2.0) + 0.4116 * speed - 1.9913 + 0.5
        if dBrake < 0:
            dBrake = 0
        return dBrake
    
    def findCollisionDeltaD(self, ego, npc):
        d = liability.get_distance_ego_npc(ego, npc)
        return d - self.brakeDist(ego.state.speed)

    def findDeltaD(self, ego, npc):
        d = liability.get_distance_ego_npc(ego, npc)
        deltaD = self.maxint # The smaller delta D, the better
        deltaDFront = self.maxint
        deltaDSide = self.maxint

        # When npc is in front
        if 4.6 < liability.ego_npc_direction(ego, npc) < 20:
            if liability.ego_npc_lateral(ego, npc) < 2:
                deltaDFront = d - self.brakeDist(ego.state.speed)
                logger.info(" --- Delta D Front: " + str(deltaDFront))

        # When ego is changing line to npc's front
        if 4.6 < liability.ego_npc_direction(npc, ego) < 20:
            if liability.ego_npc_lateral(npc, ego) < 2 and (not liability.ego_is_straight(ego, self.sim)):
                deltaDSide = d - self.brakeDist(npc.state.speed)
                logger.info(" --- Delta D Side: " + str(deltaDSide))
   
        deltaD = min(deltaDSide, deltaDFront)

        return deltaD

    def findFitness(self, deltaDlist, dList, isHit, hitTime):
       # The higher the fitness, the better.

       minDeltaD = self.maxint
       for npc in deltaDlist: # ith NPC
            hitCounter = 0
            for deltaD in npc:
                if isHit == True and hitCounter == hitTime:
                   break
                if deltaD < minDeltaD:
                    minDeltaD = deltaD # Find the min deltaD over time slices for each NPC as the fitness
                hitCounter += 1
       logger.info(" --- minDeltaD: " + str(minDeltaD))

       minD = self.maxint
       for npc in dList: # ith NPC
            hitCounter = 0
            for d in npc:
                if isHit == True and hitCounter == hitTime:
                   break
                if d < minD:
                    minD = d
                hitCounter += 1
       logger.info(" --- minD: " + str(minD))

       fitness = 0.5 * minD + 0.5 * minDeltaD

       return fitness * -1

    def runSimulation(self, scenario_obj, json_file, case_id):

        now = datetime.now()
        date_time = now.strftime("%m-%d-%Y-%H-%M-%S")
        logger.info(' === Simulation Start:  ['  + date_time + '] ===')

        self.isEgoFault = False
        self.isHit = False

        self.sim.reset()
        self.init_environment(json_file)

        time_slice_size = len(scenario_obj[0])
        mutated_npc_num = len(scenario_obj)

        logger.debug(" --- Sim mutated npc size: " + str(len(self.mutated_npc_list)))
        logger.debug(' --- Config mutated npc size: ' + str(mutated_npc_num))
        logger.debug(' --- Config fixed npc size: ' + str(len(self.fixed_npc_list)))

        assert mutated_npc_num == len(self.mutated_npc_list)
        
        deltaDList = [[self.maxint for i in range(time_slice_size)] for j in range(mutated_npc_num)] # 1-D: NPC; 2-D: Time Slice
        dList = [[self.maxint for i in range(time_slice_size)] for j in range(mutated_npc_num)] # 1-D: NPC; 2-D: Time Slice

        def on_destination_reached():
            pass

        def on_collision(agent1, agent2, contact):
            #util.print_debug(" --- On Collision, ego speed: " + str(agent1.state.speed) + ", NPC speed: " + str(agent2.state.speed))
            if self.isHit:
                return
            
            self.isHit = True
            
            if agent2 is None or agent1 is None:
                self.isEgoFault = True
                logger.info(" --- Hit road obstacle --- ")
                return

            apollo = agent1
            npcVehicle = agent2

            if agent2.name == EGO_VEHICLE_ID:
                apollo = agent2
                npcVehicle = agent1
            
            logger.debug(' --- Apollo Name: ' + apollo.name)
            logger.debug(' --- npcVehicle Name: ' + npcVehicle.name)
            logger.debug(" --- On Collision, ego speed: " + str(apollo.state.speed) + ", NPC speed: " + str(npcVehicle.state.speed))
            
            if apollo.state.speed <= 0.005:
               self.isEgoFault = False
               return

            self.isEgoFault = liability.ego_collision_fault(apollo, npcVehicle, self.cross_lines)
            
                    
        self.ego.on_collision(on_collision)
        self.ego.connect_bridge(address='127.0.0.1', port=9090) #address, port
        self.dv.set_ego(self.ego)
        if self.default_record_folder:
            util.enable_modules(self.dv, self.dy_modules)
        self.dv.set_destination(x_long_east=self.destination.x, z_lat_north=self.destination.z)
        logger.debug(' --- destination: ' + str(self.destination.x) + ',' + str(self.destination.z))
        time.sleep(1)

        for npc in self.mutated_npc_list:
            npc.follow_closest_lane(True, 0)
        
        for npc in self.fixed_npc_list:
            npc.follow_closest_lane(True, 13.4)     

        # Frequency of action change of NPCs
        total_sim_time = self.total_sim_time
        action_change_freq = total_sim_time / time_slice_size
        hit_time = time_slice_size
        
        for t in range(0, int(time_slice_size)):
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

            if self.isEgoFault:
                self.isHit = True
            
            if self.isHit:
                hit_time = t
                break
           
            # Record the min delta D and d
            minDeltaD = self.maxint
            npcDeltaAtTList = [0 for i in range(mutated_npc_num)]
            
            minD = self.maxint
            npcDAtTList = [0 for i in range(mutated_npc_num)]

            for j in range(0, int(action_change_freq) * 4):

                # Stop if there is accident
                # 1 yellow line
                for yellow_line in self.yellow_lines:
                    if liability.ego_yellow_line_fault(self.ego, yellow_line):
                        self.isEgoFault = True
                        logger.info(' --- Hit yellow line')
                        break
                
                # 2 edge line
                for edge_line in self.edge_lines:
                    if liability.ego_edge_line_fault(self.ego, edge_line):
                        self.isEgoFault = True
                        logger.info(' --- Hit edge line')
                        break
                    
                k = 0 # k th npc
                for npc in self.mutated_npc_list:
                    # Update delta D
                    curDeltaD = self.findDeltaD(self.ego, npc)
                    if minDeltaD > curDeltaD:
                        minDeltaD = curDeltaD
                    npcDeltaAtTList[k] = minDeltaD

                    # Update d
                    curD = liability.get_distance_ego_npc(self.ego, npc)
                    if minD > curD:
                        minD = curD
                    npcDAtTList[k] = minD

                    k += 1
                
                if self.isEgoFault:
                    self.isHit = True
                
                if self.isHit:
                    break

                self.sim.run(0.25)

            ####################################    
            k = 0 # kth npc 
            for npc in self.mutated_npc_list:
                deltaDList[k][t] = npcDeltaAtTList[k]
                dList[k][t] = npcDAtTList[k]
                k += 1
        
        if self.default_record_folder:
            util.disnable_modules(self.dv, self.dy_modules)
            time.sleep(0.5)

        # check new folder and move -> save folder
        if self.default_record_folder:
            util.check_rename_record(self.default_record_folder, self.target_record_folder, case_id)

        # Process deltaDList and compute fitness scores
        # Make sure it is not 0, cannot divide by 0 in GA
        fitness_score = self.findFitness(deltaDList, dList, self.isHit, hit_time)
        resultDic = {}
        resultDic['fitness'] = (fitness_score + self.maxint) / float(len(self.mutated_npc_list) - 1 ) # Try to make sure it is positive
        resultDic['fault'] = ''
        if self.isEgoFault:
            resultDic['fault'] = 'ego'
        elif self.isHit:
            resultDic['fault'] = 'npc'
        logger.info(" === Finish simulation === ")
        logger.debug(resultDic)

        return resultDic