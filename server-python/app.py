#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, send_from_directory
import xml.etree.ElementTree as ET
import json
import yaml
import os
from datetime import datetime, timedelta
import subprocess
import threading
import time
import hashlib

app = Flask(__name__, root_path=os.path.dirname(os.path.dirname(__file__)))

# 配置文件路径（优先使用yml格式）
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yml')

# 读取配置
config = {
    "svn_base_url": "http://svn.my.com/project/iorder-saas",
    "default_branch": "trunk",
    "debug": False,
    "svn_username": "svnuser",
    "svn_password": "svnpassword",
    "log_range_days": 180
}

# 加载配置文件
def load_config():
    global config
    
    print(f"[{datetime.now()}] LOAD - ============== 加载配置 ==============")
    # 优先尝试加载yml配置文件
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                if loaded_config:
                    config.update(loaded_config)
            print(f"[{datetime.now()}] LOAD - 从yml配置文件加载配置成功: {CONFIG_FILE}")
            print(f"[{datetime.now()}] LOAD - 当前配置: {config}")
            return
        except Exception as e:
            print(f"[{datetime.now()}] LOAD - 加载yml配置文件失败: {e}")
    
    # 如果都不存在，使用默认配置
    print(f"[{datetime.now()}] LOAD - 未找到配置文件，使用默认配置")

# 初始化配置
load_config()


# 缓存文件路径
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'svn_cache.json')

# 缓存结构设计:
# {
#     "version": "1.1",
#     "cache": {
#         "revision_file": {
#             "file_cache_key": {
#                 "revision": "600100",
#                 "file_path": "/path/to/file.java",
#                 "hash": "md5_hash_of_file_content",
#                 "author": "user123",
#                 "lines_added": 10,
#                 "lines_deleted": 5,
#                 "timestamp": 1620000000
#             }
#         },
#         "revision_summary": {
#             "revision_cache_key": {
#                 "revision": "600100",
#                 "branch_url": "http://svn.example.com/repo",
#                 "total_lines_added": 100,
#                 "total_lines_deleted": 50,
#                 "file_count": 10,
#                 "timestamp": 1620000000
#             }
#         }
#     }
# }

# JSON序列化自定义编码器，处理datetime对象
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)
    
# 加载缓存
def load_cache():
    """
    加载缓存数据
    """
    print(f"[{datetime.now()}] LOAD - ============== 加载缓存 ==============")
    # 创建cache目录（如果不存在）
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        print(f"[{datetime.now()}] LOAD - 已创建cache目录: {cache_dir}")
    else:
        print(f"[{datetime.now()}] LOAD - 目录已存在: {cache_dir}")
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[{datetime.now()}] LOAD - 加载缓存失败: {e}")
            print(f"[{datetime.now()}] LOAD - 缓存文件损坏，将重置缓存")
            # 删除损坏的缓存文件
            try:
                os.remove(CACHE_FILE)
                print(f"[{datetime.now()}] LOAD - 已删除损坏的缓存文件")
            except Exception as delete_error:
                print(f"[{datetime.now()}] LOAD - 删除缓存文件失败: {delete_error}")
    
    # 返回默认缓存结构
    return {
        "version": "1.1",
        "cache": {
            "revision_file": {},
            "revision_summary": {}
        }
    }

# 保存缓存
def save_cache(cache_data):
    """
    保存缓存数据
    """
    try:
        # 只保存缓存数据，不保存分析结果
        cache_to_save = cache_data.copy()
        # 移除可能存在的results字段
        if 'results' in cache_to_save:
            del cache_to_save['results']
        
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_to_save, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)
            
        cache_file_size = os.path.getsize(CACHE_FILE)
        print(f"[{datetime.now()}] cache - 缓存已保存到: {CACHE_FILE}, 缓存文件大小：{cache_file_size / 1024:.2f} kb")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] cache - 保存缓存失败: {e}")
        return False

# 生成文件级缓存键
def generate_file_cache_key(revision, file_path):
    """
    生成文件级缓存键
    :param revision: 版本号
    :param file_path: 文件路径
    :return: 缓存键字符串
    """
    key_str = f"{revision}|{file_path}"
    return hashlib.md5(key_str.encode()).hexdigest()

# 生成版本级缓存键
def generate_revision_cache_key(revision, branch_url):
    """
    生成版本级缓存键
    :param revision: 版本号
    :param branch_url: 分支URL
    :return: 缓存键字符串
    """
    # key_str = f"{revision}|{branch_url}"
    # return hashlib.md5(key_str.encode()).hexdigest()
    return revision


# 全局缓存对象
cache_data = load_cache()

# 全局任务状态
task_status = {
    'running': False,
    'progress': 0,
    'message': '',
    'completed': False,
    'error': None,
    'execution_details': []  # 新增：执行明细列表
}

# 初始化分析结果，不从缓存加载
analysis_results = {}

