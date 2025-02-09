import asyncio
import json
import tkinter as tk
from tkinter import messagebox
import websockets
from typing import Optional
import time

class Config:
    # 网络配置
    DEFAULT_HOST = 'localhost'
    DEFAULT_PORT = 8766
    
    # UI配置
    WINDOW_SIZE = "1024x768"
    WORD_FONT = ("SimSun", 48, "bold")
    OPTION_FONT = ("SimSun", 16)
    INFO_FONT = ("SimSun", 14)
    RESULT_FONT = ("SimSun", 56, "bold")
    
    # 显示延迟（秒）
    GAME_START_DELAY = 0.3  # 游戏开始提示显示时间
    NEW_ROUND_DELAY = 0.8  # 新回合开始前的延迟
    RESULT_DISPLAY_DELAY = 0.8  # 显示答题结果的延迟

class WordPKClient:
    def __init__(self, root):
        self.root = root
        self.root.title("单词PK")
        self.root.geometry(Config.WINDOW_SIZE)
        
        # 设置字体
        self.word_font = Config.WORD_FONT
        self.option_font = Config.OPTION_FONT
        self.info_font = Config.INFO_FONT
        self.result_font = Config.RESULT_FONT
        
        # 加载配置
        self.config = self.load_config()
        
        # WebSocket连接
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.name = ""
        
        # 游戏状态
        self.game_started = False
        self.question_start_time = 0
        self.answer_timer = None
        self.opponent_name = None  # 对手名字
        self.total_rounds = 0  # 总回合数，将从服务器获取
        self.answer_timeout = 20000  # 答题超时时间（毫秒），将从服务器获取
        self.can_answer = False  # 是否可以答题
        
        # 创建界面
        self.create_widgets()
        
        # 绑定键盘事件
        self.root.bind('1', lambda e: self.select_answer(0))
        self.root.bind('2', lambda e: self.select_answer(1))
        self.root.bind('3', lambda e: self.select_answer(2))
        self.root.bind('4', lambda e: self.select_answer(3))
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 用于控制程序退出
        self.running = True
    
    def load_config(self):
        """加载配置文件"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'name': '',
                'host': Config.DEFAULT_HOST,
                'port': Config.DEFAULT_PORT
            }
    
    def save_config(self):
        """保存配置文件"""
        config = {
            'name': self.name,
            'host': self.host_entry.get().strip(),
            'port': int(self.port_entry.get().strip()),
            'pronunciation_type': self.pronunciation_type.get()
        }
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    
    def create_widgets(self):
        # 创建主框架
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # 创建登录框架
        self.login_frame = tk.Frame(self.main_frame)
        self.login_frame.pack(expand=True)
        
        # 名字输入
        tk.Label(self.login_frame, text="名字：", font=self.info_font).pack(pady=5)
        self.name_entry = tk.Entry(self.login_frame, font=self.info_font)
        self.name_entry.insert(0, self.config['name'])
        self.name_entry.pack(pady=5)
        
        # 主机地址输入
        tk.Label(self.login_frame, text="主机：", font=self.info_font).pack(pady=5)
        self.host_entry = tk.Entry(self.login_frame, font=self.info_font)
        self.host_entry.insert(0, self.config['host'])
        self.host_entry.pack(pady=5)
        
        # 端口输入
        tk.Label(self.login_frame, text="端口：", font=self.info_font).pack(pady=5)
        self.port_entry = tk.Entry(self.login_frame, font=self.info_font)
        self.port_entry.insert(0, str(self.config['port']))
        self.port_entry.pack(pady=5)
        
        # 发音类型选择
        tk.Label(self.login_frame, text="发音类型：", font=self.info_font).pack(pady=5)
        pron_frame = tk.Frame(self.login_frame)
        pron_frame.pack()
        self.pronunciation_type = tk.StringVar(value=self.config.get('pronunciation_type', 'uk'))
        uk_radio = tk.Radiobutton(pron_frame, text="英式", font=self.info_font,
                                 variable=self.pronunciation_type, value='uk')
        us_radio = tk.Radiobutton(pron_frame, text="美式", font=self.info_font,
                                 variable=self.pronunciation_type, value='us')
        uk_radio.pack(side='left', padx=5)
        us_radio.pack(side='left', padx=5)
        
        # 错误信息显示
        self.login_error_label = tk.Label(self.login_frame, text="", font=self.info_font, fg="red")
        self.login_error_label.pack(pady=5)
        
        tk.Button(self.login_frame, text="加入游戏", font=self.info_font,
                 command=self.join_game).pack(pady=10)
        
        # 创建游戏框架（初始隐藏）
        self.game_frame = tk.Frame(self.main_frame)
        
        # 玩家信息显示
        self.players_frame = tk.Frame(self.game_frame)
        self.players_frame.pack(fill='x', pady=10)
        self.players_label = tk.Label(self.players_frame, text="等待玩家加入...",
                                    font=self.info_font)
        self.players_label.pack()
        
        # 准备按钮
        self.ready_button = tk.Button(self.game_frame, text="准备",
                                    font=self.info_font, command=self.ready)
        self.ready_button.pack(pady=5)
        
        # 单词显示
        self.word_label = tk.Label(self.game_frame, text="", font=self.word_font)
        self.word_label.pack(pady=10)
        
        # 音标显示
        self.pronunciation_label = tk.Label(self.game_frame, text="", font=("Arial", 24))
        self.pronunciation_label.pack(pady=5)
        
        # 选项按钮
        self.option_buttons = []
        for i in range(4):
            btn = tk.Button(self.game_frame, text="", width=40, height=2,
                          font=self.option_font,
                          command=lambda x=i: self.select_answer(x))
            btn.pack(pady=10)
            self.option_buttons.append(btn)
        
        # 比分显示
        self.score_label = tk.Label(self.game_frame, text="", font=self.info_font)
        self.score_label.pack(pady=10)
        
        # 状态显示
        self.status_label = tk.Label(self.game_frame, text="", font=self.info_font)
        self.status_label.pack(pady=10)
        
        # 上一题信息显示（右下角）
        self.last_word_frame = tk.Frame(self.root)
        self.last_word_frame.pack(side=tk.BOTTOM, anchor=tk.SE, padx=10, pady=10)
        self.last_word_label = tk.Label(self.last_word_frame, text="", font=self.info_font, fg="gray")
        self.last_word_label.pack()
    
    def join_game(self):
        self.name = self.name_entry.get().strip()
        if not self.name:
            self.login_error_label.config(text="错误：请输入名字")
            return
        
        if len(self.name) > 20:  # 名字长度限制保持为20
            self.login_error_label.config(text="错误：名字不能超过20个字符")
            return
        
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            self.login_error_label.config(text="错误：端口必须是数字")
            return
        
        # 清除错误信息
        self.login_error_label.config(text="")
        
        # 保存配置
        self.save_config()
        
        # 启动WebSocket连接
        asyncio.create_task(self.connect_to_server())
    
    def ready(self):
        if self.websocket:
            asyncio.create_task(self.send_message({
                'type': 'ready'
            }))
            self.ready_button.config(state='disabled')
    
    def select_answer(self, index):
        if self.websocket and self.game_started and self.can_answer:
            # 计算答题用时（毫秒）
            answer_time = min(
                int((time.time() - self.question_start_time) * 1000), 
                self.answer_timeout
            )
            
            # 取消超时定时器
            if self.answer_timer:
                self.root.after_cancel(self.answer_timer)
                self.answer_timer = None
            
            # 设置不可答题
            self.can_answer = False
            
            asyncio.create_task(self.send_message({
                'type': 'answer',
                'answer': self.option_buttons[index].cget('text')[3:],
                'time': answer_time
            }))
            # 禁用所有按钮，等待结果
            for btn in self.option_buttons:
                btn.config(state='disabled')
    
    def timeout_answer(self):
        """处理答题超时"""
        if self.websocket and self.game_started:
            asyncio.create_task(self.send_message({
                'type': 'answer',
                'answer': '',  # 空答案表示超时
                'time': self.answer_timeout
            }))
            # 禁用所有按钮
            for btn in self.option_buttons:
                btn.config(state='disabled')
            self.status_label.config(text="答题超时！")
    
    async def connect_to_server(self):
        try:
            host = self.host_entry.get().strip()
            port = int(self.port_entry.get().strip())
            self.websocket = await websockets.connect(f'ws://{host}:{port}')
            await self.websocket.send(self.name)
            asyncio.create_task(self.receive_messages())
        except Exception as e:
            self.login_error_label.config(text=str(e))
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
    
    async def send_message(self, message: dict):
        if self.websocket:
            await self.websocket.send(json.dumps(message))
    
    def get_player_display_name(self, player_name):
        """获取玩家显示名称"""
        if player_name == self.name:
            return "你"
        return "对方"
    
    async def receive_messages(self):
        try:
            while True:
                raw_message = await self.websocket.recv()
                message = json.loads(raw_message)
                message_type = message['type']
                
                if message_type == 'name_taken':
                    self.login_error_label.config(text=message['message'])
                    await self.websocket.close()
                    self.websocket = None
                    return
                
                elif message_type == 'game_config':
                    # 保存总回合数和答题时间限制
                    self.total_rounds = message['total_rounds']
                    self.answer_timeout = message['answer_timeout']
                
                elif message_type == 'players_update':
                    # 更新对手名字
                    old_opponent = self.opponent_name
                    other_players = [name for name in message['players'] if name != self.name]
                    self.opponent_name = other_players[0] if other_players else None
                    
                    # 显示玩家名字
                    if len(message['players']) == 2:
                        self.players_label.config(
                            text=f"{self.name} (你) vs {self.opponent_name}"
                        )
                        if not old_opponent and self.opponent_name:
                            self.status_label.config(text=f"{self.opponent_name} 加入了游戏")
                            # 重置游戏相关状态，准备新游戏
                            self.game_started = False
                            self.can_answer = False
                            self.ready_button.config(state='normal')
                            # 清空选项按钮
                            for btn in self.option_buttons:
                                btn.config(text="", state='normal', bg='SystemButtonFace')
                    else:
                        self.players_label.config(text="等待玩家加入...")
                        if old_opponent:
                            self.status_label.config(text=f"{old_opponent} 断开了连接")
                    
                    # 连接成功，切换到游戏界面
                    if self.login_frame.winfo_ismapped():
                        self.login_frame.pack_forget()
                        self.game_frame.pack(expand=True, fill='both')
                
                elif message_type == 'player_ready':
                    player_display = self.get_player_display_name(message['player'])
                    self.status_label.config(
                        text=f"{player_display} 已准备"
                    )
                
                elif message_type == 'game_start':
                    self.game_started = True
                    self.word_label.config(text="游戏开始！", font=self.result_font)
                    self.status_label.config(text="游戏开始！")
                    # 等待一段时间后清除"游戏开始"提示
                    await asyncio.sleep(Config.GAME_START_DELAY)
                    if not self.running:  # 如果程序正在退出，不再更新UI
                        return
                    self.word_label.config(text="", font=self.word_font)
                
                elif message_type == 'answer_feedback':
                    # 立即显示答题结果
                    selected_answer = message['answer']
                    is_correct = message['is_correct']
                    
                    # 只标记选中的答案
                    for btn in self.option_buttons:
                        if btn.cget('text')[3:] == selected_answer:
                            btn.config(bg="light green" if is_correct else "pink")
                            break
                
                elif message_type == 'round_result':
                    if not self.running:  # 如果程序正在退出，不再更新UI
                        return
                    # 取消超时定时器
                    if self.answer_timer:
                        self.root.after_cancel(self.answer_timer)
                        self.answer_timer = None
                        
                    result_text = ""
                    if message['both_correct']:
                        if message['winner']:
                            if message['winner'] == self.name:
                                result_text = f"你更快！(+{message['score_added']}分)"
                            else:
                                result_text = f"对方更快！(对方+{message['score_added']}分)"
                        else:
                            result_text = "双方用时相同，均不得分"
                    elif message['winner']:
                        if message['winner'] == self.name:
                            result_text = f"答对了！(+{message['score_added']}分)"
                        else:
                            result_text = f"对方答对了！(对方+{message['score_added']}分)"
                    else:
                        result_text = f"双方都答错了！正确答案是：{message['correct_answer']}"
                    
                    self.status_label.config(text=result_text)
                    
                    # 显示正确答案
                    for btn in self.option_buttons:
                        if btn.cget('text')[3:] == message['correct_answer']:
                            btn.config(bg="light green")
                            break
                    
                    # 更新上一题信息
                    self.last_word_label.config(
                        text=f"上一题：{message['word']}"
                    )
                    
                    # 等待显示结果
                    await asyncio.sleep(Config.RESULT_DISPLAY_DELAY)
                
                elif message_type == 'new_round':
                    # 设置可以答题
                    self.can_answer = True
                    
                    # 显示新的单词和选项
                    self.word_label.config(text=message['word'], font=self.word_font)
                    
                    # 显示音标（根据配置选择英式或美式）
                    pron_type = self.config.get('pronunciation_type', 'uk')
                    pronunciation = message['pronunciation'][pron_type]
                    self.pronunciation_label.config(text=f"/{pronunciation}/")
                    
                    # 更新上一个单词的显示
                    if hasattr(self, 'last_word') and hasattr(self, 'last_meaning'):
                        self.last_word_label.config(text=f"上一题：{self.last_word} - {self.last_meaning}")
                    
                    # 保存当前单词信息用于下一轮显示
                    self.last_word = message['word']
                    self.last_meaning = message['meaning']
                    
                    # 显示选项
                    for i, option in enumerate(message['options']):
                        self.option_buttons[i].config(
                            text=f"{i+1}. {option}",
                            state='normal',
                            bg='SystemButtonFace'
                        )
                    
                    # 显示回合数和倍数信息
                    round_text = f"第 {message['round']}/{self.total_rounds} 轮"
                    if message.get('multiplier', 1.0) > 1:
                        round_text += f" (得分×{message['multiplier']})"
                    self.status_label.config(text=round_text)
                    
                    # 更新比分
                    scores = message['scores']
                    scores_text = f"{self.name}: {scores[self.name]}分 vs {self.opponent_name}: {scores[self.opponent_name]}分"
                    self.score_label.config(text=scores_text)
                    
                    # 记录开始时间并设置超时
                    self.question_start_time = time.time()
                    self.answer_timer = self.root.after(self.answer_timeout, self.timeout_answer)
                
                elif message_type == 'wrong_answer':
                    if not self.running:  # 如果程序正在退出，不再更新UI
                        return
                    if message['player'] == self.name:
                        self.status_label.config(text="回答错误！")
                
                elif message_type == 'game_over':
                    if not self.running:  # 如果程序正在退出，不再更新UI
                        return
                    scores = message['scores']
                    
                    # 检查是否因为对手断开连接而结束
                    if 'reason' in message:
                        was_game_in_progress = self.game_started  # 保存当前游戏状态
                        if was_game_in_progress:  # 只在游戏已开始时显示"游戏结束"
                            self.word_label.config(text="游戏结束", font=self.result_font)
                            self.status_label.config(text=message['reason'])
                        else:
                            self.word_label.config(text="")
                            # 如果游戏还没开始，就不显示"游戏结束"字样
                            self.status_label.config(text=f"玩家 {self.opponent_name} 断开了连接")
                        # 重置游戏状态
                        self.reset_game_state()
                        continue  # 继续等待新消息
                    
                    # 正常游戏结束时重置状态
                    self.game_started = False
                    
                    # 检查是否因为对手断开连接而结束
                    if self.opponent_name and self.opponent_name in scores:
                        scores_text = f"{self.name}: {scores[self.name]}分 vs {self.opponent_name}: {scores[self.opponent_name]}分"
                    else:
                        scores_text = f"{self.name}: {scores[self.name]}分"
                    
                    if message['is_tie']:
                        self.word_label.config(text="平局！", font=self.result_font)
                    else:
                        winner = message['winners'][0]
                        if winner == self.name:
                            self.word_label.config(text="你赢了！", font=self.result_font)
                        else:
                            self.word_label.config(text="你输了！", font=self.result_font)
                    
                    self.status_label.config(text=f"最终比分：{scores_text}")
                    
                    # 重置准备按钮
                    self.ready_button.config(state='normal')
                    # 清空选项和音标
                    for btn in self.option_buttons:
                        btn.config(text="")
                    self.pronunciation_label.config(text="")
        
        except websockets.exceptions.ConnectionClosed:
            if not self.running:  # 如果程序正在退出，不再更新UI
                return
            if self.game_frame.winfo_ismapped():
                self.word_label.config(text="连接已断开", font=self.result_font)
                self.status_label.config(text="与服务器的连接已断开")
            self.websocket = None
        except Exception as e:
            if not self.running:
                return
            if self.game_frame.winfo_ismapped():
                self.word_label.config(text="发生错误", font=self.result_font)
                self.status_label.config(text=f"错误：{str(e)}")
            self.websocket = None

    def reset_game_state(self):
        """重置游戏状态"""
        self.game_started = False
        self.can_answer = False
        self.opponent_name = None  # 重置对手名字
        if hasattr(self, 'last_word'):
            delattr(self, 'last_word')
        if hasattr(self, 'last_meaning'):
            delattr(self, 'last_meaning')
        
        # 重置选项按钮
        for btn in self.option_buttons:
            btn.config(text="", state='normal', bg='SystemButtonFace')
        
        # 重置音标和比分显示
        self.pronunciation_label.config(text="")
        self.score_label.config(text="")
        self.last_word_label.config(text="")
        self.ready_button.config(state='normal')
        
        # 取消定时器
        if self.answer_timer:
            self.root.after_cancel(self.answer_timer)
            self.answer_timer = None
        
        # 重置玩家标签
        self.players_label.config(text="等待玩家加入...")

    def on_closing(self):
        """处理窗口关闭事件"""
        self.running = False
        if self.websocket:
            # 发送退出消息
            asyncio.create_task(self.send_message({
                'type': 'disconnect'
            }))
            # 关闭连接
            asyncio.create_task(self.websocket.close())
        self.root.quit()
        self.root.destroy()

async def main():
    root = tk.Tk()
    client = WordPKClient(root)
    
    # 创建一个事件循环来处理tkinter的更新
    while client.running:
        root.update()
        await asyncio.sleep(0.1)
    
    # 程序结束时确保WebSocket连接已关闭
    if client.websocket:
        await client.websocket.close()

if __name__ == "__main__":
    asyncio.run(main()) 