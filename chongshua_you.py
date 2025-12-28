import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import math
import re
import logging
from io import StringIO
from datetime import datetime, timedelta
import os
import json
import hashlib
import platform
import subprocess
import base64
import socket
import urllib.request
import urllib.error
try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logging.warning("PIL库未安装，桥梁图片功能将不可用")

# 忽略matplotlib字体警告
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams['axes.unicode_minus'] = False

# 常量定义
MAX_A_COEFFICIENT = 1.8  # 单宽流量集中系数最大值
SAMPLING_INTERVAL = 0.1  # 水力参数计算采样间隔
TRIAL_DAYS = 7  # 试用期天数
REGISTRATION_FILE = "registration.dat"  # 注册信息文件
REGISTRATION_VALID_DAYS = 365  # 注册有效期（天）


class BridgeScourApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("桥梁冲刷计算系统")
        self.geometry("1200x800")
        self.resizable(True, True)
        
        # 设置窗口关闭协议
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 创建 Notebook 分页
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 输入参数页
        self.input_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.input_frame, text="参数输入")

        # 结果显示页
        self.result_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.result_frame, text="计算结果")

        # 图形显示页
        self.plot_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.plot_frame, text="断面图形")
        
        # 断面自定义绘制页
        self.custom_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.custom_frame, text="断面自定义绘制")
        
        # 初始化自定义绘制界面
        self.init_custom_frame()

        # ---------- 整体布局多个FRAME -----------
        # 创建主容器，使用grid布局，左侧参数输入，右侧图片展示
        self.main_container = ttk.Frame(self.input_frame)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧参数输入区域
        self.left_panel = ttk.Frame(self.main_container)
        self.left_panel.grid(row=0, column=0, sticky=(tk.W, tk.N), padx=5, pady=5)
        
        # 右侧图片展示区域
        self.right_panel = ttk.LabelFrame(self.main_container, text="桥梁示意图", padding=10)
        self.right_panel.grid(row=0, column=1, sticky=(tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 创建桥梁示意图
        self.create_bridge_image_panel()

        self.section_frame = ttk.LabelFrame(self.left_panel, text="断面数据", padding=5)
        self.canshu_frame = ttk.LabelFrame(self.left_panel, text="糙率及纵坡参数", padding=5)
        self.bridge_frame = ttk.LabelFrame(self.left_panel, text="桥梁及水位参数", padding=5)
        self.button_frame = ttk.LabelFrame(self.left_panel, text="操作", padding=5)
        self.local_scour_frame = ttk.LabelFrame(self.left_panel, text="局部冲刷参数", padding=5)
        
        self.section_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.canshu_frame.grid(row=1, column=0, sticky=(tk.W, tk.N), padx=5, pady=5)
        self.bridge_frame.grid(row=1, column=1, sticky=(tk.W, tk.N), padx=5, pady=5)
        self.button_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.local_scour_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)

        #1、断面区域
        ttk.Label(self.section_frame, text="横断面数据文件:", font=('SimHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.file_path_label = ttk.Label(self.section_frame, text="未选择文件",  width=40) # 压缩显示宽度
        self.file_path_label.grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)

        self.browse_btn = ttk.Button(self.section_frame, text="浏览文件", command=self.browse_file)
        self.browse_btn.grid(row=1, column=1, padx=5, pady=2)

        self.custom_btn = ttk.Button(self.section_frame, text="自定义", command=self.open_custom_frame)
        self.custom_btn.grid(row=1, column=2, padx=5, pady=2)

        #2、参数区域
        ttk.Label(self.canshu_frame, text="左河滩糙率 n_l:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=2)
        self.n_l_entry = ttk.Entry(self.canshu_frame)
        self.n_l_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(self.canshu_frame, text="河槽糙率 n_c:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
        self.n_c_entry = ttk.Entry(self.canshu_frame)
        self.n_c_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(self.canshu_frame, text="右河滩糙率 n_r:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
        self.n_r_entry = ttk.Entry(self.canshu_frame)
        self.n_r_entry.grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(self.canshu_frame, text="河道纵坡 J:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=2)
        self.J_entry = ttk.Entry(self.canshu_frame)
        self.J_entry.grid(row=3, column=1, padx=5, pady=2)

        ttk.Label(self.canshu_frame, text="侧向压缩系数 μ:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=2)
        self.mu_entry = ttk.Entry(self.canshu_frame)
        self.mu_entry.grid(row=4, column=1, padx=5, pady=2)

        ttk.Label(self.canshu_frame, text="经验系数 E:").grid(row=5, column=0, sticky=tk.W, padx=10, pady=2)
        self.E_entry = ttk.Entry(self.canshu_frame)
        self.E_entry.grid(row=5, column=1, padx=5, pady=2)

        ttk.Label(self.canshu_frame, text="粒径 d (mm):").grid(row=6, column=0, sticky=tk.W, padx=10, pady=2)
        self.d_entry = ttk.Entry(self.canshu_frame)
        self.d_entry.grid(row=6, column=1, padx=5, pady=5)

        # 桥梁参数区域
        ttk.Label(self.bridge_frame , text="桥梁配置 (如3-32):").grid(row=0, column=0, sticky=tk.W, padx=10, pady=2)
        self.bridge_config_entry = ttk.Entry(self.bridge_frame )
        self.bridge_config_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(self.bridge_frame , text="桥墩净宽 (m):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
        self.pier_width_entry = ttk.Entry(self.bridge_frame )
        self.pier_width_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(self.bridge_frame , text="斜交角度 (度):").grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
        self.skew_angle_entry = ttk.Entry(self.bridge_frame )
        self.skew_angle_entry.grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(self.bridge_frame , text="起始墩投影距离 (m):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=2)
        self.bridge_start_entry = ttk.Entry(self.bridge_frame )
        self.bridge_start_entry.grid(row=3, column=1, padx=5, pady=2)

        # 水位输入区域
        ttk.Label(self.bridge_frame, text="水位参数", font=('SimHei', 9, 'bold')).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(self.bridge_frame, text="平滩水位高程 (m):").grid(row=5, column=0, sticky=tk.W, padx=10, pady=2)
        self.water_level_entry = ttk.Entry(self.bridge_frame)
        self.water_level_entry.grid(row=5, column=1, padx=5, pady=2)

        ttk.Label(self.bridge_frame, text="设计水位高程 (m):").grid(row=6, column=0, sticky=tk.W, padx=10, pady=2)
        self.design_water_level_entry = ttk.Entry(self.bridge_frame)
        self.design_water_level_entry.grid(row=6, column=1, padx=5, pady=2)



        # 局部冲刷计算
        ttk.Label(self.local_scour_frame, text="桥墩形状系数:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=2)
        self.K_t_entry = ttk.Entry(self.local_scour_frame)
        self.K_t_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(self.local_scour_frame, text="桥墩等效宽度 (m):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
        self.B_1_entry = ttk.Entry(self.local_scour_frame)
        self.B_1_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(self.local_scour_frame, text="初始流速 (m/s):").grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
        self.V_entry = ttk.Entry(self.local_scour_frame)
        self.V_entry.grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(self.local_scour_frame, text="设计流量 (m3):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=2)
        self.Design_Q_entry = ttk.Entry(self.local_scour_frame)
        self.Design_Q_entry.grid(row=3, column=1, padx=5, pady=2)

        ttk.Label(self.local_scour_frame, text="最大一般冲刷深").grid(row=4, column=0, sticky=tk.W, padx=10, pady=2)
        self.choice_h_p_entry = ttk.Entry(self.local_scour_frame)
        self.choice_h_p_entry.grid(row=4, column=1, padx=5, pady=2)

        self.pier_shape = tk.StringVar(value="无")  # 默认选择"无"

        ttk.Label(self.local_scour_frame, text="选择桥墩形状:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)

        shapes = ["矩形桥墩", "圆形桥墩", "T形桥墩"]
        for i, shape in enumerate(shapes):
            ttk.Radiobutton(
                self.local_scour_frame,
                text=shape,
                variable=self.pier_shape,
                value=shape,
                command=self.update_pier_inputs  # 选择变化时更新显示
            ).grid(row=i + 6, column=0, sticky=tk.W, padx=20, pady=2)

        # 2. 创建各桥墩形状对应的输入区域（初始隐藏）
        self.rect_pier_frame = ttk.LabelFrame(self.local_scour_frame, text="矩形桥墩参数")
        self.circle_pier_frame = ttk.LabelFrame(self.local_scour_frame, text="圆形桥墩参数")
        self.t_pier_frame = ttk.LabelFrame(self.local_scour_frame, text="T形桥墩参数")

        # 3. 在各区域添加对应参数输入框
        self.create_rect_pier_inputs()
        self.create_circle_pier_inputs()
        self.create_t_pier_inputs()

        # 4. 初始状态：所有区域隐藏
        self.update_pier_inputs()

        # 4、按钮frame
        self.init_btn = ttk.Button(self.button_frame, text="填充默认值", command=self.initialize_inputs)
        self.init_btn.grid(row=0, column=0,  padx=100, pady=2, sticky=tk.W)

        # 计算按钮
        self.calculate_btn = ttk.Button(self.button_frame, text="执行计算", command=self.run_calculation)
        self.calculate_btn.grid(row=0, column=1, padx=100, pady=2, sticky=tk.W)

        # ---------- 结果显示页布局 ----------
        self.result_text = tk.Text(self.result_frame, wrap=tk.NONE)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.result_text.config(state=tk.DISABLED)

        # ---------- 图形显示页布局 ----------
        # 创建控制面板
        self.plot_control_frame = ttk.Frame(self.plot_frame)
        self.plot_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 图形自定义按钮
        self.customize_btn = ttk.Button(
            self.plot_control_frame, 
            text="图形自定义", 
            command=self.customize_plot
        )
        self.customize_btn.pack(side=tk.LEFT, padx=5)
        
        # 图形显示区域
        self.figure = plt.Figure(figsize=(8, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 存储图形自定义参数
        self.plot_config = {
            'title': '河道横断面图',
            'xlabel': '距离 (m)',
            'ylabel': '高程 (m)',
            'xmin': None,
            'xmax': None,
            'ymin': None,
            'ymax': None,
            'grid_alpha': 1.0,
            'grid_style': '-'
        }
        
        # 存储当前绘图数据（用于重新绘制）
        self.current_plot_data = {}

        # 数据存储变量
        self.distances = None
        self.elevations = None
        self.file_path = None
        self.project_file_path = None  # 当前项目文件路径
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 检查注册状态
        self.check_registration_status()
    
    def create_bridge_image_panel(self):
        """创建桥梁示意图面板"""
        # 创建一个Canvas用于显示桥梁图片和绘制图标
        canvas_width = 300
        canvas_height = 400
        
        self.bridge_canvas = tk.Canvas(
            self.right_panel, 
            width=canvas_width, 
            height=canvas_height,
            bg='#D3D3D3',  # 默认灰色背景
            relief=tk.SUNKEN,
            borderwidth=2
        )
        self.bridge_canvas.pack(padx=10, pady=10)
        
        # 尝试加载桥梁图片
        self.bridge_image = None
        self.bridge_photo = None
        self.load_bridge_image(canvas_width, canvas_height)
        
        # 绘制图标和标签
        self.draw_bridge_icons()
        
        # 添加说明文字
        info_label = ttk.Label(
            self.right_panel, 
            text="桥梁冲刷计算示意图\n\n本软件用于计算桥梁基础\n在河流冲刷作用下的\n冲刷深度和安全评估",
            justify=tk.CENTER,
            font=('SimHei', 9)
        )
        info_label.pack(pady=5)
    
    def load_bridge_image(self, canvas_width, canvas_height):
        """加载桥梁图片资源"""
        if not HAS_PIL:
            # 如果没有PIL库，直接显示灰色区域
            self.bridge_canvas.create_rectangle(
                10, 10, canvas_width - 10, canvas_height - 10,
                fill='#A9A9A9', outline='#808080', width=2
            )
            self.bridge_canvas.create_text(
                canvas_width // 2, canvas_height // 2,
                text="桥梁示意图\n(请安装PIL库并\n将图片放置在\nresources/bridge_image.png)",
                font=('SimHei', 9),
                fill='#555555',
                justify=tk.CENTER
            )
            return
        
        # 图片资源路径：resources/bridge_image.png
        image_paths = [
            os.path.join('resources', 'bridge_image.png'),
            os.path.join('resource', 'bridge_image.png'),
            'bridge_image.png'
        ]
        
        for img_path in image_paths:
            if os.path.exists(img_path):
                try:
                    # 加载并调整图片大小
                    img = Image.open(img_path)
                    img = img.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                    self.bridge_photo = ImageTk.PhotoImage(img)
                    self.bridge_image = img
                    
                    # 在canvas上显示图片
                    self.bridge_canvas.create_image(
                        canvas_width // 2, canvas_height // 2,
                        image=self.bridge_photo,
                        anchor=tk.CENTER
                    )
                    return
                except Exception as e:
                    logging.warning(f"加载桥梁图片失败: {str(e)}")
        
        # 如果没有找到图片，显示灰色区域
        self.bridge_canvas.create_rectangle(
            10, 10, canvas_width - 10, canvas_height - 10,
            fill='#A9A9A9', outline='#808080', width=2
        )
        self.bridge_canvas.create_text(
            canvas_width // 2, canvas_height // 2,
            text="桥梁示意图\n(请将图片放置在\nresources/bridge_image.png)",
            font=('SimHei', 10),
            fill='#555555',
            justify=tk.CENTER
        )
    
    def draw_bridge_icons(self):
        """在canvas上绘制图标和标签"""
        canvas = self.bridge_canvas
        width = canvas.winfo_reqwidth()
        height = canvas.winfo_reqheight()
        
        # 如果已加载图片，在图片上方/下方绘制图标
        if self.bridge_image is None:
            # 没有图片时，在灰色区域上方绘制一些图标
            icon_y = 30
            
            # 绘制水流图标（波浪线）
            for i in range(3):
                x = width * 0.2 + i * width * 0.3
                canvas.create_arc(
                    x - 15, icon_y - 5, x + 15, icon_y + 5,
                    start=0, extent=180, outline='#4682B4', width=2
                )
            
            # 绘制桥墩图标（小矩形）
            pier_icon_x = width * 0.5
            pier_icon_y = icon_y + 30
            canvas.create_rectangle(
                pier_icon_x - 10, pier_icon_y - 20,
                pier_icon_x + 10, pier_icon_y,
                fill='#696969', outline='#2F4F4F', width=2
            )
            
            # 绘制冲刷深度图标（向下箭头）
            scour_icon_x = width * 0.5
            scour_icon_y = pier_icon_y + 20
            canvas.create_line(
                scour_icon_x, pier_icon_y,
                scour_icon_x, scour_icon_y,
                fill='red', width=2, dash=(3, 2)
            )
            canvas.create_polygon(
                scour_icon_x, scour_icon_y,
                scour_icon_x - 5, scour_icon_y - 8,
                scour_icon_x + 5, scour_icon_y - 8,
                fill='red', outline='red'
            )
        else:
            # 有图片时，在图片边缘绘制一些装饰性图标
            # 在底部绘制图标说明
            icon_y = height - 50
            
            # 绘制水流方向箭头
            canvas.create_line(
                width * 0.2, icon_y,
                width * 0.8, icon_y,
                fill='#0000FF', width=2, arrow=tk.LAST, arrowshape=(8, 10, 3)
            )
            canvas.create_text(
                width * 0.5, icon_y - 15,
                text="水流方向", font=('SimHei', 8), fill='blue'
            )
            
            # 绘制冲刷深度标注
            canvas.create_line(
                width * 0.1, icon_y - 30,
                width * 0.1, icon_y - 10,
                fill='red', width=2, dash=(3, 2)
            )
            canvas.create_text(
                width * 0.1 + 20, icon_y - 20,
                text="冲刷", font=('SimHei', 8), fill='red'
            )

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # 创建"文件"菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        
        # 添加菜单项
        file_menu.add_command(label="新建项目", command=self.new_project)
        file_menu.add_command(label="导入项目", command=self.load_project)
        file_menu.add_separator()
        file_menu.add_command(label="保存项目", command=self.save_project)
        file_menu.add_command(label="另存项目", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="输出结果", command=self.export_results)
        
        # 创建"注册使用"菜单
        register_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="注册使用", menu=register_menu)
        register_menu.add_command(label="输入注册码", command=self.enter_registration_code)
        register_menu.add_command(label="开始试用", command=self.start_trial)

    def get_all_inputs(self):
        """获取所有输入框的值"""
        inputs = {
            'file_path': self.file_path,
            'n_l': self.n_l_entry.get(),
            'n_c': self.n_c_entry.get(),
            'n_r': self.n_r_entry.get(),
            'J': self.J_entry.get(),
            'mu': self.mu_entry.get(),
            'E': self.E_entry.get(),
            'd': self.d_entry.get(),
            'bridge_config': self.bridge_config_entry.get(),
            'pier_width': self.pier_width_entry.get(),
            'skew_angle': self.skew_angle_entry.get(),
            'bridge_start': self.bridge_start_entry.get(),
            'water_level': self.water_level_entry.get(),
            'design_water_level': self.design_water_level_entry.get(),
            'K_t': self.K_t_entry.get(),
            'B_1': self.B_1_entry.get(),
            'V': self.V_entry.get(),
            'Design_Q': self.Design_Q_entry.get(),
            'choice_h_p': self.choice_h_p_entry.get(),
            'pier_shape': self.pier_shape.get(),
            'rect_h1': self.rect_h1_entry.get() if hasattr(self, 'rect_h1_entry') else '',
            'rect_h2': self.rect_h2_entry.get() if hasattr(self, 'rect_h2_entry') else '',
            'circle_d': self.circle_d_entry.get() if hasattr(self, 'circle_d_entry') else '',
            't_width': self.t_width_entry.get() if hasattr(self, 't_width_entry') else '',
            't_height': self.t_height_entry.get() if hasattr(self, 't_height_entry') else '',
        }
        return inputs

    def set_all_inputs(self, inputs):
        """设置所有输入框的值"""
        if 'file_path' in inputs and inputs['file_path']:
            self.file_path = inputs['file_path']
            self.file_path_label.config(text=self.file_path)
            # 如果文件路径存在，尝试读取断面数据
            if os.path.exists(self.file_path):
                self.distances, self.elevations = self.read_cross_section()
        
        self.n_l_entry.delete(0, tk.END)
        self.n_l_entry.insert(0, inputs.get('n_l', ''))
        
        self.n_c_entry.delete(0, tk.END)
        self.n_c_entry.insert(0, inputs.get('n_c', ''))
        
        self.n_r_entry.delete(0, tk.END)
        self.n_r_entry.insert(0, inputs.get('n_r', ''))
        
        self.J_entry.delete(0, tk.END)
        self.J_entry.insert(0, inputs.get('J', ''))
        
        self.mu_entry.delete(0, tk.END)
        self.mu_entry.insert(0, inputs.get('mu', ''))
        
        self.E_entry.delete(0, tk.END)
        self.E_entry.insert(0, inputs.get('E', ''))
        
        self.d_entry.delete(0, tk.END)
        self.d_entry.insert(0, inputs.get('d', ''))
        
        self.bridge_config_entry.delete(0, tk.END)
        self.bridge_config_entry.insert(0, inputs.get('bridge_config', ''))
        
        self.pier_width_entry.delete(0, tk.END)
        self.pier_width_entry.insert(0, inputs.get('pier_width', ''))
        
        self.skew_angle_entry.delete(0, tk.END)
        self.skew_angle_entry.insert(0, inputs.get('skew_angle', ''))
        
        self.bridge_start_entry.delete(0, tk.END)
        self.bridge_start_entry.insert(0, inputs.get('bridge_start', ''))
        
        self.water_level_entry.delete(0, tk.END)
        self.water_level_entry.insert(0, inputs.get('water_level', ''))
        
        self.design_water_level_entry.delete(0, tk.END)
        self.design_water_level_entry.insert(0, inputs.get('design_water_level', ''))
        
        self.K_t_entry.delete(0, tk.END)
        self.K_t_entry.insert(0, inputs.get('K_t', ''))
        
        self.B_1_entry.delete(0, tk.END)
        self.B_1_entry.insert(0, inputs.get('B_1', ''))
        
        self.V_entry.delete(0, tk.END)
        self.V_entry.insert(0, inputs.get('V', ''))
        
        self.Design_Q_entry.delete(0, tk.END)
        self.Design_Q_entry.insert(0, inputs.get('Design_Q', ''))
        
        self.choice_h_p_entry.delete(0, tk.END)
        self.choice_h_p_entry.insert(0, inputs.get('choice_h_p', ''))
        
        if 'pier_shape' in inputs:
            self.pier_shape.set(inputs.get('pier_shape', '无'))
            self.update_pier_inputs()
        
        if hasattr(self, 'rect_h1_entry') and 'rect_h1' in inputs:
            self.rect_h1_entry.delete(0, tk.END)
            self.rect_h1_entry.insert(0, inputs.get('rect_h1', ''))
        
        if hasattr(self, 'rect_h2_entry') and 'rect_h2' in inputs:
            self.rect_h2_entry.delete(0, tk.END)
            self.rect_h2_entry.insert(0, inputs.get('rect_h2', ''))
        
        if hasattr(self, 'circle_d_entry') and 'circle_d' in inputs:
            self.circle_d_entry.delete(0, tk.END)
            self.circle_d_entry.insert(0, inputs.get('circle_d', ''))
        
        if hasattr(self, 't_width_entry') and 't_width' in inputs:
            self.t_width_entry.delete(0, tk.END)
            self.t_width_entry.insert(0, inputs.get('t_width', ''))
        
        if hasattr(self, 't_height_entry') and 't_height' in inputs:
            self.t_height_entry.delete(0, tk.END)
            self.t_height_entry.insert(0, inputs.get('t_height', ''))

    def clear_all_inputs(self):
        """清空所有输入框"""
        self.file_path = None
        self.file_path_label.config(text="未选择文件")
        self.distances = None
        self.elevations = None
        
        # 清空所有Entry控件
        entries = [
            self.n_l_entry, self.n_c_entry, self.n_r_entry, self.J_entry,
            self.mu_entry, self.E_entry, self.d_entry,
            self.bridge_config_entry, self.pier_width_entry, self.skew_angle_entry,
            self.bridge_start_entry, self.water_level_entry, self.design_water_level_entry,
            self.K_t_entry, self.B_1_entry, self.V_entry, self.Design_Q_entry,
            self.choice_h_p_entry
        ]
        
        for entry in entries:
            entry.delete(0, tk.END)
        
        # 清空桥墩形状相关输入
        if hasattr(self, 'rect_h1_entry'):
            self.rect_h1_entry.delete(0, tk.END)
        if hasattr(self, 'rect_h2_entry'):
            self.rect_h2_entry.delete(0, tk.END)
        if hasattr(self, 'circle_d_entry'):
            self.circle_d_entry.delete(0, tk.END)
        if hasattr(self, 't_width_entry'):
            self.t_width_entry.delete(0, tk.END)
        if hasattr(self, 't_height_entry'):
            self.t_height_entry.delete(0, tk.END)
        
        # 重置桥墩形状选择
        self.pier_shape.set("无")
        self.update_pier_inputs()
        
        # 清空结果显示
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.config(state=tk.DISABLED)
        
        # 清空图形
        self.figure.clear()
        self.canvas.draw()

    def new_project(self):
        """新建项目"""
        # 清空所有输入框
        self.clear_all_inputs()
        
        # 打开文件保存对话框
        file_path = filedialog.asksaveasfilename(
            defaultextension=".dat",
            filetypes=[("数据文件", "*.dat"), ("所有文件", "*.*")],
            title="新建项目 - 选择保存位置"
        )
        
        if file_path:
            self.project_file_path = file_path
            # 创建一个空的项目文件
            project_data = self.get_all_inputs()
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("新建项目", f"项目已创建:\n{file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"创建项目文件失败: {str(e)}")

    def load_project(self):
        """导入项目"""
        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            defaultextension=".dat",
            filetypes=[("数据文件", "*.dat"), ("所有文件", "*.*")],
            title="导入项目 - 选择项目文件"
        )
        
        if file_path:
            try:
                # 读取项目文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                
                # 加载数据到输入框
                self.set_all_inputs(project_data)
                
                # 更新项目文件路径
                self.project_file_path = file_path
                
                messagebox.showinfo("导入成功", f"项目已导入:\n{file_path}")
                
                # 如果导入了断面文件路径，尝试切换到图形标签页显示
                if self.file_path and self.distances is not None and self.elevations is not None:
                    self.notebook.select(self.plot_frame)
                    self.plot_cross_section(
                        distances=self.distances,
                        elevations=self.elevations,
                        title="导入的断面图"
                    )
                
            except json.JSONDecodeError:
                messagebox.showerror("导入失败", "项目文件格式错误，无法解析JSON数据")
            except FileNotFoundError:
                messagebox.showerror("导入失败", "项目文件不存在")
            except Exception as e:
                messagebox.showerror("导入失败", f"导入项目失败: {str(e)}")

    def save_project(self):
        """保存项目"""
        if not self.project_file_path:
            # 如果没有项目文件路径，执行另存为
            self.save_project_as()
            return
        
        try:
            project_data = self.get_all_inputs()
            with open(self.project_file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("保存成功", f"项目已保存至:\n{self.project_file_path}")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存项目失败: {str(e)}")

    def save_project_as(self):
        """另存项目"""
        # 如果已有项目路径，使用其目录作为默认目录
        initial_dir = None
        initial_file = None
        if self.project_file_path:
            initial_dir = os.path.dirname(self.project_file_path)
            initial_file = os.path.basename(self.project_file_path)
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".dat",
            filetypes=[("数据文件", "*.dat"), ("所有文件", "*.*")],
            title="另存项目",
            initialdir=initial_dir,
            initialfile=initial_file
        )
        
        if file_path:
            try:
                project_data = self.get_all_inputs()
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, ensure_ascii=False, indent=2)
                self.project_file_path = file_path
                messagebox.showinfo("保存成功", f"项目已保存至:\n{file_path}")
            except Exception as e:
                messagebox.showerror("保存失败", f"保存项目失败: {str(e)}")

    def export_results(self):
        """输出计算结果"""
        # 获取计算结果文本
        result_text = self.result_text.get(1.0, tk.END)
        
        if not result_text.strip():
            messagebox.showwarning("提示", "当前没有计算结果可导出")
            return
        
        # 打开文件保存对话框
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"计算结果_{timestamp}.txt"
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="输出计算结果",
            initialfile=default_filename
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(result_text)
                messagebox.showinfo("导出成功", f"计算结果已导出至:\n{file_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"导出结果失败: {str(e)}")

    def create_rect_pier_inputs(self):
        """创建矩形桥墩的输入框"""
        ttk.Label(self.rect_pier_frame, text="h1 (m):").grid(row=0, column=0, padx=5, pady=2)
        self.rect_h1_entry = ttk.Entry(self.rect_pier_frame, width=10)
        self.rect_h1_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(self.rect_pier_frame, text="h2 (m):").grid(row=1, column=0, padx=5, pady=2)
        self.rect_h2_entry = ttk.Entry(self.rect_pier_frame, width=10)
        self.rect_h2_entry.grid(row=1, column=1, padx=5, pady=2)

        # 更多矩形桥墩参数...

    def create_circle_pier_inputs(self):
        """创建圆形桥墩的输入框"""
        ttk.Label(self.circle_pier_frame, text="直径 (m):").grid(row=0, column=0, padx=5, pady=2)
        self.circle_d_entry = ttk.Entry(self.circle_pier_frame, width=10)
        self.circle_d_entry.grid(row=0, column=1, padx=5, pady=2)

        # 更多圆形桥墩参数...

    def create_t_pier_inputs(self):
        """创建T形桥墩的输入框"""
        ttk.Label(self.t_pier_frame, text="宽度 (m):").grid(row=0, column=0, padx=5, pady=2)
        self.t_width_entry = ttk.Entry(self.t_pier_frame, width=10)
        self.t_width_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(self.t_pier_frame, text="高度 (m):").grid(row=1, column=0, padx=5, pady=2)
        self.t_height_entry = ttk.Entry(self.t_pier_frame, width=10)
        self.t_height_entry.grid(row=1, column=1, padx=5, pady=2)

        # 更多T形桥墩参数...

    def update_pier_inputs(self):
        """根据选择的桥墩形状更新显示的输入区域"""
        # 隐藏所有区域
        self.rect_pier_frame.grid_forget()
        self.circle_pier_frame.grid_forget()
        self.t_pier_frame.grid_forget()

        # 根据选择显示对应区域
        if self.pier_shape.get() == "矩形桥墩":
            self.rect_pier_frame.grid(row=6, column=1, rowspan=5, padx=5, pady=5, sticky=tk.NW)
        elif self.pier_shape.get() == "圆形桥墩":
            self.circle_pier_frame.grid(row=6, column=1, rowspan=5, padx=5, pady=5, sticky=tk.NW)
        elif self.pier_shape.get() == "T形桥墩":
            self.t_pier_frame.grid(row=6, column=1, rowspan=5, padx=5, pady=5, sticky=tk.NW)



    def browse_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("文本文件", "*.txt")])
        if self.file_path:
            self.file_path_label.config(text=self.file_path)

            # 读取断面数据
            self.distances, self.elevations = self.read_cross_section()
            if self.distances is not None and self.elevations is not None:
                # 切换到图形标签页
                self.notebook.select(self.plot_frame)

                # 在画布上绘制断面图
                self.plot_cross_section(
                    distances=self.distances,
                    elevations=self.elevations,
                    title="初始断面图，确定平滩水位"
                )

    def initialize_inputs(self):
        """为所有输入框填充默认初始值"""
        default_values = {
            # 糙率及纵坡参数
            self.n_l_entry: 0.034,  # 左河滩糙率默认值（示例值）
            self.n_c_entry: 0.032,  # 河槽糙率默认值（示例值）
            self.n_r_entry: 0.034,  # 右河滩糙率默认值（示例值）
            self.J_entry: 0.00173,  # 河道纵坡默认值（示例值）

            # 冲刷计算参数
            self.mu_entry: 1,  # 侧向压缩系数默认值
            self.E_entry: 0.86,  # 经验系数默认值
            self.d_entry: 3.0,  # 粒径默认值（50mm）

            # 水位参数
            self.water_level_entry: 963.38,  # 平滩水位默认高程
            self.design_water_level_entry: 968.52,  # 设计水位默认高程

            # 桥梁参数
            self.bridge_config_entry: "8-32+1-40+2-64+1-40+3-32",  # 桥梁配置默认值（3孔32米）
            self.pier_width_entry: 5,  # 桥墩净宽默认值（1.5米）
            self.skew_angle_entry: 68,  # 斜交角度默认值（0度，正交）
            self.bridge_start_entry: -426.0,  # 起始墩投影距离默认值（20米）
            self.K_t_entry:1,
            self.B_1_entry:6,
            self.V_entry:2,
            self.Design_Q_entry:3480,
            self.choice_h_p_entry:'y',
        }

        # 批量设置输入框值
        for entry, value in default_values.items():
            entry.delete(0, tk.END)  # 清空现有内容
            entry.insert(0, str(value))  # 插入默认值


    def read_cross_section(self):
        """读取断面数据，优先使用自定义输入的数据"""
        # 如果已有自定义输入的数据，直接返回
        if self.distances is not None and self.elevations is not None:
            return self.distances, self.elevations
        
        # 否则从文件读取
        if self.file_path is None:
            return None, None
        
        try:
            data = np.loadtxt(self.file_path)
            return data[:, 0], data[:, 1]
        except Exception as e:
            messagebox.showerror("数据读取错误", f"无法读取断面数据: {str(e)}")
            return None, None

    def find_waterline_intersections(self, distances, elevations, water_level):
        # 与原代码逻辑一致，省略重复实现...
        # 从左向右查找左岸交点
        left_intersection = None
        for i in range(len(distances) - 1):
            if (elevations[i] <= water_level and elevations[i + 1] > water_level) or \
                    (elevations[i] >= water_level and elevations[i + 1] < water_level):
                # 线性插值计算交点
                x = distances[i] + (water_level - elevations[i]) * \
                    (distances[i + 1] - distances[i]) / (elevations[i + 1] - elevations[i])
                left_intersection = x
                break

        # 从右向左查找右岸交点
        right_intersection = None
        for i in range(len(distances) - 1, 0, -1):
            if (elevations[i] <= water_level and elevations[i - 1] > water_level) or \
                    (elevations[i] >= water_level and elevations[i - 1] < water_level):
                # 线性插值计算交点
                x = distances[i] + (water_level - elevations[i]) * \
                    (distances[i - 1] - distances[i]) / (elevations[i - 1] - elevations[i])
                right_intersection = x
                break

        # 返回左右交点
        if left_intersection is not None and right_intersection is not None:
            return [left_intersection, right_intersection]


    def calculate_hydraulic_parameters(self, distances, elevations, water_level, interval=SAMPLING_INTERVAL):
        """计算水力参数：平均水深、最大水深、过流面积"""
        # 找到水位线与断面的交点
        intersections = self.find_waterline_intersections(distances, elevations, water_level)

        if len(intersections) < 2:
            return None, None, None, None

        # 确定水流区域
        left_boundary, right_boundary = intersections

        # 创建均匀间隔的采样点
        sample_points = np.arange(left_boundary, right_boundary + interval, interval)

        # 计算每个采样点的水深
        water_depths = []
        for x in sample_points:
            # 找到最接近的两个数据点进行线性插值
            idx = np.searchsorted(distances, x)

            if idx == 0:
                elevation = elevations[0]
            elif idx >= len(distances):
                elevation = elevations[-1]
            else:
                # 线性插值计算高程
                ratio = (x - distances[idx - 1]) / (distances[idx] - distances[idx - 1])
                elevation = elevations[idx - 1] + ratio * (elevations[idx] - elevations[idx - 1])

            # 计算水深
            depth = max(0, water_level - elevation)
            water_depths.append(depth)

        water_depths = np.array(water_depths)

        # 计算水力参数
        max_depth = np.max(water_depths)
        avg_depth = np.mean(water_depths)  # 使用平均水深

        # 计算过流面积（使用梯形法则）
        flow_area = np.trapz(water_depths, sample_points)

        return avg_depth, max_depth, flow_area, intersections

    def identify_channel_and_floodplain(self, distances, elevations, water_level):
        """识别河槽和河滩的分界点"""
        # 找到水位线与断面的交点
        intersections = self.find_waterline_intersections(distances, elevations, water_level)

        if len(intersections) == 2:
            return intersections[0], intersections[1]  # 直接返回左右交点作为河槽边界

        return None, None

    def parse_bridge_config(self, config_str):
        """解析桥梁配置字符串，如"3-32"或"1-24+3-32" """
        spans = []
        # 使用正则表达式匹配格式如"数字-数字"的片段
        parts = re.findall(r'(\d+)-(\d+)', config_str)

        for count_str, span_str in parts:
            count = int(count_str)
            span = float(span_str)
            spans.extend([span] * count)

        return spans

    def calculate_bridge_obstruction(self, spans, pier_width, skew_angle, water_level, distances, elevations, bridge_start,
                                 left_channel_boundary, right_channel_boundary):
        """计算桥墩阻水面积和阻水比率，同时区分区域"""
        # 计算水流宽度
        intersections = self.find_waterline_intersections(distances, elevations, water_level)
        if len(intersections) < 2:
            return 0, 0, [], [], [], [], []

        # 计算桥墩位置（桥墩中心坐标）
        pier_positions = []

        # 起始桥墩位置（根据输入的起始距离调整）
        current_position = bridge_start
        pier_positions.append(current_position)

        # 计算后续桥墩位置（考虑斜交角度）
        for span in spans:
            # 计算斜交角度下的投影距离
            projected_span = span * math.cos(math.radians(skew_angle))
            current_position += projected_span
            pier_positions.append(current_position)

        # 计算桥墩实际阻水宽度（考虑斜交角度）
        effective_pier_width = pier_width
        # effective_pier_width = pier_width * math.cos(math.radians(skew_angle))
        # 计算每个桥墩的阻水面积并累加
        total_obstruction_area = 0
        left_obstruction_area = 0
        channel_obstruction_area = 0
        right_obstruction_area = 0

        left_obstruction_width = 0
        channel_obstruction_width = 0
        right_obstruction_width = 0

        pier_obstructions = []

        for pier_pos in pier_positions:
            # 计算桥墩在断面上的水平投影距离
            projected_pos = pier_pos

            # 找到投影位置在断面数据中的索引
            if projected_pos < distances[0] or projected_pos > distances[-1]:
                continue  # 桥墩位置超出断面范围

            # 找到最接近的两个点进行插值
            idx = np.searchsorted(distances, projected_pos)
            if idx == 0:
                depth = water_level - elevations[0]
            elif idx >= len(distances):
                depth = water_level - elevations[-1]
            else:
                # 线性插值计算水深
                ratio = (projected_pos - distances[idx - 1]) / (distances[idx] - distances[idx - 1])
                elevation = elevations[idx - 1] + ratio * (elevations[idx] - elevations[idx - 1])
                depth = water_level - elevation

            # 确保水深为正
            depth = max(0, depth)

            # 计算单个桥墩的阻水面积
            pier_area = effective_pier_width * depth
            total_obstruction_area += pier_area

            # 确定桥墩所在区域
            if projected_pos < left_channel_boundary:
                # 左河滩
                left_obstruction_area += pier_area
                left_obstruction_width += effective_pier_width
            elif projected_pos > right_channel_boundary:
                # 右河滩
                right_obstruction_area += pier_area
                right_obstruction_width += effective_pier_width
            else:
                # 河槽
                channel_obstruction_area += pier_area
                channel_obstruction_width += effective_pier_width

            # 记录每个桥墩的信息
            pier_obstructions.append({
                'position': projected_pos,
                'depth': depth,
                'area': pier_area,
                'region': '左河滩' if projected_pos < left_channel_boundary else
                '右河滩' if projected_pos > right_channel_boundary else '河槽'
            })

        # 计算水力参数
        _, _, flow_area, _ = self.calculate_hydraulic_parameters(distances, elevations, water_level)

        # 计算阻水比率
        obstruction_ratio = total_obstruction_area / flow_area if flow_area > 0 else 0

        return (total_obstruction_area, obstruction_ratio, pier_obstructions,
                left_obstruction_area, channel_obstruction_area, right_obstruction_area,
                left_obstruction_width, channel_obstruction_width, right_obstruction_width)

    def calculate_flow(self, area, width, n, J):
        """计算流量"""
        if width <= 0:
            return 0, 0, 0  # 流量, 流速, 水力半径

        # 计算平均水深
        avg_depth = area / width

        # 计算水力半径 (假设宽浅河道，R ≈ 水深)
        hydraulic_radius = avg_depth

        # 计算谢才系数 (曼宁公式)
        C = (hydraulic_radius ** (1 / 6)) / n

        # 计算流速 (谢才公式)
        velocity = C * math.sqrt(J * hydraulic_radius)

        # 计算流量
        discharge = area * velocity

        return discharge, velocity, hydraulic_radius

    # def calculate_scour(self, channel_Q, B, H, Lcj, h_max, h_c, mu, E, d):
    #     """计算桥梁一般冲刷深度64-1"""
    #     # 计算单宽流量集中系数 A
    #     A = (math.sqrt(B) / H) ** 0.15

    #     # 限制 A 不超过最大值
    #     A = min(A, MAX_A_COEFFICIENT)

    #     # 计算冲刷深度
    #     scour_depth = (A * channel_Q / (mu * Lcj * E * d ** (1 / 6))) ** (3 / 5) * (h_max / h_c)

    #     return scour_depth, A

    def calculate_scour(self, channel_Q, B, H, Lcj, h_max, h_c, mu, E, d):
        """
        计算桥梁一般冲刷深度（64-1修正式，匹配图片8.3.1-4式）
        """
    # 1. 计算单宽流量集中系数 A_d（对应图片的A_d）
        A_d = (math.sqrt(B) / H) ** 0.15
    # 限制A_d不超过最大值
        A_d = min(A_d, MAX_A_COEFFICIENT)
    # 2. 计算图片中分子的核心项：(h_cm / h_cq)^(5/3)
        h_ratio = (h_max / h_c) ** (5 / 3)  # 对应图片的(h_cm/h_cq)^(5/3)

    # 3. 严格匹配图片公式结构
        numerator = A_d * (channel_Q / (mu * Lcj)) * h_ratio  # 分子部分
        denominator = E * (d ** (1 / 6))  # 分母部分
        scour_depth = (numerator / denominator) ** (3 / 5)  # 整体3/5次方
        return scour_depth, A_d

    # def calculate_scour_64_2(self, Q_2, Q_c, B_c, B_2, lambda_, mu, h_cm, B_z, H_z):
    #     """
    #     根据64-2计算公式计算桥梁一般冲刷后的最大水深
    #     """
    #     # 计算Ad
    #     A_d = (math.sqrt(B_z) / H_z) ** 0.15
    #     if A_d > MAX_A_COEFFICIENT:
    #         A_d = MAX_A_COEFFICIENT
    #     # 计算hp
    #     h_p = 1.04 * (A_d * (Q_2 / Q_c) ** 0.90 * (B_c / ((1 - lambda_) * mu * B_2)) ** 0.66 * h_cm)
    #     return h_p, A_d

    def calculate_scour_64_2(self, Q_2, Q_c, B_c, B_2, lambda_, mu, h_cm, B_z, H_z):
        """
        根据64-2计算公式计算桥梁一般冲刷后的最大水深（匹配图片公式）
        注：入参中B_2实际对应图片的B_eg（桥长范围内河槽宽度）
        """
        # 计算Ad（匹配图片8.3.1-3式）
        A_d = (math.sqrt(B_z) / H_z) ** 0.15
        if A_d > MAX_A_COEFFICIENT:
            A_d = MAX_A_COEFFICIENT
        
        # 修正：按图片公式，分母是(1-lambda_) * mu * B_2（B_2对应图片B_eg）
        term1 = (A_d * (Q_2 / Q_c)) ** 0.90  # 对应公式中(A_d·Q2/Qc)^0.90
        term2 = (B_c / ((1 - lambda_) * mu * B_2)) ** 0.66  # 对应公式中(Bc/((1-λ)μBcg))^0.66
        
        # 严格匹配图片公式（保留1.04系数）
        h_p = 1.04 * term1 * term2 * h_cm
        
        return h_p, A_d



    def calculate_local_scour(self, V, K_t, d, B_1, h_p):
        """
        根据65-2计算公式计算桥墩局部冲刷深度
        """
        # 计算V_0
        V_0 = 0.28 * (d + 0.7) ** 0.5
        # 计算V_0_prime
        V_0_prime = 0.12 * (d + 0.5) ** 0.55
        # 计算K_η2
        K_η2 = (0.0023 / (d ** 2.2)) + 0.375 * d ** 0.24
        # 计算n2
        n2 = (V_0 / V) ** (0.23 + 0.19 * math.log10(d))
        if V <= V_0:
            h_b = K_t * K_η2 * B_1 ** 0.6 * h_p ** 0.15 * ((V - V_0_prime) / V_0)
        else:
            h_b = K_t * K_η2 * B_1 ** 0.6 * h_p ** 0.15 * ((V - V_0_prime) / V_0) ** n2
        return h_b

    def calculate_local_scour_65_1(self, V, K_t, d, B_1, h_p):
        """
        根据65-1计算公式计算桥墩局部冲刷深度
        """
        # 计算V_0
        V_0 = 0.0246 * (h_p / d) ** 0.14 * math.sqrt(332 * d + (10 + h_p) / (d ** 0.72))
        # 计算K_η1
        K_η1 = 0.8 * (1 / (d ** 0.45) + 1 / (d ** 0.15))
        # 计算V_0_prime
        V_0_prime = 0.462 * (d / B_1) ** 0.06 * V_0
        # 计算n1
        n1 = (V_0 / V) ** (0.25 * d ** 0.19)

        if V <= V_0:
            h_b = K_t * K_η1 * B_1 ** 0.6 * (V - V_0_prime)
        else:
            h_b = K_t * K_η1 * B_1 ** 0.6 * (V_0 - V_0_prime) * ((V - V_0_prime) / (V_0 - V_0_prime)) ** n1

        return h_b


    def update_result_display(self, text):
        """更新结果显示区域"""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, text)
        self.result_text.config(state=tk.DISABLED)
        self.result_text.see(tk.END)

    def validate_inputs(self):
        """验证输入参数的有效性"""
        # 检查是否有断面数据（文件或自定义输入）
        if self.file_path is None and (self.distances is None or self.elevations is None):
            raise ValueError("请先选择断面数据文件或使用自定义输入断面数据")
        
        required_fields = {
            'n_l_entry': '左河滩糙率',
            'n_c_entry': '河槽糙率',
            'n_r_entry': '右河滩糙率',
            'J_entry': '河道纵坡',
            'mu_entry': '侧向压缩系数',
            'E_entry': '经验系数',
            'd_entry': '粒径',
            'water_level_entry': '平滩水位高程',
            'design_water_level_entry': '设计水位高程',
            'bridge_config_entry': '桥梁配置',
            'pier_width_entry': '桥墩净宽',
            'skew_angle_entry': '斜交角度',
            'bridge_start_entry': '起始墩投影距离',
            'K_t_entry': '桥墩形状系数',
            'B_1_entry': '桥墩等效宽度',
            'V_entry': '初始流速',
            'Design_Q_entry': '设计流量',
            'choice_h_p_entry': '最大一般冲刷深'
        }
        
        missing_fields = []
        for field, name in required_fields.items():
            entry = getattr(self, field)
            if not entry.get().strip():
                missing_fields.append(name)
        
        if missing_fields:
            raise ValueError(f"以下参数未填写: {', '.join(missing_fields)}")
        
        # 验证数值范围
        water_level = float(self.water_level_entry.get())
        design_water_level = float(self.design_water_level_entry.get())
        if design_water_level <= water_level:
            raise ValueError("设计水位必须大于平滩水位")

    def get_input_parameters(self):
        """获取并解析所有输入参数"""
        return {
            'n_l': float(self.n_l_entry.get()),
            'n_c': float(self.n_c_entry.get()),
            'n_r': float(self.n_r_entry.get()),
            'J': float(self.J_entry.get()),
            'mu': float(self.mu_entry.get()),
            'E': float(self.E_entry.get()),
            'd': float(self.d_entry.get()),
            'water_level': float(self.water_level_entry.get()),
            'design_water_level': float(self.design_water_level_entry.get()),
            'bridge_config': self.bridge_config_entry.get(),
            'pier_width': float(self.pier_width_entry.get()),
            'skew_angle': float(self.skew_angle_entry.get()),
            'bridge_start': float(self.bridge_start_entry.get()),
            'K_t': float(self.K_t_entry.get()),
            'B_1': float(self.B_1_entry.get()),
            'V': float(self.V_entry.get()),
            'Design_Q': float(self.Design_Q_entry.get()),
            'choice_h_p': self.choice_h_p_entry.get()
        }

    def calculate_flow_areas(self, design_water_level, boundary1, boundary2):
        """计算设计水位下各区域的过水面积"""
        intersections = self.find_waterline_intersections(
            self.distances, self.elevations, design_water_level)
        
        if len(intersections) < 2:
            return None, None, None
        
        start_idx = np.argmin(np.abs(self.distances - intersections[0]))
        end_idx = np.argmin(np.abs(self.distances - intersections[1]))
        
        # 计算水深
        water_depths = design_water_level - self.elevations[start_idx:end_idx + 1]
        water_depths = np.maximum(water_depths, 0)
        
        # 创建区域掩码
        distances_slice = self.distances[start_idx:end_idx + 1]
        channel_mask = (distances_slice >= boundary1) & (distances_slice <= boundary2)
        left_floodplain_mask = (distances_slice < boundary1)
        right_floodplain_mask = (distances_slice > boundary2)
        
        # 计算各区域面积
        channel_area = np.trapz(water_depths[channel_mask], distances_slice[channel_mask])
        left_floodplain_area = np.trapz(
            water_depths[left_floodplain_mask], distances_slice[left_floodplain_mask])
        right_floodplain_area = np.trapz(
            water_depths[right_floodplain_mask], distances_slice[right_floodplain_mask])
        
        return left_floodplain_area, channel_area, right_floodplain_area

    def calculate_flow_distribution(self, params, left_area, channel_area, right_area,
                                   left_area_after, channel_area_after, right_area_after,
                                   left_width_after, channel_width_after, right_width_after,
                                   left_width_before, channel_width_before, right_width_before,
                                   intersections, boundary1, boundary2):
        """计算流量分布"""
        # 计算各区域阻水后的流量
        left_Q, _, _ = self.calculate_flow(
            left_area_after, left_width_after, params['n_l'], params['J'])
        channel_Q, _, _ = self.calculate_flow(
            channel_area_after, channel_width_after, params['n_c'], params['J'])
        right_Q, _, _ = self.calculate_flow(
            right_area_after, right_width_after, params['n_r'], params['J'])
        
        # 计算各区域天然流量
        left_Q_before = self.calculate_flow(
            left_area, left_width_before, params['n_l'], params['J'])[0]
        channel_Q_before = self.calculate_flow(
            channel_area, channel_width_before, params['n_c'], params['J'])[0]
        right_Q_before = self.calculate_flow(
            right_area, right_width_before, params['n_r'], params['J'])[0]
        
        total_Q = left_Q + channel_Q + right_Q
        total_Q_before = left_Q_before + channel_Q_before + right_Q_before
        
        # 按设计流量分配
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

    def format_results(self, params, obstruction_results, flow_areas, flow_distribution,
                      scour_results, local_scour_results):
        """格式化计算结果输出"""
        (total_obstruction_area, obstruction_ratio, pier_obstructions,
         left_obstruction_area, channel_obstruction_area, right_obstruction_area,
         left_obstruction_width, channel_obstruction_width, right_obstruction_width) = obstruction_results
        
        (left_area, channel_area, right_area,
         left_area_after, channel_area_after, right_area_after,
         left_width_after, channel_width_after, right_width_after,
         left_depth_after, channel_depth_after, right_depth_after) = flow_areas
        
        result_output = StringIO()
        
        # 输出阻水参数
        result_output.write("\n桥墩阻水参数:\n")
        result_output.write(f"总阻水面积: {total_obstruction_area:.2f} m²\n")
        result_output.write(f"阻水比率: {obstruction_ratio * 100:.2f}%\n")
        
        # 输出各区域阻水参数
        result_output.write("\n各区域阻水参数:\n")
        result_output.write("左河滩:\n")
        result_output.write(f"  阻水面积: {left_obstruction_area:.2f} m²\n")
        result_output.write(f"  阻水宽度: {left_obstruction_width:.2f} m\n")
        result_output.write(f"  阻水后过流面积: {left_area_after:.2f} m²\n")
        result_output.write(f"  阻水后过流宽度: {left_width_after:.2f} m\n")
        result_output.write(f"  平均水深: {left_depth_after:.2f} m\n")
        result_output.write(f"  设计流量: {flow_distribution['left_Q_final']:.2f} m³/s\n")
        
        result_output.write("\n河槽:\n")
        result_output.write(f"  阻水面积: {channel_obstruction_area:.2f} m²\n")
        result_output.write(f"  阻水宽度: {channel_obstruction_width:.2f} m\n")
        result_output.write(f"  阻水后过流面积: {channel_area_after:.2f} m²\n")
        result_output.write(f"  阻水后过流宽度: {channel_width_after:.2f} m\n")
        result_output.write(f"  平均水深: {channel_depth_after:.2f} m\n")
        result_output.write(f"  设计流量: {flow_distribution['channel_Q_final']:.2f} m³/s\n")
        
        result_output.write("\n右河滩:\n")
        result_output.write(f"  阻水面积: {right_obstruction_area:.2f} m²\n")
        result_output.write(f"  阻水宽度: {right_obstruction_width:.2f} m\n")
        result_output.write(f"  阻水后过流面积: {right_area_after:.2f} m²\n")
        result_output.write(f"  阻水后过流宽度: {right_width_after:.2f} m\n")
        result_output.write(f"  平均水深: {right_depth_after:.2f} m\n")
        result_output.write(f"  设计流量: {flow_distribution['right_Q_final']:.2f} m³/s\n")
        
        result_output.write(f"\n总设计流量: {params['Design_Q']:.2f} m³/s\n")
        
        # 输出冲刷计算参数
        result_output.write("\n冲刷计算参数:\n")
        result_output.write(f"单宽流量集中系数 A: {scour_results['A']:.2f}\n")
        result_output.write(f"河槽设计流量 Qcp: {flow_distribution['channel_Q_final']:.2f} m³/s\n")
        result_output.write(f"平滩水面宽 B: {scour_results['B']:.2f} m\n")
        result_output.write(f"平滩平均水深 H: {scour_results['H']:.2f} m\n")
        result_output.write(f"河槽阻水后过流宽度 Lcj: {scour_results['Lcj']:.2f} m\n")
        result_output.write(f"设计水位最大水深 hmax: {scour_results['h_max']:.2f} m\n")
        result_output.write(f"河槽平均水深 hc: {scour_results['h_c']:.2f} m\n")
        
        result_output.write("**-----64-1计算一般冲刷结果-------**\n")
        result_output.write(f"桥梁一般冲刷深度: {scour_results['scour_depth_64_1']:.2f} m\n")
        
        result_output.write("**-----64-2计算一般冲刷结果-------**\n")
        result_output.write(f"桥梁一般冲刷深度: {scour_results['scour_depth_64_2']:.2f} m\n")
        
        result_output.write("**-----65-1计算局部冲刷结果-------**\n")
        result_output.write(f"桥梁局部冲刷深度: {local_scour_results['local_scour_65_1']:.2f} m\n")
        
        result_output.write("**-----65-2计算局部冲刷结果-------**\n")
        result_output.write(f"桥梁局部冲刷深度: {local_scour_results['local_scour_65_2']:.2f} m\n")
        
        return result_output.getvalue()

    def plot_cross_section(self, distances, elevations, water_level=None, design_water_level=None,
                           channel_boundaries=None, pier_obstructions=None, title=None, 
                           save_path=None, use_config=True):
        """
        绘制河道横断面图
        
        参数:
            save_path: 可选，保存图片的路径。如果为None则不保存
            use_config: 是否使用自定义配置
        """
        # 保存绘图数据用于重新绘制
        self.current_plot_data = {
            'distances': distances,
            'elevations': elevations,
            'water_level': water_level,
            'design_water_level': design_water_level,
            'channel_boundaries': channel_boundaries,
            'pier_obstructions': pier_obstructions
        }
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(distances, elevations, 'k-', linewidth=2, label='河道断面')
        ax.fill_between(distances, elevations, np.min(elevations) - 1, color='lightgray', alpha=0.5)

        # 绘制平滩水位线
        if water_level is not None:
            ax.axhline(y=water_level, color='b', linestyle='--', linewidth=1.5, label='平滩水位')

            # 填充平滩水位以下的区域
            intersections = self.find_waterline_intersections(distances, elevations, water_level)
            if len(intersections) >= 2:
                start_idx = np.argmin(np.abs(distances - intersections[0]))
                end_idx = np.argmin(np.abs(distances - intersections[1]))

                # 绘制平滩水位下的水流区域
                x = np.concatenate([[distances[start_idx]], distances[start_idx:end_idx + 1], [distances[end_idx]]])
                y = np.concatenate([[water_level], elevations[start_idx:end_idx + 1], [water_level]])
                ax.fill(x, y, 'b', alpha=0.3)

        # 绘制设计水位线
        if design_water_level is not None:
            ax.axhline(y=design_water_level, color='r', linestyle='-', linewidth=1.5, label='设计水位')

            # 填充设计水位以下的区域
            intersections = self.find_waterline_intersections(distances, elevations, design_water_level)
            if len(intersections) >= 2:
                start_idx = np.argmin(np.abs(distances - intersections[0]))
                end_idx = np.argmin(np.abs(distances - intersections[1]))

                # 绘制设计水位下的水流区域
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
                area = pier['area']
                region = pier['region']

                # 根据区域设置不同颜色
                color = 'purple' if region == '河槽' else 'blue' if region == '左河滩' else 'red'

                # 标记桥墩位置
                ax.axvline(x=pier_pos, color=color, linestyle='--', linewidth=1,
                           label=f'桥墩 {i + 1} ({region})' if i == 0 else None)

                # 标记桥墩高度
                ax.plot([pier_pos, pier_pos], [design_water_level - depth, design_water_level],
                        color, marker='o', markersize=4)

                # 添加桥墩信息文本
                ax.text(pier_pos, design_water_level + 0.5,
                        f'墩{i + 1}: {depth:.1f}m',
                        horizontalalignment='center',
                        rotation=90,  # 添加旋转参数
                        color=color)

        # 使用自定义配置或默认值
        if use_config and self.plot_config:
            plot_title = title if title else self.plot_config['title']
            xlabel = self.plot_config['xlabel']
            ylabel = self.plot_config['ylabel']
        else:
            plot_title = title if title else '河道横断面图'
            xlabel = '距离 (m)'
            ylabel = '高程 (m)'
        
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(plot_title)
        
        # 设置坐标轴范围
        if use_config and self.plot_config:
            if self.plot_config['xmin'] is not None:
                ax.set_xlim(left=self.plot_config['xmin'])
            if self.plot_config['xmax'] is not None:
                ax.set_xlim(right=self.plot_config['xmax'])
            if self.plot_config['ymin'] is not None:
                ax.set_ylim(bottom=self.plot_config['ymin'])
            if self.plot_config['ymax'] is not None:
                ax.set_ylim(top=self.plot_config['ymax'])
        
        # 设置网格
        grid_alpha = self.plot_config.get('grid_alpha', 1.0) if use_config else 1.0
        grid_style = self.plot_config.get('grid_style', '-') if use_config else '-'
        ax.grid(True, alpha=grid_alpha, linestyle=grid_style)
        
        ax.legend()
        self.figure.tight_layout()

        # 保存图片（如果指定了保存路径）
        if save_path:
            try:
                self.figure.savefig(save_path, dpi=300, bbox_inches='tight')
            except Exception as e:
                logging.warning(f"保存图片失败: {str(e)}")

        self.canvas.draw()

    def customize_plot(self):
        """打开图形自定义对话框"""
        if not self.current_plot_data:
            messagebox.showwarning("提示", "请先执行计算以生成图形")
            return
        
        # 创建自定义对话框
        dialog = tk.Toplevel(self)
        dialog.title("图形自定义")
        dialog.geometry("500x600")
        dialog.transient(self)
        dialog.grab_set()
        
        # 创建输入框
        ttk.Label(dialog, text="图名:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        title_entry = ttk.Entry(dialog, width=40)
        title_entry.insert(0, self.plot_config['title'])
        title_entry.grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="X轴名称:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        xlabel_entry = ttk.Entry(dialog, width=40)
        xlabel_entry.insert(0, self.plot_config['xlabel'])
        xlabel_entry.grid(row=1, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Y轴名称:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        ylabel_entry = ttk.Entry(dialog, width=40)
        ylabel_entry.insert(0, self.plot_config['ylabel'])
        ylabel_entry.grid(row=2, column=1, padx=10, pady=5)
        
        # 坐标轴范围
        ttk.Label(dialog, text="X轴最小值 (留空为自动):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        xmin_entry = ttk.Entry(dialog, width=40)
        if self.plot_config['xmin'] is not None:
            xmin_entry.insert(0, str(self.plot_config['xmin']))
        xmin_entry.grid(row=3, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="X轴最大值 (留空为自动):").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        xmax_entry = ttk.Entry(dialog, width=40)
        if self.plot_config['xmax'] is not None:
            xmax_entry.insert(0, str(self.plot_config['xmax']))
        xmax_entry.grid(row=4, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Y轴最小值 (留空为自动):").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
        ymin_entry = ttk.Entry(dialog, width=40)
        if self.plot_config['ymin'] is not None:
            ymin_entry.insert(0, str(self.plot_config['ymin']))
        ymin_entry.grid(row=5, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Y轴最大值 (留空为自动):").grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
        ymax_entry = ttk.Entry(dialog, width=40)
        if self.plot_config['ymax'] is not None:
            ymax_entry.insert(0, str(self.plot_config['ymax']))
        ymax_entry.grid(row=6, column=1, padx=10, pady=5)
        
        # 网格设置
        ttk.Label(dialog, text="网格透明度 (0-1):").grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)
        grid_alpha_entry = ttk.Entry(dialog, width=40)
        grid_alpha_entry.insert(0, str(self.plot_config['grid_alpha']))
        grid_alpha_entry.grid(row=7, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="网格样式 (-, --, -., :):").grid(row=8, column=0, sticky=tk.W, padx=10, pady=5)
        grid_style_entry = ttk.Entry(dialog, width=40)
        grid_style_entry.insert(0, self.plot_config['grid_style'])
        grid_style_entry.grid(row=8, column=1, padx=10, pady=5)
        
        def apply_customization():
            """应用自定义设置"""
            try:
                # 更新配置
                self.plot_config['title'] = title_entry.get()
                self.plot_config['xlabel'] = xlabel_entry.get()
                self.plot_config['ylabel'] = ylabel_entry.get()
                
                # 坐标轴范围
                xmin_val = xmin_entry.get().strip()
                self.plot_config['xmin'] = float(xmin_val) if xmin_val else None
                
                xmax_val = xmax_entry.get().strip()
                self.plot_config['xmax'] = float(xmax_val) if xmax_val else None
                
                ymin_val = ymin_entry.get().strip()
                self.plot_config['ymin'] = float(ymin_val) if ymin_val else None
                
                ymax_val = ymax_entry.get().strip()
                self.plot_config['ymax'] = float(ymax_val) if ymax_val else None
                
                # 网格设置
                grid_alpha_val = float(grid_alpha_entry.get())
                if 0 <= grid_alpha_val <= 1:
                    self.plot_config['grid_alpha'] = grid_alpha_val
                else:
                    raise ValueError("网格透明度必须在0-1之间")
                
                grid_style_val = grid_style_entry.get().strip()
                if grid_style_val in ['-', '--', '-.', ':']:
                    self.plot_config['grid_style'] = grid_style_val
                else:
                    raise ValueError("网格样式必须是 -, --, -., 或 :")
                
                # 重新绘制图形
                self.replot_with_config()
                
                # 保存图片
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"自定义断面图_{timestamp}.png"
                image_path = os.path.join(os.getcwd(), image_filename)
                self.figure.savefig(image_path, dpi=300, bbox_inches='tight')
                
                dialog.destroy()
                messagebox.showinfo("完成", f"图形已重新绘制并保存至:\n{image_path}")
                
            except ValueError as e:
                messagebox.showerror("输入错误", str(e))
            except Exception as e:
                messagebox.showerror("错误", f"应用设置失败: {str(e)}")
        
        # 确认按钮
        confirm_btn = ttk.Button(dialog, text="确认", command=apply_customization)
        confirm_btn.grid(row=9, column=0, columnspan=2, pady=20)
    
    def replot_with_config(self):
        """使用当前配置重新绘制图形"""
        if self.current_plot_data:
            self.plot_cross_section(
                self.current_plot_data['distances'],
                self.current_plot_data['elevations'],
                self.current_plot_data['water_level'],
                self.current_plot_data['design_water_level'],
                self.current_plot_data['channel_boundaries'],
                self.current_plot_data['pier_obstructions'],
                use_config=True
            )

    def run_calculation(self):
        try:
            # 清空之前的结果
            self.result_text.config(state=tk.NORMAL)
            self.result_text.delete(1.0, tk.END)
            self.result_text.config(state=tk.DISABLED)

            # 验证输入
            self.validate_inputs()
            
            # 获取输入参数
            params = self.get_input_parameters()

            # 读取断面数据
            self.distances, self.elevations = self.read_cross_section()
            if self.distances is None:
                return

            # 计算平滩水位下的水力参数
            avg_depth, max_depth, _, _ = self.calculate_hydraulic_parameters(
                self.distances, self.elevations, params['water_level'])
            
            if avg_depth is None:
                raise ValueError("平滩水位设置不合理，无法计算水力参数")

            # 识别河槽和河滩的分界点
            boundary1, boundary2 = self.identify_channel_and_floodplain(
                self.distances, self.elevations, params['water_level'])
            
            if boundary1 is None or boundary2 is None:
                raise ValueError("无法识别河槽和河滩的分界点")

            # 计算设计水位下的参数
            avg_depth_design, max_depth_design, flow_area, _ = self.calculate_hydraulic_parameters(
                self.distances, self.elevations, params['design_water_level'])
            
            if avg_depth_design is None:
                raise ValueError("设计水位设置不合理，无法计算水力参数")

            # 计算各区域过水面积
            left_area, channel_area, right_area = self.calculate_flow_areas(
                params['design_water_level'], boundary1, boundary2)
            
            if left_area is None:
                raise ValueError("无法计算各区域过水面积")





            # 解析桥梁配置
            spans = self.parse_bridge_config(params['bridge_config'])
            if not spans:
                raise ValueError("桥梁配置解析失败，请检查格式")

            # 计算桥墩阻水面积
            intersections = self.find_waterline_intersections(
                self.distances, self.elevations, params['design_water_level'])
            
            obstruction_results = self.calculate_bridge_obstruction(
                spans, params['pier_width'], params['skew_angle'], 
                params['design_water_level'], self.distances, self.elevations, 
                params['bridge_start'], boundary1, boundary2)

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
            flow_distribution = self.calculate_flow_distribution(
                params, left_area, channel_area, right_area,
                left_area_after, channel_area_after, right_area_after,
                left_width_after, channel_width_after, right_width_after,
                left_width_before, channel_width_before, right_width_before,
                intersections, boundary1, boundary2)

            # 计算冲刷深度参数
            B = boundary2 - boundary1  # 平滩水位时的水面宽
            H = avg_depth  # 平滩水位时的平均水深
            Lcj = channel_width_after  # 河槽阻水后的过流宽度
            h_max = max_depth_design  # 设计水位下的最大水深
            h_c = channel_depth_after  # 河槽部分的平均水深
            B_c = B
            B_2 = channel_width_after

            # 计算一般冲刷深度
            scour_depth_64_1, A = self.calculate_scour(
                flow_distribution['channel_Q_final'], B_c, H, Lcj, h_max, h_c, 
                params['mu'], params['E'], params['d'])
            
            scour_depth_64_2, A_2 = self.calculate_scour_64_2(
                flow_distribution['channel_Q_final'], flow_distribution['Q_c'], 
                B_c, B_2, obstruction_ratio, params['mu'], h_max, B, H)

            # 确定一般冲刷深度
            if params['choice_h_p'].lower() in ('y', 'yes', ''):
                h_p = max(scour_depth_64_1, scour_depth_64_2)
            else:
                try:
                    h_p = float(params['choice_h_p'])
                except ValueError:
                    raise ValueError(
                        f"输入错误: '{params['choice_h_p']}' 无法转换为浮点数。"
                        "请输入 'y' 自动选择最大值，或输入具体数值。")

            # 计算局部冲刷深度
            local_scour_65_2 = self.calculate_local_scour(
                params['V'], params['K_t'], params['d'], params['B_1'], h_p)
            local_scour_65_1 = self.calculate_local_scour_65_1(
                params['V'], params['K_t'], params['d'], params['B_1'], h_p)

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

            # 格式化并显示结果
            result_text = self.format_results(
                params, obstruction_results, flow_areas, flow_distribution,
                scour_results, local_scour_results)
            self.update_result_display(result_text)

            # 绘制最终图形
            self.plot_cross_section(
                self.distances, self.elevations, 
                params['water_level'], params['design_water_level'],
                [boundary1, boundary2], pier_obstructions, 
                title="河道横断面分析")
            
            # 保存计算结果图片
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"桥梁冲刷计算结果_{timestamp}.png"
            image_path = os.path.join(os.getcwd(), image_filename)
            
            try:
                self.figure.savefig(image_path, dpi=300, bbox_inches='tight')
                # 在结果中显示保存信息
                save_info = f"\n\n图片已保存至: {image_path}\n"
                self.update_result_display(save_info)
            except Exception as e:
                error_msg = f"\n\n图片保存失败: {str(e)}\n"
                self.update_result_display(error_msg)
            
            # 切换到计算结果标签页
            self.notebook.select(self.result_frame)
            
            # 弹出计算完成提示
            messagebox.showinfo("计算完成", "计算已完成！\n结果已显示在'计算结果'标签页中。")

        except ValueError as e:
            messagebox.showerror("输入错误", str(e))
            self.update_result_display(f"计算失败: {str(e)}\n")
        except Exception as e:
            messagebox.showerror("计算错误", f"发生错误: {str(e)}")
            self.update_result_display(f"计算失败: {str(e)}\n")
    
    def on_closing(self):
        """窗口关闭事件处理"""
        self.destroy()
    
    def open_custom_frame(self):
        """打开自定义绘制界面"""
        self.notebook.select(self.custom_frame)
    
    def init_custom_frame(self):
        """初始化断面自定义绘制界面"""
        # 创建子标签页
        self.custom_notebook = ttk.Notebook(self.custom_frame)
        self.custom_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 子标签页1：文本输入
        self.text_input_frame = ttk.Frame(self.custom_notebook)
        self.custom_notebook.add(self.text_input_frame, text="文本输入")
        self.init_text_input()
        
        # 子标签页2：画布绘制
        self.canvas_input_frame = ttk.Frame(self.custom_notebook)
        self.custom_notebook.add(self.canvas_input_frame, text="画布绘制")
        self.init_canvas_input()
    
    def init_text_input(self):
        """初始化文本输入界面"""
        # 说明标签
        info_label = ttk.Label(
            self.text_input_frame,
            text="请输入或粘贴断面数据（距离、高程），格式：每行一个点，用空格或制表符分隔",
            font=('SimHei', 9),
            foreground='blue'
        )
        info_label.pack(pady=5)
        
        # 主容器：左侧输入区域 + 右侧绘图区域
        main_container = ttk.Frame(self.text_input_frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左侧输入区域（30%宽度）
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        left_frame.config(width=300)  # 设置固定宽度
        
        # 序号列和文本输入框的容器
        input_container = ttk.Frame(left_frame)
        input_container.pack(fill=tk.BOTH, expand=True)
        
        # 序号列（左侧）
        self.line_numbers = tk.Text(
            input_container,
            width=4,
            wrap=tk.NONE,
            font=('Courier', 10),
            bg='#f0f0f0',
            state=tk.DISABLED,
            padx=5,
            pady=0
        )
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        
        # 文本输入框（右侧，带滚动条）
        text_scroll_frame = ttk.Frame(input_container)
        text_scroll_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar_y = ttk.Scrollbar(text_scroll_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.text_input = tk.Text(
            text_scroll_frame,
            wrap=tk.NONE,
            yscrollcommand=self.on_text_scroll,
            font=('Courier', 10),
            padx=5,
            pady=0
        )
        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.config(command=self.on_text_yscroll)
        
        # 绑定文本变化事件，实时更新序号和绘图
        self.text_input.bind('<KeyRelease>', self.on_text_change)
        self.text_input.bind('<Button-1>', self.on_text_change)
        self.text_input.bind('<MouseWheel>', self.on_text_change)
        
        # 输入完成按钮
        complete_btn = ttk.Button(
            left_frame,
            text="输入完成并开始计算",
            command=self.process_text_input,
            width=25
        )
        complete_btn.pack(pady=10)
        
        # 右侧绘图区域（60%宽度）
        right_frame = ttk.LabelFrame(main_container, text="实时断面预览", padding=5)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # 绘图画布
        self.preview_canvas = tk.Canvas(
            right_frame,
            bg='white',
            relief=tk.SUNKEN,
            borderwidth=2
        )
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绑定画布大小改变事件
        self.preview_canvas.bind("<Configure>", lambda e: self.update_preview_plot())
        
        # 存储临时数据用于预览
        self.temp_distances = None
        self.temp_elevations = None
    
    def init_canvas_input(self):
        """初始化画布绘制界面"""
        # 控制面板
        control_frame = ttk.LabelFrame(self.canvas_input_frame, text="画布设置", padding=5)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 横坐标范围
        ttk.Label(control_frame, text="横坐标范围:").grid(row=0, column=0, padx=5, pady=2)
        self.xmin_entry = ttk.Entry(control_frame, width=10)
        self.xmin_entry.insert(0, "0")
        self.xmin_entry.grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(control_frame, text="至").grid(row=0, column=2, padx=5)
        self.xmax_entry = ttk.Entry(control_frame, width=10)
        self.xmax_entry.insert(0, "100")
        self.xmax_entry.grid(row=0, column=3, padx=5, pady=2)
        
        # 纵坐标范围
        ttk.Label(control_frame, text="纵坐标范围:").grid(row=1, column=0, padx=5, pady=2)
        self.ymin_entry = ttk.Entry(control_frame, width=10)
        self.ymin_entry.insert(0, "0")
        self.ymin_entry.grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(control_frame, text="至").grid(row=1, column=2, padx=5)
        self.ymax_entry = ttk.Entry(control_frame, width=10)
        self.ymax_entry.insert(0, "100")
        self.ymax_entry.grid(row=1, column=3, padx=5, pady=2)
        
        # 间距
        ttk.Label(control_frame, text="采样间距:").grid(row=2, column=0, padx=5, pady=2)
        self.spacing_entry = ttk.Entry(control_frame, width=10)
        self.spacing_entry.insert(0, "1.0")
        self.spacing_entry.grid(row=2, column=1, padx=5, pady=2)
        
        # 应用设置按钮
        apply_btn = ttk.Button(control_frame, text="应用设置", command=self.apply_canvas_settings)
        apply_btn.grid(row=2, column=2, columnspan=2, padx=5, pady=2)
        
        # 画布
        canvas_frame = ttk.Frame(self.canvas_input_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.draw_canvas = tk.Canvas(
            canvas_frame,
            bg='white',
            relief=tk.SUNKEN,
            borderwidth=2
        )
        self.draw_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绑定鼠标事件
        self.draw_canvas.bind("<Button-1>", self.on_canvas_click)
        self.draw_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.draw_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.draw_canvas.bind("<Configure>", self.on_canvas_configure)
        
        # 初始绘制坐标轴
        self.draw_canvas.after(100, self.draw_canvas_axes)
        
        # 画布数据
        self.canvas_points = []
        self.canvas_x_range = (0, 100)
        self.canvas_y_range = (0, 100)
        self.canvas_spacing = 1.0
        self.is_drawing = False
        
        # 保存按钮
        save_btn = ttk.Button(
            self.canvas_input_frame,
            text="保存并开始计算",
            command=self.process_canvas_input,
            width=25
        )
        save_btn.pack(pady=10)
    
    def apply_canvas_settings(self):
        """应用画布设置"""
        try:
            xmin = float(self.xmin_entry.get())
            xmax = float(self.xmax_entry.get())
            ymin = float(self.ymin_entry.get())
            ymax = float(self.ymax_entry.get())
            spacing = float(self.spacing_entry.get())
            
            if xmin >= xmax or ymin >= ymax:
                raise ValueError("坐标范围设置错误：最小值必须小于最大值")
            if spacing <= 0:
                raise ValueError("采样间距必须大于0")
            
            self.canvas_x_range = (xmin, xmax)
            self.canvas_y_range = (ymin, ymax)
            self.canvas_spacing = spacing
            
            # 清空画布并重新绘制
            self.draw_canvas.delete("all")
            self.canvas_points = []
            
            # 绘制坐标轴
            self.draw_canvas.after(50, self.draw_canvas_axes)
            
            messagebox.showinfo("成功", "画布设置已应用")
        except ValueError as e:
            messagebox.showerror("输入错误", str(e))
    
    def on_canvas_configure(self, event):
        """画布大小改变时重新绘制坐标轴"""
        self.draw_canvas_axes()
    
    def draw_canvas_axes(self):
        """绘制画布坐标轴"""
        width = self.draw_canvas.winfo_width()
        height = self.draw_canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            return
        
        # 删除旧的坐标轴（通过标签查找）
        for item in self.draw_canvas.find_all():
            tags = self.draw_canvas.gettags(item)
            if 'axis' in tags:
                self.draw_canvas.delete(item)
        
        # 绘制坐标轴
        margin = 50
        plot_width = width - 2 * margin
        plot_height = height - 2 * margin
        
        # X轴
        self.draw_canvas.create_line(
            margin, height - margin,
            width - margin, height - margin,
            fill='black', width=2, tags='axis'
        )
        
        # Y轴
        self.draw_canvas.create_line(
            margin, margin,
            margin, height - margin,
            fill='black', width=2, tags='axis'
        )
        
        # 标签
        self.draw_canvas.create_text(
            width // 2, height - 20,
            text=f"距离 ({self.canvas_x_range[0]} - {self.canvas_x_range[1]})",
            font=('SimHei', 10),
            tags='axis'
        )
        
        self.draw_canvas.create_text(
            20, height // 2,
            text=f"高程\n({self.canvas_y_range[0]} - {self.canvas_y_range[1]})",
            font=('SimHei', 10),
            tags='axis'
        )
    
    def on_canvas_click(self, event):
        """画布点击事件"""
        self.is_drawing = True
        self.on_canvas_drag(event)
    
    def on_canvas_drag(self, event):
        """画布拖拽事件"""
        if not self.is_drawing:
            return
        
        margin = 50
        width = self.draw_canvas.winfo_width()
        height = self.draw_canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            return
        
        plot_width = width - 2 * margin
        plot_height = height - 2 * margin
        
        # 转换坐标
        x_plot = event.x - margin
        y_plot = height - margin - event.y
        
        if 0 <= x_plot <= plot_width and 0 <= y_plot <= plot_height:
            # 转换为实际坐标
            x_real = self.canvas_x_range[0] + (x_plot / plot_width) * (self.canvas_x_range[1] - self.canvas_x_range[0])
            y_real = self.canvas_y_range[0] + (y_plot / plot_height) * (self.canvas_y_range[1] - self.canvas_y_range[0])
            
            self.canvas_points.append((x_real, y_real))
            
            # 绘制点
            self.draw_canvas.create_oval(
                event.x - 2, event.y - 2,
                event.x + 2, event.y + 2,
                fill='blue', outline='blue'
            )
    
    def on_canvas_release(self, event):
        """画布释放事件"""
        self.is_drawing = False
    
    def process_canvas_input(self):
        """处理画布输入数据并自动开始计算"""
        if len(self.canvas_points) < 2:
            messagebox.showwarning("警告", "请至少绘制2个点")
            return
        
        try:
            # 按X坐标排序
            sorted_points = sorted(self.canvas_points, key=lambda p: p[0])
            
            # 生成等间距数据
            x_min = sorted_points[0][0]
            x_max = sorted_points[-1][0]
            
            # 使用线性插值生成等间距点
            distances = []
            elevations = []
            
            for x in np.arange(x_min, x_max + self.canvas_spacing, self.canvas_spacing):
                # 找到最近的点进行插值
                if x <= sorted_points[0][0]:
                    y = sorted_points[0][1]
                elif x >= sorted_points[-1][0]:
                    y = sorted_points[-1][1]
            else:
                    # 线性插值
                    for i in range(len(sorted_points) - 1):
                        if sorted_points[i][0] <= x <= sorted_points[i+1][0]:
                            x1, y1 = sorted_points[i]
                            x2, y2 = sorted_points[i+1]
                            if x2 != x1:
                                y = y1 + (y2 - y1) * (x - x1) / (x2 - x1)
                            else:
                                y = y1
                            break
                
                    distances.append(x)
                    elevations.append(y)
            
            # 保存数据
            self.distances = np.array(distances)
            self.elevations = np.array(elevations)
            self.file_path = None
            self.file_path_label.config(text="自定义绘制数据")
            
            # 切换到输入界面
            self.notebook.select(self.input_frame)
            
            # 自动开始计算
            messagebox.showinfo("成功", f"已保存 {len(distances)} 个断面数据点，开始计算...")
            self.run_calculation()
            
        except Exception as e:
            messagebox.showerror("错误", f"处理画布数据失败: {str(e)}")
    
    def on_text_scroll(self, *args):
        """文本滚动时同步序号列"""
        self.line_numbers.yview_moveto(args[0])
        self.update_line_numbers()
    
    def on_text_yscroll(self, *args):
        """处理文本滚动"""
        self.text_input.yview(*args)
        self.on_text_scroll(*args)
    
    def on_text_change(self, event=None):
        """文本变化时更新序号和绘图"""
        self.update_line_numbers()
        self.update_preview_plot()
    
    def update_line_numbers(self):
        """更新行号显示"""
        # 获取文本行数
        content = self.text_input.get(1.0, tk.END)
        line_count = content.count('\n')
        
        # 更新序号列
        self.line_numbers.config(state=tk.NORMAL)
        self.line_numbers.delete(1.0, tk.END)
        
        for i in range(1, line_count + 1):
            self.line_numbers.insert(tk.END, f"{i}\n")
        
        self.line_numbers.config(state=tk.DISABLED)
        
        # 同步滚动
        self.line_numbers.yview_moveto(self.text_input.yview()[0])
    
    def update_preview_plot(self):
        """更新实时预览绘图"""
        text = self.text_input.get(1.0, tk.END).strip()
        
        if not text:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                self.preview_canvas.winfo_width() // 2,
                self.preview_canvas.winfo_height() // 2,
                text="请输入断面数据以查看预览",
                font=('SimHei', 12),
                fill='gray'
            )
            return
        
        try:
            distances = []
            elevations = []
            
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 支持空格、制表符、逗号分隔
                parts = re.split(r'[\s,\t]+', line)
                if len(parts) >= 2:
                    try:
                        dist = float(parts[0])
                        elev = float(parts[1])
                        distances.append(dist)
                        elevations.append(elev)
                    except ValueError:
                        continue
            
            if len(distances) >= 2:
                self.temp_distances = np.array(distances)
                self.temp_elevations = np.array(elevations)
                self.draw_preview_plot()
            else:
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(
                    self.preview_canvas.winfo_width() // 2,
                    self.preview_canvas.winfo_height() // 2,
                    text="至少需要2个有效数据点",
                    font=('SimHei', 12),
                    fill='orange'
                )
        except Exception:
            pass
    
    def draw_preview_plot(self):
        """绘制预览图"""
        if self.temp_distances is None or self.temp_elevations is None:
            return
        
        self.preview_canvas.delete("all")
        
        width = self.preview_canvas.winfo_width()
        height = self.preview_canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            return
        
        # 计算绘图区域
        margin = 50
        plot_width = width - 2 * margin
        plot_height = height - 2 * margin
        
        # 计算数据范围
        dist_min, dist_max = np.min(self.temp_distances), np.max(self.temp_distances)
        elev_min, elev_max = np.min(self.temp_elevations), np.max(self.temp_elevations)
        
        # 添加边距
        dist_range = dist_max - dist_min
        elev_range = elev_max - elev_min
        if dist_range == 0:
            dist_range = 1
        if elev_range == 0:
            elev_range = 1
        
        dist_min -= dist_range * 0.1
        dist_max += dist_range * 0.1
        elev_min -= elev_range * 0.1
        elev_max += elev_range * 0.1
        
        # 坐标转换函数
        def to_canvas_x(x):
            return margin + (x - dist_min) / (dist_max - dist_min) * plot_width
        
        def to_canvas_y(y):
            return height - margin - (y - elev_min) / (elev_max - elev_min) * plot_height
        
        # 绘制坐标轴
        self.preview_canvas.create_line(
            margin, height - margin,
            width - margin, height - margin,
            fill='black', width=2
        )
        self.preview_canvas.create_line(
            margin, margin,
            margin, height - margin,
            fill='black', width=2
        )
        
        # 绘制断面线
        if len(self.temp_distances) > 1:
            points = []
            for i in range(len(self.temp_distances)):
                x = to_canvas_x(self.temp_distances[i])
                y = to_canvas_y(self.temp_elevations[i])
                points.extend([x, y])
            
            self.preview_canvas.create_line(*points, fill='blue', width=2, smooth=True)
            
            # 绘制数据点
            for i in range(len(self.temp_distances)):
                x = to_canvas_x(self.temp_distances[i])
                y = to_canvas_y(self.temp_elevations[i])
                self.preview_canvas.create_oval(x-3, y-3, x+3, y+3, fill='red', outline='red')
        
        # 绘制标签
        self.preview_canvas.create_text(
            width // 2, height - 20,
            text=f"距离 ({dist_min:.1f} - {dist_max:.1f})",
            font=('SimHei', 9)
        )
        self.preview_canvas.create_text(
            20, height // 2,
            text=f"高程\n({elev_min:.1f} - {elev_max:.1f})",
            font=('SimHei', 9),
            angle=90
        )
    
    def process_text_input(self):
        """处理文本输入数据并自动开始计算"""
        text = self.text_input.get(1.0, tk.END).strip()
        
        if not text:
            messagebox.showwarning("警告", "请输入断面数据")
            return
        
        try:
            distances = []
            elevations = []
            
            lines = text.split('\n')
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                
                # 支持空格、制表符、逗号分隔
                parts = re.split(r'[\s,\t]+', line)
                if len(parts) < 2:
                    raise ValueError(f"第 {i} 行数据格式错误：需要至少两个数值（距离、高程）")
                
                try:
                    dist = float(parts[0])
                    elev = float(parts[1])
                    distances.append(dist)
                    elevations.append(elev)
                except ValueError:
                    raise ValueError(f"第 {i} 行数据格式错误：无法转换为数值")
            
            if len(distances) < 2:
                raise ValueError("至少需要2个数据点")
            
            # 检查数据有效性
            if len(distances) != len(elevations):
                raise ValueError("距离和高程数据数量不匹配")
            
            # 保存数据
            self.distances = np.array(distances)
            self.elevations = np.array(elevations)
            self.file_path = None
            self.file_path_label.config(text="自定义文本数据")
            
            # 切换到输入界面
            self.notebook.select(self.input_frame)
            
            # 自动开始计算
            messagebox.showinfo("成功", f"已保存 {len(distances)} 个断面数据点，开始计算...")
            self.run_calculation()
            
        except ValueError as e:
            messagebox.showerror("输入错误", str(e))
        except Exception as e:
            messagebox.showerror("错误", f"处理文本数据失败: {str(e)}")
    
    def get_network_time(self):
        """获取网络时间"""
        ntp_servers = [
            'pool.ntp.org',
            'time.nist.gov',
            'time.windows.com',
            'cn.pool.ntp.org'
        ]
        
        for server in ntp_servers:
            try:
                # 尝试通过HTTP获取时间（更简单可靠）
                url = f'http://{server}'
                response = urllib.request.urlopen(url, timeout=5)
                # 从响应头获取时间
                date_str = response.headers.get('Date')
                if date_str:
                    from email.utils import parsedate_to_datetime
                    return parsedate_to_datetime(date_str)
            except Exception:
                continue
        
        # 如果HTTP方法失败，尝试NTP协议
        try:
            import struct
            import time
            
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(5)
            
            for server in ntp_servers:
                try:
                    data = b'\x1b' + 47 * b'\0'
                    client.sendto(data, (server, 123))
                    data, address = client.recvfrom(1024)
                    if data:
                        t = struct.unpack('!12I', data)[10]
                        t -= 2208988800  # 1900-01-01 00:00:00
                        client.close()
                        return datetime.fromtimestamp(t)
                except Exception:
                    continue
            
            client.close()
        except Exception:
            pass
        
        return None
    
    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        if HAS_PYPERCLIP:
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                pass
        
        # 备用方法：使用tkinter的剪贴板
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            return True
        except Exception:
            return False
    
    def get_machine_id(self):
        """获取机器唯一标识（基于CPU和主板信息）"""
        try:
            # Windows系统
            if platform.system() == 'Windows':
                # 获取CPU序列号
                cpu_id = subprocess.check_output('wmic cpu get ProcessorId', shell=True).decode().strip().split('\n')[1].strip()
                # 获取主板序列号
                board_id = subprocess.check_output('wmic baseboard get serialnumber', shell=True).decode().strip().split('\n')[1].strip()
                machine_id = f"{cpu_id}_{board_id}_{platform.machine()}"
            else:
                # Linux/Mac系统
                machine_id = platform.node() + platform.machine() + platform.processor()
            
            # 生成哈希值
            hash_obj = hashlib.md5(machine_id.encode())
            return hash_obj.hexdigest()[:16].upper()
        except Exception as e:
            # 如果获取失败，使用备用方法
            machine_id = platform.node() + platform.machine() + str(os.getpid())
            hash_obj = hashlib.md5(machine_id.encode())
            return hash_obj.hexdigest()[:16].upper()
    
    def generate_registration_code(self, machine_id):
        """生成注册码"""
        # 使用机器ID和密钥生成注册码
        secret_key = "BRIDGE_SCOUR_2024_SECRET_KEY"
        combined = f"{machine_id}{secret_key}"
        
        # 多次哈希
        hash1 = hashlib.sha256(combined.encode()).hexdigest()
        hash2 = hashlib.md5((hash1 + machine_id).encode()).hexdigest()
        
        # 格式化注册码（每4位用-分隔）
        code = hash2[:16].upper()
        formatted_code = f"{code[:4]}-{code[4:8]}-{code[8:12]}-{code[12:16]}"
        
        return formatted_code
    
    def verify_registration_code(self, code, machine_id):
        """验证注册码"""
        # 移除分隔符
        code_clean = code.replace('-', '').replace(' ', '').upper()
        
        # 生成正确的注册码
        correct_code = self.generate_registration_code(machine_id)
        correct_code_clean = correct_code.replace('-', '').replace(' ', '').upper()
        
        return code_clean == correct_code_clean
    
    def load_registration_info(self):
        """加载注册信息"""
        if not os.path.exists(REGISTRATION_FILE):
            return None
        
        try:
            with open(REGISTRATION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception:
            return None
    
    def save_registration_info(self, is_registered, trial_start_date=None, registration_code=None, registration_date=None):
        """保存注册信息"""
        data = {
            'is_registered': is_registered,
            'trial_start_date': trial_start_date,
            'registration_code': registration_code,
            'registration_date': registration_date,
            'machine_id': self.get_machine_id()
        }
        
        try:
            with open(REGISTRATION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存注册信息失败: {str(e)}")
    
    def check_trial_expired(self, trial_start_date):
        """检查试用期是否过期"""
        if trial_start_date is None:
            return True
        
        try:
            start_date = datetime.strptime(trial_start_date, '%Y-%m-%d')
            end_date = start_date + timedelta(days=TRIAL_DAYS)
            return datetime.now() > end_date
        except Exception:
            return True
    
    def get_trial_days_left(self, trial_start_date):
        """获取剩余试用天数"""
        if trial_start_date is None:
            return 0
        
        try:
            start_date = datetime.strptime(trial_start_date, '%Y-%m-%d')
            end_date = start_date + timedelta(days=TRIAL_DAYS)
            days_left = (end_date - datetime.now()).days
            return max(0, days_left)
        except Exception:
            return 0
    
    def check_registration_status(self):
        """检查注册状态"""
        # 首先检查网络时间
        network_time = self.get_network_time()
        if network_time is None:
            messagebox.showerror(
                "网络错误",
                "无法获取网络时间！\n\n"
                "本程序需要网络连接以验证时间。\n"
                "请检查网络连接后重试。"
            )
            self.destroy()
            return
        
        reg_info = self.load_registration_info()
        machine_id = self.get_machine_id()
        
        if reg_info is None:
            # 首次运行，显示试用提示
            result = messagebox.askyesno(
                "欢迎使用",
                f"欢迎使用桥梁冲刷计算系统！\n\n"
                f"您的机器ID: {machine_id}\n\n"
                f"是否开始试用？试用期为 {TRIAL_DAYS} 天。\n\n"
                f"点击'是'开始试用，点击'否'退出程序。"
            )
            
            if result:
                self.start_trial()
            else:
                self.destroy()
                return
        else:
            # 检查机器ID是否匹配
            if reg_info.get('machine_id') != machine_id:
                messagebox.showerror(
                    "注册错误",
                    "检测到机器ID不匹配，请重新注册！\n\n"
                    f"当前机器ID: {machine_id}"
                )
                self.enter_registration_code()
                return
            
            # 检查是否已注册
            if reg_info.get('is_registered', False):
                # 验证注册码
                reg_code = reg_info.get('registration_code', '')
                if not self.verify_registration_code(reg_code, machine_id):
                    # 注册码无效
                    messagebox.showerror("注册错误", "注册码验证失败，请重新输入注册码！")
                    self.enter_registration_code()
                    return
                
                # 检查注册有效期
                reg_date = reg_info.get('registration_date')
                if reg_date:
                    try:
                        reg_datetime = datetime.strptime(reg_date, '%Y-%m-%d')
                        expiry_date = reg_datetime + timedelta(days=REGISTRATION_VALID_DAYS)
                        
                        if network_time > expiry_date:
                            # 注册已过期
                            messagebox.showerror(
                                "注册过期",
                                f"您的注册已过期！\n\n"
                                f"注册日期: {reg_date}\n"
                                f"有效期: {REGISTRATION_VALID_DAYS} 天\n"
                                f"过期日期: {expiry_date.strftime('%Y-%m-%d')}\n\n"
                                f"请续费或重新注册。"
                            )
                            self.enter_registration_code()
                            return
                        else:
                            # 注册有效，正常使用
                            days_left = (expiry_date - network_time).days
                            if days_left <= 30:
                                messagebox.showwarning(
                                    "注册提醒",
                                    f"您的注册将在 {days_left} 天后过期。\n\n"
                                    f"请及时续费。"
                                )
                    except Exception:
                        pass
                
                # 已注册且有效，正常使用
                return
            else:
                # 试用模式
                trial_start = reg_info.get('trial_start_date')
                if self.check_trial_expired(trial_start):
                    # 试用期已过期
                    self.show_registration_dialog()
                else:
                    # 显示剩余试用天数
                    days_left = self.get_trial_days_left(trial_start)
                    messagebox.showinfo(
                        "试用模式",
                        f"当前为试用模式\n\n剩余试用天数: {days_left} 天\n\n"
                        f"您的机器ID: {machine_id}\n\n"
                        f"如需继续使用，请购买注册码。"
                    )
    
    def show_registration_dialog(self):
        """显示注册对话框（试用期过期后）"""
        machine_id = self.get_machine_id()
        
        dialog = tk.Toplevel(self)
        dialog.title("注册验证")
        dialog.geometry("500x300")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (300 // 2)
        dialog.geometry(f"500x300+{x}+{y}")
        
        # 提示信息
        info_frame = ttk.Frame(dialog)
        info_frame.pack(pady=20)
        
        info_text = (
            f"试用期已过期！\n\n"
            f"您的机器ID: {machine_id}\n\n"
            f"请输入注册码以继续使用，或点击'退出'关闭程序。"
        )
        ttk.Label(info_frame, text=info_text, justify=tk.CENTER, font=('SimHei', 10)).pack()
        
        # 复制机器ID按钮
        copy_btn = ttk.Button(
            info_frame,
            text="复制机器ID",
            command=lambda: self.copy_machine_id(machine_id, dialog),
            width=15
        )
        copy_btn.pack(pady=5)
        
        # 注册码输入
        ttk.Label(dialog, text="注册码:", font=('SimHei', 10)).pack(pady=5)
        code_entry = ttk.Entry(dialog, width=30, font=('Courier', 11))
        code_entry.pack(pady=5)
        code_entry.focus()
        
        def verify_and_close():
            code = code_entry.get().strip()
            if not code:
                messagebox.showerror("错误", "请输入注册码")
                return
            
            if self.verify_registration_code(code, machine_id):
                # 注册成功，获取网络时间作为注册日期
                network_time = self.get_network_time()
                if network_time is None:
                    messagebox.showerror("错误", "无法获取网络时间，注册失败！")
                    return
                
                reg_date = network_time.strftime('%Y-%m-%d')
                self.save_registration_info(True, None, code, reg_date)
                expiry_date = network_time + timedelta(days=REGISTRATION_VALID_DAYS)
                messagebox.showinfo(
                    "成功",
                    f"注册成功！感谢您的使用！\n\n"
                    f"注册日期: {reg_date}\n"
                    f"有效期至: {expiry_date.strftime('%Y-%m-%d')}\n"
                    f"有效期: {REGISTRATION_VALID_DAYS} 天"
                )
                dialog.destroy()
            else:
                messagebox.showerror("错误", "注册码错误，请重新输入！")
                code_entry.delete(0, tk.END)
                code_entry.focus()
        
        def exit_app():
            dialog.destroy()
            self.destroy()
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="验证", command=verify_and_close, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="退出", command=exit_app, width=15).pack(side=tk.LEFT, padx=10)
        
        # 绑定回车键
        code_entry.bind('<Return>', lambda e: verify_and_close())
        
        # 等待对话框关闭
        dialog.wait_window()
        
        # 如果对话框关闭后仍未注册，则退出程序
        reg_info = self.load_registration_info()
        if reg_info is None or not reg_info.get('is_registered', False):
            self.destroy()
    
    def enter_registration_code(self):
        """输入注册码"""
        machine_id = self.get_machine_id()
        
        dialog = tk.Toplevel(self)
        dialog.title("输入注册码")
        dialog.geometry("500x350")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (350 // 2)
        dialog.geometry(f"500x350+{x}+{y}")
        
        # 提示信息
        info_frame = ttk.Frame(dialog)
        info_frame.pack(pady=20)
        
        info_text = (
            f"请输入注册码\n\n"
            f"您的机器ID: {machine_id}\n\n"
            f"请向软件供应商提供此机器ID以获取注册码。"
        )
        ttk.Label(info_frame, text=info_text, justify=tk.CENTER, font=('SimHei', 10)).pack()
        
        # 复制机器ID按钮
        copy_btn = ttk.Button(
            info_frame,
            text="复制机器ID",
            command=lambda: self.copy_machine_id(machine_id, dialog),
            width=15
        )
        copy_btn.pack(pady=5)
        
        # 注册码输入
        ttk.Label(dialog, text="注册码:", font=('SimHei', 10)).pack(pady=5)
        code_entry = ttk.Entry(dialog, width=30, font=('Courier', 11))
        code_entry.pack(pady=5)
        code_entry.focus()
        
        def verify():
            code = code_entry.get().strip()
            if not code:
                messagebox.showerror("错误", "请输入注册码")
                return
            
            if self.verify_registration_code(code, machine_id):
                # 注册成功，获取网络时间作为注册日期
                network_time = self.get_network_time()
                if network_time is None:
                    messagebox.showerror("错误", "无法获取网络时间，注册失败！")
                    return
                
                reg_date = network_time.strftime('%Y-%m-%d')
                self.save_registration_info(True, None, code, reg_date)
                expiry_date = network_time + timedelta(days=REGISTRATION_VALID_DAYS)
                messagebox.showinfo(
                    "成功",
                    f"注册成功！感谢您的使用！\n\n"
                    f"注册日期: {reg_date}\n"
                    f"有效期至: {expiry_date.strftime('%Y-%m-%d')}\n"
                    f"有效期: {REGISTRATION_VALID_DAYS} 天"
                )
                dialog.destroy()
            else:
                messagebox.showerror("错误", "注册码错误，请检查后重新输入！")
                code_entry.delete(0, tk.END)
                code_entry.focus()
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="验证", command=verify, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=10)
        
        # 绑定回车键
        code_entry.bind('<Return>', lambda e: verify())
    
    def copy_machine_id(self, machine_id, parent=None):
        """复制机器ID到剪贴板"""
        if self.copy_to_clipboard(machine_id):
            messagebox.showinfo("成功", f"机器ID已复制到剪贴板:\n{machine_id}", parent=parent)
        else:
            messagebox.showerror("失败", "复制失败，请手动复制", parent=parent)
    
    def start_trial(self):
        """开始试用"""
        # 检查网络时间
        network_time = self.get_network_time()
        if network_time is None:
            messagebox.showerror(
                "网络错误",
                "无法获取网络时间！\n\n"
                "本程序需要网络连接以验证时间。\n"
                "请检查网络连接后重试。"
            )
            return
        
        machine_id = self.get_machine_id()
        trial_start = network_time.strftime('%Y-%m-%d')
        
        self.save_registration_info(False, trial_start, None, None)
        
        days_left = self.get_trial_days_left(trial_start)
        messagebox.showinfo(
            "试用开始",
            f"试用已开始！\n\n"
            f"试用期: {TRIAL_DAYS} 天\n"
            f"剩余天数: {days_left} 天\n\n"
            f"您的机器ID: {machine_id}\n\n"
            f"试用期结束后需要输入注册码才能继续使用。"
        )


if __name__ == "__main__":
    app = BridgeScourApp()
    app.mainloop()