# 获取SVN externals配置
def get_svn_externals(branch_url, username=None, password=None):
    """
    从SVN服务器获取指定分支的externals配置，包括特定子目录的externals
    :param branch_url: SVN分支URL
    :param username: SVN用户名
    :param password: SVN密码
    :return: 包含externals信息的字典列表
    """
    global task_status
    externals = []
    
    # 记录开始获取externals
    task_status['execution_details'].append({
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'message': '开始获取SVN externals配置',
        'level': 'info'
    })
    
    # 需要检查externals的目录列表
    check_dirs = [
        "src/main/java/com/fh/iasp/app",  # 用户指定的Java目录
        "src/main/resources/com/fh/iasp/app"  # 用户指定的资源目录
    ]
    
    for check_dir in check_dirs:
        # 构建完整的URL
        if check_dir:
            target_url = f"{branch_url.rstrip('/')}/{check_dir}"
        else:
            target_url = branch_url
        
        # 记录正在检查的目录
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'正在检查目录: {target_url}',
            'level': 'info'
        })
        
        cmd = ['svn', 'propget', 'svn:externals', '--no-auth-cache']
        
        if username:
            cmd.extend(['--username', username])
        if password:
            cmd.extend(['--password', password])
        
        cmd.append(target_url)
        
        print(f"[{datetime.now()}] SVN任务 - 正在获取externals配置: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                error_msg = f'获取 {target_url} externals失败: {result.stderr}'
                print(f"[{datetime.now()}] SVN任务 - {error_msg}")
                task_status['execution_details'].append({
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'message': error_msg,
                    'level': 'warning'
                })
                continue
            
            # 解析结果
            for line in result.stdout.strip().split('\n'):
                print(f"[{datetime.now()}] SVN任务 - 解析external: {line}")
                if line.strip():
                    # 解析externals行（格式：relative_path external_url）
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        relative_path = parts[0]
                        app = parts[1]
                        
                        # 替换所有以"^/trunk/"开头的SVN路径引用为完整URL
                        if relative_path.startswith("^/trunk/"):
                            relative_path = "{}{}".format(config.get("svn_base_url", ""), relative_path)
                    
                        
                        externals.append({
                            'path': app,
                            'url': relative_path
                        })
                        external_msg = f'发现external: {app} -> {relative_path}'
                        print(f"[{datetime.now()}] SVN任务 - {external_msg}")
                        task_status['execution_details'].append({
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'message': external_msg,
                            'level': 'info'
                        })
        except Exception as e:
            error_msg = f'获取 {target_url} externals发生错误: {e}'
            print(f"[{datetime.now()}] SVN任务 - {error_msg}")
            task_status['execution_details'].append({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': error_msg,
                'level': 'error'
            })
            continue
    
    # 记录完成获取externals
    task_status['execution_details'].append({
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'message': f'完成获取externals，共发现 {len(externals)} 个配置',
        'level': 'info'
    })
    
    print(f"[{datetime.now()}] SVN任务 - 共发现 {len(externals)} 个externals配置")
    return externals

# 获取文件内容哈希值
def get_svn_file_content_hash(branch_url, revision, file_path, username=None, password=None):
    """
    获取指定版本文件的内容哈希值
    :param branch_url: SVN分支URL
    :param revision: 版本号
    :param file_path: 文件路径
    :param username: SVN用户名
    :param password: SVN密码
    :return: 文件内容的MD5哈希值
    """
    # 构建命令获取文件内容
    cmd = ['svn', 'cat', f'-r{revision}', f'{branch_url}/{file_path}']
    
    if username:
        cmd.extend(['--username', username])
    if password:
        cmd.extend(['--password', password])
    
    try:
        # 执行命令获取文件内容（不使用encoding参数）
        result = subprocess.run(cmd, capture_output=True, text=False, timeout=30)
        
        # 手动解码输出
        content = ""
        try:
            content = result.stdout.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = result.stdout.decode('gbk')
            except UnicodeDecodeError:
                content = result.stdout.decode('latin-1')
        
        if result.returncode != 0:
            return None
        
        # 计算MD5哈希值
        file_hash = hashlib.md5(content.encode()).hexdigest()
        return file_hash
    except Exception as e:
        print(f"获取文件内容哈希失败 ({revision}:{file_path}): {e}")
        return None
    
# 从SVN服务器获取特定版本的diff
def get_svn_log(branch_url, username=None, password=None, revision_range=None):
    """
    从SVN服务器获取指定分支的提交记录
    :param branch_url: SVN分支URL
    :param username: SVN用户名
    :param password: SVN密码
    :param revision_range: 版本范围，格式如"1234:5678"或"HEAD"
    :return: SVN log的XML字符串
    """
 
    print(f"[{datetime.now()}] SVN-log - 分支 {branch_url} 版本范围: {revision_range}")

    # 从SVN服务器获取指定分支的提交记录
    cmd = ['svn', 'log', '--xml', '--verbose', '--no-auth-cache']  # 添加--no-auth-cache参数
    
    if username:
        cmd.extend(['--username', username])
    if password:
        cmd.extend(['--password', password])
    if revision_range:
        cmd.extend(['-r', revision_range])

    cmd.append(branch_url)
    
    print(f"[{datetime.now()}] SVN-log - 正在执行SVN命令: {' '.join(cmd)}")
    try:
        # 不使用encoding参数，获取原始字节输出
        result = subprocess.run(cmd, capture_output=True, text=False, timeout=600)  # 增加超时时间到600秒
        
        # 手动解码输出
        stdout = stderr = ""
        try:
            stdout = result.stdout.decode('utf-8')
            stderr = result.stderr.decode('utf-8')
        except UnicodeDecodeError:
            print(f"[{datetime.now()}] SVN-log - UTF-8编码解码失败，尝试使用GBK编码")
            try:
                stdout = result.stdout.decode('gbk')
                stderr = result.stderr.decode('gbk')
            except UnicodeDecodeError:
                # 如果GBK也失败，尝试使用latin-1（不会失败）
                stdout = result.stdout.decode('latin-1')
                stderr = result.stderr.decode('latin-1')
                print(f"[{datetime.now()}] SVN-log - GBK编码解码失败，使用latin-1编码")
        
        if result.returncode != 0:
            error_msg = f'SVN命令执行失败: {stderr}'
            print(f"[{datetime.now()}] SVN-log - 错误: {error_msg}")
            task_status['error'] = error_msg
            task_status['running'] = False
            return
        
        print(f"[{datetime.now()}] SVN-log - SVN命令执行成功，返回码: {result.returncode}")
        
        # 构造并返回结果对象
        class Result:
            def __init__(self, stdout, stderr, returncode):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode
        
        return Result(stdout, stderr, result.returncode)
    except subprocess.TimeoutExpired:
        error_msg = f'SVN命令超时，请减小版本范围或检查网络连接\n命令: {" ".join(cmd)}'
        print(f"[{datetime.now()}] SVN-log - 错误: {error_msg}")
        task_status['error'] = error_msg
        task_status['running'] = False
        return
    except Exception as e:
        error_msg = f'获取SVN日志失败: {e}'
        print(f"[{datetime.now()}] SVN-log - 错误: {error_msg}")
        task_status['error'] = error_msg
        task_status['running'] = False
        return

# 从SVN服务器获取特定版本的diff
def get_svn_diff(branch_url, revision, username=None, password=None, use_cache=False):
    """
    获取特定版本的代码变化，支持细粒度文件缓存和增量分析
    :param branch_url: SVN分支URL
    :param revision: 版本号
    :param username: SVN用户名
    :param password: SVN密码
    :param use_cache: 是否直接从缓存中获取数据
    :return: (新增行数, 删除行数, 文件详情字典)
    """
    # print(f"[{datetime.now()}] SVN - branch_url: {branch_url}, revision: {revision}, username: {username}, password: {'*' * len(password) if password else 'None'}, use_cache: {use_cache}")
    
    # 生成版本级缓存键
    revision_cache_key = generate_revision_cache_key(revision, branch_url);
    
    # 如果使用缓存，先检查版本级缓存
    if use_cache:
        if revision_cache_key in cache_data['cache']['revision_summary']:
            # 版本级缓存存在，获取缓存的摘要信息
            cached_summary = cache_data['cache']['revision_summary'][revision_cache_key]
            total_lines_added = cached_summary['total_lines_added']
            total_lines_deleted = cached_summary['total_lines_deleted']
            file_list = cached_summary['file_list']
            
            need_refresh = False
            
            # 构建文件详情字典
            file_details = {}
            for file_path in file_list:
                file_cache_key = generate_file_cache_key(revision, file_path)
                if file_cache_key in cache_data['cache']['revision_file']:
                    cached_file = cache_data['cache']['revision_file'][file_cache_key]
                    file_details[file_path] = {
                        'lines_added': cached_file['lines_added'],
                        'lines_deleted': cached_file['lines_deleted'],
                        'cached': True,
                        'author': cached_file['author']
                    }
                else:
                    # 如果文件缓存不存在，标记为需要重新获取
                    need_refresh = True
            if not need_refresh:
                print(f"[{datetime.now()}] SVN-diff - 版本 {revision} 文件差异, -- 缓存数据")
                return (total_lines_added, total_lines_deleted, file_details)
    
    print(f"[{datetime.now()}] SVN-diff - 版本 {revision} 文件差异, -- 重新获取")
    # 解析SVN diff结果，获取每个文件的变化
    cmd = ['svn', 'diff', '-c', str(revision), '--no-auth-cache']
    
    if username:
        cmd.extend(['--username', username])
    if password:
        cmd.extend(['--password', password])
    
    cmd.append(branch_url)
    # print(f"[{datetime.now()}] SVN-diff - 正在执行SVN命令: {' '.join(cmd)}")
    
    try:
        # 使用text=False获取原始字节输出
        result = subprocess.run(cmd, capture_output=True, text=False, timeout=60)
        
        # 手动解码输出
        diff_output = ""
        try:
            diff_output = result.stdout.decode('utf-8')
        except UnicodeDecodeError:
            try:
                diff_output = result.stdout.decode('gbk')
            except UnicodeDecodeError:
                diff_output = result.stdout.decode('latin-1')
        
        if result.returncode != 0:
            return (0, 0, {})
        
        # 解析diff结果
        
        # 初始化统计变量
        total_lines_added = 0
        total_lines_deleted = 0
        file_details = {}
        
        # 按照标准SVN diff格式解析
        # 首先按Index分割每个文件
        file_blocks = diff_output.split('Index: ')
        
        for file_block in file_blocks:
            if not file_block.strip():
                continue
                
            # 提取文件路径
            lines = file_block.split('\n')
            if not lines:
                continue
                
            # 第一行是文件路径
            file_path = lines[0].strip()
            
            # 查找---和+++行
            old_file_line = None
            new_file_line = None
            
            for line in lines:
                if line.startswith('--- '):
                    old_file_line = line
                elif line.startswith('+++ '):
                    new_file_line = line
                    break
            
            # 如果没有找到---和+++行，跳过
            if not old_file_line or not new_file_line:
                continue
                
            # 计算该文件的新增和删除行数
            lines_added = 0
            lines_deleted = 0
            
            # 统计行变化
            for line in lines:
                # 单个+表示增加的行（不包括+++）
                if line.startswith('+') and not line.startswith('+++'):
                    lines_added += 1
                # 单个-表示删除的行（不包括---）
                elif line.startswith('-') and not line.startswith('---'):
                    lines_deleted += 1
            
            # 累加到总统计
            total_lines_added += lines_added
            total_lines_deleted += lines_deleted
            
            # 保存文件详情
            file_details[file_path] = {
                'lines_added': lines_added,
                'lines_deleted': lines_deleted,
                'cached': False,
                'author': ''
            }
            
            print(f"[{datetime.now()}] SVN-diff 解析文件: {file_path}, 新增: {lines_added}, 删除: {lines_deleted}")
        
        return (total_lines_added, total_lines_deleted, file_details)
    except Exception as e:
        print(f"[{datetime.now()}] SVN-diff 获取diff失败 (rev {revision}): {e}")
        import traceback
        traceback.print_exc()
        return (0, 0, {})

# 从文件路径中提取分支信息
def extract_branch(path):
    if '/src/main/' in path:
        branch_part = path.split('/src/main/')[0]
        return branch_part
    return 'trunk'



# 获取指定分支的最新版本号
def get_latest_revision_in_cache(branch_url):
    """
    从svn.cache中获取指定分支的最新版本号
    :param branch_url: SVN分支URL
    :return: 最新版本号，如果没有找到则返回None
    """
    try:
        global cache_data
        
        # 检查缓存中是否有该分支的版本记录
        cache_keys = sorted(cache_data['cache']['revision_summary'].keys(), reverse=True)
        for key in cache_keys:
            cached_summary = cache_data['cache']['revision_summary'][key]
            if branch_url == cached_summary['branch_url']:
                latest_revision = cached_summary['revision']
                print(f"[{datetime.now()}] 从缓存中找到分支 {branch_url} 的最新版本号: {latest_revision}")
                return latest_revision
        else:
            print(f"[{datetime.now()}] 缓存中未找到分支 {branch_url} 的版本记录")
            return None
    except Exception as e:
        print(f"[{datetime.now()}] 获取分支 {branch_url} 最新版本号时出错: {e}")
        return None

# 获取年份对应的日志文件路径
def get_year_log_file(year, root_path=None):
    """
    获取指定年份的日志文件路径
    :param year: 年份
    :param root_path: 根目录路径，默认使用app.root_path
    :return: 日志文件的绝对路径
    """
    if root_path is None:
        root_path = app.root_path
    logs_dir = os.path.join(root_path, 'logs')
    return os.path.join(logs_dir, f'svn_{year}.log')

# 获取所有年份日志文件
def get_all_year_log_files(start_date=None, end_date=None, root_path=None):
    """
    获取所有年份日志文件的列表
    :param start_date: 开始日期
    :param end_date: 结束日期   
    :param root_path: 根目录路径，默认使用app.root_path
    :return: 日志文件路径列表，按年份从早到晚排序
    """
    
    if root_path is None:
        root_path = app.root_path
    logs_dir = os.path.join(root_path, 'logs')
    log_files = []
    
    # 解析开始日期和结束日期，提取年份
    start_year = None
    end_year = None
    
    if start_date:
        start_year = int(start_date.split('-')[0])
    
    if end_date:
        end_year = int(end_date.split('-')[0])
    
    # 查找所有svn_YYYY.log格式的文件
    for filename in os.listdir(logs_dir):
        if filename.startswith('svn_') and filename.endswith('.log'):
            # 提取文件名中的年份
            try:
                year = int(filename[4:-4])  # 从文件名'svn_YYYY.log'中提取YYYY
                
                # 检查年份是否在指定范围内
                if ((start_year is None or year >= start_year) and 
                    (end_year is None or year <= end_year)):
                    log_files.append(os.path.join(logs_dir, filename))
            except ValueError:
                continue  # 跳过文件名格式不正确的文件
    
    # 按年份排序（文件名格式：svn_2023.log）
    log_files.sort()
    return log_files

# 写入SVN日志文件
def write_svn_log(all_log_results):
    global task_status
    # 创建字典存储每个版本的最新日志条目（使用revision作为键）
    logentries_dict = {}
    old_revisions = 0
    new_revisions = 0
    
    # 读取所有年份日志文件中的现有日志
    all_log_files = get_all_year_log_files()
    print(f"[{datetime.now()}] SVN任务 - 找到 {len(all_log_files)} 个年份日志文件")
    
    for log_file in all_log_files:
        try:
            # 解析现有日志文件
            existing_tree = ET.parse(log_file)
            existing_root = existing_tree.getroot()
            
            # 添加现有日志条目
            for logentry in existing_root.findall('logentry'):
                revision = logentry.get('revision')
                logentries_dict[revision] = logentry
            
            print(f"[{datetime.now()}] SVN任务 - 从 {log_file} 加载了 {len([entry for entry in existing_root.findall('logentry')])} 个版本")
        except ET.ParseError as e:
            print(f"[{datetime.now()}] SVN任务 - 解析 {log_file} 时XML解析错误: {e}")
            # 尝试修复XML文件
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 简单的XML修复：移除或替换无效字符
            import re
            # 移除所有控制字符，只保留空格、制表符、换行符
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
            # 替换特殊字符为HTML实体
            content = content.replace('&', '&amp;')
            
            # 重新写入修复后的内容
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"[{datetime.now()}] SVN任务 - {log_file} XML文件已修复，重新尝试解析")
            try:
                # 重新尝试解析
                existing_tree = ET.parse(log_file)
                existing_root = existing_tree.getroot()
                
                # 添加现有日志条目
                for logentry in existing_root.findall('logentry'):
                    revision = logentry.get('revision')
                    logentries_dict[revision] = logentry
                
                print(f"[{datetime.now()}] SVN任务 - 从修复后的 {log_file} 加载了 {len([entry for entry in existing_root.findall('logentry')])} 个版本")
            except ET.ParseError as e2:
                print(f"[{datetime.now()}] SVN任务 - {log_file} 修复后仍无法解析: {e2}")
                continue
    
    old_revisions = len(logentries_dict)

    # 处理所有获取的日志结果（主分支+externals）
    for log_result in all_log_results:
        try:
            # 解析新获取的日志数据
            new_tree = ET.ElementTree(ET.fromstring(log_result.stdout))
            new_root = new_tree.getroot()
            
            # 添加新日志条目（相同版本会覆盖现有条目，保留最新）
            for logentry in new_root.findall('logentry'):
                revision = logentry.get('revision')
                logentries_dict[revision] = logentry
        except ET.ParseError as e:
            print(f"[{datetime.now()}] SVN任务 - 解析新日志结果时XML解析错误: {e}")
            # 尝试修复XML内容
            content = log_result.stdout
            import re
            # 移除所有控制字符，只保留空格、制表符、换行符
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
            # 替换特殊字符为HTML实体
            content = content.replace('&', '&amp;')
            
            try:
                # 重新尝试解析修复后的XML
                new_tree = ET.ElementTree(ET.fromstring(content))
                new_root = new_tree.getroot()
                
                # 添加新日志条目
                for logentry in new_root.findall('logentry'):
                    revision = logentry.get('revision')
                    logentries_dict[revision] = logentry
                
                print(f"[{datetime.now()}] SVN任务 - 新日志XML已修复并成功解析")
            except ET.ParseError as e2:
                print(f"[{datetime.now()}] SVN任务 - 修复后仍无法解析XML: {e2}")
                continue
        
    new_revisions = len(logentries_dict) - old_revisions
    
    print(f"[{datetime.now()}] SVN任务 - 合并完成，共 {len(logentries_dict)} 个唯一版本，新增 {new_revisions} 个版本")
    
    # 更新任务状态
    task_status['execution_details'].append({
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'message': f'合并完成，共 {len(logentries_dict)} 个唯一版本，新增 {new_revisions} 个版本',
        'level': 'info'
    })
    
    # 按年份分组日志条目
    logentries_by_year = {}
    for rev in logentries_dict:
        logentry = logentries_dict[rev]
        date_str = logentry.find('date').text
        date = datetime.fromisoformat(date_str[:-1])
        year = str(date.year)
        
        if year not in logentries_by_year:
            logentries_by_year[year] = []
        logentries_by_year[year].append(logentry)
    
    # 写入每年的日志到对应的文件
    for year in logentries_by_year:
        # 按版本号降序排序（最新版本在前）
        year_logentries = logentries_by_year[year]
        year_logentries.sort(key=lambda x: int(x.get('revision')), reverse=True)
        
        # 构建XML根元素
        year_root = ET.Element('log')
        for logentry in year_logentries:
            year_root.append(logentry)
        
        # 获取年份日志文件路径
        year_log_file = get_year_log_file(year)
        
        # 写入日志到文件
        year_tree = ET.ElementTree(year_root)
        year_tree.write(year_log_file, encoding='utf-8', xml_declaration=True)
        print(f"[{datetime.now()}] SVN任务 - 已保存 {year} 年日志到 {year_log_file}，共 {len(year_logentries)} 条记录")
        
        # 更新任务状态
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'已保存 {year} 年日志到 {year_log_file}，共 {len(year_logentries)} 条记录',
            'level': 'info'
        })
        
