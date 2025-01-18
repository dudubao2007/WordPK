from dataclasses import dataclass
from typing import Dict, Set
import asyncio
import json
import random
import websockets

class Config:
    # 游戏配置
    TOTAL_ROUNDS = 9  # 总回合数
    MIN_DIFFICULTY = 1  # 最小题目难度
    ANSWER_TIMEOUT = 10000  # 答题超时时间（毫秒）
    SPECIAL_NOS = [(-1, 1.6)]  # 特殊题目配置：(题号, 倍数)，-1表示最后一题
    
    # 计分规则
    QUICK_ANSWER_TIME = 1000  # 快速答题时间阈值（毫秒）
    QUICK_ANSWER_SCORE = 120  # 快速答题得分
    SLOW_ANSWER_TIME = 8000  # 慢速答题时间阈值（毫秒）
    SLOW_ANSWER_SCORE = 50  # 慢速答题最低得分
    
    # 双方都答对时的计分规则
    BASE_SCORE = 30  # 基础分数
    TIME_DIFF_MULTIPLIER = 7  # 时间差分数乘数（每秒）
    MAX_SCORE_DIFF = 42  # 最大分数差值（BASE_SCORE + MAX_SCORE_DIFF = 最高可得分数）
    
    # 网络配置
    DEFAULT_PORT = 8766

@dataclass
class Player:
    websocket: websockets.WebSocketServerProtocol
    name: str
    score: int = 0
    ready: bool = False

class WordPKGame:
    def __init__(self):
        # 加载词汇表
        with open('vocabulary.json', 'r', encoding='utf-8') as f:
            self.vocabulary = json.load(f)
        
        self.players: Dict[str, Player] = {}  # websocket -> Player
        self.current_word = None
        self.current_answer = None
        self.round = 0
        self.game_in_progress = False
        self.answered_players: Dict[str, tuple] = {}  # websocket -> (answer, time)
        self.round_timer = None  # 用于存储轮次超时任务
    
    def reset_game(self):
        """重置游戏状态"""
        self.current_word = None
        self.current_answer = None
        self.round = 0
        self.game_in_progress = False
        self.answered_players.clear()
        if self.round_timer:
            self.round_timer.cancel()
            self.round_timer = None
        for player in self.players.values():
            player.score = 0
            player.ready = False
    
    def calculate_score(self, answer_time: int) -> int:
        """根据答题时间计算得分"""
        if answer_time <= Config.QUICK_ANSWER_TIME:
            return Config.QUICK_ANSWER_SCORE
        elif answer_time >= Config.SLOW_ANSWER_TIME:
            return Config.SLOW_ANSWER_SCORE
        else:
            # 线性插值：1秒得120分，8秒得50分
            return Config.QUICK_ANSWER_SCORE - (
                (answer_time - Config.QUICK_ANSWER_TIME) / 
                (Config.SLOW_ANSWER_TIME - Config.QUICK_ANSWER_TIME)
            ) * (Config.QUICK_ANSWER_SCORE - Config.SLOW_ANSWER_SCORE)
    
    def get_random_word(self) -> dict:
        """获取随机单词和选项"""
        # 筛选难度大于1的题目
        hard_words = [word for word in self.vocabulary if word.get('difficulty', 0) > Config.MIN_DIFFICULTY]
        word_data = random.choice(hard_words)
        correct_answer = word_data['options'][0]  # 第一个选项总是正确答案
        wrong_options = word_data['options'][1:]  # 其他选项
        random.shuffle(wrong_options)  # 打乱错误选项
        selected_wrong_options = wrong_options[:3]  # 选择三个错误选项
        
        # 组合所有选项并打乱
        all_options = [correct_answer] + selected_wrong_options
        random.shuffle(all_options)
        
        return {
            'word': word_data['word'],
            'options': all_options,
            'correct_answer': correct_answer
        }
    
    async def handle_player_disconnect(self, websocket):
        """处理玩家断开连接"""
        if websocket in self.players:
            player = self.players[websocket]
            print(f"玩家 {player.name} 断开连接")
            
            # 如果游戏正在进行，先结束游戏
            if self.game_in_progress:
                self.game_in_progress = False
                # 取消当前轮次的定时器
                if self.round_timer:
                    self.round_timer.cancel()
                    self.round_timer = None
                
                # 重置所有游戏相关状态
                self.current_word = None
                self.current_answer = None
                self.round = 0
                self.answered_players.clear()
                
                # 重置所有玩家状态
                for p in self.players.values():
                    p.score = 0
                    p.ready = False
            
            # 获取其他玩家
            other_players = {ws: p for ws, p in self.players.items() if ws != websocket}
            
            # 通知其他玩家有玩家离开并重置他们的游戏状态
            if other_players:
                try:
                    await asyncio.gather(
                        *[p.websocket.send(json.dumps({
                            'type': 'game_over',
                            'reason': f"玩家 {player.name} 断开连接，游戏结束",
                            'scores': {p.name: p.score for p in other_players.values()},
                            'reset_game': True  # 添加标志通知客户端重置游戏状态
                        })) for p in other_players.values()]
                    )
                    
                    # 更新玩家列表
                    await asyncio.gather(
                        *[p.websocket.send(json.dumps({
                            'type': 'players_update',
                            'players': [p.name for p in other_players.values()]
                        })) for p in other_players.values()]
                    )
                except websockets.exceptions.ConnectionClosed:
                    pass  # 忽略发送消息时的连接关闭错误
            
            # 最后才删除玩家
            del self.players[websocket]
            try:
                await websocket.close()
            except:
                pass  # 忽略关闭连接时的错误
    
    def all_players_ready(self) -> bool:
        return len(self.players) == 2 and all(p.ready for p in self.players.values())
    
    def get_round_multiplier(self) -> float:
        """获取当前回合的分数倍数"""
        current_round_zero_based = self.round - 1  # 转换为从0开始的轮数
        for round_no, multiplier in Config.SPECIAL_NOS:
            # 如果是负数，从最后一题往前数
            actual_round = round_no if round_no >= 0 else Config.TOTAL_ROUNDS + round_no
            if current_round_zero_based == actual_round:
                return multiplier
        return 1.0

