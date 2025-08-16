#!/usr/bin/env python3
"""
日志查看工具
用于查看和筛选程序日志
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import List
from loguru import logger

# 配置简单的日志输出
logger.remove()
logger.add(sys.stdout, colorize=True, level="INFO")

def get_log_files(log_dir: str = "logs", days: int = 7) -> List[str]:
    """获取指定天数内的日志文件"""
    log_files = []
    
    if not os.path.exists(log_dir):
        logger.warning(f"日志目录 {log_dir} 不存在")
        return log_files
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    for filename in os.listdir(log_dir):
        if filename.startswith("bnalpha_") and filename.endswith(".log"):
            # 提取日期部分
            try:
                date_str = filename.split("_")[1].replace(".log", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if start_date <= file_date <= end_date:
                    log_files.append(os.path.join(log_dir, filename))
            except (ValueError, IndexError):
                continue
    
    return sorted(log_files)

def view_logs(log_files: List[str], level_filter: str = None, search_term: str = None):
    """查看日志内容"""
    if not log_files:
        logger.warning("没有找到符合条件的日志文件")
        return
    
    total_lines = 0
    
    for log_file in log_files:
        logger.info(f"📄 查看日志文件: {log_file}")
        print("=" * 80)
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            file_lines = 0
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 级别过滤
                if level_filter:
                    if f"| {level_filter.upper()} " not in line:
                        continue
                
                # 搜索过滤
                if search_term:
                    if search_term.lower() not in line.lower():
                        continue
                
                print(line)
                file_lines += 1
                total_lines += 1
            
            if file_lines == 0:
                logger.info("该文件中没有符合条件的日志")
            else:
                logger.info(f"显示了 {file_lines} 行日志")
                
        except Exception as e:
            logger.error(f"读取日志文件失败: {e}")
        
        print("\n")
    
    logger.info(f"总共显示了 {total_lines} 行日志")

def list_log_files(log_dir: str = "logs"):
    """列出所有日志文件"""
    if not os.path.exists(log_dir):
        logger.warning(f"日志目录 {log_dir} 不存在")
        return
    
    logger.info("📁 可用的日志文件:")
    print("-" * 50)
    
    files = []
    for filename in os.listdir(log_dir):
        if filename.endswith(".log"):
            file_path = os.path.join(log_dir, filename)
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
            
            size_str = f"{file_size:,} bytes" if file_size < 1024*1024 else f"{file_size/(1024*1024):.1f} MB"
            
            files.append({
                'name': filename,
                'size': size_str,
                'modified': file_mtime.strftime('%Y-%m-%d %H:%M'),
                'path': file_path
            })
    
    if not files:
        logger.info("没有找到日志文件")
        return
    
    files.sort(key=lambda x: x['name'])
    
    for file_info in files:
        print(f"{file_info['name']:<30} {file_info['size']:<15} {file_info['modified']}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='查看币安余额监控器日志')
    parser.add_argument('--days', '-d', type=int, default=7, help='查看最近几天的日志（默认7天）')
    parser.add_argument('--level', '-l', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       help='过滤特定级别的日志')
    parser.add_argument('--search', '-s', type=str, help='搜索包含特定文字的日志')
    parser.add_argument('--list', action='store_true', help='列出所有日志文件')
    parser.add_argument('--dir', type=str, default='logs', help='日志文件目录（默认logs）')
    
    args = parser.parse_args()
    
    try:
        if args.list:
            list_log_files(args.dir)
        else:
            log_files = get_log_files(args.dir, args.days)
            view_logs(log_files, args.level, args.search)
    
    except Exception as e:
        logger.error(f"程序运行出错: {e}")

if __name__ == "__main__":
    main()