# 解析svn.log文件
def parse_svn_log(startDate=None, endDate=None):
    """
    解析一个或多个svn.log文件
    :param log_files: 单个文件路径字符串或文件路径列表
    :param startDate: 开始日期
    :param endDate: 结束日期
    :return: 提交记录列表
    """

    # 获取所有年份日志文件
    log_files = get_all_year_log_files(startDate, endDate)
    
    # 如果是单个文件路径，转换为列表
    if isinstance(log_files, str):
        log_files = [log_files]
    
    print(f"[{datetime.now()}] SVN任务 - 要处理的日志文件: {(log_files)}")
    all_commits = []
    
    for log_file in log_files:
        try:
            tree = ET.parse(log_file)
            root = tree.getroot()
        except ET.ParseError as e:
            print(f"[{datetime.now()}] SVN任务 - 解析 {log_file} 时XML解析错误: {e}")
            # 尝试修复XML文件
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 简单的XML修复：移除或替换无效字符
            import re
            # 移除所有控制字符，只保留空格、制表符、换行符
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
            # 替换特殊字符为HTML实体
            content = content.replace('&', '&amp;')
            
            # 重新写入修复后的内容
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"[{datetime.now()}] SVN任务 - {log_file} XML文件已修复，重新尝试解析")
            try:
                # 重新尝试解析
                tree = ET.parse(log_file)
                root = tree.getroot()
            except ET.ParseError as e2:
                print(f"[{datetime.now()}] SVN任务 - {log_file} 修复后仍无法解析: {e2}")
                continue
        
        # 过滤日期范围
        parsed_startDate = None
        parsed_endDate = None
        if startDate and endDate:
            parsed_startDate = datetime.fromisoformat(startDate[:])
            parsed_endDate = datetime.fromisoformat(endDate[:])
            print(f"[{datetime.now()}] SVN任务 - 要处理的日期范围: {startDate} 到 {endDate}")
        
        # 解析当前文件的提交记录
        commits = []
        for logentry in root.findall('logentry'):
            revision = logentry.get('revision')
            author = logentry.find('author').text if logentry.find('author') is not None else 'unknown'
            date_str = logentry.find('date').text
            date = datetime.fromisoformat(datetime.fromisoformat(date_str[:-1]).strftime('%Y-%m-%d')[:])
            # print(f"[{datetime.now()}] SVN任务 - 处理版本 {revision}，日期 {date}")
            
            # 过滤日期范围
            if parsed_startDate and parsed_endDate:
                if date < parsed_startDate or date > parsed_endDate:
                    # print(f"[{datetime.now()}] SVN任务 - 版本 {revision} - {date < parsed_startDate or date > parsed_endDate}")
                    continue
            
            # 计算修改的文件数和提取分支信息
            paths = logentry.find('paths')
            files_changed = len(paths.findall('path'))
            
            # 提取所有相关分支和修改的文件信息
            branches = set()
            changed_files = []
            for path in paths.findall('path'):
                if path.text:
                    file_path = path.text
                    action = path.get('action') or 'M'  # 默认修改
                    
                    # 提取分支信息
                    branch = extract_branch(file_path)
                    branches.add(branch)
                    
                    # 记录详细的文件修改信息
                    changed_files.append({
                        'path': file_path,
                        'action': action,
                        'branch': branch
                    })

            if branches:
                tmp_branch_url = list(branches)[0]
                if tmp_branch_url.startswith('/trunk'):
                    branch_url = "{}{}".format(config.get("svn_base_url", ""), branch)
                else:
                    branch_url = tmp_branch_url
            
            # 代码行数统计（初始化为0，后续通过svn diff获取）
            lines_added = 0
            lines_deleted = 0
            
            commits.append({
                'revision': revision,
                'author': author,
                'date': date.isoformat(),
                'date_str': date_str,
                'branch_url': branch_url,
                'files_changed': files_changed,
                'changed_files': changed_files,
                'branches': list(branches),
                'lines_added': lines_added,
                'lines_deleted': lines_deleted
            })
        
        all_commits.extend(commits)
    
    # 按revision排序，确保正确顺序
    all_commits.sort(key=lambda x: int(x['revision']))

    return all_commits

