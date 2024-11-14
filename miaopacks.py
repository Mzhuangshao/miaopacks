import tkinter as tk
from tkinter import filedialog, messagebox
import zipfile
import os
import shutil
import json
from PIL import Image, ImageTk
import subprocess
from tkinter import ttk
import math
import pyperclip

# 添加以下函数来处理图片操作
def split_image(image_path, crop_box, target_path):
    """裁剪图片
    
    Args:
        image_path: 源图片路径
        crop_box: 裁剪区域 (left, top, right, bottom)
        target_path: 目标图片保存路径
    """
    try:
        with Image.open(image_path) as img:
            cropped = img.crop(crop_box)
            # 确保目标目录存在
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            cropped.save(target_path)
        return True
    except Exception as e:
        print(f"裁剪图片出错：{str(e)}")
        return False

def merge_images(base_path, overlay_path, position, target_path=None):
    """合并图片
    
    Args:
        base_path: 底图路径
        overlay_path: 要叠加的图片路径
        position: 叠加位置 (x, y)
        target_path: 保存路径，如果为None则覆盖base_path
    """
    try:
        with Image.open(base_path) as base:
            with Image.open(overlay_path) as overlay:
                # 转换为RGBA模式以支持透明度
                base = base.convert('RGBA')
                overlay = overlay.convert('RGBA')
                # 粘贴图片
                base.paste(overlay, position, overlay)
                # 保存结果
                save_path = target_path or base_path
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                base.save(save_path)
        return True
    except Exception as e:
        print(f"合并图片出错：{str(e)}")
        return False

def get_version_category(version):
    """获取版本所属的大类
    
    Args:
        version: 具体版本号，如 "1.19.4"
    Returns:
        version_category: 版本大类，如 "1.19"
    """
    version_num = float(version.replace("1.", ""))
    if version_num <= 19.4:
        return "1.19"
    elif version_num <= 20.6:
        return "1.20"
    else:
        return "1.21"

def load_version_configs():
    """加载所有版本配置"""
    configs = {}
    config_dir = os.path.join(os.path.dirname(__file__), 'config')
    for file in os.listdir(config_dir):
        if file.endswith('.json'):
            version = file.replace('.json', '')
            with open(os.path.join(config_dir, file), 'r', encoding='utf-8') as f:
                configs[version] = json.load(f)
    return configs

