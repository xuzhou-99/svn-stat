import xml.etree.ElementTree as ET
import os
from datetime import datetime
import json

# 从文件路径中提取分支信息
def extract_branch(path):
    # 寻找branch关键字后的分支名称
    if '/branch/' in path:
        branch_part = path.split('/branch/')[1]
        # 提取第一个/之前的内容作为分支名称
        branch_name = branch_part.split('/')[0]
        return branch_name
    return 'trunk'  # 默认主干

# 解析svn.log文件
def parse_svn_log(log_file):
    tree = ET.parse(log_file)
    root = tree.getroot()
    
    commits = []
    for logentry in root.findall('logentry'):
        revision = logentry.get('revision')
        author = logentry.find('author').text if logentry.find('author') is not None else 'unknown'
        date_str = logentry.find('date').text
        date = datetime.fromisoformat(date_str[:-1])  # 移除Z后缀
        
        # 计算修改的文件数和提取分支信息
        paths = logentry.find('paths')
        files_changed = len(paths.findall('path'))
        
        # 提取所有相关分支和修改的文件信息
        branches = set()
        changed_files = []
        for path in paths.findall('path'):
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
        
        # 代码行数统计（初始化为0，后续通过svn diff获取）
        lines_added = 0
        lines_deleted = 0
        
        commits.append({
            'revision': revision,
            'author': author,
            'date': date,
            'date_str': date_str,
            'files_changed': files_changed,
            'changed_files': changed_files,
            'branches': list(branches),
            'lines_added': lines_added,
            'lines_deleted': lines_deleted
        })
    
    return commits

# 统计每个月的数据（包含分支和代码行数）
def get_monthly_stats(commits):
    monthly_stats = {}
    for commit in commits:
        month_key = commit['date'].strftime('%Y-%m')
        author = commit['author']
        
        # 遍历所有相关分支
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
            
            monthly_stats[month_key][branch][author]['files_changed'] += commit['files_changed']
            monthly_stats[month_key][branch][author]['lines_added'] += commit['lines_added']
            monthly_stats[month_key][branch][author]['lines_deleted'] += commit['lines_deleted']
    
    return monthly_stats

# 统计每个作者的总数据（包含分支和代码行数）
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
        
        author_stats[author]['commits'] += 1
        author_stats[author]['files_changed'] += commit['files_changed']
        author_stats[author]['lines_added'] += commit['lines_added']
        author_stats[author]['lines_deleted'] += commit['lines_deleted']
        
        # 添加相关分支
        for branch in commit['branches']:
            author_stats[author]['branches'].add(branch)
    
    # 将set转换为list方便JSON序列化
    for author in author_stats:
        author_stats[author]['branches'] = list(author_stats[author]['branches'])
    
    return author_stats

# 统计每个分支的总数据
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
            
            branch_stats[branch]['commits'] += 1
            branch_stats[branch]['files_changed'] += commit['files_changed']
            branch_stats[branch]['lines_added'] += commit['lines_added']
            branch_stats[branch]['lines_deleted'] += commit['lines_deleted']
            branch_stats[branch]['authors'].add(commit['author'])
    
    # 将set转换为list方便JSON序列化
    for branch in branch_stats:
        branch_stats[branch]['authors'] = list(branch_stats[branch]['authors'])
    
    return branch_stats

# 统计每天的数据（包含分支和代码行数）
def get_daily_stats(commits):
    daily_stats = {}
    for commit in commits:
        day_key = commit['date'].strftime('%Y-%m-%d')
        author = commit['author']
        
        # 遍历所有相关分支
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
            
            daily_stats[day_key][branch][author]['files_changed'] += commit['files_changed']
            daily_stats[day_key][branch][author]['lines_added'] += commit['lines_added']
            daily_stats[day_key][branch][author]['lines_deleted'] += commit['lines_deleted']
    
    return daily_stats