# SVN日志获取任务
def svn_log_task(branches, revision_range, start_date=None, end_date=None, withExternals=False, full_analysis=False):
    global task_status

    print(f"[{datetime.now()}] SVN任务 - 开始执行SVN代码统计任务")
    print(f"[{datetime.now()}] SVN任务 - 参数: 分支数量: {len(branches)}, 版本范围: {revision_range}, 开始日期: {start_date}, 结束日期: {end_date}")
    
    try:
        # 重置执行明细
        task_status['execution_details'] = []
        
        task_status['running'] = True
        task_status['progress'] = 5
        task_status['message'] = '正在连接SVN服务器...'
        
        # 添加执行明细
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'开始执行SVN代码统计任务，共 {len(branches)} 个分支',
            'level': 'info'
        })

        # 收集所有分支的日志结果
        all_branch_results = []

        # 遍历每个分支
        for i, branch_config in enumerate(branches, 1):
            branch_url = branch_config.get('branch_url')
            username = branch_config.get('username')
            password = branch_config.get('password')

            task_status['progress'] = 5 + (i - 1) * 15
            task_status['message'] = f'正在分析分支 {i}/{len(branches)}...'
            
            task_status['execution_details'].append({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': f'开始分析分支 {i}/{len(branches)}: {branch_url}',
                'level': 'info'
            })

            task_status['execution_details'].append({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': f'使用用户名: {username}',
                'level': 'info'
            })
        
            # 密码脱敏
            task_status['execution_details'].append({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': '使用密码: ******',
                'level': 'info'
            })
            
            try:
                # 如果勾选了全量分析，不限制版本范围
                if full_analysis:
                    revision_range = ''
                    task_status['execution_details'].append({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': '全量分析模式：不限制版本范围',
                        'level': 'info'
                    })
                else:
                    # 如果没有勾选全量分析，从缓存获取最新版本号
                    latest_revision = get_latest_revision_in_cache(branch_url)
                    if latest_revision:
                        # 如果找到最新版本号，使用从最新版本开始的版本范围
                        if revision_range:
                            start_rev, end_rev = revision_range.split(":")
                            if start_rev and end_rev:
                                revision_range = f"{start_rev}:{end_rev}"
                            elif start_rev:
                                revision_range = f"{latest_revision}:{start_rev}"
                        else:
                            revision_range = f"{latest_revision}:HEAD"
                    
                    task_status['execution_details'].append({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': f'增量分析模式：缓存获取最新版本号: {latest_revision}，使用版本范围: {revision_range}',
                        'level': 'info'
                    })   

                task_status['execution_details'].append({
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'message': f'开始获取分支 {branch_url} 日志',
                    'level': 'info'
                })   

                # 获取SVN日志（主分支）
                main_result = get_svn_log(branch_url, username, password, revision_range)
                
                # 检查结果是否为None（表示获取失败）
                if main_result is None:
                    error_msg = f'获取分支 {branch_url} 日志失败，请检查网络连接或SVN配置'
                    print(f"[{datetime.now()}] SVN任务 - 错误: {error_msg}")
                    task_status['execution_details'].append({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': error_msg,
                        'level': 'warning'
                    })
                    continue
                # 检查命令执行结果
                elif main_result.returncode != 0:
                    error_msg = f'分支 {branch_url} SVN命令执行失败: {main_result.stderr}'
                    print(f"[{datetime.now()}] SVN任务 - 错误: {error_msg}")
                    task_status['execution_details'].append({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': error_msg,
                        'level': 'warning'
                    })
                    continue

                print(f"[{datetime.now()}] SVN任务 - 分支 {branch_url} SVN命令执行成功，返回码: {main_result.returncode}")
                all_branch_results.append(main_result)

                success_msg = f'分支 {branch_url} 日志获取成功， 版本范围: {revision_range}，分支日志数: {len(main_result.stdout)}'
                print(f"[{datetime.now()}] SVN任务 - {success_msg}")
                task_status['execution_details'].append({
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'message': success_msg,
                    'level': 'success'
                })

                # 获取并处理SVN externals
                if withExternals:
                    task_status['execution_details'].append({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': '开始处理SVN externals',
                        'level': 'info'
                    })

                    externals = get_svn_externals(branch_url, username, password)
                
                    task_status['execution_details'].append({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': f'开始获取 {len(externals)} 个external分支的日志',
                        'level': 'info'
                    })
                    
                    # 获取每个external的日志
                    for i, external in enumerate(externals, 1):
                        external_msg = f'正在获取external分支日志 ({i}/{len(externals)}): {external["url"]}'
                        print(f"[{datetime.now()}] SVN任务 - {external_msg}")
                        task_status['execution_details'].append({
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'message': external_msg,
                            'level': 'info'
                        })
                        
                        external_result = get_svn_log(external['url'], username, password, revision_range)
                        
                        if external_result and external_result.returncode == 0:
                            all_branch_results.append(external_result)
                            success_msg = f'external分支日志获取成功: {external["url"]}'
                            print(f"[{datetime.now()}] SVN任务 - {success_msg}")
                            task_status['execution_details'].append({
                                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'message': success_msg,
                                'level': 'success'
                            })
                        else:
                            error_msg = f'external分支日志获取失败: {external["url"]}'
                            print(f"[{datetime.now()}] SVN任务 - {error_msg}")
                            task_status['execution_details'].append({
                                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'message': error_msg,
                                'level': 'warning'
                            })
                else:
                    task_status['execution_details'].append({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': '忽略获取external配置',
                        'level': 'info'
                    })
        
            
            except Exception as e:
                error_msg = f'分支 {branch_url} 处理失败: {e}'
                print(f"[{datetime.now()}] SVN任务 - 错误: {error_msg}")
                task_status['execution_details'].append({
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'message': error_msg,
                    'level': 'error'
                })
                continue

        if not all_branch_results:
            task_status['error'] = '所有分支日志获取失败，请检查网络连接或SVN配置'
            task_status['running'] = False
            return
        
        task_status['progress'] = 40
        task_status['message'] = '正在获取SVN日志...'
        
        print(f"[{datetime.now()}] SVN任务 - 正在保存日志到文件")
        
        # 增量写入日志文件：合并现有日志和所有新获取的日志（主分支+externals）  
        write_svn_log(all_branch_results)
        
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'日志获取完成，已按年份保存到 logs 目录下',
            'level': 'info'
        })

        task_status['progress'] = 50
        task_status['message'] = '正在解析日志并获取代码行数...'
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': '开始解析日志文件',
            'level': 'info'
        })
        
        print(f"[{datetime.now()}] SVN任务 - 开始解析日志文件")

        # 解析日志获取版本列表
        commits = parse_svn_log(start_date, end_date)
        total_commits = len(commits)
        print(f"[{datetime.now()}] SVN任务 - 日志解析完成，共找到 {total_commits} 条提交记录")
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'日志解析完成，{start_date or "/"} - {end_date or "/"} 共找到 {total_commits} 条提交记录',
            'level': 'info'
        })

        if total_commits == 0:
            task_status['error'] = f'在指定日期范围内没有找到提交记录\n开始日期: {start_date or "无"}\n结束日期: {end_date or "无"}'
            task_status['running'] = False
            return
        
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'开始获取代码行数，共 {total_commits} 个版本需要分析',
            'level': 'info'
        })
        
        # 获取每个版本的代码行数变化
        print(f"[{datetime.now()}] SVN任务 - 开始获取代码行数变化，共 {total_commits} 个版本需要分析")
        for i, commit in enumerate(commits):
            revision = commit['revision']
            branch_url = commit['branch_url']
            author = commit['author']
            
            print(f"[{datetime.now()}] SVN任务 - 分析版本 {revision} ({i + 1}/{total_commits})")
            task_status['execution_details'].append({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': f'分析版本 {revision} ({i + 1}/{total_commits})',
                'level': 'debug'
            })
            
            # 获取代码行数变化，包含文件详情
            # 对于多分支分析，我们需要根据提交记录中的分支信息来获取对应的分支URL
            # 这里简化处理，使用第一个分支的配置
            if branches and len(branches) > 0:
                username = branches[0].get('username')
                password = branches[0].get('password')
            else:
                username = config.get('svn_username', '')
                password = config.get('svn_password', '')

            # 获取代码行数变化，包含文件详情
            print(f"[{datetime.now()}] SVN任务 - 调用 get_svn_diff 版本 {revision} 获取代码行数变化")
            lines_added, lines_deleted, file_details = get_svn_diff(branch_url, revision, username, password, True)
            print(f"[{datetime.now()}] SVN任务 - 调用 get_svn_diff 版本 {revision} 分析完成，新增 {lines_added} 行，删除 {lines_deleted} 行，涉及 {len(file_details)} 个文件")
            
            if file_details:
                # 生成版本级缓存键
                revision_cache_key = generate_revision_cache_key(revision, branch_url);

                for file_path, details in file_details.items():
                    if details['cached']:
                        continue
                    
                    details['author'] = author
                    file_cache_key = generate_file_cache_key(revision, file_path)
                    cache_data['cache']['revision_file'][file_cache_key] = {
                        'revision': revision,
                        'file_path': file_path,
                        'lines_added': details['lines_added'],
                        'lines_deleted': details['lines_deleted'],
                        'author': author,
                        'timestamp': int(time.time())
                    }

                # 保存版本级缓存摘要
                cache_data['cache']['revision_summary'][revision_cache_key] = {
                    'revision': revision,
                    'branch_url': branch_url,
                    'total_lines_added': lines_added,
                    'total_lines_deleted': lines_deleted,
                    'file_count': len(file_details),
                    'file_list': list(file_details.keys()),
                    'timestamp': int(time.time())
                }
            
                # 保存缓存文件
                # save_cache(cache_data)

            # 保存到提交记录
            commit['lines_added'] = lines_added
            commit['lines_deleted'] = lines_deleted
            commit['file_details'] = file_details
            
            # 更新进度
            progress = 50 + (i + 1) * 50 // total_commits
            task_status['progress'] = progress
            task_status['message'] = f'正在获取代码行数... ({i + 1}/{total_commits})'
            print(f"[{datetime.now()}] SVN任务 - 进度更新: {progress}%")
        
        task_status['progress'] = 90
        task_status['message'] = '正在生成统计数据...'
        
        # 生成统计
        print(f"[{datetime.now()}] SVN任务 - 生成新的统计数据")
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': '生成新的统计数据',
            'level': 'info'
        })
        # 生成新的统计，不使用现有结果
        gen_analysis_results(commits, start_date, end_date, revision_range)

        # 更新缓存文件，只保存缓存数据
        task_status['progress'] = 95
        task_status['message'] = '正在更新缓存文件...'
        print(f"[{datetime.now()}] SVN任务 - 正在更新缓存文件")
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': '正在更新缓存文件',
            'level': 'info'
        })
        
        try:
            # 只保存缓存数据，不保存分析结果
            save_cache(cache_data)
            print(f"[{datetime.now()}] SVN任务 - 缓存文件更新完成")
            task_status['execution_details'].append({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': '缓存文件更新完成',
                'level': 'info'
            })
        except Exception as e:
            print(f"[{datetime.now()}] SVN任务 - 更新缓存文件失败: {e}")
            task_status['execution_details'].append({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': f'更新缓存文件失败: {e}',
                'level': 'error'
            })
        
        task_status['progress'] = 100
        task_status['message'] = f'分析完成! 共{len(commits)}条提交记录'
        task_status['completed'] = True
        task_status['running'] = False
        
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'任务执行完成，共处理 {len(commits)} 条提交记录',
            'level': 'success'
        })
        
        print(f"[{datetime.now()}] SVN任务 - 任务执行完成，状态: 成功")
    except Exception as e:
        error_msg = str(e)
        print(f"[{datetime.now()}] SVN任务 - 任务执行失败: {error_msg}")
        task_status['error'] = error_msg
        task_status['running'] = False
        task_status['execution_details'].append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'任务执行失败: {error_msg}',
            'level': 'error'
        })
        import traceback
        traceback.print_exc()

