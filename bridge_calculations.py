"""
桥梁冲刷计算核心模块
包含所有计算逻辑，与原始Tkinter应用保持一致
"""
import numpy as np
import math
import re

# 常量定义
MAX_A_COEFFICIENT = 1.8  # 单宽流量集中系数最大值
SAMPLING_INTERVAL = 0.1  # 水力参数计算采样间隔


def find_waterline_intersections(distances, elevations, water_level):
    """找到水位线与断面的交点"""
    left_intersection = None
    for i in range(len(distances) - 1):
        if (elevations[i] <= water_level and elevations[i + 1] > water_level) or \
                (elevations[i] >= water_level and elevations[i + 1] < water_level):
            x = distances[i] + (water_level - elevations[i]) * \
                (distances[i + 1] - distances[i]) / (elevations[i + 1] - elevations[i])
            left_intersection = x
            break

    right_intersection = None
    for i in range(len(distances) - 1, 0, -1):
        if (elevations[i] <= water_level and elevations[i - 1] > water_level) or \
                (elevations[i] >= water_level and elevations[i - 1] < water_level):
            x = distances[i] + (water_level - elevations[i]) * \
                (distances[i - 1] - distances[i]) / (elevations[i - 1] - elevations[i])
            right_intersection = x
            break

    if left_intersection is not None and right_intersection is not None:
        return [left_intersection, right_intersection]
    return []


def calculate_hydraulic_parameters(distances, elevations, water_level, interval=SAMPLING_INTERVAL):
    """计算水力参数：平均水深、最大水深、过流面积"""
    intersections = find_waterline_intersections(distances, elevations, water_level)

    if len(intersections) < 2:
        return None, None, None, None

    left_boundary, right_boundary = intersections
    sample_points = np.arange(left_boundary, right_boundary + interval, interval)

    water_depths = []
    for x in sample_points:
        idx = np.searchsorted(distances, x)

        if idx == 0:
            elevation = elevations[0]
        elif idx >= len(distances):
            elevation = elevations[-1]
        else:
            ratio = (x - distances[idx - 1]) / (distances[idx] - distances[idx - 1])
            elevation = elevations[idx - 1] + ratio * (elevations[idx] - elevations[idx - 1])

        depth = max(0, water_level - elevation)
        water_depths.append(depth)

    water_depths = np.array(water_depths)

    max_depth = np.max(water_depths)
    avg_depth = np.mean(water_depths)
    flow_area = np.trapz(water_depths, sample_points)

    return avg_depth, max_depth, flow_area, intersections


def identify_channel_and_floodplain(distances, elevations, water_level):
    """识别河槽和河滩的分界点"""
    intersections = find_waterline_intersections(distances, elevations, water_level)

    if len(intersections) == 2:
        return intersections[0], intersections[1]

    return None, None


def parse_bridge_config(config_str):
    """解析桥梁配置字符串，如"3-32"或"1-24+3-32" """
    spans = []
    parts = re.findall(r'(\d+)-(\d+)', config_str)

    for count_str, span_str in parts:
        count = int(count_str)
        span = float(span_str)
        spans.extend([span] * count)

    return spans