# 生成HTML报告
def generate_html_report(monthly_stats, author_stats, branch_stats, daily_stats):
    # 获取所有作者和分支
    authors = list(author_stats.keys())
    branches = list(branch_stats.keys())
    
    # 准备月度数据用于图表（按作者分组，包含代码行数）
    months = sorted(monthly_stats.keys())
    monthly_data_files = []  # 文件数
    monthly_data_lines = []   # 代码行数（新增-删除）
    
    for author in authors:
        # 文件数数据
        author_files_data = {
            'label': author,
            'data': []
        }
        # 代码行数数据
        author_lines_data = {
            'label': author,
            'data': []
        }
        
        for month in months:
            total_files = 0
            total_lines = 0
            
            # 遍历所有分支，累加该作者的统计数据
            for branch in branches:
                if branch in monthly_stats[month] and author in monthly_stats[month][branch]:
                    stats = monthly_stats[month][branch][author]
                    total_files += stats['files_changed']
                    total_lines += (stats['lines_added'] - stats['lines_deleted'])
            
            author_files_data['data'].append(total_files)
            author_lines_data['data'].append(total_lines)
        
        monthly_data_files.append(author_files_data)
        monthly_data_lines.append(author_lines_data)
    
    # 准备每日数据用于图表（按作者分组，包含代码行数）
    days = sorted(daily_stats.keys())
    daily_data_files = []  # 文件数
    daily_data_lines = []   # 代码行数（新增-删除）
    
    for author in authors:
        # 文件数数据
        author_files_data = {
            'label': author,
            'data': []
        }
        # 代码行数数据
        author_lines_data = {
            'label': author,
            'data': []
        }
        
        for day in days:
            total_files = 0
            total_lines = 0
            
            # 遍历所有分支，累加该作者的统计数据
            for branch in branches:
                if branch in daily_stats[day] and author in daily_stats[day][branch]:
                    stats = daily_stats[day][branch][author]
                    total_files += stats['files_changed']
                    total_lines += (stats['lines_added'] - stats['lines_deleted'])
            
            author_files_data['data'].append(total_files)
            author_lines_data['data'].append(total_lines)
        
        daily_data_files.append(author_files_data)
        daily_data_lines.append(author_lines_data)
    
    # 生成HTML内容
    html_content = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SVN代码提交统计</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .filters {
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f0f0f0;
            border-radius: 4px;
        }
        .filters select, .filters button {
            margin: 0 5px;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .chart-container {
            margin: 20px 0;
            height: 400px;
        }
        .stats-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .stats-table th, .stats-table td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        .stats-table th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        .stats-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .stats-table tr:hover {
            background-color: #e9e9e9;
        }
        .section {
            margin-bottom: 30px;
        }
        .section h2 {
            color: #555;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }
        .chart-tabs {
            margin-bottom: 10px;
        }
        .chart-tab {
            display: inline-block;
            padding: 8px 16px;
            background-color: #f0f0f0;
            border: 1px solid #ddd;
            cursor: pointer;
            border-radius: 4px 4px 0 0;
            margin-right: 5px;
        }
        .chart-tab.active {
            background-color: white;
            border-bottom: 1px solid white;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>SVN代码提交统计</h1>
        
        <div class="filters">
            <label for="author-filter">作者筛选:</label>
            <select id="author-filter">
                <option value="all">所有作者</option>
'''
    
    # 添加作者选项
    for author in authors:
        html_content += f'                <option value="{author}">{author}</option>\n'
    
    html_content += '''
            </select>
            
            <label for="branch-filter">分支筛选:</label>
            <select id="branch-filter">
                <option value="all">所有分支</option>
'''
    
    # 添加分支选项
    for branch in branches:
        html_content += f'                <option value="{branch}">{branch}</option>\n'
    
    html_content += '''
            </select>
            
            <label for="start-date">开始日期:</label>
            <input type="date" id="start-date">
            
            <label for="end-date">结束日期:</label>
            <input type="date" id="end-date">
            
            <label for="chart-type">图表类型:</label>
            <select id="chart-type">
                <option value="line">折线图</option>
                <option value="bar">柱状图</option>
            </select>
            
            <button onclick="updateCharts()">更新图表</button>
        </div>
        
        <div class="section">
            <h2>月度提交统计</h2>
            <div class="chart-tabs">
                <span class="chart-tab active" onclick="switchChartType('monthly', 'files')">修改文件数</span>
                <span class="chart-tab" onclick="switchChartType('monthly', 'lines')">代码行数</span>
            </div>
            <div class="chart-container">
                <canvas id="monthlyChart"></canvas>
            </div>
        </div>
        
        <div class="section">
            <h2>每日提交统计</h2>
            <div class="chart-tabs">
                <span class="chart-tab active" onclick="switchChartType('daily', 'files')">修改文件数</span>
                <span class="chart-tab" onclick="switchChartType('daily', 'lines')">代码行数</span>
            </div>
            <div class="chart-container">
                <canvas id="dailyChart"></canvas>
            </div>
        </div>
        
        <div class="section">
            <h2>作者统计汇总</h2>
            <table class="stats-table">
                <tr>
                    <th>作者</th>
                    <th>提交次数</th>
                    <th>修改文件数</th>
                    <th>新增代码行数</th>
                    <th>删除代码行数</th>
                    <th>净增代码行数</th>
                    <th>参与分支</th>
                </tr>
'''
    
    # 添加作者统计表格行
    for author, stats in author_stats.items():
        net_lines = stats['lines_added'] - stats['lines_deleted']
        branches_str = ','.join(stats['branches'])
        html_content += f'                <tr><td>{author}</td><td>{stats["commits"]}</td><td>{stats["files_changed"]}</td><td>{stats["lines_added"]}</td><td>{stats["lines_deleted"]}</td><td>{net_lines}</td><td>{branches_str}</td></tr>\n'
    
    html_content += '''
            </table>
        </div>
        
        <div class="section">
            <h2>分支统计汇总</h2>
            <table class="stats-table">
                <tr>
                    <th>分支</th>
                    <th>提交次数</th>
                    <th>修改文件数</th>
                    <th>新增代码行数</th>
                    <th>删除代码行数</th>
                    <th>净增代码行数</th>
                    <th>参与作者</th>
                </tr>
'''
    
    # 添加分支统计表格行
    for branch, stats in branch_stats.items():
        net_lines = stats['lines_added'] - stats['lines_deleted']
        authors_str = ','.join(stats['authors'])
        html_content += f'                <tr><td>{branch}</td><td>{stats["commits"]}</td><td>{stats["files_changed"]}</td><td>{stats["lines_added"]}</td><td>{stats["lines_deleted"]}</td><td>{net_lines}</td><td>{authors_str}</td></tr>\n'
    
    html_content += '''
            </table>
        </div>
    </div>
    
    <script>
        // 数据
'''
    
    # 添加JavaScript数据
    html_content += f'        const monthlyDataFiles = {json.dumps(monthly_data_files)};\n'
    html_content += f'        const monthlyDataLines = {json.dumps(monthly_data_lines)};\n'
    html_content += f'        const dailyDataFiles = {json.dumps(daily_data_files)};\n'
    html_content += f'        const dailyDataLines = {json.dumps(daily_data_lines)};\n'
    html_content += f'        const months = {json.dumps(months)};\n'
    html_content += f'        const days = {json.dumps(days)};\n\n'
    
    html_content += '''
        // 当前图表配置
        let currentMonthlyType = 'files';
        let currentDailyType = 'files';
        
        // 图表实例
        let monthlyChart, dailyChart;
        
        // 初始化图表
        function initCharts() {
            const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
            const dailyCtx = document.getElementById('dailyChart').getContext('2d');
            
            // 月度图表
            monthlyChart = new Chart(monthlyCtx, {
                type: 'line',
                data: {
                    labels: months,
                    datasets: monthlyDataFiles
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: '修改文件数'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: '月份'
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: '月度代码提交统计 - 修改文件数'
                        },
                        legend: {
                            position: 'top'
                        }
                    }
                }
            });
            
            // 每日图表
            dailyChart = new Chart(dailyCtx, {
                type: 'line',
                data: {
                    labels: days,
                    datasets: dailyDataFiles
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: '修改文件数'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: '日期'
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: '每日代码提交统计 - 修改文件数'
                        },
                        legend: {
                            position: 'top'
                        }
                    }
                }
            });
        }
        
        // 切换图表类型（文件数/代码行数）
        function switchChartType(chartId, dataType) {
            if (chartId === 'monthly') {
                currentMonthlyType = dataType;
                updateMonthlyChart();
                
                // 更新标签样式
                document.querySelectorAll('.section:nth-of-type(2) .chart-tab').forEach(tab => tab.classList.remove('active'));
                document.querySelector(`.section:nth-of-type(2) .chart-tab:nth-of-type(${dataType === 'files' ? 1 : 2})`).classList.add('active');
            } else if (chartId === 'daily') {
                currentDailyType = dataType;
                updateDailyChart();
                
                // 更新标签样式
                document.querySelectorAll('.section:nth-of-type(3) .chart-tab').forEach(tab => tab.classList.remove('active'));
                document.querySelector(`.section:nth-of-type(3) .chart-tab:nth-of-type(${dataType === 'files' ? 1 : 2})`).classList.add('active');
            }
        }
        
        // 更新月度图表
        function updateMonthlyChart() {
            const authorFilter = document.getElementById('author-filter').value;
            const chartType = document.getElementById('chart-type').value;
            const startDate = document.getElementById('start-date').value;
            const endDate = document.getElementById('end-date').value;
            
            // 选择数据类型
            let dataSource = currentMonthlyType === 'files' ? monthlyDataFiles : monthlyDataLines;
            
            // 过滤数据
            let filteredData = dataSource;
            if (authorFilter !== 'all') {
                filteredData = dataSource.filter(dataset => dataset.label === authorFilter);
            }
            
            // 日期筛选
            let filteredLabels = months;
            let filteredDatasets = filteredData;
            
            if (startDate || endDate) {
                // 计算日期范围内的索引
                const startIndex = startDate ? months.findIndex(month => month >= startDate.substring(0, 7)) : 0;
                const endIndex = endDate ? months.findIndex(month => month <= endDate.substring(0, 7)) + 1 : months.length;
                
                // 筛选标签
                filteredLabels = months.slice(startIndex, endIndex);
                
                // 筛选每个数据集的数据
                filteredDatasets = filteredData.map(dataset => {
                    const newDataset = { ...dataset };
                    newDataset.data = dataset.data.slice(startIndex, endIndex);
                    return newDataset;
                });
            }
            
            // 更新图表
            monthlyChart.config.type = chartType;
            monthlyChart.data.labels = filteredLabels;
            monthlyChart.data.datasets = filteredDatasets;
            monthlyChart.options.scales.y.title.text = currentMonthlyType === 'files' ? '修改文件数' : '代码行数';
            monthlyChart.options.plugins.title.text = `月度代码提交统计 - ${currentMonthlyType === 'files' ? '修改文件数' : '代码行数'}`;
            monthlyChart.update();
        }
        
        // 更新每日图表
        function updateDailyChart() {
            const authorFilter = document.getElementById('author-filter').value;
            const chartType = document.getElementById('chart-type').value;
            const startDate = document.getElementById('start-date').value;
            const endDate = document.getElementById('end-date').value;
            
            // 选择数据类型
            let dataSource = currentDailyType === 'files' ? dailyDataFiles : dailyDataLines;
            
            // 过滤数据
            let filteredData = dataSource;
            if (authorFilter !== 'all') {
                filteredData = dataSource.filter(dataset => dataset.label === authorFilter);
            }
            
            // 日期筛选
            let filteredLabels = days;
            let filteredDatasets = filteredData;
            
            if (startDate || endDate) {
                // 计算日期范围内的索引
                const startIndex = startDate ? days.findIndex(day => day >= startDate) : 0;
                const endIndex = endDate ? days.findIndex(day => day <= endDate) + 1 : days.length;
                
                // 筛选标签
                filteredLabels = days.slice(startIndex, endIndex);
                
                // 筛选每个数据集的数据
                filteredDatasets = filteredData.map(dataset => {
                    const newDataset = { ...dataset };
                    newDataset.data = dataset.data.slice(startIndex, endIndex);
                    return newDataset;
                });
            }
            
            // 更新图表
            dailyChart.config.type = chartType;
            dailyChart.data.labels = filteredLabels;
            dailyChart.data.datasets = filteredDatasets;
            dailyChart.options.scales.y.title.text = currentDailyType === 'files' ? '修改文件数' : '代码行数';
            dailyChart.options.plugins.title.text = `每日代码提交统计 - ${currentDailyType === 'files' ? '修改文件数' : '代码行数'}`;
            dailyChart.update();
        }
        
        // 更新所有图表
        function updateCharts() {
            updateMonthlyChart();
            updateDailyChart();
        }
        
        // 页面加载时初始化图表
        window.onload = initCharts;
    </script>