def get_log(start_date=None, end_date=None):
    """
    获取SVN任务的日志，包含提交记录的详细信息。
    
    参数:
    branch_url (str): SVN分支URL
    start_date (str, 可选): 开始日期，格式为 'YYYY-MM-DD'
    end_date (str, 可选): 结束日期，格式为 'YYYY-MM-DD'
    withExternals (bool, 可选): 是否包含SVN externals
    
    返回:
    list: 包含提交记录详细信息的列表
    """
    global task_status
    
    print(f"[{datetime.now()}] SVN任务 - 开始执行SVN代码统计任务")
    print(f"[{datetime.now()}] SVN任务 - 参数: 开始日期: {start_date}, 结束日期: {end_date}")
    
    try:
        print(f"[{datetime.now()}] SVN任务 - 开始解析日志文件")

        # 解析日志获取版本列表
        commits = parse_svn_log(start_date, end_date)
        print(f"[{datetime.now()}] SVN任务 - 日志解析完成，共找到 {len(commits)} 条提交记录")
        
        total_commits = len(commits)
        if total_commits == 0:
            gen_analysis_results(commits, start_date, end_date, "")
            return
        
        # 获取每个版本的代码行数变化
        print(f"[{datetime.now()}] SVN任务 - 开始获取代码行数变化，共 {total_commits} 个版本需要分析")
        for i, commit in enumerate(commits):
            branch_url = commit['branch_url']
            revision = commit['revision']
            author = commit['author']
            username = config.get('svn_username', "")
            password = config.get('svn_password', "")
            
            print(f"[{datetime.now()}] SVN任务 - 分析版本 {revision} ({i + 1}/{total_commits})")
            
            # 获取代码行数变化，包含文件详情
            print(f"[{datetime.now()}] SVN任务 - 调用 get_svn_diff 版本 {revision} 获取代码行数变化")
            lines_added, lines_deleted, file_details = get_svn_diff(branch_url, revision, username, password, True)
            print(f"[{datetime.now()}] SVN任务 - 调用 get_svn_diff 版本 {revision} 分析完成，新增 {lines_added} 行，删除 {lines_deleted} 行，涉及 {len(file_details)} 个文件")
            
            if file_details:
                # 生成版本级缓存键
                revision_cache_key = generate_revision_cache_key(revision, branch_url);

                for file_path, details in file_details.items():
                    if details['cached']:
                        continue
                    
                    details['author'] = author
                    file_cache_key = generate_file_cache_key(revision, file_path)
                    cache_data['cache']['revision_file'][file_cache_key] = {
                        'revision': revision,
                        'file_path': file_path,
                        'lines_added': details['lines_added'],
                        'lines_deleted': details['lines_deleted'],
                        'author': author,
                        'timestamp': int(time.time())
                    }

                # 保存版本级缓存摘要
                cache_data['cache']['revision_summary'][revision_cache_key] = {
                    'revision': revision,
                    'branch_url': branch_url,
                    'total_lines_added': lines_added,
                    'total_lines_deleted': lines_deleted,
                    'file_count': len(file_details),
                    'file_list': list(file_details.keys()),
                    'timestamp': int(time.time())
                }
            
                # 保存缓存文件
                # save_cache(cache_data)

            # 保存到提交记录
            commit['lines_added'] = lines_added
            commit['lines_deleted'] = lines_deleted
            commit['file_details'] = file_details
            
            # 更新进度
            progress = 50 + (i + 1) * 50 // total_commits
            print(f"[{datetime.now()}] SVN任务 - 进度更新: {progress}%")
        
        print(f"[{datetime.now()}] SVN任务 - 开始生成统计数据")
        
        # 生成新的统计数据
        gen_analysis_results(commits, start_date, end_date, "")

        # 更新缓存文件，只保存缓存数据
        print(f"[{datetime.now()}] SVN任务 - 正在更新缓存文件")
        try:
            # 只保存缓存数据，不保存分析结果
            save_cache(cache_data)
            print(f"[{datetime.now()}] SVN任务 - 缓存文件更新完成")
        except Exception as e:
            print(f"[{datetime.now()}] SVN任务 - 更新缓存文件失败: {e}")
        
        print(f"[{datetime.now()}] SVN任务 - 任务执行完成，状态: 成功")
    except Exception as e:
        error_msg = str(e)
        print(f"[{datetime.now()}] SVN任务 - 任务执行失败: {error_msg}")
        import traceback
        traceback.print_exc()

