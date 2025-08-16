# 币安余额监控器 (BnAlphaChecker)

一个自动监控币安账户余额的工具，支持多账户管理、USDT价值计算、定时通知和历史数据记录。

## 功能特性

- 🔄 **定时监控**: 每分钟自动检查账户余额
- 💰 **多平台支持**: 币安CEX + OKX钱包EVM链资产
- 🌐 **跨链查询**: 支持Ethereum、BSC、Polygon等主要EVM链
- 👥 **多账户支持**: 支持同时监控多个账户和钱包
- 📱 **实时通知**: 支持自定义通知推送
- 📊 **历史记录**: SQLite数据库存储余额变化历史
- 🔧 **配置灵活**: 支持热重载配置文件
- 📝 **完整日志**: 使用loguru提供彩色日志和文件记录

## 安装与配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或者使用安装脚本：
```bash
python install.py
```

### 2. 配置文件设置

复制并编辑 `config.json` 文件：

```json
{
  "binance_accounts": [
    {
      "api_key": "your_binance_api_key",
      "api_secret": "your_binance_api_secret",
      "note": "主账户",
      "notify_users": ["user1", "user2"],
      "okx_wallet": {
        "address": "0x1234...abcd",
        "chains": "1,56,137"
      }
    }
  ],
  "okx_api": {
    "project_id": "your_okx_project_id",
    "api_key": "your_okx_api_key",
    "secret_key": "your_okx_secret_key",
    "passphrase": "your_okx_passphrase"
  },
  "notification_settings": {
    "title": "余额监控",
    "enable_notifications": true
  },
  "database": {
    "path": "balance_history.db"
  }
}
```

### 3. 币安API设置

1. 登录币安账户
2. 进入 API 管理页面
3. 创建新的 API Key
4. **重要**: 只需要读取权限，不要开启交易权限
5. 将 API Key 和 Secret 填入配置文件

### 4. OKX OS API设置

1. 访问 [OKX Web3 Build](https://web3.okx.com/build/docs)
2. 注册并创建项目
3. 获取 Project ID、API Key、Secret Key 和 Passphrase
4. 将相关信息填入配置文件的 `okx_api` 部分
5. 在每个用户的 `okx_wallet` 中配置要监控的钱包地址和链ID

## 使用方法

### 测试配置

在启动监控器之前，建议先测试配置是否正确：

```bash
python test_okx_api.py
```

### 启动监控器

```bash
python main.py
```

程序会：
- 立即执行一次余额检查
- 每分钟自动检查所有配置的账户（币安+OKX钱包）
- 发送通知给指定用户
- 将结果保存到数据库

### 查询历史记录

查看所有账户摘要：
```bash
python query_balance_history.py --summary
```

查看特定账户的余额变化：
```bash
python query_balance_history.py --account "主账户" --days 7
```

查看最近30天的所有记录：
```bash
python query_balance_history.py --days 30
```

### 日志查看工具

查看最近7天的日志：
```bash
python view_logs.py
```

查看特定级别的日志：
```bash
python view_logs.py --level ERROR
```

搜索包含特定关键词的日志：
```bash
python view_logs.py --search "账户"
```

列出所有日志文件：
```bash
python view_logs.py --list
```

## 日志功能

程序使用loguru提供完整的日志记录：

### 日志文件位置
- `logs/bnalpha_YYYY-MM-DD.log` - 每日主日志文件
- `logs/bnalpha_error_YYYY-MM-DD.log` - 错误日志文件

### 日志级别
- **DEBUG**: 详细调试信息
- **INFO**: 一般信息（控制台显示）
- **WARNING**: 警告信息
- **ERROR**: 错误信息

### 日志配置
- 控制台输出：彩色格式化显示
- 文件输出：每日轮转，保留30天
- 自动压缩：老日志文件自动zip压缩

## 配置说明

### 用户账户配置
每个用户可以配置币安账户和OKX钱包：

- `api_key`: 币安API密钥
- `api_secret`: 币安API密钥对应的私钥
- `note`: 用户备注名称，用于识别不同用户
- `notify_users`: 接收通知的用户ID列表
- `okx_wallet`: （可选）该用户的OKX钱包配置
  - `address`: EVM兼容钱包地址
  - `chains`: 要查询的链ID，用逗号分隔（如："1,56,137"）

### OKX API配置
- `project_id`: OKX项目ID
- `api_key`: OKX API密钥
- `secret_key`: OKX私钥
- `passphrase`: OKX口令

### 通知设置
- `title`: 通知消息的标题
- `enable_notifications`: 是否启用通知功能

### 数据库设置
- `path`: SQLite数据库文件路径

## 数据库结构

程序会自动创建 `balance_history` 表，包含以下字段：
- `id`: 主键
- `account_type`: 账户类型（binance/okx_wallet）
- `account_note`: 账户备注
- `account_identifier`: 账户标识符哈希（隐私保护）
- `timestamp`: 记录时间
- `total_usdt`: 总USD价值
- `asset_details`: 资产详情（JSON格式）
- `created_at`: 创建时间

### 支持的区块链

OKX钱包支持以下主要区块链：
- `1`: Ethereum 主网
- `56`: BSC (Binance Smart Chain)
- `137`: Polygon
- `43114`: Avalanche
- `250`: Fantom
- `42161`: Arbitrum
- `10`: Optimism

## 安全注意事项

1. **API权限**: 仅启用读取权限，禁用交易权限
2. **配置文件**: 妥善保管包含API密钥的配置文件
3. **网络安全**: 确保运行环境的网络安全
4. **定期更新**: 定期更新API密钥

## 故障排除

### 常见错误

1. **API权限不足**
   - 检查API密钥是否正确
   - 确认API有读取账户信息的权限

2. **网络连接问题**
   - 检查网络连接
   - 确认能访问币安API

3. **配置文件错误**
   - 检查JSON格式是否正确
   - 确认所有必需字段都已填写

## 开发说明

### 项目结构
```
bnAlphaChecker/
├── main.py                 # 主程序
├── query_balance_history.py # 历史查询工具
├── view_logs.py            # 日志查看工具
├── test_okx_api.py         # OKX API测试脚本
├── install.py              # 安装脚本
├── config.json             # 配置文件
├── requirements.txt        # 依赖列表
├── pyproject.toml         # 项目配置
├── logs/                   # 日志文件目录
│   ├── bnalpha_*.log      # 主日志文件
│   └── bnalpha_error_*.log # 错误日志文件
└── README.md              # 说明文档
```

### 扩展功能

可以根据需要扩展以下功能：
- 添加更多交易所支持
- 实现Web界面
- 添加更多通知方式
- 增强数据分析功能

## 许可证

MIT License