async def broadcast_message(game: WordPKGame, message: dict):
    """向所有玩家广播消息"""
    if game.players:
        try:
            await asyncio.gather(
                *[player.websocket.send(json.dumps(message))
                  for player in game.players.values()]
            )
        except websockets.exceptions.ConnectionClosed:
            pass  # 忽略发送消息时的连接关闭错误

async def start_game(game: WordPKGame):
    """开始游戏"""
    await broadcast_message(game, {'type': 'game_start'})
    await next_round(game)

async def next_round(game: WordPKGame):
    """进入下一轮"""
    game.answered_players.clear()
    game.round += 1
    
    if game.round <= Config.TOTAL_ROUNDS:
        word_data = game.get_random_word()
        game.current_word = word_data['word']
        game.current_answer = word_data['correct_answer']
        
        # 设置轮次超时检查
        game.round_timer = asyncio.create_task(check_round_timeout(game))
        
        # 获取当前回合的倍数
        multiplier = game.get_round_multiplier()
        
        await broadcast_message(game, {
            'type': 'new_round',
            'round': game.round,
            'word': word_data['word'],
            'options': word_data['options'],
            'scores': {p.name: p.score for p in game.players.values()},
            'multiplier': multiplier  # 添加倍数信息
        })
    else:
        # 游戏结束
        scores = {p.name: p.score for p in game.players.values()}
        max_score = max(scores.values())
        winners = [name for name, score in scores.items() if score == max_score]
        
        await broadcast_message(game, {
            'type': 'game_over',
            'scores': scores,
            'winners': winners,
            'is_tie': len(winners) > 1
        })
        game.reset_game()

async def process_round_result(game: WordPKGame):
    """处理本轮结果并计算分数"""
    correct_players = []  # [(player, time), ...]
    wrong_players = []    # [(player, answer, time), ...]
    
    # 分类答题结果
    for ws, (answer, time) in game.answered_players.items():
        player = game.players[ws]
        if answer == game.current_answer:
            correct_players.append((player, time))
        else:
            wrong_players.append((player, answer, time))
    
    # 获取当前回合的倍数
    multiplier = game.get_round_multiplier()
    
    # 计算得分
    if len(correct_players) == 2:  # 双方都答对
        # 按时间排序
        correct_players.sort(key=lambda x: x[1])
        if correct_players[0][1] == correct_players[1][1]:
            # 用时相同，都不得分
            score_added = 0
            winner = None
        else:
            # 计算时间差（秒）
            time_diff = (correct_players[1][1] - correct_players[0][1]) / 1000
            score_added = round(min(
                Config.BASE_SCORE + time_diff * Config.TIME_DIFF_MULTIPLIER,
                Config.BASE_SCORE + Config.MAX_SCORE_DIFF
            ) * multiplier)  # 应用倍数
            winner = correct_players[0][0]
            winner.score += score_added
        
        await broadcast_message(game, {
            'type': 'round_result',
            'both_correct': True,
            'winner': winner.name if winner else None,
            'score_added': score_added,
            'correct_answer': game.current_answer,
            'word': game.current_word,
            'is_last_round': game.round == Config.TOTAL_ROUNDS
        })
    
    elif len(correct_players) == 1:  # 只有一人答对
        winner = correct_players[0][0]
        score_added = round(game.calculate_score(correct_players[0][1]) * multiplier)  # 应用倍数
        winner.score += score_added
        
        await broadcast_message(game, {
            'type': 'round_result',
            'both_correct': False,
            'winner': winner.name,
            'score_added': score_added,
            'correct_answer': game.current_answer,
            'wrong_answer': wrong_players[0][1] if wrong_players else None,
            'word': game.current_word,
            'is_last_round': game.round == Config.TOTAL_ROUNDS
        })
    
    else:  # 都答错或超时
        await broadcast_message(game, {
            'type': 'round_result',
            'both_correct': False,
            'winner': None,
            'correct_answer': game.current_answer,
            'word': game.current_word,
            'is_last_round': game.round == Config.TOTAL_ROUNDS
        })
    
    # 进入下一轮
    await next_round(game)