# 生成分析结果
def gen_analysis_results(commits, startDate=None, endDate=None, revision_range=None):
    global analysis_results
    # 生成统计
    monthly_stats = get_monthly_stats(commits)
    author_stats = get_author_stats(commits)
    branch_stats = get_branch_stats(commits)
    daily_stats = get_daily_stats(commits)
    chart_data = prepare_chart_data(monthly_stats, author_stats, branch_stats, daily_stats)
    print(f"[{datetime.now()}] SVN任务 - 统计数据生成完成")
    
    # 保存结果
    print(f"[{datetime.now()}] SVN任务 - 正在保存分析结果")

    total_files = sum(c['files_changed'] for c in commits)
    total_lines_added = sum(c['lines_added'] for c in commits)
    total_lines_deleted = sum(c['lines_deleted'] for c in commits)
    
    analysis_results = {
        'commits': commits,
        'monthly_stats': monthly_stats,
        'author_stats': author_stats,
        'branch_stats': branch_stats,
        'daily_stats': daily_stats,
        'chart_data': chart_data,
        'total_commits': len(commits),
        'total_files': total_files,
        'total_lines_added': total_lines_added,
        'total_lines_deleted': total_lines_deleted,
        'filter': {
            'start_date': startDate,
            'end_date': endDate,
            'revision_range': revision_range
        }
    }
    
    print(f"[{datetime.now()}] SVN任务 - 分析结果保存完成，共 {len(commits)} 条提交记录, 新增 {total_lines_added} 行代码, 删除 {total_lines_deleted} 行代码")

