import math

from shapely.geometry import Polygon, LineString

def right_rotation(coord, theta):
    """
    theta : degree
    """
    theta = math.radians(theta) 
    x = coord[0]
    y = coord[1]
    x1 = x * math.cos(theta) - y * math.sin(theta)
    y1 = x * math.cos(theta) + y * math.cos(theta)
    return [x1, y1]

def get_bbox(agent):
    agent_theta = agent.transform.rotation.y
    agent_bbox = agent.bounding_box # min max (x_min, y_min, z_min) (x_max, y_max, z_max)
    global_x = agent.transform.position.x
    global_z = agent.transform.position.z
    x_min = agent_bbox.min.x
    x_max = agent_bbox.max.x
    z_min = agent_bbox.min.z
    z_max = agent_bbox.max.z
    coords = [[x_min, z_min], [x_max, z_min], [x_max, z_max], [x_min, z_max]]
    for i in range(len(coords)):
        coord_i = coords[i]
        new_coord_i = right_rotation(coord_i, agent_theta)
        new_coord_i[0] += global_x
        new_coord_i[1] += global_z
        coords[i] = new_coord_i 
    p1, p2, p3, p4 = coords[0], coords[1], coords[2], coords[3]
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

def get_distance_ego_line(ego, line_start, line_end):
    """
    lines: support many edges
    line_start: [x_start, z_start]
    line_end: [x_end, z_end]
    """
    line = LineString([line_start, line_end])
    ego_bbox = get_bbox(ego)
    d = ego_bbox.distance(line)
    return d

def is_hit_line(ego, lane_line):
    """
    lane_line: single line, each line contains many points
    """
    pass

