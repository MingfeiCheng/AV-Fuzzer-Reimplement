import math
import numpy as np

from loguru import logger
from shapely.geometry import Polygon, LineString

def calc_abc_from_line_2d(x0, y0, x1, y1):
    a = y0 - y1
    b = x1 - x0
    c = x0 * y1 - x1 * y0
    return a, b, c

def get_line_cross_point(line1, line2):
    a0, b0, c0 = calc_abc_from_line_2d(*line1)
    a1, b1, c1 = calc_abc_from_line_2d(*line2)
    D = a0 * b1 - a1 * b0
    if D == 0:
        return None
    x = (b0 * c1 - b1 * c0) / D
    y = (a1 * c0 - a0 * c1) / D
    return x, y

def right_rotation(coord, theta):
    """
    theta : degree
    """
    theta = math.radians(theta) 
    x = coord[1]
    y = coord[0]
    x1 = x * math.cos(theta) - y * math.sin(theta)
    y1 = x * math.sin(theta) + y * math.cos(theta)
    return [y1, x1]

def get_bbox(agent):
    agent_theta = agent['state'].transform.rotation.y
    agent_bbox = agent['bbox'] # min max (x_min, y_min, z_min) (x_max, y_max, z_max)
        
    global_x = agent['state'].transform.position.x
    global_z = agent['state'].transform.position.z
    x_min = agent_bbox.min.x + 0.1
    x_max = agent_bbox.max.x - 0.1
    z_min = agent_bbox.min.z + 0.1
    z_max = agent_bbox.max.z - 0.1

    line1 = [x_min, z_min, x_max, z_max]
    line2 = [x_min, z_max, x_max, z_min]
    x_center, z_center = get_line_cross_point(line1, line2)

    coords = [[x_min, z_min], [x_max, z_min], [x_max, z_max], [x_min, z_max]]
    new_coords = []
    for i in range(len(coords)):
        coord_i = coords[i]
        coord_i[0] = coord_i[0] - x_center
        coord_i[1] = coord_i[1] - z_center
        new_coord_i = right_rotation(coord_i, agent_theta)
        new_coord_i[0] += global_x
        new_coord_i[1] += global_z
        new_coords.append(new_coord_i)
    p1, p2, p3, p4 = new_coords[0], new_coords[1], new_coords[2], new_coords[3]

    agent_poly = Polygon((p1, p2, p3, p4))
    if agent_poly.area <= 0:
        print(agent_poly.area)
        exit(-1)
    return agent_poly

def get_distance_ego_npc(ego, npc):
    ego_bbox = get_bbox(ego)
    npc_bbox = get_bbox(npc)
    d = ego_bbox.distance(npc_bbox)
    return d

def get_distance_ego_line(ego, line_points):
    """
    line_points: [start_point, ..., end_point]
    point (x, y)
    """
    line = LineString(line_points)
    ego_bbox = get_bbox(ego)
    d = ego_bbox.distance(line)
    return d

def is_hit_edge(ego, edge_lines):
    """
    edge_lines : [line1, line2, line3]
    """
    ego_bbox = get_bbox(ego)
    for l_i in edge_lines:
        l = LineString(l_i)
        d_i = ego_bbox.distance(l)
        if d_i == 0:
            return True
    return False

def ego_npc_direction(ego, npc):
    ego_x = ego['state'].transform.position.x
    ego_z = ego['state'].transform.position.z
    npc_x = npc['state'].transform.position.x
    npc_z = npc['state'].transform.position.z

    ego_rotation = ego['state'].transform.rotation.y
    unit_direction = [0, 1]
    ego_direction = right_rotation(unit_direction, ego_rotation)

    dist_direction = [npc_x - ego_x, npc_z - ego_z]
    
    d = ego_direction[0] * dist_direction[0] + ego_direction[1] * dist_direction[1]

    return d

def ego_npc_lateral(ego, npc):
    ego_x = ego['state'].transform.position.x
    ego_z = ego['state'].transform.position.z
    npc_x = npc['state'].transform.position.x
    npc_z = npc['state'].transform.position.z

    ego_rotation = ego['state'].transform.rotation.y
    unit_direction = [1, 0]
    ego_direction = right_rotation(unit_direction, ego_rotation)

    dist_direction = [npc_x - ego_x, npc_z - ego_z]
    
    d = abs(ego_direction[0] * dist_direction[0] + ego_direction[1] * dist_direction[1])

    return d

def ego_is_straight(ego, sim):
    ego_rotation = ego['state'].transform.rotation.y
    lane_center = sim.map_point_on_lane(ego['state'].transform.position)
    lane_rotation = lane_center.rotation.y
    if abs(ego_rotation - lane_rotation) > 8:
        return False
    else:
        return True


def ego_yellow_line_fault(ego, yellow_line_points):
    ego_bbox = get_bbox(ego)

    yellow_line = LineString(yellow_line_points)
    distance_yellow = ego_bbox.distance(yellow_line)
    if distance_yellow <= 0:
        return True
    else:
        return False  

def ego_edge_line_fault(ego, edge_line_points):
    # 2. hit edge line
    ego_bbox = get_bbox(ego)
    edge_line = LineString(edge_line_points)
    distance_edge = ego_bbox.distance(edge_line)

    if distance_edge <= 0:
        return True
    else:
        return False

def ego_cross_line(ego, cross_lines):
    ego_bbox = get_bbox(ego)
    for cross_line_points in cross_lines:
        cross_line = LineString(cross_line_points)
        cross_line_distance = ego_bbox.distance(cross_line)
        if cross_line_distance <= 0:
            return True
    return False

def ego_collision_fault(ego, npc, cross_lines):
    """
    coarse filter
    """
    ego_speed = np.linalg.norm(np.array([ego['state'].velocity.x, ego['state'].velocity.y, ego['state'].velocity.z]))
    if ego_speed <= 0.1:
        return False

    is_ego_cross_line = ego_cross_line(ego, cross_lines)
    direct_ego_npc = ego_npc_direction(ego, npc)
    if is_ego_cross_line:
        logger.debug('Ego cross, seen as the ego fault')
        return True
    else:
        # zhui wei & jia sai
        logger.debug('Ego stay in line')
        if direct_ego_npc <= 0:
            logger.error('NPC fault')
            return False
        else:
            logger.error('Ego fault')
            return True

def compute_danger_fitness(ego, npc, collision=False):
    if collision:
        ego_speed = np.array([ego['state'].velocity.x, ego['state'].velocity.y, ego['state'].velocity.z])
        npc_speed = np.array([npc['state'].velocity.x, npc['state'].velocity.y, npc['state'].velocity.z])
        fitness = np.linalg.norm(ego_speed - npc_speed)
        fitness = fitness + 100
    else:
        ego_speed = np.array([ego['state'].velocity.x, ego['state'].velocity.y, ego['state'].velocity.z])
        npc_speed = np.array([npc['state'].velocity.x, npc['state'].velocity.y, npc['state'].velocity.z])
        speed_norm = np.linalg.norm(ego_speed - npc_speed)
        location_norm = (get_distance_ego_npc(ego, npc) + 1) ** 2
        if location_norm <= 0:
            logger.warning('No collision, but distance norm <= 0')
            location_norm = 1.0
        fitness = speed_norm / location_norm
    
    return fitness