def get_available_versions():
    """从配置文件中获取所有可用的版本"""
    versions = set()
    config_dir = os.path.join(os.path.dirname(__file__), 'config')
    
    # 遍历配置目录中的所有json文件
    for file in os.listdir(config_dir):
        if file.endswith('.json'):
            try:
                with open(os.path.join(config_dir, file), 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 将该配置文件中定义的版本添加到集合中
                    if 'versions' in config:
                        versions.update(config['versions'])
            except Exception as e:
                print(f"读取配置文件 {file} 出错：{str(e)}")
    
    # 将版本号按数字大小排序（降序）
    return sorted(list(versions), 
                 key=lambda x: [int(n) for n in x.replace('1.', '').split('.')], 
                 reverse=True)

def get_version_operations(source_version, target_version):
    """获取从源版本到目标版本的所有操作
    
    Args:
        source_version: 源版本号（如 "1.19.4"）
        target_version: 目标版本号（如 "1.21"）
    Returns:
        list: 需要执行的操作列表
    """
    configs = load_version_configs()
    source_num = float(source_version.replace('1.', ''))
    target_num = float(target_version.replace('1.', ''))
    
    # 确定需要经过的版本
    version_path = []
    current_version = source_version
    
    # 从源版本开始，找到通向目标版本的路径
    while float(current_version.replace('1.', '')) != target_num:
        next_version = None
        next_num = float('inf') if target_num > source_num else float('-inf')
        
        for version, config in configs.items():
            version_num = float(version.replace('1.', ''))
            if target_num > source_num:
                # 向上升级
                if version_num > float(current_version.replace('1.', '')) and version_num <= target_num and version_num < next_num:
                    next_version = version
                    next_num = version_num
            else:
                # 向下降级
                if version_num < float(current_version.replace('1.', '')) and version_num >= target_num and version_num > next_num:
                    next_version = version
                    next_num = version_num
        
        if next_version is None:
            break
        version_path.append(next_version)
        current_version = next_version
    
    # 收集所有操作
    operations = []
    for version in version_path:
        config = configs[version]
        operations.append({
            'version': version,
            'config': config
        })
    
    return operations

def process_version_conversion(source_path, target_path, source_version, target_version):
    """处理版本转换"""
    operations = get_version_operations(source_version, target_version)
    exclude_files = set()
    
    try:
        # 处理所有转换操作
        for operation in operations:
            config = operation['config']
            version = operation['version']  # 获取当前操作的版本
            
            # 处理文件的添加和删除
            for file in config.get('removed_files', []):
                exclude_files.add(file)
            
            # 处理分割操作
            for source_file, splits in config.get('split_operations', {}).items():
                source_file_path = os.path.join(source_path, source_file)
                if os.path.exists(source_file_path):
                    for split in splits:
                        target_file = os.path.join(target_path, split["target"])
                        split_image(source_file_path, split["source"], target_file)
            
            # 处理合并操作
            for target_file, merges in config.get('merge_operations', {}).items():
                target_file_path = os.path.join(target_path, target_file)
                for merge in merges:
                    source_file = merge["source"]
                    source_file_path = os.path.join(source_path, source_file)
                    if os.path.exists(source_file_path):
                        merge_images(target_file_path, source_file_path, merge["position"])
            
            # 处理透明度操作
            for source_file, trans_config in config.get('transparency_operations', {}).items():
                source_file_path = os.path.join(source_path, source_file)
                if os.path.exists(source_file_path):
                    target_file = os.path.join(target_path, trans_config["target"])
                    os.makedirs(os.path.dirname(target_file), exist_ok=True)
                    shutil.copy2(source_file_path, target_file)
                    apply_transparency(target_file, trans_config["keep_area"])
            
            # 处理当前版本的 mcmeta 文件
            mcmeta_version_path = os.path.join(os.path.dirname(__file__), 'config', 'mcmetaFile', version)
            print(f"在处理版本 {version} 的 mcmeta 文件")
            
            if os.path.exists(mcmeta_version_path):
                for root, dirs, files in os.walk(mcmeta_version_path):
                    for file in files:
                        if file.endswith('.mcmeta'):
                            # 获取相对于版本目录的路径
                            rel_path = os.path.relpath(root, mcmeta_version_path)
                            original_file = file[:-7]
                            
                            print(f"找到 mcmeta 文件: {file}")
                            print(f"相对路径: {rel_path}")
                            
                            # 检查是否是分割操作产生的文件
                            is_split_target = False
                            for _, splits in config.get('split_operations', {}).items():
                                for split in splits:
                                    split_target = split['target'].replace('\\', '/')
                                    check_path = os.path.join(rel_path, original_file).replace('\\', '/')
                                    if split_target == check_path:
                                        is_split_target = True
                                        break
                                if is_split_target:
                                    break
                            
                            # 构建目标路径
                            target_dir = os.path.join(target_path, rel_path)
                            target_original_file = os.path.join(target_dir, original_file)
                            
                            # 如果是分割操作的目标文件或者原始文件存在，则复制对应的.mcmeta文件
                            if is_split_target or os.path.exists(target_original_file):
                                source_mcmeta = os.path.join(root, file)
                                target_mcmeta = os.path.join(target_dir, file)
                                
                                print(f"正在复制 mcmeta 文件:")
                                print(f"源文件: {source_mcmeta}")
                                print(f"目标文件: {target_mcmeta}")
                                
                                os.makedirs(os.path.dirname(target_mcmeta), exist_ok=True)
                                shutil.copy2(source_mcmeta, target_mcmeta)
                                print(f"版本 {version} 的 mcmeta 文件复制完成")
        
        return True, exclude_files
    except Exception as e:
        print(f"处理版本转换时出错：{str(e)}")
        messagebox.showerror("错误", f"处理版本转换时出错：{str(e)}")
        return False, exclude_files

def apply_transparency(image_path, keep_area, target_path=None):
    """将指定区域外的像素变为透明
    
    Args:
        image_path: 源图片路径
        keep_area: 保持不透明的区域 (left, top, right, bottom)
        target_path: 保存路径，如果为None则覆盖原图
    """
    try:
        with Image.open(image_path) as img:
            # 转换为RGBA模式以支持透明度
            img = img.convert('RGBA')
            # 获取图片尺寸
            width, height = img.size
            # 创建像素访问对象
            pixels = img.load()
            
            # 遍历所有像素
            for y in range(height):
                for x in range(width):
                    # 如果像素在保持区域外，将其设为透明
                    if not (keep_area[0] <= x <= keep_area[2] and 
                           keep_area[1] <= y <= keep_area[3]):
                        r, g, b, a = pixels[x, y]
                        pixels[x, y] = (r, g, b, 0)
            
            # 保存结果
            save_path = target_path or image_path
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            img.save(save_path)
        return True
    except Exception as e:
        print(f"处理图片透明度时出错：{str(e)}")
        return False

# 添加一些全局样式变量
COLORS = {
    'primary': '#0067C0',  # Win11 主色调
    'primary_dark': '#005BA1',  # 深色主色调
    'primary_light': '#0078D4',  # 浅色主色调
    'background': '#FFFFFF',  # 背景色
    'text': '#202020',  # 主文本色
    'text_secondary': '#5D5D5D',  # 次要文本色
    'border': '#D1D1D1',  # 边框颜色
    'selected': '#CCE4F7',  # 选中状态颜色
    'hover': '#F5F5F5',  # 悬停状态颜色
    'button': '#FFFFFF',  # 按钮背景色
    'button_hover': '#F5F5F5',  # 按钮悬停色
    'button_pressed': '#E5E5E5',  # 按钮按下色
    'button_border': '#D1D1D1'  # 按钮边框色
}

def style_button(button):
    """Windows 11 风格的按钮样式"""
    button.configure(
        bg=COLORS['button'],
        fg=COLORS['text'],
        relief='flat',
        bd=1,
        highlightthickness=1,
        highlightbackground=COLORS['button_border'],
        highlightcolor=COLORS['button_border'],
        padx=15,
        pady=5,
        font=('Segoe UI', 9),  # Win11 默认字体
        cursor='hand2'
    )
    
    def on_enter(e):
        """鼠标进入时的效果"""
        e.widget.configure(
            bg=COLORS['button_hover'],
            highlightbackground=COLORS['primary'],
            highlightcolor=COLORS['primary']
        )
    
    def on_leave(e):
        """鼠标离开时的效果"""
        e.widget.configure(
            bg=COLORS['button'],
            highlightbackground=COLORS['button_border'],
            highlightcolor=COLORS['button_border']
        )
    
    def on_press(e):
        """鼠标按下时的效果"""
        e.widget.configure(bg=COLORS['button_pressed'])
    
    def on_release(e):
        """鼠标释放时的效果"""
        e.widget.configure(bg=COLORS['button_hover'])
    
    button.bind('<Enter>', on_enter)
    button.bind('<Leave>', on_leave)
    button.bind('<Button-1>', on_press)
    button.bind('<ButtonRelease-1>', on_release)

# 创建主窗口
root = tk.Tk()
root.title("喵喵的材质包管理器")

# 设置窗口图标
try:
    icon_path = os.path.join(os.path.dirname(__file__), 'icon', 'miao.png')
    if os.path.exists(icon_path):
        icon = ImageTk.PhotoImage(file=icon_path)
        root.iconphoto(True, icon)
except Exception as e:
    print(f"加载图标出错：{str(e)}")

# 设置窗口大小
root.geometry("1280x700")

# 修改主窗口样式
root.configure(bg=COLORS['background'])

# 创建个框架来容纳滚动条和画布
scroll_frame = tk.Frame(root, bd=0, relief='flat', bg=COLORS['background'])
scroll_frame.place(x=0, y=0, width=300, height=700)

# 创建画布
canvas = tk.Canvas(scroll_frame)
scrollbar = tk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
frame_file = tk.Frame(canvas, bg=COLORS['background'])  # 这个框架将包含所有文件标签

# 配置画布滚动
canvas.configure(yscrollcommand=scrollbar.set)

# 打包滚动条和画布
scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

# 在画布上创建窗口来显示框架
canvas_frame = canvas.create_window((0, 0), window=frame_file, anchor="nw")

# 配置框架大小随内容调整
def on_frame_configure(event):
    # 获取框架实际需要的高度
    frame_height = frame_file.winfo_reqheight()
    # 获取画布可见的高度
    canvas_height = canvas.winfo_height()
    
    if frame_height > canvas_height:
        # 内容超出显示区域时，启用滚动条
        scrollbar.pack(side="right", fill="y")
        canvas.configure(scrollregion=canvas.bbox("all"))
    else:
        # 内容未超出显示区域时，禁用滚动条
        scrollbar.pack_forget()
        canvas.configure(scrollregion=(0, 0, 0, canvas_height))
    
    # 确保框架宽度与画布相同
    canvas.itemconfig(canvas_frame, width=canvas.winfo_width())

frame_file.bind("<Configure>", on_frame_configure)

# 添加鼠标滚轮支持
def on_mousewheel(event):
    # 只在内容超出显示区域时响应滚轮事件
    if frame_file.winfo_reqheight() > canvas.winfo_height():
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

canvas.bind_all("<MouseWheel>", on_mousewheel)

# 确保框架宽度随窗口调整
def on_canvas_configure(event):
    canvas.itemconfig(canvas_frame, width=event.width)

canvas.bind("<Configure>", on_canvas_configure)

# 标签
frame_label = tk.Frame(root, bd=0, relief='flat', bg=COLORS['background'])
frame_label.place(x=300, y=0, width=980, height=40)

# 页面
frame_page = tk.Frame(root, bd=0, relief='flat', bg=COLORS['background'])
frame_page.place(x=300, y=40, width=980, height=620)

# 操作
frame_operate = tk.Frame(root, bd=0, relief='flat', bg=COLORS['background'])
frame_operate.place(x=300, y=660, width=980, height=40)

selected_label = None

# 添加 Minecraft 颜色代码映射
MC_COLORS = {
    '§0': '#000000',  # 黑色
    '§1': '#0000AA',  # 深蓝色
    '§2': '#00AA00',  # 深绿色
    '§3': '#00AAAA',  # 湖蓝色
    '§4': '#AA0000',  # 深红色
    '§5': '#AA00AA',  # 紫色
    '§6': '#FFAA00',  # 金色
    '§7': '#AAAAAA',  # 灰色
    '§8': '#555555',  # 深灰色
    '§9': '#5555FF',  # 蓝色
    '§a': '#55FF55',  # 绿色
    '§b': '#55FFFF',  # 天蓝色
    '§c': '#FF5555',  # 红色
    '§d': '#FF55FF',  # 粉红色
    '§e': '#FFFF55',  # 黄色
    '§f': '#FFFFFF',  # 白
}

def create_colored_text_label(parent, text):
    """创建一个支持 Minecraft 颜色代码的标签"""
    frame = tk.Frame(parent, background=parent.cget('background'))
    current_index = 0
    current_color = '#000000'  # 默认黑色
    
    while current_index < len(text):
        if text[current_index:current_index+2] in MC_COLORS:
            current_color = MC_COLORS[text[current_index:current_index+2]]
            current_index += 2
        else:
            # 找到下一个颜色代码或文本结束
            next_code_index = len(text)
            for code in MC_COLORS:
                pos = text.find(code, current_index)
                if pos != -1 and pos < next_code_index:
                    next_code_index = pos
            
            # 创建这段文本的标签
            segment = text[current_index:next_code_index]
            if segment:
                label = tk.Label(frame, text=segment, fg=current_color, 
                               background=parent.cget('background'))
                label.pack(side=tk.LEFT)
            current_index = next_code_index
    
    return frame

def create_file_label(file_path):
    """创建一个现代风格的文件标签"""
    frame = tk.Frame(frame_file, bg=COLORS['background'], relief='flat')
    frame.pack(fill=tk.X, padx=5, pady=2)
    
    # 添加悬停效果
    def on_enter(e):
        if frame != selected_label:
            frame.configure(bg=COLORS['hover'])
            for child in frame.winfo_children():
                child.configure(bg=COLORS['hover'])
    
    def on_leave(e):
        if frame != selected_label:
            frame.configure(bg=COLORS['background'])
            for child in frame.winfo_children():
                child.configure(bg=COLORS['background'])
    
    frame.bind('<Enter>', on_enter)
    frame.bind('<Leave>', on_leave)
    
    # 获取zip文件名（不含扩展名）用于到对应的缓存目录
    zip_name = os.path.splitext(os.path.basename(file_path))[0]
    icon_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name, 'pack.png')
    
    # 创建图片标签
    icon_label = tk.Label(frame, background='white')
    icon_label.pack(side=tk.LEFT, padx=5, pady=5)
    
    # 尝试加载并显示图片
    try:
        if os.path.exists(icon_path):
            # 加载图片并调整大小
            image = Image.open(icon_path)
            image = image.resize((64, 64), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            icon_label.configure(image=photo)
            icon_label.image = photo  # 保持引用防止被垃圾回收
        else:
            icon_label.configure(width=64, height=64)  # 如果没有图片，保留空间
    except Exception as e:
        print(f"加载图片出错：{str(e)}")
        icon_label.configure(width=64, height=64)  # 加载失败时保留空间
    
    # 获取文件名并检查是否有 pack.mcmeta 中的显示名称
    file_name = os.path.basename(file_path)
    description = None
    mcmeta_path = os.path.join(os.path.dirname(__file__), 'packagecache', 
                              zip_name, 'pack.mcmeta')
    try:
        if os.path.exists(mcmeta_path):
            with open(mcmeta_path, 'r', encoding='utf-8-sig') as f:
                mcmeta = json.load(f)
                if 'pack' in mcmeta and 'description' in mcmeta['pack']:
                    description = mcmeta['pack']['description']
    except Exception as e:
        print(f"读取pack.mcmeta出错：{str(e)}")
    
    # 创一个垂直布局的框架来容纳文件名和描述
    text_frame = tk.Frame(frame, background=COLORS['background'])
    text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=5)
    
    # 创建文件名标（支持颜色代码）
    name_container = create_colored_text_label(text_frame, file_name)
    name_container.pack(fill=tk.X)
    
    # 如果有描述，创建描述标签
    if description:
        desc_label = tk.Label(text_frame, text=description, fg=COLORS['text_secondary'], background=COLORS['background'])
        desc_label.pack(fill=tk.X)
    
    # 存储完整路径
    frame.full_path = file_path
    
    # 绑定点击事件到有元素
    def click_handler(event):
        select_label(frame)
    
    # 绑定点击事件到框架和所有元素
    frame.bind("<Button-1>", click_handler)
    text_frame.bind("<Button-1>", click_handler)
    icon_label.bind("<Button-1>", click_handler)
    name_container.bind("<Button-1>", click_handler)
    if description:
        desc_label.bind("<Button-1>", click_handler)
    
    # 为 name_container 中的所有标签也绑定点击事件
    for widget in name_container.winfo_children():
        widget.bind("<Button-1>", click_handler)
    
    return frame

