"""
桥梁冲刷计算系统 - Streamlit Web应用
功能与原始Tkinter应用完全一致
"""
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import pandas as pd
from io import StringIO, BytesIO
import re

# 导入计算模块
from bridge_calculations import *

# 设置matplotlib中文字体
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "Arial Unicode MS"]
plt.rcParams['axes.unicode_minus'] = False

# 页面配置
st.set_page_config(
    page_title="桥梁冲刷计算系统",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化session state
if 'distances' not in st.session_state:
    st.session_state.distances = None
    st.session_state.elevations = None
    st.session_state.calculation_results = None

def read_cross_section_from_file(uploaded_file):
    """从上传的文件读取断面数据"""
    try:
        if uploaded_file is not None:
            # 读取文件内容
            content = uploaded_file.read().decode('utf-8')
            lines = content.strip().split('\n')
            
            distances = []
            elevations = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # 支持空格、制表符、逗号分隔
                parts = re.split(r'[\s,\t]+', line)
                if len(parts) >= 2:
                    try:
                        distances.append(float(parts[0]))
                        elevations.append(float(parts[1]))
                    except ValueError:
                        continue
            
            if len(distances) >= 2:
                return np.array(distances), np.array(elevations)
    except Exception as e:
        st.error(f"读取文件错误: {str(e)}")
    return None, None

def read_cross_section_from_text(text_input):
    """从文本输入读取断面数据"""
    try:
        if text_input:
            lines = text_input.strip().split('\n')
            distances = []
            elevations = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = re.split(r'[\s,\t]+', line)
                if len(parts) >= 2:
                    try:
                        distances.append(float(parts[0]))
                        elevations.append(float(parts[1]))
                    except ValueError:
                        continue
            
            if len(distances) >= 2:
                return np.array(distances), np.array(elevations)
    except Exception as e:
        st.error(f"解析文本数据错误: {str(e)}")
    return None, None

def plot_cross_section(distances, elevations, water_level=None, design_water_level=None,
                       channel_boundaries=None, pier_obstructions=None, title="河道横断面图"):
    """绘制河道横断面图"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(distances, elevations, 'k-', linewidth=2, label='河道断面')
    ax.fill_between(distances, elevations, np.min(elevations) - 1, color='lightgray', alpha=0.5)

    # 绘制平滩水位线
    if water_level is not None:
        ax.axhline(y=water_level, color='b', linestyle='--', linewidth=1.5, label='平滩水位')
        intersections = find_waterline_intersections(distances, elevations, water_level)
        if len(intersections) >= 2:
            start_idx = np.argmin(np.abs(distances - intersections[0]))
            end_idx = np.argmin(np.abs(distances - intersections[1]))
            x = np.concatenate([[distances[start_idx]], distances[start_idx:end_idx + 1], [distances[end_idx]]])
            y = np.concatenate([[water_level], elevations[start_idx:end_idx + 1], [water_level]])
            ax.fill(x, y, 'b', alpha=0.3)

    # 绘制设计水位线
    if design_water_level is not None:
        ax.axhline(y=design_water_level, color='r', linestyle='-', linewidth=1.5, label='设计水位')
        intersections = find_waterline_intersections(distances, elevations, design_water_level)
        if len(intersections) >= 2:
            start_idx = np.argmin(np.abs(distances - intersections[0]))
            end_idx = np.argmin(np.abs(distances - intersections[1]))
            x = np.concatenate([[distances[start_idx]], distances[start_idx:end_idx + 1], [distances[end_idx]]])
            y = np.concatenate([[design_water_level], elevations[start_idx:end_idx + 1], [design_water_level]])
            ax.fill(x, y, 'r', alpha=0.2)

    # 标记河槽和河滩的分界点
    if channel_boundaries is not None and len(channel_boundaries) == 2:
        ax.axvline(x=channel_boundaries[0], color='g', linestyle='-.', linewidth=1.5, label='河槽左边界')
        ax.axvline(x=channel_boundaries[1], color='g', linestyle='-.', linewidth=1.5, label='河槽右边界')

    # 标记桥墩位置和阻水区域
    if pier_obstructions and len(pier_obstructions) > 0:
        for i, pier in enumerate(pier_obstructions):
            pier_pos = pier['position']
            depth = pier['depth']
            region = pier['region']
            
            color = 'purple' if region == '河槽' else 'blue' if region == '左河滩' else 'red'
            
            ax.axvline(x=pier_pos, color=color, linestyle='--', linewidth=1,
                      label=f'桥墩 {i + 1} ({region})' if i == 0 else '')
            
            if design_water_level is not None:
                ax.plot([pier_pos, pier_pos], [design_water_level - depth, design_water_level],
                       color, marker='o', markersize=4)
                ax.text(pier_pos, design_water_level + 0.5, f'墩{i + 1}: {depth:.1f}m',
                       horizontalalignment='center', rotation=90, color=color)

    ax.set_xlabel('距离 (m)')
    ax.set_ylabel('高程 (m)')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    
    return fig

def format_results(params, obstruction_results, flow_areas, flow_distribution,
                  scour_results, local_scour_results):
    """格式化计算结果输出"""
    (total_obstruction_area, obstruction_ratio, pier_obstructions,
     left_obstruction_area, channel_obstruction_area, right_obstruction_area,
     left_obstruction_width, channel_obstruction_width, right_obstruction_width) = obstruction_results
    
    (left_area, channel_area, right_area,
     left_area_after, channel_area_after, right_area_after,
     left_width_after, channel_width_after, right_width_after,
     left_depth_after, channel_depth_after, right_depth_after) = flow_areas
    
    result_text = []
    
    result_text.append("## 桥墩阻水参数")
    result_text.append(f"- 总阻水面积: {total_obstruction_area:.2f} m²")
    result_text.append(f"- 阻水比率: {obstruction_ratio * 100:.2f}%")
    
    result_text.append("\n## 各区域阻水参数")
    result_text.append("\n### 左河滩:")
    result_text.append(f"- 阻水面积: {left_obstruction_area:.2f} m²")
    result_text.append(f"- 阻水宽度: {left_obstruction_width:.2f} m")
    result_text.append(f"- 阻水后过流面积: {left_area_after:.2f} m²")
    result_text.append(f"- 阻水后过流宽度: {left_width_after:.2f} m")
    result_text.append(f"- 平均水深: {left_depth_after:.2f} m")
    result_text.append(f"- 设计流量: {flow_distribution['left_Q_final']:.2f} m³/s")
    
    result_text.append("\n### 河槽:")
    result_text.append(f"- 阻水面积: {channel_obstruction_area:.2f} m²")
    result_text.append(f"- 阻水宽度: {channel_obstruction_width:.2f} m")
    result_text.append(f"- 阻水后过流面积: {channel_area_after:.2f} m²")
    result_text.append(f"- 阻水后过流宽度: {channel_width_after:.2f} m")
    result_text.append(f"- 平均水深: {channel_depth_after:.2f} m")
    result_text.append(f"- 设计流量: {flow_distribution['channel_Q_final']:.2f} m³/s")
    
    result_text.append("\n### 右河滩:")
    result_text.append(f"- 阻水面积: {right_obstruction_area:.2f} m²")
    result_text.append(f"- 阻水宽度: {right_obstruction_width:.2f} m")
    result_text.append(f"- 阻水后过流面积: {right_area_after:.2f} m²")
    result_text.append(f"- 阻水后过流宽度: {right_width_after:.2f} m")
    result_text.append(f"- 平均水深: {right_depth_after:.2f} m")
    result_text.append(f"- 设计流量: {flow_distribution['right_Q_final']:.2f} m³/s")
    
    result_text.append(f"\n- 总设计流量: {params['Design_Q']:.2f} m³/s")
    
    result_text.append("\n## 冲刷计算参数")
    result_text.append(f"- 单宽流量集中系数 A: {scour_results['A']:.2f}")
    result_text.append(f"- 河槽设计流量 Qcp: {flow_distribution['channel_Q_final']:.2f} m³/s")
    result_text.append(f"- 平滩水面宽 B: {scour_results['B']:.2f} m")
    result_text.append(f"- 平滩平均水深 H: {scour_results['H']:.2f} m")
    result_text.append(f"- 河槽阻水后过流宽度 Lcj: {scour_results['Lcj']:.2f} m")
    result_text.append(f"- 设计水位最大水深 hmax: {scour_results['h_max']:.2f} m")
    result_text.append(f"- 河槽平均水深 hc: {scour_results['h_c']:.2f} m")
    
    result_text.append("\n## 64-1计算一般冲刷结果")
    result_text.append(f"- 桥梁一般冲刷深度: {scour_results['scour_depth_64_1']:.2f} m")
    
    result_text.append("\n## 64-2计算一般冲刷结果")
    result_text.append(f"- 桥梁一般冲刷深度: {scour_results['scour_depth_64_2']:.2f} m")
    
    result_text.append("\n## 65-1计算局部冲刷结果")
    result_text.append(f"- 桥梁局部冲刷深度: {local_scour_results['local_scour_65_1']:.2f} m")
    
    result_text.append("\n## 65-2计算局部冲刷结果")
    result_text.append(f"- 桥梁局部冲刷深度: {local_scour_results['local_scour_65_2']:.2f} m")
    
    return "\n".join(result_text)

# 主界面
st.title("🌉 桥梁冲刷计算系统")

# 侧边栏 - 数据输入
st.sidebar.header("📊 断面数据输入")

# 数据输入方式选择
input_method = st.sidebar.radio(
    "选择输入方式",
    ["上传文件", "文本输入"],
    index=0
)

distances = None
elevations = None

if input_method == "上传文件":
    uploaded_file = st.sidebar.file_uploader("上传断面数据文件 (txt格式)", type=['txt'])
    if uploaded_file is not None:
        distances, elevations = read_cross_section_from_file(uploaded_file)
        if distances is not None:
            st.sidebar.success(f"成功读取 {len(distances)} 个数据点")
            st.session_state.distances = distances
            st.session_state.elevations = elevations
else:
    text_input = st.sidebar.text_area(
        "输入断面数据",
        height=200,
        help="格式：每行一个点，用空格或制表符分隔距离和高程\n例如：\n0 100\n10 98\n20 96"
    )
    if text_input:
        distances, elevations = read_cross_section_from_text(text_input)
        if distances is not None:
            st.sidebar.success(f"成功解析 {len(distances)} 个数据点")
            st.session_state.distances = distances
            st.session_state.elevations = elevations

# 使用session state中的数据
if st.session_state.distances is not None:
    distances = st.session_state.distances
    elevations = st.session_state.elevations

# 主内容区域 - 使用tabs组织
tab1, tab2, tab3, tab4 = st.tabs(["参数输入", "计算结果", "断面图形", "自定义绘制"])

with tab1:
    st.header("参数输入")
    
    if distances is None:
        st.warning("⚠️ 请先在侧边栏输入断面数据")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("糙率及纵坡参数")
            n_l = st.number_input("左河滩糙率 n_l", value=0.034, format="%.4f")
            n_c = st.number_input("河槽糙率 n_c", value=0.032, format="%.4f")
            n_r = st.number_input("右河滩糙率 n_r", value=0.034, format="%.4f")
            J = st.number_input("河道纵坡 J", value=0.00173, format="%.6f")
            mu = st.number_input("侧向压缩系数 μ", value=1.0, format="%.2f")
            E = st.number_input("经验系数 E", value=0.86, format="%.2f")
            d = st.number_input("粒径 d (mm)", value=3.0, format="%.1f")
        
        with col2:
            st.subheader("桥梁及水位参数")
            bridge_config = st.text_input("桥梁配置 (如3-32)", value="8-32+1-40+2-64+1-40+3-32")
            pier_width = st.number_input("桥墩净宽 (m)", value=5.0, format="%.2f")
            skew_angle = st.number_input("斜交角度 (度)", value=68.0, format="%.1f")
            bridge_start = st.number_input("起始墩投影距离 (m)", value=-426.0, format="%.2f")
            water_level = st.number_input("平滩水位高程 (m)", value=963.38, format="%.2f")
            design_water_level = st.number_input("设计水位高程 (m)", value=968.52, format="%.2f")
            
            st.subheader("局部冲刷参数")
            K_t = st.number_input("桥墩形状系数", value=1.0, format="%.2f")
            B_1 = st.number_input("桥墩等效宽度 (m)", value=6.0, format="%.2f")
            V = st.number_input("初始流速 (m/s)", value=2.0, format="%.2f")
            Design_Q = st.number_input("设计流量 (m³/s)", value=3480.0, format="%.2f")
            choice_h_p = st.text_input("最大一般冲刷深 (输入'y'自动选择最大值，或输入具体数值)", value="y")
        
        # 填充默认值按钮
        if st.button("填充默认值", use_container_width=True):
            st.rerun()
        
        # 执行计算按钮
        if st.button("🚀 执行计算", type="primary", use_container_width=True):
            try:
                # 验证输入
                if design_water_level <= water_level:
                    st.error("设计水位必须大于平滩水位")
                else:
                    # 准备参数
                    params = {
                        'n_l': n_l,
                        'n_c': n_c,
                        'n_r': n_r,
                        'J': J,
                        'mu': mu,
                        'E': E,
                        'd': d,
                        'water_level': water_level,
                        'design_water_level': design_water_level,
                        'bridge_config': bridge_config,
                        'pier_width': pier_width,
                        'skew_angle': skew_angle,
                        'bridge_start': bridge_start,
                        'K_t': K_t,
                        'B_1': B_1,
                        'V': V,
                        'Design_Q': Design_Q,
                        'choice_h_p': choice_h_p
                    }
                    
                    # 执行计算
                    with st.spinner("正在计算..."):
                        # 计算平滩水位下的水力参数
                        avg_depth, max_depth, _, _ = calculate_hydraulic_parameters(
                            distances, elevations, water_level)
                        
                        if avg_depth is None:
                            raise ValueError("平滩水位设置不合理，无法计算水力参数")
                        
                        # 识别河槽和河滩的分界点
                        boundary1, boundary2 = identify_channel_and_floodplain(
                            distances, elevations, water_level)
                        
                        if boundary1 is None or boundary2 is None:
                            raise ValueError("无法识别河槽和河滩的分界点")
                        
                        # 计算设计水位下的参数
                        avg_depth_design, max_depth_design, flow_area, _ = calculate_hydraulic_parameters(
                            distances, elevations, design_water_level)
                        
                        if avg_depth_design is None:
                            raise ValueError("设计水位设置不合理，无法计算水力参数")
                        
                        # 计算各区域过水面积
                        left_area, channel_area, right_area = calculate_flow_areas(
                            distances, elevations, design_water_level, boundary1, boundary2)
                        
                        if left_area is None:
                            raise ValueError("无法计算各区域过水面积")
                        
                        # 解析桥梁配置
                        spans = parse_bridge_config(bridge_config)
                        if not spans:
                            raise ValueError("桥梁配置解析失败，请检查格式")
                        
                        # 计算桥墩阻水面积
                        intersections = find_waterline_intersections(
                            distances, elevations, design_water_level)
                        
                        obstruction_results = calculate_bridge_obstruction(
                            spans, pier_width, skew_angle, design_water_level, distances, elevations,
                            bridge_start, boundary1, boundary2)
                        
                        (total_obstruction_area, obstruction_ratio, pier_obstructions,
                         left_obstruction_area, channel_obstruction_area, right_obstruction_area,
                         left_obstruction_width, channel_obstruction_width, right_obstruction_width) = obstruction_results
                        
                        # 计算各区域阻水后的过流面积和宽度
                        left_area_after = left_area - left_obstruction_area
                        right_area_after = right_area - right_obstruction_area
                        channel_area_after = channel_area - channel_obstruction_area
                        
                        left_width_after = (boundary1 - intersections[0]) - left_obstruction_width
                        right_width_after = (intersections[1] - boundary2) - right_obstruction_width
                        channel_width_after = (boundary2 - boundary1) - channel_obstruction_width
                        
                        left_width_before = (boundary1 - intersections[0])
                        channel_width_before = (boundary2 - boundary1)
                        right_width_before = (intersections[1] - boundary2)
                        
                        # 计算各区域平均水深
                        left_depth_after = left_area_after / left_width_after if left_width_after > 0 else 0
                        right_depth_after = right_area_after / right_width_after if right_width_after > 0 else 0
                        channel_depth_after = channel_area_after / channel_width_after if channel_width_after > 0 else 0
                        
                        # 计算流量分布
                        flow_distribution = calculate_flow_distribution(
                            params, left_area, channel_area, right_area,
                            left_area_after, channel_area_after, right_area_after,
                            left_width_after, channel_width_after, right_width_after,
                            left_width_before, channel_width_before, right_width_before)
                        
                        # 计算冲刷深度参数
                        B = boundary2 - boundary1
                        H = avg_depth
                        Lcj = channel_width_after
                        h_max = max_depth_design
                        h_c = channel_depth_after
                        B_c = B
                        B_2 = channel_width_after
                        
                        # 计算一般冲刷深度
                        scour_depth_64_1, A = calculate_scour(
                            flow_distribution['channel_Q_final'], B_c, H, Lcj, h_max, h_c,
                            mu, E, d)
                        
                        scour_depth_64_2, A_2 = calculate_scour_64_2(
                            flow_distribution['channel_Q_final'], flow_distribution['Q_c'],
                            B_c, B_2, obstruction_ratio, mu, h_max, B, H)
                        
                        # 确定一般冲刷深度
                        if choice_h_p.lower() in ('y', 'yes', ''):
                            h_p = max(scour_depth_64_1, scour_depth_64_2)
                        else:
                            try:
                                h_p = float(choice_h_p)
                            except ValueError:
                                raise ValueError(
                                    f"输入错误: '{choice_h_p}' 无法转换为浮点数。"
                                    "请输入 'y' 自动选择最大值，或输入具体数值。")
                        
                        # 计算局部冲刷深度
                        local_scour_65_2 = calculate_local_scour(V, K_t, d, B_1, h_p)
                        local_scour_65_1 = calculate_local_scour_65_1(V, K_t, d, B_1, h_p)
                        
                        # 准备结果数据
                        flow_areas = (
                            left_area, channel_area, right_area,
                            left_area_after, channel_area_after, right_area_after,
                            left_width_after, channel_width_after, right_width_after,
                            left_depth_after, channel_depth_after, right_depth_after
                        )
                        
                        scour_results = {
                            'A': A,
                            'B': B,
                            'H': H,
                            'Lcj': Lcj,
                            'h_max': h_max,
                            'h_c': h_c,
                            'scour_depth_64_1': scour_depth_64_1,
                            'scour_depth_64_2': scour_depth_64_2
                        }
                        
                        local_scour_results = {
                            'local_scour_65_1': local_scour_65_1,
                            'local_scour_65_2': local_scour_65_2
                        }
                        
                        # 保存计算结果
                        st.session_state.calculation_results = {
                            'params': params,
                            'obstruction_results': obstruction_results,
                            'flow_areas': flow_areas,
                            'flow_distribution': flow_distribution,
                            'scour_results': scour_results,
                            'local_scour_results': local_scour_results,
                            'distances': distances,
                            'elevations': elevations,
                            'boundary1': boundary1,
                            'boundary2': boundary2,
                            'pier_obstructions': pier_obstructions
                        }
                        
                        st.success("✅ 计算完成！请切换到'计算结果'或'断面图形'标签页查看结果。")
                        st.rerun()
                        
            except Exception as e:
                st.error(f"计算错误: {str(e)}")

with tab2:
    st.header("计算结果")
    
    if st.session_state.calculation_results is None:
        st.info("请先在'参数输入'标签页执行计算")
    else:
        results = st.session_state.calculation_results
        result_text = format_results(
            results['params'],
            results['obstruction_results'],
            results['flow_areas'],
            results['flow_distribution'],
            results['scour_results'],
            results['local_scour_results']
        )
        st.markdown(result_text)
        
        # 下载结果按钮
        st.download_button(
            label="📥 下载计算结果",
            data=result_text,
            file_name="桥梁冲刷计算结果.txt",
            mime="text/plain"
        )

with tab3:
    st.header("断面图形")
    
    if st.session_state.calculation_results is None:
        st.info("请先在'参数输入'标签页执行计算")
    else:
        results = st.session_state.calculation_results
        params = results['params']
        
        fig = plot_cross_section(
            results['distances'],
            results['elevations'],
            params['water_level'],
            params['design_water_level'],
            [results['boundary1'], results['boundary2']],
            results['pier_obstructions'],
            title="河道横断面分析"
        )
        
        st.pyplot(fig)
        
        # 下载图形按钮
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        st.download_button(
            label="📥 下载图形",
            data=buf,
            file_name="桥梁冲刷计算结果图.png",
            mime="image/png"
        )

with tab4:
    st.header("断面自定义绘制")
    st.info("此功能允许您通过绘制方式输入断面数据。")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("绘制设置")
        x_min = st.number_input("横坐标最小值", value=0.0)
        x_max = st.number_input("横坐标最大值", value=100.0)
        y_min = st.number_input("纵坐标最小值", value=0.0)
        y_max = st.number_input("纵坐标最大值", value=100.0)
        spacing = st.number_input("采样间距", value=1.0)
        
        st.info("💡 提示：绘制功能需要手动输入坐标点。")
        
        # 手动输入点
        st.subheader("输入坐标点")
        point_input = st.text_area(
            "输入坐标点 (格式：x1 y1\\nx2 y2\\n...)",
            height=150,
            help="每行一个点，用空格分隔x和y坐标"
        )
        
        if st.button("处理输入的点", use_container_width=True):
            if point_input:
                distances_draw, elevations_draw = read_cross_section_from_text(point_input)
                if distances_draw is not None:
                    st.session_state.distances = distances_draw
                    st.session_state.elevations = elevations_draw
                    st.success(f"成功处理 {len(distances_draw)} 个点")
                    st.rerun()
    
    with col2:
        st.subheader("断面预览")
        if distances is not None and elevations is not None:
            fig_preview = plot_cross_section(distances, elevations, title="当前断面数据")
            st.pyplot(fig_preview)
        else:
            st.info("暂无断面数据")

