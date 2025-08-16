#!/usr/bin/env python3
"""
币安余额历史查询工具
用于查看和分析余额变化曲线
"""

import sqlite3
import json
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
from loguru import logger

# 配置简单的日志输出
logger.remove()
logger.add(sys.stdout, colorize=True, level="INFO")

def connect_to_database(db_path: str = 'balance_history.db') -> sqlite3.Connection:
    """连接到数据库"""
    return sqlite3.connect(db_path)

def get_balance_history(db_path: str = 'balance_history.db', 
                       account_note: str = None, 
                       days: int = 30) -> List[Dict[str, Any]]:
    """获取余额历史记录"""
    conn = connect_to_database(db_path)
    cursor = conn.cursor()
    
    # 计算时间范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    query = '''
        SELECT account_type, account_note, account_identifier, timestamp, total_usdt, asset_details
        FROM balance_history
        WHERE timestamp >= ?
    '''
    params = [start_date]
    
    if account_note:
        query += ' AND account_note = ?'
        params.append(account_note)
    
    query += ' ORDER BY timestamp DESC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    history = []
    for row in rows:
        history.append({
            'account_type': row[0],
            'account_note': row[1],
            'account_identifier': row[2],
            'timestamp': row[3],
            'total_usdt': row[4],
            'asset_details': json.loads(row[5]) if row[5] else []
        })
    
    conn.close()
    return history

def get_account_summary(db_path: str = 'balance_history.db') -> List[Dict[str, Any]]:
    """获取账户摘要信息"""
    conn = connect_to_database(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            account_type,
            account_note,
            COUNT(*) as record_count,
            MIN(timestamp) as first_record,
            MAX(timestamp) as last_record,
            AVG(total_usdt) as avg_usdt,
            MIN(total_usdt) as min_usdt,
            MAX(total_usdt) as max_usdt
        FROM balance_history
        GROUP BY account_type, account_note
        ORDER BY last_record DESC
    ''')
    
    rows = cursor.fetchall()
    summaries = []
    
    for row in rows:
        summaries.append({
            'account_type': row[0],
            'account_note': row[1],
            'record_count': row[2],
            'first_record': row[3],
            'last_record': row[4],
            'avg_usdt': round(row[5], 2) if row[5] else 0,
            'min_usdt': round(row[6], 2) if row[6] else 0,
            'max_usdt': round(row[7], 2) if row[7] else 0
        })
    
    conn.close()
    return summaries

def print_balance_chart(history: List[Dict[str, Any]], account_note: str = None):
    """打印简单的余额变化图表"""
    if not history:
        print("没有找到历史记录")
        return
    
    print(f"\n📈 余额变化趋势 {'- ' + account_note if account_note else ''}")
    print("=" * 60)
    
    # 按时间排序（最早的在前）
    history.sort(key=lambda x: x['timestamp'])
    
    for record in history:
        timestamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
        account_type = record.get('account_type', 'unknown')
        print(f"{timestamp.strftime('%Y-%m-%d %H:%M')} | ${record['total_usdt']:>10.2f} USD | [{account_type}] {record['account_note']}")

def print_account_summaries(summaries: List[Dict[str, Any]]):
    """打印账户摘要"""
    logger.info("📊 账户摘要")
    print("=" * 80)
    print(f"{'类型':<12} {'账户名称':<20} {'记录数':<8} {'平均余额':<12} {'最小余额':<12} {'最大余额':<12} {'最后更新'}")
    print("-" * 95)
    
    for summary in summaries:
        last_update = datetime.fromisoformat(summary['last_record'].replace('Z', '+00:00'))
        print(f"{summary['account_type']:<12} {summary['account_note']:<20} {summary['record_count']:<8} "
              f"${summary['avg_usdt']:<11.2f} ${summary['min_usdt']:<11.2f} "
              f"${summary['max_usdt']:<11.2f} {last_update.strftime('%m-%d %H:%M')}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='查询币安余额历史记录')
    parser.add_argument('--account', '-a', type=str, help='指定账户名称')
    parser.add_argument('--days', '-d', type=int, default=7, help='查询天数（默认7天）')
    parser.add_argument('--summary', '-s', action='store_true', help='显示账户摘要')
    parser.add_argument('--db', type=str, default='balance_history.db', help='数据库文件路径')
    
    args = parser.parse_args()
    
    try:
        if args.summary:
            summaries = get_account_summary(args.db)
            print_account_summaries(summaries)
        else:
            history = get_balance_history(args.db, args.account, args.days)
            print_balance_chart(history, args.account)
            
            if history:
                logger.info(f"共找到 {len(history)} 条记录")
    
    except Exception as e:
        logger.error(f"查询失败: {e}")

if __name__ == "__main__":
    main()