def check_duplicate_file(file_path):
    """检查是否存在同名文件"""
    new_file_name = os.path.basename(file_path)
    for widget in frame_file.winfo_children():
        if isinstance(widget, tk.Frame):
            existing_path = widget.full_path
            existing_name = os.path.basename(existing_path)
            if existing_name == new_file_name:
                return True
    return False

def select_file():
    file_path = filedialog.askopenfilename(filetypes=[("Zip files", "*.zip"), ("All files", "*.*")])
    if file_path:
        # 检查是否已经添加过同名文件
        if check_duplicate_file(file_path):
            messagebox.showwarning("警", "这个材质包已添加过了")
            return
            
        if check_and_extract_zip(file_path):
            global selected_label
            label = create_file_label(file_path)
            selected_label = None
            update_delete_button_state()
            save_file_list()

def check_and_extract_zip(zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 检查是否包含 pack.mcmeta 文件
            if 'pack.mcmeta' in zip_ref.namelist():
                # 获取zip文件名（含路径和扩展名）
                zip_name = os.path.splitext(os.path.basename(zip_path))[0]
                
                # 创建缓存目录
                cache_dir = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name)
                
                # 如果目录已存在，先删除
                if os.path.exists(cache_dir):
                    shutil.rmtree(cache_dir)
                
                # 建新目录并解压
                os.makedirs(cache_dir)
                zip_ref.extractall(cache_dir)
                return True
            else:
                messagebox.showwarning("警告", '找不到"pack.mcmeta"')
                return False
    except Exception as e:
        messagebox.showerror("错误", f"处理zip文件时出错：{str(e)}")
        return False

# 确保packagecache目录存在
def ensure_cache_dir():
    cache_dir = os.path.join(os.path.dirname(__file__), 'packagecache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

# 在程序启动时创建缓存目录
ensure_cache_dir()

def select_label(frame):
    """修改选择标签函数以适应新的框架结构"""
    global selected_label
    # 将所有框架的背景设置为白色
    for widget in frame_file.winfo_children():
        if isinstance(widget, tk.Frame):
            widget.configure(background=COLORS['background'])
            # 更新框架内所有标签的背景色
            for child in widget.winfo_children():
                if isinstance(child, tk.Frame):
                    for subchild in child.winfo_children():
                        subchild.configure(background=COLORS['background'])
                else:
                    child.configure(background=COLORS['background'])
    
    # 将新选择的框架背景设置为蓝色
    selected_label = frame
    frame.configure(background=COLORS['selected'])
    # 更新框架内所有标签的背景色
    for child in frame.winfo_children():
        if isinstance(child, tk.Frame):
            child.configure(background=COLORS['selected'])
            for subchild in child.winfo_children():
                subchild.configure(background=COLORS['selected'])
        else:
            child.configure(background=COLORS['selected'])
    update_delete_button_state()
    
    # 根据当前标签更新贴图显示
    if current_tab:
        tab_text = current_tab.cget('text')
        if tab_text == "方块":
            update_block_textures()
        elif tab_text == "物品":
            update_item_textures()
        elif tab_text == "实体":
            update_entity_textures()
        elif tab_text == "界面":
            update_gui_textures()
        elif tab_text == "粒子":
            update_particle_textures()

def delete_selected_file():
    global selected_label
    if selected_label:
        # 获取完整文件路径
        file_path = selected_label.full_path
        # 获取zip文件名（不含路径和扩名）
        zip_name = os.path.splitext(os.path.basename(file_path))[0]
        # 构建缓存目录路径
        cache_dir = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name)
        
        # 在删除之前找到下一个要选择的文件
        next_file = None
        all_files = [w for w in frame_file.winfo_children() if isinstance(w, tk.Frame)]
        current_index = all_files.index(selected_label)
        
        # 如果有下一个文件，选择；否则选择前一个文件
        if current_index < len(all_files) - 1:
            next_file = all_files[current_index + 1]
        elif current_index > 0:
            next_file = all_files[current_index - 1]
        
        # 如果缓存目录存在，删除它
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
            except Exception as e:
                messagebox.showerror("错误", f"删除缓存文件夹时出错：{str(e)}")
        
        # 删除标签
        selected_label.destroy()
        selected_label = None
        
        # 选择下一个文件
        if next_file:
            select_label(next_file)
        else:
            update_delete_button_state()
        
        save_file_list()