# 统计函数
def get_monthly_stats(commits):
    monthly_stats = {}
    for commit in commits:
        # 将ISO字符串转换为datetime对象
        commit_date = datetime.fromisoformat(commit['date'])
        month_key = commit_date.strftime('%Y-%m')
        author = commit['author']
        
        for branch in commit['branches']:
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {}
            
            if branch not in monthly_stats[month_key]:
                monthly_stats[month_key][branch] = {}
            
            if author not in monthly_stats[month_key][branch]:
                monthly_stats[month_key][branch][author] = {
                    'files_changed': 0,
                    'lines_added': 0,
                    'lines_deleted': 0
                }
            
            # 更新统计数据
            monthly_stats[month_key][branch][author]['files_changed'] += commit['files_changed']
            monthly_stats[month_key][branch][author]['lines_added'] += commit['lines_added']
            monthly_stats[month_key][branch][author]['lines_deleted'] += commit['lines_deleted']
    
    return monthly_stats

def get_author_stats(commits):
    author_stats = {}
    for commit in commits:
        author = commit['author']
        
        if author not in author_stats:
            author_stats[author] = {
                'commits': 0,
                'files_changed': 0,
                'lines_added': 0,
                'lines_deleted': 0,
                'branches': set()
            }
        
        # 更新统计数据
        author_stats[author]['commits'] += 1
        author_stats[author]['files_changed'] += commit['files_changed']
        author_stats[author]['lines_added'] += commit['lines_added']
        author_stats[author]['lines_deleted'] += commit['lines_deleted']
        
        for branch in commit['branches']:
            author_stats[author]['branches'].add(branch)
    
    for author in author_stats:
        author_stats[author]['branches'] = list(author_stats[author]['branches'])
    
    return author_stats

def get_branch_stats(commits):
    branch_stats = {}
    for commit in commits:
        for branch in commit['branches']:
            if branch not in branch_stats:
                branch_stats[branch] = {
                    'commits': 0,
                    'files_changed': 0,
                    'lines_added': 0,
                    'lines_deleted': 0,
                    'authors': set()
                }
            
            # 更新统计数据
            branch_stats[branch]['commits'] += 1
            branch_stats[branch]['files_changed'] += commit['files_changed']
            branch_stats[branch]['lines_added'] += commit['lines_added']
            branch_stats[branch]['lines_deleted'] += commit['lines_deleted']
            branch_stats[branch]['authors'].add(commit['author'])
    
    for branch in branch_stats:
        branch_stats[branch]['authors'] = list(branch_stats[branch]['authors'])
    
    return branch_stats

def get_daily_stats(commits):
    daily_stats = {}
    for commit in commits:
        # 将ISO字符串转换为datetime对象
        commit_date = datetime.fromisoformat(commit['date'])
        day_key = commit_date.strftime('%Y-%m-%d')
        author = commit['author']
        
        for branch in commit['branches']:
            if day_key not in daily_stats:
                daily_stats[day_key] = {}
            
            if branch not in daily_stats[day_key]:
                daily_stats[day_key][branch] = {}
            
            if author not in daily_stats[day_key][branch]:
                daily_stats[day_key][branch][author] = {
                    'files_changed': 0,
                    'lines_added': 0,
                    'lines_deleted': 0
                }
            
            # 更新统计数据
            daily_stats[day_key][branch][author]['files_changed'] += commit['files_changed']
            daily_stats[day_key][branch][author]['lines_added'] += commit['lines_added']
            daily_stats[day_key][branch][author]['lines_deleted'] += commit['lines_deleted']
    
    return daily_stats

