import tkinter as tk
from tkinter import ttk
import json
import random

class VocabularyQuiz:
    def __init__(self, root):
        self.root = root
        self.root.title("单词测试")
        self.root.geometry("800x600")  # 增大窗口尺寸
        
        # 设置字体
        self.word_font = ("SimSun", 36, "bold")  # 单词显示用的字体
        self.pronunciation_font = ("SimSun", 18)  # 音标显示用的字体
        self.option_font = ("SimSun", 14)        # 选项用的字体
        self.info_font = ("SimSun", 12)          # 信息显示用的字体
        
        # 加载词汇表和配置
        with open('vocabulary.json', 'r', encoding='utf-8') as f:
            self.vocabulary = json.load(f)
        with open('config.json', 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # 初始化时就打乱词汇顺序
        random.shuffle(self.vocabulary)
        
        # 初始化统计数据
        self.correct_count = 0
        self.wrong_count = 0
        self.current_word_index = 0
        self.current_options = []
        self.correct_answer = ""
        self.last_word = ""
        self.last_answer = ""
        
        # 创建界面元素
        self.create_widgets()
        
        # 显示第一个问题
        self.show_next_question()
        
        # 绑定键盘事件
        self.root.bind('1', lambda e: self.check_answer(0))
        self.root.bind('2', lambda e: self.check_answer(1))
        self.root.bind('3', lambda e: self.check_answer(2))
        self.root.bind('4', lambda e: self.check_answer(3))
    
    def create_widgets(self):
        # 创建主框架
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # 创建单词显示标签
        self.word_label = tk.Label(self.main_frame, text="", font=self.word_font)
        self.word_label.pack(pady=10)
        
        # 创建音标显示标签
        self.pronunciation_label = tk.Label(self.main_frame, text="", font=self.pronunciation_font)
        self.pronunciation_label.pack(pady=5)
        
        # 创建选项按钮
        self.option_buttons = []
        for i in range(4):
            btn = tk.Button(self.main_frame, text="", width=40, height=2,
                          font=self.option_font,
                          command=lambda x=i: self.check_answer(x))
            btn.pack(pady=10)
            self.option_buttons.append(btn)
        
        # 创建统计信息显示
        self.stats_frame = tk.Frame(self.main_frame)
        self.stats_frame.pack(pady=20)
        
        self.correct_label = tk.Label(self.stats_frame, text="正确: 0", font=self.info_font)
        self.correct_label.pack(side=tk.LEFT, padx=10)
        
        self.wrong_label = tk.Label(self.stats_frame, text="错误: 0", font=self.info_font)
        self.wrong_label.pack(side=tk.LEFT, padx=10)
        
        self.accuracy_label = tk.Label(self.stats_frame, text="正确率: 0%", font=self.info_font)
        self.accuracy_label.pack(side=tk.LEFT, padx=10)
        
        # 创建上一题信息显示（右下角）
        self.last_word_frame = tk.Frame(self.root)
        self.last_word_frame.pack(side=tk.BOTTOM, anchor=tk.SE, padx=10, pady=10)
        self.last_word_label = tk.Label(self.last_word_frame, text="", font=self.info_font, fg="gray")
        self.last_word_label.pack()
    
    def show_next_question(self):
        if self.current_word_index >= len(self.vocabulary):
            self.current_word_index = 0
            random.shuffle(self.vocabulary)
        
        word_data = self.vocabulary[self.current_word_index]
        self.word_label.config(text=word_data["word"])
        
        # 显示音标
        pron_type = self.config.get('pronunciation_type', 'uk')
        pronunciation = word_data["pronunciation"][pron_type]
        self.pronunciation_label.config(text=f"/{pronunciation}/")
        
        # 获取正确答案
        meanings = word_data["meanings"]
        if len(meanings) == 1:
            self.correct_answer = meanings[0]
        else:
            # 75%概率选择第一个，25%概率选择第二个
            self.correct_answer = meanings[0] if random.random() < 0.75 else meanings[1]
        
        # 获取错误选项
        options1 = [opt["meaning"] for opt in word_data["options1"]]
        options2 = [opt["meaning"] for opt in word_data["options2"]]
        random.shuffle(options1)
        random.shuffle(options2)
        wrong_options = options1[:2] + [options2[0]]  # 从options1选两个，从options2选一个
        
        # 组合并打乱选项
        self.current_options = [self.correct_answer] + wrong_options
        random.shuffle(self.current_options)
        
        # 更新按钮文本
        for i, option in enumerate(self.current_options):
            self.option_buttons[i].config(text=f"{i+1}. {option}", bg="SystemButtonFace")
    
    def check_answer(self, button_index):
        selected_answer = self.current_options[button_index]
        current_word = self.word_label.cget("text")
        
        if selected_answer == self.correct_answer:
            self.correct_count += 1
            self.option_buttons[button_index].config(bg="light green")
        else:
            self.wrong_count += 1
            self.option_buttons[button_index].config(bg="pink")
            # 显示正确答案
            correct_index = self.current_options.index(self.correct_answer)
            self.option_buttons[correct_index].config(bg="light green")
        
        # 更新统计信息
        total = self.correct_count + self.wrong_count
        accuracy = (self.correct_count / total * 100) if total > 0 else 0
        
        self.correct_label.config(text=f"正确: {self.correct_count}")
        self.wrong_label.config(text=f"错误: {self.wrong_count}")
        self.accuracy_label.config(text=f"正确率: {accuracy:.1f}%")
        
        # 保存当前题目信息，用于下一题显示
        word_data = self.vocabulary[self.current_word_index]
        self.last_word = current_word
        self.last_answer = word_data["meaning"]  # 使用meaning字段作为答案显示
        
        # 延迟显示下一题
        self.root.after(1000, self.next_question)
    
    def next_question(self):
        # 更新上一题信息
        if self.last_word:
            self.last_word_label.config(text=f"上一题: {self.last_word} = {self.last_answer}")
        
        self.current_word_index += 1
        self.show_next_question()

if __name__ == "__main__":
    root = tk.Tk()
    quiz = VocabularyQuiz(root)
    root.mainloop() 