def calculate_bridge_obstruction(spans, pier_width, skew_angle, water_level, distances, elevations, 
                                 bridge_start, left_channel_boundary, right_channel_boundary):
    """计算桥墩阻水面积和阻水比率，同时区分区域"""
    intersections = find_waterline_intersections(distances, elevations, water_level)
    if len(intersections) < 2:
        return 0, 0, [], 0, 0, 0, 0, 0, 0

    pier_positions = []
    current_position = bridge_start
    pier_positions.append(current_position)

    for span in spans:
        projected_span = span * math.cos(math.radians(skew_angle))
        current_position += projected_span
        pier_positions.append(current_position)

    effective_pier_width = pier_width
    total_obstruction_area = 0
    left_obstruction_area = 0
    channel_obstruction_area = 0
    right_obstruction_area = 0

    left_obstruction_width = 0
    channel_obstruction_width = 0
    right_obstruction_width = 0

    pier_obstructions = []

    for pier_pos in pier_positions:
        projected_pos = pier_pos

        if projected_pos < distances[0] or projected_pos > distances[-1]:
            continue

        idx = np.searchsorted(distances, projected_pos)
        if idx == 0:
            depth = water_level - elevations[0]
        elif idx >= len(distances):
            depth = water_level - elevations[-1]
        else:
            ratio = (projected_pos - distances[idx - 1]) / (distances[idx] - distances[idx - 1])
            elevation = elevations[idx - 1] + ratio * (elevations[idx] - elevations[idx - 1])
            depth = water_level - elevation

        depth = max(0, depth)
        pier_area = effective_pier_width * depth
        total_obstruction_area += pier_area

        if projected_pos < left_channel_boundary:
            left_obstruction_area += pier_area
            left_obstruction_width += effective_pier_width
        elif projected_pos > right_channel_boundary:
            right_obstruction_area += pier_area
            right_obstruction_width += effective_pier_width
        else:
            channel_obstruction_area += pier_area
            channel_obstruction_width += effective_pier_width

        pier_obstructions.append({
            'position': projected_pos,
            'depth': depth,
            'area': pier_area,
            'region': '左河滩' if projected_pos < left_channel_boundary else
            '右河滩' if projected_pos > right_channel_boundary else '河槽'
        })

    _, _, flow_area, _ = calculate_hydraulic_parameters(distances, elevations, water_level)
    obstruction_ratio = total_obstruction_area / flow_area if flow_area > 0 else 0

    return (total_obstruction_area, obstruction_ratio, pier_obstructions,
            left_obstruction_area, channel_obstruction_area, right_obstruction_area,
            left_obstruction_width, channel_obstruction_width, right_obstruction_width)


def calculate_flow(area, width, n, J):
    """计算流量"""
    if width <= 0:
        return 0, 0, 0  # 流量, 流速, 水力半径

    avg_depth = area / width
    hydraulic_radius = avg_depth
    C = (hydraulic_radius ** (1 / 6)) / n
    velocity = C * math.sqrt(J * hydraulic_radius)
    discharge = area * velocity

    return discharge, velocity, hydraulic_radius


def calculate_scour(channel_Q, B, H, Lcj, h_max, h_c, mu, E, d):
    """计算桥梁一般冲刷深度（64-1修正式）"""
    A_d = (math.sqrt(B) / H) ** 0.15
    A_d = min(A_d, MAX_A_COEFFICIENT)
    h_ratio = (h_max / h_c) ** (5 / 3)
    numerator = A_d * (channel_Q / (mu * Lcj)) * h_ratio
    denominator = E * (d ** (1 / 6))
    scour_depth = (numerator / denominator) ** (3 / 5)
    return scour_depth, A_d


def calculate_scour_64_2(Q_2, Q_c, B_c, B_2, lambda_, mu, h_cm, B_z, H_z):
    """根据64-2计算公式计算桥梁一般冲刷后的最大水深"""
    A_d = (math.sqrt(B_z) / H_z) ** 0.15
    if A_d > MAX_A_COEFFICIENT:
        A_d = MAX_A_COEFFICIENT

    term1 = (A_d * (Q_2 / Q_c)) ** 0.90
    term2 = (B_c / ((1 - lambda_) * mu * B_2)) ** 0.66
    h_p = 1.04 * term1 * term2 * h_cm

    return h_p, A_d


def calculate_local_scour(V, K_t, d, B_1, h_p):
    """根据65-2计算公式计算桥墩局部冲刷深度"""
    V_0 = 0.28 * (d + 0.7) ** 0.5
    V_0_prime = 0.12 * (d + 0.5) ** 0.55
    K_η2 = (0.0023 / (d ** 2.2)) + 0.375 * d ** 0.24
    n2 = (V_0 / V) ** (0.23 + 0.19 * math.log10(d))
    
    if V <= V_0:
        h_b = K_t * K_η2 * B_1 ** 0.6 * h_p ** 0.15 * ((V - V_0_prime) / V_0)
    else:
        h_b = K_t * K_η2 * B_1 ** 0.6 * h_p ** 0.15 * ((V - V_0_prime) / V_0) ** n2
    return h_b