</body>
</html>
'''
    
    # 写入HTML文件
    with open('svn_stats_report.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("HTML报告已生成: svn_stats_report.html")

import subprocess
import re
import hashlib
import time

# 缓存文件路径
CACHE_FILE = 'svn_cache.json'

# 加载缓存
def load_cache():
    """
    加载缓存数据
    """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载缓存失败: {e}")
    
    # 返回默认缓存结构
    return {
        "version": "1.1",  # 升级版本号
        "cache": {
            "revision_file": {},  # 按版本+文件路径缓存
            "revision_summary": {}  # 按版本缓存摘要
        }
    }

# 保存缓存
def save_cache(cache_data):
    """
    保存缓存数据
    """
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存缓存失败: {e}")
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
    key_str = f"{revision}|{branch_url}"
    return hashlib.md5(key_str.encode()).hexdigest()

# 获取文件内容哈希值
def get_file_content_hash(branch_url, revision, file_path, username=None, password=None):
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
        # 执行命令获取文件内容
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', timeout=30)
        if result.returncode != 0:
            # 尝试使用gbk编码
            result = subprocess.run(cmd, capture_output=True, encoding='gbk', timeout=30)
            if result.returncode != 0:
                return None
        
        # 计算MD5哈希值
        content = result.stdout
        file_hash = hashlib.md5(content.encode()).hexdigest()
        return file_hash
    except Exception as e:
        print(f"获取文件内容哈希失败 ({revision}:{file_path}): {e}")
        return None

# 全局缓存对象
cache_data = load_cache()

# 从SVN服务器获取提交记录
def get_svn_log_from_server(branch_url, username=None, password=None, revision_range=None):
    """
    从SVN服务器获取指定分支的提交记录
    :param branch_url: SVN分支URL
    :param username: SVN用户名
    :param password: SVN密码
    :param revision_range: 版本范围，格式如"1234:5678"或"HEAD"
    :return: SVN log的XML字符串
    """
    # 构建SVN命令
    cmd = ['svn', 'log', '--xml', '--verbose']
    
    # 添加版本范围
    if revision_range:
        cmd.extend(['-r', revision_range])
    
    # 添加认证信息
    if username:
        cmd.extend(['--username', username])
    if password:
        cmd.extend(['--password', password])
    
    # 添加分支URL
    cmd.append(branch_url)
    
    print(f"正在从SVN服务器获取日志: {branch_url}")
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 优化1: 增加超时时间到600秒
        # 优化2: 添加--no-auth-cache参数避免认证缓存问题
        cmd_with_opt = cmd.copy()
        cmd_with_opt.append('--no-auth-cache')
        
        # 执行命令，使用utf-8编码
        result = subprocess.run(cmd_with_opt, capture_output=True, encoding='utf-8', timeout=600)
        return result.stdout
    except subprocess.TimeoutExpired:
        print(f"SVN命令超时: {' '.join(cmd)}")
        print("建议: 减小版本范围，或检查网络连接")
        return None
    except UnicodeDecodeError:
        # 如果utf-8失败，尝试使用gbk编码
        print("使用utf-8编码失败，尝试使用gbk编码...")
        try:
            result = subprocess.run(cmd_with_opt, capture_output=True, encoding='gbk', timeout=600)
            return result.stdout
        except subprocess.TimeoutExpired:
            print(f"SVN命令超时(gbk): {' '.join(cmd)}")
            return None
    except subprocess.CalledProcessError as e:
        print(f"SVN命令执行失败: {e}")
        if hasattr(e, 'stderr'):
            print(f"错误输出: {e.stderr}")
        return None
    except Exception as e:
        print(f"获取SVN日志失败: {e}")
        import traceback
        traceback.print_exc()
        return None

# 从SVN服务器获取特定版本的diff
def get_svn_diff(branch_url, revision, username=None, password=None):
    """
    获取特定版本的代码变化，支持细粒度文件缓存和增量分析
    :param branch_url: SVN分支URL
    :param revision: 版本号
    :param username: SVN用户名
    :param password: SVN密码
    :return: (新增行数, 删除行数, 文件详情字典)
    """
    # 生成版本级缓存键
    revision_cache_key = generate_revision_cache_key(revision, branch_url)
    
    # 解析SVN diff结果，获取每个文件的变化
    cmd = ['svn', 'diff', '-c', str(revision)]
    
    if username:
        cmd.extend(['--username', username])
    if password:
        cmd.extend(['--password', password])
    
    cmd.append(branch_url)
    
    try:
        print(f"获取diff (rev {revision})")
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', timeout=60)
        if result.returncode != 0:
            # 尝试使用gbk编码
            result = subprocess.run(cmd, capture_output=True, encoding='gbk', timeout=60)
            if result.returncode != 0:
                return (0, 0, {})
        
        # 解析diff结果
        diff_output = result.stdout
        
        # 初始化统计变量
        total_lines_added = 0
        total_lines_deleted = 0
        file_details = {}
        
        # 正则表达式匹配文件块
        file_block_pattern = re.compile(r'---\s+(.*?)\s+\d+.*?\n\+\+\+\s+(.*?)\s+\d+.*?(?=\n---|\Z)', re.DOTALL)
        
        # 遍历所有文件块
        for match in file_block_pattern.finditer(diff_output):
            old_file = match.group(1).strip()
            new_file = match.group(2).strip()
            
            # 提取相对文件路径，处理各种情况
            if old_file == '/dev/null':
                # 新增文件
                file_path = new_file
                action = 'A'
            elif new_file == '/dev/null':
                # 删除文件
                file_path = old_file
                action = 'D'
            else:
                # 修改文件
                file_path = old_file if old_file.startswith('/') else new_file
                action = 'M'
            
            # 简化文件路径，获取有意义的相对路径
            # 移除可能的分支URL前缀
            if file_path.startswith('/'):
                file_path = file_path.lstrip('/')
            
            # 获取文件内容
            file_content = match.group(0)
            
            # 计算该文件的新增和删除行数
            lines_added = 0
            lines_deleted = 0
            
            for line in file_content.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    lines_added += 1
                elif line.startswith('-') and not line.startswith('---'):
                    lines_deleted += 1
            
            # 生成文件级缓存键
            file_cache_key = generate_file_cache_key(revision, file_path)
            
            # 获取文件当前版本的哈希值
            current_file_hash = get_file_content_hash(branch_url, revision, file_path, username, password)
            
            # 检查文件缓存
            use_cached = False
            if file_cache_key in cache_data['cache']['revision_file']:
                cached_file = cache_data['cache']['revision_file'][file_cache_key]
                if cached_file['hash'] == current_file_hash:
                    # 文件内容未变化，使用缓存数据
                    lines_added = cached_file['lines_added']
                    lines_deleted = cached_file['lines_deleted']
                    use_cached = True
                    print(f"  使用缓存文件数据: {file_path}")
            
            # 如果没有缓存或文件内容变化，更新缓存
            if not use_cached:
                # 保存文件级缓存
                cache_data['cache']['revision_file'][file_cache_key] = {
                    'revision': revision,
                    'file_path': file_path,
                    'hash': current_file_hash,
                    'lines_added': lines_added,
                    'lines_deleted': lines_deleted,
                    'action': action,
                    'timestamp': int(time.time())
                }
            
            # 累加到总统计
            total_lines_added += lines_added
            total_lines_deleted += lines_deleted
            
            # 保存文件详情
            file_details[file_path] = {
                'lines_added': lines_added,
                'lines_deleted': lines_deleted,
                'cached': use_cached,
                'action': action
            }
        
        # 保存版本级缓存摘要
        cache_data['cache']['revision_summary'][revision_cache_key] = {
            'revision': revision,
            'branch_url': branch_url,
            'total_lines_added': total_lines_added,
            'total_lines_deleted': total_lines_deleted,
            'file_count': len(file_details),
            'file_details': file_details,
            'timestamp': int(time.time())
        }
        
        # 保存缓存文件
        save_cache(cache_data)
        
        return (total_lines_added, total_lines_deleted, file_details)
    except Exception as e:
        print(f"获取diff失败 (rev {revision}): {e}")
        import traceback
        traceback.print_exc()
        return (0, 0, {})

# 准备图表数据
def prepare_chart_data(monthly_stats, author_stats, branch_stats, daily_stats):
    """
    准备图表数据
    :param monthly_stats: 月度统计数据
    :param author_stats: 作者统计数据
    :param branch_stats: 分支统计数据
    :param daily_stats: 每日统计数据
    :return: 图表数据字典
    """
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
                    total_lines += (stats['lines_added'] - stats['lines_deleted'])
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
                    total_lines += (stats['lines_added'] - stats['lines_deleted'])
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

# SVN日志获取任务
def svn_log_task(branch_url, username, password, revision_range, output_file):
    """
    从SVN服务器获取日志并分析每个版本的代码行数变化
    :param branch_url: SVN分支URL
    :param username: SVN用户名
    :param password: SVN密码
    :param revision_range: 版本范围
    :param output_file: 输出文件路径
    """
    global task_status
    
    try:
        task_status['running'] = True
        task_status['progress'] = 10
        task_status['message'] = '正在连接SVN服务器...'
        
        cmd = ['svn', 'log', '--xml', '--verbose']
        
        if revision_range:
            cmd.extend(['-r', revision_range])
        
        if username:
            cmd.extend(['--username', username])
        if password:
            cmd.extend(['--password', password])
        
        cmd.append(branch_url)
        
        task_status['progress'] = 30
        task_status['message'] = '正在获取SVN日志...'
        
        try:
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', timeout=300)
        except UnicodeDecodeError:
            result = subprocess.run(cmd, capture_output=True, encoding='gbk', timeout=300)
        
        if result.returncode != 0:
            task_status['error'] = f'SVN命令执行失败: {result.stderr}'
            task_status['running'] = False
            return
        
        task_status['progress'] = 40
        task_status['message'] = '正在保存日志...'
        
        # 保存日志文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        
        task_status['progress'] = 50
        task_status['message'] = '正在解析日志并获取代码行数...'
        
        # 解析日志获取版本列表
        commits = parse_svn_log(output_file)
        total_commits = len(commits)
        
        # 获取每个版本的代码行数变化
        for i, commit in enumerate(commits):
            revision = commit['revision']
            lines_added, lines_deleted, file_details = get_svn_diff(branch_url, revision, username, password)
            commit['lines_added'] = lines_added
            commit['lines_deleted'] = lines_deleted
            commit['file_details'] = file_details
            
            # 更新进度
            progress = 50 + (i + 1) * 50 // total_commits
            task_status['progress'] = progress
            task_status['message'] = f'正在获取代码行数... ({i + 1}/{total_commits})'
        
        task_status['progress'] = 80
        task_status['message'] = '正在分析日志...'
        
        # 生成统计
        monthly_stats = get_monthly_stats(commits)
        author_stats = get_author_stats(commits)
        branch_stats = get_branch_stats(commits)
        daily_stats = get_daily_stats(commits)
        chart_data = prepare_chart_data(monthly_stats, author_stats, branch_stats, daily_stats)
        
        # 保存结果
        global analysis_results
        analysis_results = {
            'commits': commits,
            'monthly_stats': monthly_stats,
            'author_stats': author_stats,
            'branch_stats': branch_stats,
            'daily_stats': daily_stats,
            'chart_data': chart_data,
            'total_commits': len(commits),
            'total_files': sum(c['files_changed'] for c in commits),
            'total_lines_added': sum(c['lines_added'] for c in commits),
            'total_lines_deleted': sum(c['lines_deleted'] for c in commits)
        }
        
        task_status['progress'] = 100
        task_status['message'] = f'分析完成! 共{len(commits)}条提交记录, 新增{analysis_results["total_lines_added"]}行代码'
        task_status['completed'] = True
        task_status['running'] = False
        
    except Exception as e:
        task_status['error'] = str(e)
        task_status['running'] = False
        import traceback
        traceback.print_exc()

# 保存SVN log到文件
def save_svn_log(log_content, log_file='svn.log'):
    """
    将SVN log保存到文件
    :param log_content: SVN log的XML字符串
    :param log_file: 保存路径
    """
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(log_content)
        print(f"SVN日志已保存到 {log_file}")
        return True
    except Exception as e:
        print(f"保存SVN日志失败: {e}")
        return False

# 交互式获取用户输入
def get_user_input():
    """
    交互式获取用户输入
    """
    print("=== SVN代码统计工具 ===")
    print("1. 使用现有svn.log文件")
    print("2. 从SVN服务器获取日志")
    
    choice = input("请选择操作 (1/2): ").strip()
    
    if choice == '1':
        log_file = input("请输入日志文件路径 (默认: svn.log): ").strip() or 'svn.log'
        if not os.path.exists(log_file):
            print(f"错误: 找不到文件 {log_file}")
            return None
        return {
            'mode': 'file',
            'log_file': log_file
        }
    elif choice == '2':
        branch_url = input("请输入SVN分支URL: ").strip()
        if not branch_url:
            print("错误: SVN分支URL不能为空")
            return None
        
        username = input("请输入SVN用户名 (可选): ").strip() or None
        password = input("请输入SVN密码 (可选): ").strip() or None
        revision_range = input("请输入版本范围 (可选，格式如1234:5678或HEAD): ").strip() or None
        
        return {
            'mode': 'server',
            'branch_url': branch_url,
            'username': username,
            'password': password,
            'revision_range': revision_range
        }
    else:
        print("错误: 无效的选择")
        return None

# 主函数
def main():
    # 获取用户输入
    config = get_user_input()
    if not config:
        return
    
    commits = []
    
    # 处理不同模式
    if config['mode'] == 'file':
        # 使用现有log文件
        log_file = config['log_file']
        print(f"正在解析 {log_file} 文件...")
        commits = parse_svn_log(log_file)
        
        # 对于文件模式，我们没有分支URL，无法获取代码行数变化
        print("文件模式下无法获取代码行数变化，仅显示提交记录统计")
    else:
        # 从SVN服务器获取log
        branch_url = config['branch_url']
        log_content = get_svn_log_from_server(
            branch_url,
            config['username'],
            config['password'],
            config['revision_range']
        )
        
        if not log_content:
            print("获取SVN日志失败，程序退出")
            return
        
        # 保存日志到文件
        save_svn_log(log_content)
        
        # 解析日志
        print("正在解析SVN日志...")
        # 将日志内容写入临时文件，然后解析
        temp_log_file = 'temp_svn.log'
        with open(temp_log_file, 'w', encoding='utf-8') as f:
            f.write(log_content)
        
        commits = parse_svn_log(temp_log_file)
        
        # 删除临时文件
        os.remove(temp_log_file)
        
        # 获取每个版本的代码行数变化
        print("正在获取代码行数变化...")
        total_commits = len(commits)
        for i, commit in enumerate(commits):
            revision = commit['revision']
            lines_added, lines_deleted, file_details = get_svn_diff(
                branch_url, 
                revision, 
                config['username'], 
                config['password']
            )
            commit['lines_added'] = lines_added
            commit['lines_deleted'] = lines_deleted
            commit['file_details'] = file_details
            
            # 显示进度
            progress = (i + 1) * 100 // total_commits
            print(f"获取代码行数... {progress}% ({i + 1}/{total_commits})", end='\r')
        print()
    
    print(f"共解析 {len(commits)} 条提交记录")
    
    print("正在生成统计数据...")
    monthly_stats = get_monthly_stats(commits)
    author_stats = get_author_stats(commits)
    branch_stats = get_branch_stats(commits)
    daily_stats = get_daily_stats(commits)
    
    print("正在生成HTML报告...")
    generate_html_report(monthly_stats, author_stats, branch_stats, daily_stats)
    
    print("统计完成!")

if __name__ == "__main__":
    main()