def update_delete_button_state():
    if selected_label:
        delete_button.config(state=tk.NORMAL)
    else:
        delete_button.config(state=tk.DISABLED)

def save_file_list():
    """保存文件列表到配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'file_list.json')
    file_list = []
    for widget in frame_file.winfo_children():
        if isinstance(widget, tk.Frame):
            file_list.append(widget.full_path)
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(file_list, f, ensure_ascii=False)
    except Exception as e:
        messagebox.showerror("错误", f"保存配置文件时出错：{str(e)}")

def load_file_list():
    """从配置文件加载文件列表"""
    config_path = os.path.join(os.path.dirname(__file__), 'file_list.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_list = json.load(f)
                for file_path in file_list:
                    if os.path.exists(file_path):  # 只加载仍然存在的文件
                        if check_and_extract_zip(file_path):
                            create_file_label(file_path)
        except Exception as e:
            messagebox.showerror("错误", f"加载配置文件时出错：{str(e)}")

# 添加窗口关闭事件处理
def on_closing():
    save_file_list()
    root.destroy()

# 在主窗口创建后添加这些
root.protocol("WM_DELETE_WINDOW", on_closing)
load_file_list()  # 程序启动时加载文件列表

# 在 delete_button 之前添加以下函数
def open_cache_folder():
    """打开应用的缓存文件夹"""
    cache_dir = os.path.join(os.path.dirname(__file__), 'packagecache')
    try:
        # Windows系统使用 explorer
        if os.name == 'nt':
            os.startfile(cache_dir)
        # macOS 系统使用 open
        elif os.name == 'darwin':
            subprocess.run(['open', cache_dir])
        # Linux系统使用 xdg-open
        else:
            subprocess.run(['xdg-open', cache_dir])
    except Exception as e:
        messagebox.showerror("错误", f"无法打开文件夹：{str(e)}")

def get_version_from_pack_format(pack_format):
    """根据 pack_format 获取对应的版本号"""
    format_to_version = {
        6: "1.16.5",
        7: "1.17.1",
        8: "1.18.2",
        9: "1.19.2",
        12: "1.19.3",
        13: "1.19.4",
        15: "1.20.1",
        18: "1.20.2",
        26: "1.20.4",
        30: "1.21"
    }
    return format_to_version.get(pack_format)

def open_convert_window():
    """打开转换窗口"""
    if not selected_label:
        messagebox.showwarning("警告", "请先选择一个质包")
        return
    
    # 获取选中文件的信息
    file_path = selected_label.full_path
    zip_name = os.path.splitext(os.path.basename(file_path))[0]
    mcmeta_path = os.path.join(os.path.dirname(__file__), 'packagecache', 
                              zip_name, 'pack.mcmeta')
    
    # 读取 pack.mcmeta 获取 pack_format
    current_version = None
    try:
        with open(mcmeta_path, 'r', encoding='utf-8-sig') as f:
            mcmeta = json.load(f)
            pack_format = mcmeta['pack']['pack_format']
            current_version = get_version_from_pack_format(pack_format)
    except Exception as e:
        print(f"读取pack.mcmeta出错：{str(e)}")
    
    # 获取可用的版本列表
    versions = get_available_versions()
    if not versions:
        messagebox.showwarning("警告", "未在配置文件中找到可用的版本")
        return
    
    # 创建转换窗口
    convert_window = tk.Toplevel(root)
    convert_window.title("转换")
    convert_window.geometry("400x200")
    
    # 设置窗口模态
    convert_window.grab_set()
    
    # 设置窗口图标
    try:
        convert_window.iconphoto(True, icon)
    except:
        pass
    
    # 创建文件信息框架
    file_frame = tk.Frame(convert_window, bg='white', relief='raised')
    file_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # 获取选中文件的信息
    file_path = selected_label.full_path
    zip_name = os.path.splitext(os.path.basename(file_path))[0]
    icon_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name, 'pack.png')
    
    # 创建图片标签
    icon_label = tk.Label(file_frame, bg='white')
    icon_label.pack(side=tk.LEFT, padx=5, pady=5)
    
    # 尝试加载并显示图片
    try:
        if os.path.exists(icon_path):
            image = Image.open(icon_path)
            image = image.resize((32, 32), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            icon_label.configure(image=photo)
            icon_label.image = photo
        else:
            icon_label.configure(width=32, height=32)
    except Exception as e:
        print(f"加载图片出错：{str(e)}")
        icon_label.configure(width=32, height=32)
    
    # 创建文件名标签
    text_frame = tk.Frame(file_frame, bg='white')
    text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    name_container = create_colored_text_label(text_frame, os.path.basename(file_path))
    name_container.pack(fill=tk.X)
    
    # 创建版本选择框架
    version_frame = tk.Frame(convert_window)
    version_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
    
    # 创建版本选择部分
    tk.Label(version_frame, text="原版本：").pack(side=tk.LEFT)
    source_version = ttk.Combobox(version_frame, values=versions, width=10, state="readonly")
    # 如果能获取到当前版本，就设置为当前版本，否则设置为第一个版本
    if current_version and current_version in versions:
        source_version.set(current_version)
    else:
        source_version.set(versions[0])
    source_version.pack(side=tk.LEFT, padx=(0, 10))
    
    tk.Label(version_frame, text="-->").pack(side=tk.LEFT, padx=5)
    
    tk.Label(version_frame, text="目标版本：").pack(side=tk.LEFT)
    target_version = ttk.Combobox(version_frame, values=versions, width=10, state="readonly")
    target_version.set(versions[0])
    target_version.pack(side=tk.LEFT)
    
    # 创建进度条框架
    progress_frame = tk.Frame(convert_window)
    progress_frame.pack(fill=tk.X, padx=20, pady=10)
    
    # 添加进度条
    progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=300)
    progress_bar.pack(fill=tk.X)
    
    # 创建按钮框架
    button_frame = tk.Frame(convert_window)
    button_frame.pack(side=tk.BOTTOM, pady=10, padx=10, anchor='e')  # 使用 anchor='e' 使按钮靠右
    
    # 确定按钮
    def on_confirm():
        """处理转换确认"""
        source = source_version.get()
        target = target_version.get()
        
        # 获取材质包路径
        source_path = os.path.join(os.path.dirname(__file__), 'packagecache',
                                  os.path.splitext(os.path.basename(selected_label.full_path))[0])
    
        # 创建临时转换目录
        temp_dir = os.path.join(os.path.dirname(__file__), 'packagecache', 'temp_convert')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        try:
            # 复制所有文件到临时目录
            shutil.copytree(source_path, temp_dir)
            
            # 更新进度条
            progress_bar['value'] = 20
            convert_window.update_idletasks()
            
            # 更新 pack.mcmeta 中的 pack_format
            mcmeta_path = os.path.join(temp_dir, 'pack.mcmeta')
            if os.path.exists(mcmeta_path):
                with open(mcmeta_path, 'r', encoding='utf-8-sig') as f:
                    mcmeta = json.load(f)
                
                version_format = {
                    "1.16.5": 6,
                    "1.17.1": 7,
                    "1.18.2": 8,
                    "1.19.2": 9,
                    "1.19.3": 12,
                    "1.19.4": 13,
                    "1.20.1": 15,
                    "1.20.2": 18,
                    "1.20.4": 26,
                    "1.21": 30
                }
                
                mcmeta['pack']['pack_format'] = version_format.get(target, 15)
                
                with open(mcmeta_path, 'w', encoding='utf-8') as f:
                    json.dump(mcmeta, f, indent=4)
            
            # 更新进度条
            progress_bar['value'] = 40
            convert_window.update_idletasks()
            
            # 处理版本转换
            success, exclude_files = process_version_conversion(source_path, temp_dir, source, target)
            if success:
                progress_bar['value'] = 80
                convert_window.update_idletasks()
                
                # 询问保存位置
                default_name = f"{os.path.splitext(os.path.basename(selected_label.full_path))[0]}_{target}.zip"
                save_path = filedialog.asksaveasfilename(
                    defaultextension=".zip",
                    filetypes=[("Zip files", "*.zip")],
                    initialfile=default_name
                )
                
                if save_path:
                    # 创建zip文件，排除指定的文件
                    with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                # 获取相对路径用于检查是否需要排除
                                rel_path = os.path.relpath(file_path, temp_dir)
                                rel_path = rel_path.replace('\\', '/')  # 统一使用正斜杠
                                # 如果文件不在排除列表中，则添加到zip
                                if rel_path not in exclude_files:
                                    zipf.write(file_path, rel_path)
                    
                    # 更新进度条到100%
                    progress_bar['value'] = 100
                    convert_window.update_idletasks()
                    
                    messagebox.showinfo("成功", f"材质包已转换并保存到：\n{save_path}")
                    convert_window.destroy()
            
        except Exception as e:
            messagebox.showerror("错误", f"转换过程中出错：{str(e)}")
            convert_window.destroy()
        
        finally:
            # 清理临时目录
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    # 修改确定和取消按钮的样式
    cancel_button = tk.Button(button_frame, text="取消", command=convert_window.destroy)
    confirm_button = tk.Button(button_frame, text="确定", command=on_confirm)
    
    style_button(cancel_button)
    style_button(confirm_button)
    
    cancel_button.pack(side=tk.RIGHT, padx=(5, 0))
    confirm_button.pack(side=tk.RIGHT)
    
    # 居中显示（相于主窗口）
    convert_window.update_idletasks()
    width = convert_window.winfo_width()
    height = convert_window.winfo_height()
    
    # 获取主窗口的位置和大小
    main_x = root.winfo_x()
    main_y = root.winfo_y()
    main_width = root.winfo_width()
    main_height = root.winfo_height()
    
    # 计算子窗口应该出现的位置（相对于主窗口居中）
    x = main_x + (main_width - width) // 2
    y = main_y + (main_height - height) // 2
    
    # 设置子窗口位置
    convert_window.geometry(f'{width}x{height}+{x}+{y}')

# 修改左侧按钮部分的代码
# 创建一个框架来容纳左侧的按钮
left_buttons_frame = tk.Frame(frame_operate)
left_buttons_frame.pack(side=tk.LEFT)

# 添加"打开应用文件夹"按钮
open_folder_button = tk.Button(left_buttons_frame, text="打开应用文件夹", command=open_cache_folder)
open_folder_button.pack(side=tk.LEFT, padx=(0, 5))  # 添加右边距

# 添加"转换"按钮
convert_button = tk.Button(left_buttons_frame, text="转换", command=open_convert_window)
convert_button.pack(side=tk.LEFT)

# 右侧按钮保持不变
open_button = tk.Button(frame_operate, text="打开文件...", command=select_file)
open_button.pack(side=tk.RIGHT)

delete_button = tk.Button(frame_operate, text="删除文件", command=delete_selected_file, state=tk.DISABLED)
delete_button.pack(side=tk.RIGHT)

# 在全局变量区域添加
current_tab = None
tabs = []
tab_frames = {}

# 修标签和页面部分的代码
def create_tab(text, frame_page):
    """创建现代风格的标签页"""
    tab = tk.Label(
        frame_label,
        text=text,
        bg=COLORS['background'],
        fg=COLORS['text'],
        padx=15,
        pady=8,
        font=('Arial', 9)
    )
    tab.pack(side=tk.LEFT, padx=2, pady=2)
    
    def on_enter(e):
        if tab != current_tab:
            tab.configure(fg=COLORS['primary'])
    
    def on_leave(e):
        if tab != current_tab:
            tab.configure(fg=COLORS['text'])
    
    tab.bind('<Enter>', on_enter)
    tab.bind('<Leave>', on_leave)
    
    # 创建对应的内容框架
    content_frame = tk.Frame(frame_page, bg=COLORS['background'])  # 改为白色背景
    tab_frames[tab] = content_frame
    
    def select_tab(event):
        global current_tab
        # 重置所有标签样式
        for t in tabs:
            t.configure(bg=COLORS['background'])
        # 设置当前标签样式
        tab.configure(bg=COLORS['selected'])
        # 隐藏所有内容框架
        for frame in tab_frames.values():
            frame.pack_forget()
        # 显示当前标签对应的内容框
        content_frame.pack(fill=tk.BOTH, expand=True)
        current_tab = tab
        
        # 根据不同标签更新图显示
        if text == "方块":
            update_block_textures()
        elif text == "物品":
            update_item_textures()
        elif text == "实体":
            update_entity_textures()
        elif text == "界面":
            update_gui_textures()
        elif text == "粒子":
            update_particle_textures()
    
    tab.bind('<Button-1>', select_tab)
    tabs.append(tab)
    return tab, content_frame

# 在全局变量区域添加
from tkinter import ttk
import math

def create_texture_grid(parent_frame):
    """创建现代风格的贴图网格"""
    container = tk.Frame(parent_frame, bg=COLORS['background'])
    container.pack(fill=tk.BOTH, expand=True)
    
    canvas = tk.Canvas(
        container,
        bg=COLORS['background'],
        highlightthickness=0
    )
    
    # 创建用于放置贴图的框架
    texture_frame = tk.Frame(canvas, bg=COLORS['background'])
    
    # 自定义滚动条样式
    style = ttk.Style()
    style.configure(
        "Custom.Vertical.TScrollbar",
        troughcolor=COLORS['background'],
        background=COLORS['primary'],
        arrowcolor=COLORS['primary'],
        bordercolor=COLORS['background'],
        lightcolor=COLORS['primary'],
        darkcolor=COLORS['primary']
    )
    
    scrollbar_y = ttk.Scrollbar(
        container,
        orient="vertical",
        command=canvas.yview,
        style="Custom.Vertical.TScrollbar"
    )
    
    scrollbar_x = ttk.Scrollbar(
        container,
        orient="horizontal",
        command=canvas.xview
    )
    
    canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
    
    # 打包滚动条和画布
    scrollbar_y.pack(side="right", fill="y")
    scrollbar_x.pack(side="bottom", fill="x")
    canvas.pack(side="left", fill="both", expand=True)
    
    # 在画布上创建窗口来显示框架
    canvas.create_window((0, 0), window=texture_frame, anchor="nw")
    
    # 配置滚动区域
    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    texture_frame.bind("<Configure>", on_frame_configure)
    
    # 添加鼠标滚轮支持
    def on_mousewheel(event):
        # 确保内容超显示区域时才滚动
        if texture_frame.winfo_reqheight() > canvas.winfo_height():
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    # 将滚轮事件绑定到画布和texture_frame上
    canvas.bind_all("<MouseWheel>", on_mousewheel)
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
    
    return texture_frame

def load_textures(frame, texture_path, search_text=""):
    """统一的贴图加载函数"""
    # 清除现有的贴图
    for widget in frame.winfo_children():
        widget.destroy()
    
    if not os.path.exists(texture_path):
        return
    
    # 收集所有贴图（包括子文件夹）
    all_textures = []
    for root, dirs, files in os.walk(texture_path):
        for file in files:
            if file.endswith(('.png', '.jpg', '.jpeg')):
                # 获取相对路径
                rel_path = os.path.relpath(root, texture_path)
                if rel_path == '.':
                    texture_name = file
                else:
                    texture_name = os.path.join(rel_path, file)
                
                # 如果有搜索文本，进行过滤
                if not search_text or search_text.lower() in texture_name.lower():
                    full_path = os.path.join(root, file)
                    all_textures.append((full_path, texture_name))
    
    # 计算每行显示的图片数量
    frame_width = 900
    item_width = 100
    columns = max(1, frame_width // item_width)
    
    # 创建网格布局
    for index, (full_path, texture_name) in enumerate(all_textures):
        row = index // columns
        col = index % columns
        
        # 创建图片容器
        item_frame = tk.Frame(frame, bg=COLORS['background'])
        item_frame.grid(row=row, column=col, padx=5, pady=5)
        
        try:
            # 加载并显示图片
            image = Image.open(full_path)
            image = image.resize((64, 64), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(image)
            
            # 创建图片标签
            img_label = tk.Label(item_frame, image=photo, bg=COLORS['background'])
            img_label.image = photo
            img_label.pack()
            
            # 创建文件名标签
            name_label = tk.Label(item_frame, text=texture_name, fg=COLORS['text'], bg=COLORS['background'],
                                wraplength=90)
            name_label.pack()
            
            # 绑定点击和右键事件
            for widget in [item_frame, img_label, name_label]:
                widget.bind('<Button-1>', 
                          lambda e, f=item_frame, p=full_path: select_texture(e, f, p))
                widget.bind('<Double-Button-1>', 
                          lambda e, p=full_path: replace_texture(e, p))
                widget.bind('<Button-3>', 
                          lambda e, p=full_path: show_context_menu(e, p))
            
        except Exception as e:
            print(f"加载贴图出错 {texture_name}: {str(e)}")

def update_block_textures():
    """更新方块贴图显示"""
    if not selected_label or not current_tab:
        return
    
    zip_name = os.path.splitext(os.path.basename(selected_label.full_path))[0]
    texture_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name,
                               'assets', 'minecraft', 'textures', 'block')
    load_textures(block_texture_frame, texture_path, current_search_text)

def update_item_textures():
    """更新物品贴图显示"""
    if not selected_label or not current_tab:
        return
    
    zip_name = os.path.splitext(os.path.basename(selected_label.full_path))[0]
    texture_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name,
                               'assets', 'minecraft', 'textures', 'item')
    load_textures(item_texture_frame, texture_path, current_search_text)

# 在全局变量区域添加
entity_texture_frame = None

# 在全局变量区域添加
gui_texture_frame = None

# 在全局变量区域添加
particle_texture_frame = None

# 在 create_tab 数之前添加 update_particle_textures 函数
def update_particle_textures():
    """更新粒子贴图显示"""
    if not selected_label or not current_tab:
        return
        
    # 获取选中的材质包路径
    zip_name = os.path.splitext(os.path.basename(selected_label.full_path))[0]
    base_particle_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name,
                                   'assets', 'minecraft', 'textures', 'particle')
    
    # 收集所有粒子贴图（包括子文件夹）
    all_textures = []
    if os.path.exists(base_particle_path):
        for root, dirs, files in os.walk(base_particle_path):
            for file in files:
                if file.endswith(('.png', '.jpg', '.jpeg')):
                    # 获取相对于particle文件夹的路径
                    rel_path = os.path.relpath(root, base_particle_path)
                    if rel_path == '.':
                        # 如果在particle文件夹根目录
                        texture_name = file
                    else:
                        # 如果在子文件夹中
                        texture_name = os.path.join(rel_path, file)
                    all_textures.append((os.path.join(root, file), texture_name))
    
    # 清除现有的贴图
    for widget in particle_texture_frame.winfo_children():
        widget.destroy()
    
    # 计算每行显示的图片数量
    frame_width = 900
    item_width = 100
    columns = max(1, frame_width // item_width)
    
    # 创建网格布局
    for index, (full_path, texture_name) in enumerate(all_textures):
        if current_search_text and current_search_text.lower() not in texture_name.lower():
            continue
            
        row = index // columns
        col = index % columns
        
        # 创建图片容器
        item_frame = tk.Frame(particle_texture_frame, bg=COLORS['background'])
        item_frame.grid(row=row, column=col, padx=5, pady=5)
        
        try:
            # 加载并显示图片
            image = Image.open(full_path)
            image = image.resize((64, 64), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(image)
            
            # 创建图片标签
            img_label = tk.Label(item_frame, image=photo, bg=COLORS['background'])
            img_label.image = photo
            img_label.pack()
            
            # 创建文件名标签
            name_label = tk.Label(item_frame, text=texture_name, fg=COLORS['text'], bg=COLORS['background'],
                                wraplength=90)
            name_label.pack()
            
            # 绑定点击和双击事件
            for widget in [item_frame, img_label, name_label]:
                widget.bind('<Button-1>', 
                          lambda e, f=item_frame, p=full_path: select_texture(e, f, p))
                widget.bind('<Double-Button-1>', 
                          lambda e, p=full_path: replace_texture(e, p))
            
        except Exception as e:
            print(f"加载贴图出错 {texture_name}: {str(e)}")

# 然是 create_tab 函数
def create_tab(text, frame_page):
    """创建现代风格的标签页"""
    tab = tk.Label(
        frame_label,
        text=text,
        bg=COLORS['background'],
        fg=COLORS['text'],
        padx=15,
        pady=8,
        font=('Arial', 9)
    )
    tab.pack(side=tk.LEFT, padx=2, pady=2)
    
    def on_enter(e):
        if tab != current_tab:
            tab.configure(fg=COLORS['primary'])
    
    def on_leave(e):
        if tab != current_tab:
            tab.configure(fg=COLORS['text'])
    
    tab.bind('<Enter>', on_enter)
    tab.bind('<Leave>', on_leave)
    
    # 创建对应的内容框架
    content_frame = tk.Frame(frame_page, bg=COLORS['background'])  # 改为白色背景
    tab_frames[tab] = content_frame
    
    def select_tab(event):
        global current_tab
        # 重置所有标签样式
        for t in tabs:
            t.configure(bg=COLORS['background'])
        # 设置当前标签样式
        tab.configure(bg=COLORS['selected'])
        # 隐藏所有内容框架
        for frame in tab_frames.values():
            frame.pack_forget()
        # 显示当前标签对应的内容框
        content_frame.pack(fill=tk.BOTH, expand=True)
        current_tab = tab
        
        # 根据不同标签更新图显示
        if text == "方块":
            update_block_textures()
        elif text == "物品":
            update_item_textures()
        elif text == "实体":
            update_entity_textures()
        elif text == "界面":
            update_gui_textures()
        elif text == "粒子":
            update_particle_textures()
    
    tab.bind('<Button-1>', select_tab)
    tabs.append(tab)
    return tab, content_frame

# 首先创建标签页
tab1, frame1 = create_tab("方块", frame_page)
tab3, frame3 = create_tab("物品", frame_page)
tab4, frame4 = create_tab("实体", frame_page)
tab6, frame6 = create_tab("界面", frame_page)
tab7, frame7 = create_tab("粒子", frame_page)

# 然后创建标签页的内容
block_texture_frame = create_texture_grid(frame1)
item_texture_frame = create_texture_grid(frame3)
entity_texture_frame = create_texture_grid(frame4)
gui_texture_frame = create_texture_grid(frame6)
particle_texture_frame = create_texture_grid(frame7)

# 默认选中第一个标签
if tabs:
    tabs[0].event_generate('<Button-1>')

# 在全局变量区域添加
selected_textures = set()  # 存储选中的贴图
last_selected_texture = None  # 用于shift选

def select_texture(event, item_frame, texture_path):
    """处理贴图的选择逻辑"""
    global last_selected_texture
    
    # 获取所有贴图框架
    all_texture_frames = [w for w in item_frame.master.winfo_children() 
                         if isinstance(w, tk.Frame)]
    
    if event.state & 0x4:  # Ctrl被按下
        # 切换选择状态
        if item_frame in selected_textures:
            selected_textures.remove(item_frame)
            item_frame.configure(bg=COLORS['background'])
            for widget in item_frame.winfo_children():
                widget.configure(bg=COLORS['background'])
        else:
            selected_textures.add(item_frame)
            item_frame.configure(bg=COLORS['selected'])
            for widget in item_frame.winfo_children():
                widget.configure(bg=COLORS['selected'])
        last_selected_texture = item_frame
        
    elif event.state & 0x1:  # Shift按
        if last_selected_texture:
            # 获取当前和上次选择的索引
            current_idx = all_texture_frames.index(item_frame)
            last_idx = all_texture_frames.index(last_selected_texture)
            
            # 清除之前的选择
            selected_textures.clear()
            for frame in all_texture_frames:
                frame.configure(bg=COLORS['background'])
                for widget in frame.winfo_children():
                    widget.configure(bg=COLORS['background'])
            
            # 选择范围内的所有贴图
            start_idx = min(current_idx, last_idx)
            end_idx = max(current_idx, last_idx) + 1
            for idx in range(start_idx, end_idx):
                frame = all_texture_frames[idx]
                selected_textures.add(frame)
                frame.configure(bg=COLORS['selected'])
                for widget in frame.winfo_children():
                    widget.configure(bg=COLORS['selected'])
    
    else:  # 普通点击
        # 清除之前的选择
        selected_textures.clear()
        for frame in all_texture_frames:
            frame.configure(bg=COLORS['background'])
            for widget in frame.winfo_children():
                widget.configure(bg=COLORS['background'])
        
        # 选择当前贴图
        selected_textures.add(item_frame)
        item_frame.configure(bg=COLORS['selected'])
        for widget in item_frame.winfo_children():
            widget.configure(bg=COLORS['selected'])
        last_selected_texture = item_frame
    
    update_delete_texture_button_state()

def replace_texture(event, texture_path):
    """处理贴的双击替换逻辑"""
    new_texture = filedialog.askopenfilename(
        filetypes=[("Image files", "*.png *.jpg *.jpeg")]
    )
    if new_texture:
        try:
            # 复制新贴图到原位置
            shutil.copy2(new_texture, texture_path)
            # 更新显示
            update_block_textures()
        except Exception as e:
            messagebox.showerror("错误", f"替换贴图时出错：{str(e)}")

def delete_selected_textures():
    """删除选中的贴图"""
    if not selected_textures:
        return
        
    if messagebox.askyesno("确认", "确定要删除选的贴图吗？"):
        for item_frame in selected_textures:
            try:
                # 获取贴图文件名
                filename = item_frame.winfo_children()[-1].cget("text")
                # 获取完整路径
                texture_path = os.path.join(
                    os.path.dirname(__file__), 
                    'packagecache',
                    os.path.splitext(os.path.basename(selected_label.full_path))[0],
                    'assets', 'minecraft', 'textures', 'block',
                    filename
                )
                # 删除文件
                if os.path.exists(texture_path):
                    os.remove(texture_path)
                # 删除界面示
                item_frame.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"删除贴图时出错：{str(e)}")
        
        selected_textures.clear()
        update_delete_texture_button_state()

def update_delete_texture_button_state():
    """更新删除贴图按钮状态"""
    if selected_textures:
        delete_texture_button.config(state=tk.NORMAL)
    else:
        delete_texture_button.config(state=tk.DISABLED)

# 修改 load_textures 函数
def load_textures(frame, texture_path, search_text=""):
    """统一的贴图加载函数"""
    # 清除现有的贴图
    for widget in frame.winfo_children():
        widget.destroy()
    
    if not os.path.exists(texture_path):
        return
    
    # 收集所有贴图（包括子文件夹）
    all_textures = []
    for root, dirs, files in os.walk(texture_path):
        for file in files:
            if file.endswith(('.png', '.jpg', '.jpeg')):
                # 获取相对路径
                rel_path = os.path.relpath(root, texture_path)
                if rel_path == '.':
                    texture_name = file
                else:
                    texture_name = os.path.join(rel_path, file)
                
                # 如果有搜索文本，进行过滤
                if not search_text or search_text.lower() in texture_name.lower():
                    full_path = os.path.join(root, file)
                    all_textures.append((full_path, texture_name))
    
    # 计算每行显示的图片数量
    frame_width = 900
    item_width = 100
    columns = max(1, frame_width // item_width)
    
    # 创建网格布局
    for index, (full_path, texture_name) in enumerate(all_textures):
        row = index // columns
        col = index % columns
        
        # 创建图片容器
        item_frame = tk.Frame(frame, bg=COLORS['background'])
        item_frame.grid(row=row, column=col, padx=5, pady=5)
        
        try:
            # 加载并显示图片
            image = Image.open(full_path)
            image = image.resize((64, 64), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(image)
            
            # 创建图片标签
            img_label = tk.Label(item_frame, image=photo, bg=COLORS['background'])
            img_label.image = photo
            img_label.pack()
            
            # 创建文件名标签
            name_label = tk.Label(item_frame, text=texture_name, fg=COLORS['text'], bg=COLORS['background'],
                                wraplength=90)
            name_label.pack()
            
            # 绑定点击和右键事件
            for widget in [item_frame, img_label, name_label]:
                widget.bind('<Button-1>', 
                          lambda e, f=item_frame, p=full_path: select_texture(e, f, p))
                widget.bind('<Double-Button-1>', 
                          lambda e, p=full_path: replace_texture(e, p))
                widget.bind('<Button-3>', 
                          lambda e, p=full_path: show_context_menu(e, p))
            
        except Exception as e:
            print(f"加载贴图出错 {texture_name}: {str(e)}")

# 修改操作框架部分的代码，添删除贴图按钮
delete_texture_button = tk.Button(frame_operate, text="删除贴图", 
                                command=delete_selected_textures, 
                                state=tk.DISABLED)
delete_texture_button.pack(side=tk.RIGHT, padx=10)  # 添加一些间距

# 在全局变量区域添加
current_search_text = ""

def create_search_widgets(frame_operate):
    """创建现代风格的搜索控件"""
    center_frame = tk.Frame(frame_operate, bg=COLORS['background'])
    center_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
    
    search_container = tk.Frame(
        center_frame,
        bg=COLORS['background'],
        highlightthickness=1,
        highlightbackground=COLORS['border']
    )
    search_container.pack(expand=False)
    
    # 修改搜索图标样式
    search_icon = tk.Label(
        search_container,
        text="🔍",
        fg=COLORS['text_secondary'],
        bg=COLORS['background']
    )
    search_icon.pack(side=tk.LEFT, padx=(5, 0))
    
    # 修改搜索输入框样式
    entry_container = tk.Frame(search_container, bg=COLORS['background'])
    entry_container.pack(side=tk.LEFT)
    
    search_var = tk.StringVar()
    search_entry = tk.Entry(
        entry_container,
        width=30,
        textvariable=search_var,
        relief='flat',
        bg=COLORS['background'],
        fg=COLORS['text'],
        insertbackground=COLORS['text'],  # 光标颜色
        font=('Microsoft YaHei', 9)  # 设置字体为微软雅黑
    )
    search_entry.pack(side=tk.LEFT, padx=5, pady=5)
    
    # 修改清除按钮样式
    clear_button = tk.Label(
        entry_container,
        text="✕",
        fg=COLORS['text_secondary'],
        bg=COLORS['background'],
        cursor="hand2",
        font=('Microsoft YaHei', 9)  # 设置字体为微软雅黑
    )
    
    def on_search_change(*args):
        """当搜索文本改变时触发"""
        global current_search_text
        search_text = search_var.get().lower()
        current_search_text = search_text
        
        # 根据当前标签更新显示
        if current_tab:
            tab_text = current_tab.cget('text')
            if tab_text == "方块":
                update_block_textures()
            elif tab_text == "物品":
                update_item_textures()
            elif tab_text == "实体":
                update_entity_textures()
            elif tab_text == "界面":
                update_gui_textures()
            elif tab_text == "粒子":
                update_particle_textures()
        
        # 更新清除按钮显示状态
        if search_text:
            clear_button.pack(side=tk.RIGHT, in_=entry_container)
        else:
            clear_button.pack_forget()
    
    # 绑定搜索文本变化事件
    search_var.trace_add("write", on_search_change)
    
    # 添加清除按钮点击事件
    def clear_search(event):
        search_var.set("")  # 清除搜索文本
        search_entry.focus()  # 让输入框重新获得焦点
    
    clear_button.bind("<Button-1>", clear_search)
    
    # 初始状态隐藏清除按钮
    clear_button.pack_forget()
    
    return search_entry

def perform_search(search_text):
    """执行搜索"""
    if not selected_label:
        return
        
    # 获取选中的材质包路径
    zip_name = os.path.splitext(os.path.basename(selected_label.full_path))[0]
    base_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name,
                            'assets', 'minecraft', 'textures')
    
    # 确定搜索范围
    if current_tab and current_tab.cget('text') == "方块":
        if "block" in root_path:
            load_textures(block_texture_frame, root_path, search_text)
    # 为其他标签页添加类似的处理...

# 修改 update_block_textures 函数
def update_block_textures():
    """更新方块贴图显示"""
    if not selected_label or not current_tab:
        return
    
    zip_name = os.path.splitext(os.path.basename(selected_label.full_path))[0]
    texture_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name,
                               'assets', 'minecraft', 'textures', 'block')
    load_textures(block_texture_frame, texture_path, current_search_text)

# 在创建操作框架的分添加搜索控件
# 创建搜索控件
search_entry = create_search_widgets(frame_operate)

# 添加更新实体贴图的函数
def update_entity_textures():
    """更新实体贴图显示"""
    if not selected_label or not current_tab:
        return
        
    # 获取选中的材质包路
    zip_name = os.path.splitext(os.path.basename(selected_label.full_path))[0]
    texture_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name,
                               'assets', 'minecraft', 'textures', 'entity')
    load_textures(entity_texture_frame, texture_path, current_search_text)

# 添加更新界面贴图的函数
def update_gui_textures():
    """更新界面贴图显示"""
    if not selected_label or not current_tab:
        return
        
    # 获取选中的材质包路径
    zip_name = os.path.splitext(os.path.basename(selected_label.full_path))[0]
    texture_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name,
                               'assets', 'minecraft', 'textures', 'gui')
    load_textures(gui_texture_frame, texture_path, current_search_text)

# 添加更新粒子贴图的函数
def update_particle_textures():
    """更新粒子贴图显示"""
    if not selected_label or not current_tab:
        return
        
    # 获取选中的材质包路径
    zip_name = os.path.splitext(os.path.basename(selected_label.full_path))[0]
    texture_path = os.path.join(os.path.dirname(__file__), 'packagecache', zip_name,
                               'assets', 'minecraft', 'textures', 'particle')
    load_textures(particle_texture_frame, texture_path, current_search_text)

# 添加剪贴板和系统打开文件的支持
def create_context_menu(parent, texture_path):
    """创建现代风格的右键菜单"""
    menu = tk.Menu(
        parent,
        tearoff=0,
        bg=COLORS['background'],
        fg=COLORS['text'],
        activebackground=COLORS['primary'],
        activeforeground='white',
        relief='flat',
        bd=0
    )
    
    def copy_path():
        """制文件路径到剪贴板"""
        pyperclip.copy(texture_path)
    
    def open_containing_folder():
        """打开文件所在文件夹"""
        try:
            if os.name == 'nt':  # Windows
                subprocess.run(['explorer', '/select,', texture_path])
            elif os.name == 'darwin':  # macOS
                subprocess.run(['open', '-R', texture_path])
            else:  # Linux
                subprocess.run(['xdg-open', os.path.dirname(texture_path)])
        except Exception as e:
            messagebox.showerror("错误", f"打开文件夹时出错：{str(e)}")
    
    def open_image():
        """使用系统默认程序打开图片"""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(texture_path)
            elif os.name == 'darwin':  # macOS
                subprocess.run(['open', texture_path])
            else:  # Linux
                subprocess.run(['xdg-open', texture_path])
        except Exception as e:
            messagebox.showerror("错误", f"打开图片时出错：{str(e)}")
    
    menu.add_command(label="打开所在文件夹", command=open_containing_folder)
    menu.add_command(label="复制路径", command=copy_path)
    menu.add_command(label="查看图片", command=open_image)
    
    return menu

def show_context_menu(event, texture_path):
    """显示右键菜单"""
    menu = create_context_menu(event.widget, texture_path)
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()

# 在主循环前添加以下代码
# 默认选中第一个标签
if tabs:
    tabs[0].event_generate('<Button-1>')

# 默认选中第一个文件
def select_first_file():
    # 获取第个文件框架
    first_file = None
    for widget in frame_file.winfo_children():
        if isinstance(widget, tk.Frame):
            first_file = widget
            break
    
    # 如果存在文件，选中它
    if first_file:
        select_label(first_file)

# 在程序启动时调用
root.after(100, select_first_file)  # 使用 after 确保界面完全加载后再执行

# 在主循环前添加以下代码
def initialize_app():
    """初始化应用程序，选中第一个标签和文件"""
    # 选中第一个标签
    if tabs:
        tabs[0].event_generate('<Button-1>')
    
    # 选中第一个文件
    first_file = None
    for widget in frame_file.winfo_children():
        if isinstance(widget, tk.Frame):
            first_file = widget
            break
    
    # 如果存在文件，选中它
    if first_file:
        select_label(first_file)

# 在程序启动时调用初始化函数
root.after(100, initialize_app)

# 修改所有按钮的样式
style_button(open_button)
style_button(delete_button)
style_button(delete_texture_button)
style_button(convert_button)
style_button(open_folder_button)

# 最后是主循环
root.mainloop()