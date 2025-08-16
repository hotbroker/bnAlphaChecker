#!/usr/bin/env python3
"""
OKX API测试脚本
用于测试OKX OS API是否配置正确
"""

import json
import sys
import os
from loguru import logger

# 配置简单的日志输出
logger.remove()
logger.add(sys.stdout, colorize=True, level="INFO")

def test_okx_config():
    """测试OKX配置"""
    try:
        # 读取配置文件
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        okx_api = config.get('okx_api', {})
        binance_accounts = config.get('binance_accounts', [])
        
        # 检查OKX API配置
        required_keys = ['project_id', 'api_key', 'secret_key', 'passphrase']
        missing_keys = [key for key in required_keys if not okx_api.get(key)]
        
        if missing_keys:
            logger.error(f"OKX API配置缺少: {', '.join(missing_keys)}")
            return False
        
        logger.success("OKX API配置检查通过")
        
        # 检查用户的OKX钱包配置
        okx_wallet_count = 0
        for i, account in enumerate(binance_accounts):
            okx_wallet = account.get('okx_wallet')
            if okx_wallet:
                okx_wallet_count += 1
                address = okx_wallet.get('address')
                chains = okx_wallet.get('chains', '1')
                note = account.get('note', f'用户{i+1}')
                
                if not address:
                    logger.error(f"用户 {note} 的OKX钱包缺少地址配置")
                    return False
                
                logger.info(f"用户 {note} 的OKX钱包 - 地址: {address[:6]}...{address[-4:]} - 链: {chains}")
        
        if okx_wallet_count == 0:
            logger.warning("没有用户配置OKX钱包")
        else:
            logger.success(f"找到 {okx_wallet_count} 个OKX钱包配置")
        return True
        
    except FileNotFoundError:
        logger.error("配置文件 config.json 不存在")
        return False
    except json.JSONDecodeError:
        logger.error("配置文件格式错误")
        return False
    except Exception as e:
        logger.error(f"配置检查失败: {e}")
        return False

def test_okx_api_call():
    """测试OKX API调用"""
    try:
        # 导入主模块
        from main import BinanceBalanceChecker
        
        checker = BinanceBalanceChecker()
        config = checker.load_config()
        
        okx_api = config.get('okx_api', {})
        binance_accounts = config.get('binance_accounts', [])
        
        # 找到第一个配置了OKX钱包的用户
        test_wallet = None
        test_user_note = None
        
        for account in binance_accounts:
            okx_wallet = account.get('okx_wallet')
            if okx_wallet and okx_wallet.get('address'):
                test_wallet = okx_wallet
                test_user_note = account.get('note', '测试用户')
                break
        
        if not test_wallet:
            logger.warning("没有用户配置OKX钱包，跳过API测试")
            return True
        
        address = test_wallet.get('address')
        chains = test_wallet.get('chains', '1')
        
        logger.info(f"测试用户 {test_user_note} 的OKX钱包API调用: {address[:6]}...{address[-4:]}")
        
        balance = checker.get_okx_wallet_balance(address, chains, okx_api)
        
        if balance >= 0:
            logger.success(f"用户 {test_user_note} 的OKX API调用成功，余额: ${balance:.2f} USD")
            return True
        else:
            logger.error(f"用户 {test_user_note} 的OKX API调用失败")
            return False
            
    except ImportError as e:
        logger.error(f"导入模块失败: {e}")
        return False
    except Exception as e:
        logger.error(f"API测试失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("🧪 OKX API配置测试")
    logger.info("=" * 40)
    
    # 配置检查
    if not test_okx_config():
        logger.error("配置检查失败，请检查config.json文件")
        return
    
    # API调用测试
    logger.info("\n🔗 OKX API调用测试")
    logger.info("=" * 40)
    
    if test_okx_api_call():
        logger.success("\n✅ 所有测试通过！OKX配置正常")
    else:
        logger.error("\n❌ API测试失败，请检查OKX配置")

if __name__ == "__main__":
    main()