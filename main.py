import requests
import hashlib
import hmac
import time
import json
import sqlite3
import schedule
import threading
import sys
import base64
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

# 配置loguru日志
def setup_logger():
    """配置loguru日志"""
    # 移除默认的控制台输出
    logger.remove()
    
    # 添加控制台输出，带颜色和格式
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # 添加文件输出
    logger.add(
        "logs/bnalpha_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )
    
    # 添加错误日志文件
    logger.add(
        "logs/bnalpha_error_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR"
    )

# 初始化日志
setup_logger()

# 通知函数实现
ipc_msg_key_msgcontent = "msgcontent"
sendtimeout = 0
lasttimesend = 0

def sendtext_remote(touser, content, texttitle="bnbh_bot", rawtext=False):
    newtexttitle = texttitle + "\n"
    global sendtimeout
    if content.find('Operation timed out after') != -1:
        if time.time() - sendtimeout < 60 * 60:
            logger.warning(f'Too much timeout: {content}')
            return
        sendtimeout = time.time()

    data = {"cmd": "sendtext",
            "touser": touser,
            ipc_msg_key_msgcontent: newtexttitle + content,
            }
    if rawtext:
        data[ipc_msg_key_msgcontent] = content
    
    try:
        r = requests.post("http://gossiphere.com:9999/cmd", json=data, timeout=10)
        logger.info(f"Notification sent to {touser}: {texttitle}, response: {r.text}")
    except Exception as e:
        logger.error(f"发送通知失败: {e}")

def sendtext_remote_delay(touser, content, texttitle="solHotBot", delay=0, rawtext=False):
    global lasttimesend
    if delay > 0:
        time.sleep(delay)
        if lasttimesend != 0:
            if time.time() - lasttimesend < delay:
                time.sleep(delay - time.time() + lasttimesend)

    lasttimesend = time.time()
    sendtext_remote(touser, content, texttitle, rawtext)

def sendtext_remote_async(touser, content, texttitle="solHotBot", delay=0, rawtext=False):
    logger.debug(f"Async notification queued: {texttitle} to {touser}")
    thread = threading.Thread(target=sendtext_remote_delay, args=(touser, content, texttitle, delay, rawtext))
    thread.start()

class BinanceBalanceChecker:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.db_path = None
        self.init_database()

    def load_config(self) -> Dict[str, Any]:
        """每次查询时重新加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.db_path = config.get('database', {}).get('path', 'balance_history.db')
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}

    def init_database(self):
        """初始化SQLite数据库"""
        config = self.load_config()
        db_path = config.get('database', {}).get('path', 'balance_history.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_type TEXT NOT NULL,
                account_note TEXT NOT NULL,
                account_identifier TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                total_usdt REAL NOT NULL,
                asset_details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")

    def get_binance_signature(self, query_string: str, secret: str) -> str:
        """生成币安API签名"""
        return hmac.new(
            secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def get_account_balance(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        """获取币安账户余额"""
        base_url = "https://api.binance.com"
        endpoint = "/api/v3/account"
        
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}&recvWindow=60000"
        signature = self.get_binance_signature(query_string, api_secret)
        
        headers = {
            'X-MBX-APIKEY': api_key
        }
        
        url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"币安API请求失败: {response.status_code}, {response.text}")
                return {}
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return {}

    def convert_to_usdt(self, balances: List[Dict]) -> float:
        """将所有资产转换为USDT价值"""
        total_usdt = 0.0
        
        # 获取所有需要的交易对价格
        symbols_needed = []
        for balance in balances:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total_balance = free + locked
            
            if total_balance > 0:
                if asset == 'USDT':
                    total_usdt += total_balance
                elif asset == 'BUSD':
                    total_usdt += total_balance  # BUSD通常与USDT等价
                else:
                    symbols_needed.append(f"{asset}USDT")
        
        if symbols_needed:
            # 批量获取价格
            try:
                price_url = "https://api.binance.com/api/v3/ticker/price"
                response = requests.get(price_url, timeout=10)
                if response.status_code == 200:
                    all_prices = response.json()
                    price_dict = {item['symbol']: float(item['price']) for item in all_prices}
                    
                    # 计算每个资产的USDT价值
                    for balance in balances:
                        asset = balance['asset']
                        free = float(balance['free'])
                        locked = float(balance['locked'])
                        total_balance = free + locked
                        
                        if total_balance > 0 and asset not in ['USDT', 'BUSD']:
                            symbol = f"{asset}USDT"
                            if symbol in price_dict:
                                total_usdt += total_balance * price_dict[symbol]
                            else:
                                # 尝试通过BTC转换
                                btc_symbol = f"{asset}BTC"
                                if btc_symbol in price_dict and 'BTCUSDT' in price_dict:
                                    btc_value = total_balance * price_dict[btc_symbol]
                                    total_usdt += btc_value * price_dict['BTCUSDT']
            except Exception as e:
                logger.error(f"获取价格失败: {e}")
        
        return total_usdt

    def get_okx_signature(self, timestamp: str, method: str, request_path: str, body: str, secret_key: str) -> str:
        """生成OKX API签名"""
        message = timestamp + method + request_path + body
        signature = base64.b64encode(
            hmac.new(
                secret_key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        return signature

    def get_okx_wallet_balance(self, address: str, chains: str, okx_config: Dict[str, str]) -> float:
        """使用OKX OS API获取钱包余额"""
        base_url = "https://web3.okx.com"
        endpoint = "/api/v5/wallet/asset/total-value-by-address"
        
        # 构建请求参数
        params = {
            'address': address,
            'chains': chains,
            'assetType': '0',  # 查询所有资产
            'excludeRiskToken': 'true'  # 过滤风险代币
        }
        
        # 构建查询字符串
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        url = f"{base_url}{endpoint}?{query_string}"
        
        # 生成时间戳
        timestamp = str(int(time.time() * 1000))
        
        # 生成签名
        signature = self.get_okx_signature(
            timestamp, 
            'GET', 
            f"{endpoint}?{query_string}", 
            '', 
            okx_config['secret_key']
        )
        
        headers = {
            'OK-ACCESS-PROJECT': okx_config['project_id'],
            'OK-ACCESS-KEY': okx_config['api_key'],
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-PASSPHRASE': okx_config['passphrase'],
            'OK-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0' and data.get('data'):
                    total_value = float(data['data'][0].get('totalValue', '0'))
                    return total_value
                else:
                    logger.error(f"OKX API错误: {data.get('msg', 'Unknown error')}")
                    return 0.0
            else:
                logger.error(f"OKX API请求失败: {response.status_code}, {response.text}")
                return 0.0
        except Exception as e:
            logger.error(f"获取OKX钱包余额失败: {e}")
            return 0.0

    def save_balance_to_db(self, account_type: str, account_note: str, account_identifier: str, total_usdt: float, asset_details: str):
        """保存余额记录到数据库"""
        config = self.load_config()
        db_path = config.get('database', {}).get('path', 'balance_history.db')
        
        # 对敏感信息进行哈希处理保护隐私
        identifier_hash = hashlib.sha256(account_identifier.encode()).hexdigest()[:16]
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO balance_history 
            (account_type, account_note, account_identifier, timestamp, total_usdt, asset_details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (account_type, account_note, identifier_hash, datetime.now(), total_usdt, asset_details))
        
        conn.commit()
        conn.close()

    def check_all_accounts(self):
        """检查所有配置的账户余额"""
        config = self.load_config()
        if not config:
            logger.error("无法加载配置文件")
            return
        
        notification_settings = config.get('notification_settings', {})
        okx_api_config = config.get('okx_api', {})
        
        # 检查币安账户（现在包含OKX钱包配置）
        binance_accounts = config.get('binance_accounts', [])
        for account in binance_accounts:
            self.check_user_assets(account, okx_api_config, notification_settings)

    def check_user_assets(self, account: Dict, okx_api_config: Dict, notification_settings: Dict):
        """检查用户的所有资产（币安+OKX钱包）并汇总通知"""
        note = account.get('note', '未命名用户')
        notify_users = account.get('notify_users', [])
        
        logger.info(f"正在检查用户 {note} 的所有资产")
        
        # 存储用户资产信息
        user_assets = {
            'binance': None,
            'okx_wallet': None,
            'total_usd': 0.0
        }
        
        # 检查币安账户
        binance_result = self.check_binance_account_silent(account)
        if binance_result:
            user_assets['binance'] = binance_result
            user_assets['total_usd'] += binance_result['total_usdt']
        
        # 检查OKX钱包（如果配置了）
        okx_wallet = account.get('okx_wallet')
        if okx_wallet and okx_api_config:
            okx_result = self.check_okx_wallet_silent(account, okx_wallet, okx_api_config)
            if okx_result:
                user_assets['okx_wallet'] = okx_result
                user_assets['total_usd'] += okx_result['total_usd']
        
        # 发送汇总通知
        if notification_settings.get('enable_notifications', True) and notify_users:
            message = self.format_user_assets_message(note, user_assets)
            title = notification_settings.get('title', '余额监控')
            
            for user in notify_users:
                sendtext_remote_async(user, message, title)
        
        logger.info(f"用户 {note} 总资产价值: ${user_assets['total_usd']:.2f} USD")

    def check_binance_account_silent(self, account: Dict) -> Dict:
        """静默检查单个币安账户（不发送通知）"""
        api_key = account.get('api_key')
        api_secret = account.get('api_secret')
        note = account.get('note', '未命名币安账户')
        
        if not api_key or not api_secret:
            logger.warning(f"币安账户 {note} 缺少API配置")
            return None
        
        logger.info(f"正在检查币安账户: {note}")
        
        # 获取账户余额
        account_data = self.get_account_balance(api_key, api_secret)
        if not account_data:
            return None
        
        balances = account_data.get('balances', [])
        total_usdt = self.convert_to_usdt(balances)
        
        # 准备资产详情
        significant_balances = []
        for balance in balances:
            free = float(balance['free'])
            locked = float(balance['locked'])
            total_balance = free + locked
            if total_balance > 0.001:  # 过滤掉极小余额
                significant_balances.append({
                    'asset': balance['asset'],
                    'total': total_balance,
                    'free': free,
                    'locked': locked
                })
        
        asset_details = json.dumps(significant_balances, ensure_ascii=False)
        
        # 保存到数据库
        self.save_balance_to_db('binance', note, api_key, total_usdt, asset_details)
        
        logger.info(f"币安账户 {note} 总价值: ${total_usdt:.2f} USDT")
        
        return {
            'total_usdt': total_usdt,
            'balances': significant_balances,
            'note': note
        }

    def check_okx_wallet_silent(self, account: Dict, okx_wallet: Dict, okx_config: Dict) -> Dict:
        """静默检查用户的OKX钱包（不发送通知）"""
        address = okx_wallet.get('address')
        chains = okx_wallet.get('chains', '1')  # 默认以太坊主网
        logger.info(f'chains')
        note = account.get('note', '未命名用户')

        
        if not address:
            logger.warning(f"用户 {note} 的OKX钱包缺少地址配置")
            return None
        
        # 检查OKX API配置
        required_keys = ['project_id', 'api_key', 'secret_key', 'passphrase']
        if not all(okx_config.get(key) for key in required_keys):
            logger.warning(f"OKX API配置不完整，跳过用户 {note} 的钱包")
            return None
        
        logger.info(f"正在检查用户 {note} 的OKX钱包: {address[:6]}...{address[-4:]}")
        
        # 获取钱包余额
        total_usd = self.get_okx_wallet_balance(address, chains, okx_config)
        if total_usd == 0:
            logger.warning(f"用户 {note} 的OKX钱包余额为0或获取失败")
        
        # OKX API返回的是总值，不需要详细的资产列表
        asset_details = json.dumps({
            'address': address,
            'chains': chains,
            'total_value_usd': total_usd
        }, ensure_ascii=False)
        
        # 保存到数据库
        wallet_note = f"{note}-OKX钱包"
        self.save_balance_to_db('okx_wallet', wallet_note, address, total_usd, asset_details)
        
        logger.info(f"用户 {note} 的OKX钱包总价值: ${total_usd:.2f} USD")
        
        return {
            'total_usd': total_usd,
            'address': address,
            'chains': chains,
            'note': wallet_note
        }

    def format_user_assets_message(self, user_note: str, user_assets: Dict) -> str:
        """格式化用户资产汇总消息"""
        message = f"💰 用户资产报告\n"
        message += f"用户: {user_note}\n"
        message += f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"总资产价值: ${user_assets['total_usd']:.2f} USD\n\n"
        
        # 币安账户信息
        if user_assets.get('binance'):
            binance = user_assets['binance']
            message += f"🏢 币安账户: ${binance['total_usdt']:.2f} USDT\n"
            
            # 显示主要资产
            if binance.get('balances'):
                balances = binance['balances']
                balances.sort(key=lambda x: x['total'], reverse=True)
                top_assets = [b for b in balances[:5] if b['total'] > 1]  # 只显示前5个大于1的资产
                if top_assets:
                    message += "主要币安资产:\n"
                    for asset in top_assets:
                        message += f"  • {asset['asset']}: {asset['total']:.4f}\n"
        else:
            message += "🏢 币安账户: 未配置或获取失败\n"
        
        # OKX钱包信息
        if user_assets.get('okx_wallet'):
            okx = user_assets['okx_wallet']
            # 链ID映射
            chain_names = {
                '1': 'Ethereum',
                '56': 'BSC', 
                '137': 'Polygon',
                '43114': 'Avalanche',
                '250': 'Fantom',
                '42161': 'Arbitrum',
                '10': 'Optimism'
            }
            chain_list = okx['chains'].split(',')
            chain_display = ', '.join([chain_names.get(chain.strip(), f'Chain-{chain.strip()}') for chain in chain_list])
            
            message += f"\n💼 OKX钱包: ${okx['total_usd']:.2f} USD\n"
            message += f"地址: {okx['address'][:6]}...{okx['address'][-4:]}\n"
            message += f"链: {chain_display}\n"
        else:
            message += "\n💼 OKX钱包: 未配置或获取失败\n"
        
        return message

    def check_binance_account(self, account: Dict, notification_settings: Dict):
        """检查单个币安账户（旧方法，现在不推荐使用）"""
        api_key = account.get('api_key')
        api_secret = account.get('api_secret')
        note = account.get('note', '未命名币安账户')
        notify_users = account.get('notify_users', [])
        
        if not api_key or not api_secret:
            logger.warning(f"币安账户 {note} 缺少API配置")
            return
        
        logger.info(f"正在检查币安账户: {note}")
        
        # 获取账户余额
        account_data = self.get_account_balance(api_key, api_secret)
        if not account_data:
            return
        
        balances = account_data.get('balances', [])
        total_usdt = self.convert_to_usdt(balances)
        
        # 准备资产详情
        significant_balances = []
        for balance in balances:
            free = float(balance['free'])
            locked = float(balance['locked'])
            total_balance = free + locked
            if total_balance > 0.001:  # 过滤掉极小余额
                significant_balances.append({
                    'asset': balance['asset'],
                    'total': total_balance,
                    'free': free,
                    'locked': locked
                })
        
        asset_details = json.dumps(significant_balances, ensure_ascii=False)
        
        # 保存到数据库
        self.save_balance_to_db('binance', note, api_key, total_usdt, asset_details)
        
        # 发送通知
        if notification_settings.get('enable_notifications', True):
            message = self.format_balance_message(note, total_usdt, significant_balances, 'Binance')
            title = notification_settings.get('title', '余额监控')
            
            for user in notify_users:
                sendtext_remote_async(user, message, title)
        
        logger.info(f"币安账户 {note} 总价值: ${total_usdt:.2f} USDT")

    def check_user_okx_wallet(self, account: Dict, okx_wallet: Dict, okx_config: Dict, notification_settings: Dict):
        """检查用户的OKX钱包"""
        address = okx_wallet.get('address')
        chains = okx_wallet.get('chains', '1')  # 默认以太坊主网
        note = account.get('note', '未命名用户')
        notify_users = account.get('notify_users', [])
        
        if not address:
            logger.warning(f"用户 {note} 的OKX钱包缺少地址配置")
            return
        
        # 检查OKX API配置
        required_keys = ['project_id', 'api_key', 'secret_key', 'passphrase']
        if not all(okx_config.get(key) for key in required_keys):
            logger.warning(f"OKX API配置不完整，跳过用户 {note} 的钱包")
            return
        
        logger.info(f"正在检查用户 {note} 的OKX钱包: {address[:6]}...{address[-4:]}")
        
        # 获取钱包余额
        total_usdt = self.get_okx_wallet_balance(address, chains, okx_config)
        if total_usdt == 0:
            logger.warning(f"用户 {note} 的OKX钱包余额为0或获取失败")
        
        # OKX API返回的是总值，不需要详细的资产列表
        asset_details = json.dumps({
            'address': address,
            'chains': chains,
            'total_value_usd': total_usdt
        }, ensure_ascii=False)
        
        # 保存到数据库
        wallet_note = f"{note}-OKX钱包"
        self.save_balance_to_db('okx_wallet', wallet_note, address, total_usdt, asset_details)
        
        # 发送通知
        if notification_settings.get('enable_notifications', True):
            message = self.format_okx_balance_message(wallet_note, address, total_usdt, chains)
            title = notification_settings.get('title', '余额监控')
            
            for user in notify_users:
                sendtext_remote_async(user, message, title)
        
        logger.info(f"用户 {note} 的OKX钱包总价值: ${total_usdt:.2f} USD")

    def format_balance_message(self, account_note: str, total_usdt: float, balances: List[Dict], account_type: str = '') -> str:
        """格式化币安账户余额消息"""
        message = f"📊 {account_type}账户余额报告\n"
        message += f"账户: {account_note}\n"
        message += f"总价值: ${total_usdt:.2f} USDT\n"
        message += f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if balances:
            message += "主要资产:\n"
            # 按总价值排序
            balances.sort(key=lambda x: x['total'], reverse=True)
            for balance in balances[:10]:  # 只显示前10个
                if balance['total'] > 1:  # 只显示大于1的资产
                    message += f"• {balance['asset']}: {balance['total']:.4f}\n"
        
        return message

    def format_okx_balance_message(self, wallet_note: str, address: str, total_usd: float, chains: str) -> str:
        """格式化OKX钱包余额消息"""
        # 链ID映射
        chain_names = {
            '1': 'Ethereum',
            '56': 'BSC', 
            '137': 'Polygon',
            '43114': 'Avalanche',
            '250': 'Fantom',
            '42161': 'Arbitrum',
            '10': 'Optimism'
        }
        
        chain_list = chains.split(',')
        chain_display = ', '.join([chain_names.get(chain.strip(), f'Chain-{chain.strip()}') for chain in chain_list])
        
        message = f"💰 OKX钱包余额报告\n"
        message += f"钱包: {wallet_note}\n"
        message += f"地址: {address[:6]}...{address[-4:]}\n"
        message += f"链: {chain_display}\n"
        message += f"总价值: ${total_usd:.2f} USD\n"
        message += f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return message

    def run_scheduler(self):
        """运行定时任务"""
        logger.info("币安余额监控器已启动")
        logger.info("定时任务: 每分钟检查一次账户余额")
        
        # 立即执行一次
        self.check_all_accounts()
        
        # 设置定时任务
        schedule.every().minutes.do(self.check_all_accounts)
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次是否有任务要执行

def main():
    """主函数"""
 
    checker = BinanceBalanceChecker()
    
    try:
        checker.run_scheduler()
    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")

if __name__ == "__main__":
    main()
