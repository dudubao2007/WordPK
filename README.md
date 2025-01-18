# WordPK - 单词对战游戏

这是一个基于WebSocket的双人单词对战游戏。玩家可以在游戏中进行实时对战，通过选择正确的单词翻译来获取分数。

## 功能特点

- 实时双人对战
- 计时答题机制
- 动态计分系统
- 特殊题目翻倍得分
- 断线自动处理

## 技术栈

- Python 3.8+
- WebSocket (websockets库)
- Tkinter (GUI界面)
- asyncio (异步IO)

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/你的用户名/WordPK.git
cd WordPK
```

2. 安装依赖：
```bash
pip install websockets
```

## 使用方法

1. 启动服务器：
```bash
python word_pk_server.py
```

2. 启动客户端：
```bash
python word_pk_client.py
```

3. 在客户端界面输入用户名并连接服务器
4. 等待对手加入并点击准备按钮
5. 开始游戏！

## 游戏规则

- 每局游戏共9轮
- 每题10秒答题时间
- 根据答题速度获得不同分数：
  - 1秒内答对：120分
  - 8秒后答对：50分
  - 中间时间段：按时间线性计算
- 双方都答对时：
  - 先答对的玩家获得额外分数
  - 基础30分 + 时间差 × 7（最多加42分）
- 特殊题目：
  - 最后一题得分×1.6

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License 