async def check_round_timeout(game: WordPKGame):
    """检查轮次是否超时"""
    await asyncio.sleep(20)  # 等待20秒
    if game.game_in_progress:
        disconnected_players = []
        # 检查是否有玩家未答题
        for ws in game.players:
            if ws not in game.answered_players:
                try:
                    # 尝试发送一个ping消息
                    pong_waiter = await ws.ping()
                    try:
                        await asyncio.wait_for(pong_waiter, timeout=1.0)
                    except asyncio.TimeoutError:
                        # 如果1秒内没有收到pong响应，认为客户端已断开
                        disconnected_players.append(ws)
                        continue
                except websockets.exceptions.ConnectionClosed:
                    disconnected_players.append(ws)
                    continue
                # 如果客户端还在线，添加超时答案
                game.answered_players[ws] = ('', 10000)
        
        # 处理断开连接的玩家
        for ws in disconnected_players:
            await game.handle_player_disconnect(ws)
        
        # 如果还有玩家在线，处理本轮结果
        if len(game.players) > 0:
            await process_round_result(game)

async def main():
    game = WordPKGame()
    
    async def handle_client(websocket):
        try:
            # 检查是否已有两个玩家
            if len(game.players) >= 2:
                try:
                    await websocket.send(json.dumps({
                        'type': 'name_taken',
                        'message': '游戏房间已满，请稍后再试'
                    }))
                    await websocket.close(code=4000, reason='游戏房间已满')
                except:
                    pass
                return
            
            # 等待客户端发送名字
            try:
                name = await websocket.recv()
            except websockets.exceptions.ConnectionClosed:
                return
            
            # 检查是否有同名玩家
            if any(p.name == name for p in game.players.values()):
                await websocket.send(json.dumps({
                    'type': 'name_taken',
                    'message': '该名字已被使用，请使用其他名字'
                }))
                await websocket.close(code=4001, reason='名字已被使用')
                return
            
            player = Player(websocket=websocket, name=name)
            game.players[websocket] = player
            
            print(f"玩家 {name} 已连接")
            
            # 发送游戏配置信息
            await websocket.send(json.dumps({
                'type': 'game_config',
                'total_rounds': Config.TOTAL_ROUNDS,
                'answer_timeout': Config.ANSWER_TIMEOUT  # 使用正确的超时时间
            }))
            
            # 通知所有玩家有新玩家加入
            player_names = [p.name for p in game.players.values()]
            await broadcast_message(game, {
                'type': 'players_update',
                'players': player_names
            })
            
            # 通知新玩家已准备的玩家状态
            ready_players = [p.name for p in game.players.values() if p.ready]
            for ready_player in ready_players:
                await websocket.send(json.dumps({
                    'type': 'player_ready',
                    'player': ready_player
                }))
            
            # 主消息循环
            async for message in websocket:
                data = json.loads(message)
                
                if data['type'] == 'disconnect':
                    # 收到客户端的退出消息
                    print(f"收到玩家 {player.name} 的退出消息")
                    await game.handle_player_disconnect(websocket)
                    return
                
                elif data['type'] == 'ready':
                    player.ready = True
                    await broadcast_message(game, {
                        'type': 'player_ready',
                        'player': player.name
                    })
                    
                    # 检查是否所有玩家都准备好了
                    if game.all_players_ready() and not game.game_in_progress:
                        game.game_in_progress = True
                        asyncio.create_task(start_game(game))
                
                elif data['type'] == 'answer':
                    if game.game_in_progress and websocket not in game.answered_players:
                        answer = data['answer']
                        answer_time = data['time']
                        game.answered_players[websocket] = (answer, answer_time)
                        
                        try:
                            # 只向答题玩家发送答题反馈
                            await websocket.send(json.dumps({
                                'type': 'answer_feedback',
                                'answer': answer,
                                'is_correct': answer == game.current_answer
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            await game.handle_player_disconnect(websocket)
                            return
                        
                        # 如果所有玩家都已答题，进入下一轮
                        if len(game.answered_players) == len(game.players):
                            # 取消轮次超时定时器
                            if game.round_timer:
                                game.round_timer.cancel()
                                game.round_timer = None
                            await process_round_result(game)
        
        except websockets.exceptions.ConnectionClosed:
            await game.handle_player_disconnect(websocket)
        except Exception as e:
            print(f"处理客户端消息时发生错误: {e}")
            await game.handle_player_disconnect(websocket)
    
    async with websockets.serve(handle_client, "localhost", Config.DEFAULT_PORT):
        print("服务器已启动：ws://localhost:8766")
        await asyncio.Future()  # 运行到被中断

if __name__ == "__main__":
    asyncio.run(main()) 