def calculate_local_scour_65_1(V, K_t, d, B_1, h_p):
    """根据65-1计算公式计算桥墩局部冲刷深度"""
    V_0 = 0.0246 * (h_p / d) ** 0.14 * math.sqrt(332 * d + (10 + h_p) / (d ** 0.72))
    K_η1 = 0.8 * (1 / (d ** 0.45) + 1 / (d ** 0.15))
    V_0_prime = 0.462 * (d / B_1) ** 0.06 * V_0
    n1 = (V_0 / V) ** (0.25 * d ** 0.19)

    if V <= V_0:
        h_b = K_t * K_η1 * B_1 ** 0.6 * (V - V_0_prime)
    else:
        h_b = K_t * K_η1 * B_1 ** 0.6 * (V_0 - V_0_prime) * ((V - V_0_prime) / (V_0 - V_0_prime)) ** n1

    return h_b


def calculate_flow_areas(distances, elevations, design_water_level, boundary1, boundary2):
    """计算设计水位下各区域的过水面积"""
    intersections = find_waterline_intersections(distances, elevations, design_water_level)

    if len(intersections) < 2:
        return None, None, None

    start_idx = np.argmin(np.abs(distances - intersections[0]))
    end_idx = np.argmin(np.abs(distances - intersections[1]))

    water_depths = design_water_level - elevations[start_idx:end_idx + 1]
    water_depths = np.maximum(water_depths, 0)

    distances_slice = distances[start_idx:end_idx + 1]
    channel_mask = (distances_slice >= boundary1) & (distances_slice <= boundary2)
    left_floodplain_mask = (distances_slice < boundary1)
    right_floodplain_mask = (distances_slice > boundary2)

    channel_area = np.trapz(water_depths[channel_mask], distances_slice[channel_mask])
    left_floodplain_area = np.trapz(water_depths[left_floodplain_mask], distances_slice[left_floodplain_mask])
    right_floodplain_area = np.trapz(water_depths[right_floodplain_mask], distances_slice[right_floodplain_mask])

    return left_floodplain_area, channel_area, right_floodplain_area


def calculate_flow_distribution(params, left_area, channel_area, right_area,
                               left_area_after, channel_area_after, right_area_after,
                               left_width_after, channel_width_after, right_width_after,
                               left_width_before, channel_width_before, right_width_before):
    """计算流量分布"""
    left_Q, _, _ = calculate_flow(left_area_after, left_width_after, params['n_l'], params['J'])
    channel_Q, _, _ = calculate_flow(channel_area_after, channel_width_after, params['n_c'], params['J'])
    right_Q, _, _ = calculate_flow(right_area_after, right_width_after, params['n_r'], params['J'])

    left_Q_before = calculate_flow(left_area, left_width_before, params['n_l'], params['J'])[0]
    channel_Q_before = calculate_flow(channel_area, channel_width_before, params['n_c'], params['J'])[0]
    right_Q_before = calculate_flow(right_area, right_width_before, params['n_r'], params['J'])[0]

    total_Q = left_Q + channel_Q + right_Q
    total_Q_before = left_Q_before + channel_Q_before + right_Q_before

    channel_Q_final = channel_Q * params['Design_Q'] / total_Q if total_Q > 0 else 0
    left_Q_final = left_Q * params['Design_Q'] / total_Q if total_Q > 0 else 0
    right_Q_final = right_Q * params['Design_Q'] / total_Q if total_Q > 0 else 0

    Q_c = channel_Q_before * params['Design_Q'] / total_Q_before if total_Q_before > 0 else 0

    return {
        'channel_Q_final': channel_Q_final,
        'left_Q_final': left_Q_final,
        'right_Q_final': right_Q_final,
        'Q_c': Q_c,
        'total_Q': total_Q
    }