# 准备图表数据
def prepare_chart_data(monthly_stats, author_stats, branch_stats, daily_stats):
    authors = list(author_stats.keys())
    branches = list(branch_stats.keys())
    
    months = sorted(monthly_stats.keys())
    days = sorted(daily_stats.keys())
    
    # 准备月度文件数数据
    monthly_data_files = []
    for author in authors:
        author_data = {'label': author, 'data': []}
        for month in months:
            total_files = 0
            for branch in branches:
                if branch in monthly_stats[month] and author in monthly_stats[month][branch]:
                    total_files += monthly_stats[month][branch][author]['files_changed']
            author_data['data'].append(total_files)
        monthly_data_files.append(author_data)
    
    # 准备月度代码行数数据
    monthly_data_lines = []
    for author in authors:
        author_data = {'label': author, 'data': []}
        for month in months:
            total_lines = 0
            for branch in branches:
                if branch in monthly_stats[month] and author in monthly_stats[month][branch]:
                    stats = monthly_stats[month][branch][author]
                    total_lines += stats['lines_added']
            author_data['data'].append(total_lines)
        monthly_data_lines.append(author_data)
    
    # 准备每日文件数数据
    daily_data_files = []
    for author in authors:
        author_data = {'label': author, 'data': []}
        for day in days:
            total_files = 0
            for branch in branches:
                if branch in daily_stats[day] and author in daily_stats[day][branch]:
                    total_files += daily_stats[day][branch][author]['files_changed']
            author_data['data'].append(total_files)
        daily_data_files.append(author_data)
    
    # 准备每日代码行数数据
    daily_data_lines = []
    for author in authors:
        author_data = {'label': author, 'data': []}
        for day in days:
            total_lines = 0
            for branch in branches:
                if branch in daily_stats[day] and author in daily_stats[day][branch]:
                    stats = daily_stats[day][branch][author]
                    total_lines += stats['lines_added']
            author_data['data'].append(total_lines)
        daily_data_lines.append(author_data)
    
    return {
        'months': months,
        'days': days,
        'authors': authors,
        'branches': branches,
        'monthlyDataFiles': monthly_data_files,
        'monthlyDataLines': monthly_data_lines,
        'dailyDataFiles': daily_data_files,
        'dailyDataLines': daily_data_lines
    }


# 添加静态文件路由
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start-analysis', methods=['POST'])
def start_analysis():
    global task_status
    
    print(f"[{datetime.now()}] API POST /api/start-analysis - params: {request.json}")
    
    if task_status['running']:
        print(f"[{datetime.now()}] API POST /api/start-analysis - 任务正在运行中，拒绝新请求")
        return jsonify({'success': False, 'message': '任务正在运行中...'})
    
    data = request.json
    branches = data.get('branches', [])
    branch_url = (data.get('branch_url') or '').strip()
    username = (data.get('username') or '').strip() or None
    password = (data.get('password') or '').strip() or None
    revision_range = (data.get('revision_range') or '').strip() or None
    start_date = (data.get('start_date') or '').strip() or None
    end_date = (data.get('end_date') or '').strip() or None
    full_analysis = data.get('full_analysis', False)
    

    # 日期处理逻辑：保证最小日期范围，如果开始日期和结束日期都存在，检查日期范围是否小于180天
    if not end_date:
        # 结束日期不存在，取今天作为结束日期
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        # 开始日期不存在，取配置中的天数前作为开始日期
        start_date = (datetime.now() - timedelta(days=config.get('log_range_days', 180))).strftime('%Y-%m-%d')
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            date_diff = (end_dt - start_dt).days
            
            if date_diff < config.get('log_range_days', 180):
                # 日期范围小于180天，调整开始日期为结束日期前180天
                new_start_dt = end_dt - timedelta(days=config.get('log_range_days', 180))
                start_date = new_start_dt.strftime('%Y-%m-%d')
                print(f"[{datetime.now()}] API POST /api/start-analysis - 日期范围{date_diff}天小于配置的{config.get('log_range_days', 180)}天，调整开始日期为: {start_date}")
        except ValueError as e:
            print(f"[{datetime.now()}] API POST /api/start-analysis - 日期格式错误: {e}")
    
    print(f"[{datetime.now()}] API POST /api/start-analysis - 处理后日期范围，开始日期: {start_date}, 结束日期: {end_date}")

    # 检查是否使用多分支配置
    if branches:
        print(f"[{datetime.now()}] API POST /api/start-analysis - 使用多分支配置，共 {len(branches)} 个分支")
        
        if not branches:
            print(f"[{datetime.now()}] API POST /api/start-analysis - 缺少分支配置，拒绝请求")
            return jsonify({'success': False, 'message': '请选择至少一个分支配置'})
        
    else:
        print(f"[{datetime.now()}] API POST /api/start-analysis - 分支URL: {branch_url}, 版本范围: {revision_range}, 开始日期: {start_date}, 结束日期: {end_date}")
        
        if not branch_url:
            print(f"[{datetime.now()}] API POST /api/start-analysis - 缺少必填参数 branch_url，拒绝请求")
            return jsonify({'success': False, 'message': '请输入SVN分支URL'})

    # 重置状态
    task_status = {
        'running': True,
        'progress': 0,
        'message': '准备开始...',
        'completed': False,
        'error': None,
        'execution_details': []
    }
    
    print(f"[{datetime.now()}] SVN任务 - 执行明细已重置，状态已更新")
    # 在后台线程中执行任务
    print(f"[{datetime.now()}] API POST /api/start-analysis - 启动后台线程执行任务: 开始分析svn日志")
    
    if not branches:
        branches = []
        branches.append({
            'branch_url': branch_url,
            'username': username,
            'password': password
        })
    
    thread = threading.Thread(target=svn_log_task, args=(branches, revision_range, start_date, end_date, False, full_analysis))
    thread.start()
    
    print(f"[{datetime.now()}] API POST /api/start-analysis - 任务已启动，返回成功响应")
    return jsonify({'success': True, 'message': '任务已启动'})

@app.route('/api/status')
def get_status():
    global task_status, analysis_results
    
    response = {
        'running': task_status['running'],
        'progress': task_status['progress'],
        'message': task_status['message'],
        'completed': task_status['completed'],
        'error': task_status['error'],
        'execution_details': task_status['execution_details']
    }
    
    return jsonify(response)

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    print(f"[{datetime.now()}] API POST /api/cache/clear - 请求清除缓存")
    
    global cache_data
    
    try:
        # 清空全局缓存数据
        cache_data = {
            'version': '1.1',
            'cache': {
                'revision_file': {},
                'revision_summary': {}
            }
        }
        
        # 保存到文件
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"[{datetime.now()}] CACHE - 缓存已清空并保存到文件: {CACHE_FILE}")
        
        return jsonify({'success': True, 'message': '缓存已清除成功'})
    except Exception as e:
        print(f"[{datetime.now()}] CACHE - 清除缓存失败: {e}")
        return jsonify({'success': False, 'message': f'清除缓存失败: {str(e)}'})

@app.route('/api/results', methods=['POST'])
def get_results():
    global analysis_results

    data = request.json
    startDate = (data.get('startDate') or '').strip() or None
    endDate = (data.get('endDate') or '').strip() or None

    get_log(startDate, endDate)

    return jsonify(analysis_results)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
