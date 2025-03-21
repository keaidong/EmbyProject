import re
import os
from tqdm import tqdm  # 导入 tqdm 库

def adjust_lrc_timing(file_path, adjustment):
    # 正则表达式匹配时间戳
    time_pattern = re.compile(r"\[(\d+):(\d+\.\d+)]")

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    adjusted_lines = []

    for line in lines:
        def adjust_match(match):
            minutes, seconds = int(match.group(1)), float(match.group(2))
            total_seconds = minutes * 60 + seconds + adjustment
            if total_seconds < 0:  # 防止时间为负
                total_seconds = 0
            new_minutes = int(total_seconds // 60)
            new_seconds = total_seconds % 60
            return f"[{new_minutes:02}:{new_seconds:05.2f}]"

        # 替换时间戳
        adjusted_line = time_pattern.sub(adjust_match, line)
        adjusted_lines.append(adjusted_line)

    # 覆盖原文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(adjusted_lines)

def process_lrc_files_in_directory(directory, adjustment=-1):
    # 获取所有.lrc文件的列表
    lrc_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.lrc'):
                lrc_files.append(os.path.join(root, file))

    # 使用 tqdm 显示进度条
    for file_path in tqdm(lrc_files, desc="处理文件", unit="个文件"):
        #print(f"正在处理文件: {file_path}")
        adjust_lrc_timing(file_path, adjustment)

    print("所有文件处理完成！")

# 使用指定的目录路径
directory_path = "D:\\MusicFree下载目录"  # 替换为实际路径
