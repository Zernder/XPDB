import discord
import asyncio
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import os
import random
from typing import List, Dict
import pytz

def LoadJson(filename: str) -> dict:
    """
    Loads JSON data from a file. If the file doesn't exist or is invalid, it returns an empty dictionary.
    """
    if not os.path.exists(filename):
        print(f"Warning: {filename} does not exist. Returning an empty dictionary.")
        return {}

    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: {filename} is empty or contains invalid JSON. Returning an empty dictionary.")
        return {}
    except Exception as e:
        print(f"Unexpected error while loading {filename}: {e}")
        return {}

def SaveJson(filename: str, data: dict) -> None:
    """
    Saves a dictionary to a file in JSON format. Ensures the directory exists.
    """
    # Ensure the directory exists
    folder = os.path.dirname(filename)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)

    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error: Failed to save data to {filename}. Exception: {e}")


class QuizView(discord.ui.View):
    def __init__(self, question: str, choices: List[str], correct_index: int, quiz_callback):
        super().__init__(timeout=None)  # No timeout for quiz buttons
        self.question = question
        self.choices = choices
        self.correct_index = correct_index
        self.quiz_callback = quiz_callback
        self.answered_users = {}
        
        for i, choice in enumerate(choices):
            button = discord.ui.Button(label=choice, style=discord.ButtonStyle.primary, custom_id=f"choice_{i}")
            button.callback = self.create_response_callback(i)
            self.add_item(button)

    def create_response_callback(self, idx: int):
        async def response_callback(interaction: discord.Interaction):
            await self.handle_response(interaction, idx)
        return response_callback

    async def handle_response(self, interaction: discord.Interaction, chosen_index: int):
        if interaction.user.id in self.answered_users:
            await interaction.response.send_message("You have already answered this question!", ephemeral=True, delete_after=5)
            return

        self.answered_users[interaction.user.id] = chosen_index
        correct = chosen_index == self.correct_index
        await self.quiz_callback(interaction, correct, self.choices[self.correct_index])

class Quiz(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.data: Dict = LoadJson("DataFiles/quiz-data.json")
        self.questions: Dict[str, List] = LoadJson("DataFiles/questions.json")
        self.used_questions: Dict[str, List] = LoadJson("DataFiles/used-questions.json")

        # Initialize default data if empty
        if not self.data:
            self.data = {
                "current_quiz": {},
                "points": {},
                "quiz_time": "06:00",
                "reveal_time": "18:00",
                "quiz_channel_id": None,
                "quiz_started": False,  # Ensure default is False
                "quiz_finished_today": False,
                "enabled_categories": ["General Knowledge"]
            }
            SaveJson("DataFiles/quiz-data.json", self.data)
        else:
            # Reset quiz_started if bot restarts with no active quiz
            if self.data.get("quiz_started") and not self.data.get("current_quiz"):
                self.data["quiz_started"] = False
                SaveJson("DataFiles/quiz-data.json", self.data)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()
        print("Quiz System Online")
        self.check_quiz_time.start()
 
    @tasks.loop(minutes=1)
    async def check_quiz_time(self):
        try:
            arizona_tz = pytz.timezone("US/Arizona")
            current_time = datetime.now(arizona_tz)

            # Parse quiz and reveal times as timezone-aware datetimes
            quiz_time = datetime.strptime(self.data["quiz_time"], "%H:%M").time()
            start_time_today = current_time.replace(
                hour=quiz_time.hour, minute=quiz_time.minute, second=0, microsecond=0
            )

            reveal_time = datetime.strptime(self.data["reveal_time"], "%H:%M").time()
            reveal_time_today = current_time.replace(
                hour=reveal_time.hour, minute=reveal_time.minute, second=0, microsecond=0
            )

            # Reset daily flags at midnight
            if current_time.hour == 0 and current_time.minute == 0:
                self.data["quiz_finished_today"] = False
                SaveJson("DataFiles/quiz-data.json", self.data)

            # Quiz Start Logic
            if (current_time >= start_time_today 
                and not self.data["quiz_started"]
                and not self.data["quiz_finished_today"]):
                
                self.data["quiz_started"] = True
                SaveJson("DataFiles/quiz-data.json", self.data)  # Immediate save
                
                success = await self.start_quiz()
                if not success:
                    self.data["quiz_started"] = False
                    self.data["quiz_finished_today"] = False
                    SaveJson("DataFiles/quiz-data.json", self.data)
                    print("Failed to start quiz, resetting state")

            # Answer Reveal Logic
            if (current_time >= reveal_time_today 
                and self.data["quiz_started"]
                and not self.data["current_quiz"].get("revealed", True)):
                
                await self.reveal_answers()
                self.data["quiz_started"] = False
                self.data["quiz_finished_today"] = True
                SaveJson("DataFiles/quiz-data.json", self.data)

        except Exception as e:
            print(f"Critical error in check_quiz_time: {e}")
            # Full state reset on critical failure
            self.data["quiz_started"] = False
            self.data["quiz_finished_today"] = False
            SaveJson("DataFiles/quiz-data.json", self.data)
            import traceback
            traceback.print_exc()

    def get_random_question(self) -> tuple:
        enabled_categories = self.data.get("enabled_categories", [])
        if not enabled_categories:
            return None, None
        
        # Select category weighted by question count
        available_questions = []
        for category in enabled_categories:
            available_questions.extend([(category, q) for q in self.questions.get(category, [])])
        
        if not available_questions:
            return None, None
        
        return random.choice(available_questions)

    async def start_quiz(self) -> bool:
        try:
            # Log initial state
            print(f"Start Quiz Called - Quiz Channel ID: {self.data.get('quiz_channel_id')}")
            print(f"Enabled Categories: {self.data.get('enabled_categories')}")

            # Initialize current quiz data
            self.data["current_quiz"] = {
                "answers": {},
                "revealed": False
            }

            # Channel validation with more detailed logging
            channel_id = self.data.get("quiz_channel_id")
            if not channel_id:
                print("FAILURE: No quiz channel set")
                return False

            channel = self.client.get_channel(channel_id)
            if not channel:
                print(f"FAILURE: Cannot find channel with ID {channel_id}")
                return False

            if not isinstance(channel, discord.TextChannel):
                print(f"FAILURE: Channel {channel_id} is not a text channel")
                return False

            # Detailed permission check
            bot_member = channel.guild.get_member(self.client.user.id)
            if not bot_member:
                print("FAILURE: Bot not found in guild")
                return False

            permissions = channel.permissions_for(bot_member)
            if not permissions.send_messages:
                print(f"FAILURE: No send messages permission in {channel.name}")
                return False

            # Question availability detailed logging
            enabled_categories = self.data.get("enabled_categories", [])
            print(f"Checking questions in categories: {enabled_categories}")

            total_questions = sum(len(self.questions.get(cat, [])) for cat in enabled_categories)
            print(f"Total questions available: {total_questions}")

            if total_questions == 0:
                print("FAILURE: No questions in enabled categories")
                print(f"Questions dict: {self.questions}")
                return False

            # Get and validate question with more logging
            category_result = self.get_random_question()
            if not category_result or not category_result[1]:
                print("FAILURE: No valid question found")
                return False

            category, question = category_result
            print(f"Selected Question - Category: {category}")
            print(f"Question: {question}")

            if "question" not in question or "choices" not in question:
                print("FAILURE: Invalid question format")
                print(f"Question details: {question}")
                return False

            # Prepare current quiz data
            self.data["current_quiz"].update({
                "question": question["question"],
                "choices": question["choices"],
                "correct_index": question["correct_index"],
                "category": category
            })
            SaveJson("DataFiles/quiz-data.json", self.data)

            # Send quiz message
            view = QuizView(
                question["question"],
                question["choices"],
                question["correct_index"],
                self.handle_quiz_callback
            )
            await channel.send("🎯 **Daily Quiz Time!**\n" + question["question"], view=view)
            
            # Move used question
            self.move_question_to_used(question, category)
            return True

        except Exception as e:
            print(f"CRITICAL FAILURE in start_quiz: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def move_question_to_used(self, question: dict, category: str):
        """Moves a used question from active pool to used-questions.json"""
        try:
            # Remove from active questions
            if category in self.questions and question in self.questions[category]:
                self.questions[category].remove(question)
                SaveJson("DataFiles/questions.json", self.questions)

            # Add to used questions
            if category not in self.used_questions:
                self.used_questions[category] = []
            self.used_questions[category].append(question)
            SaveJson("DataFiles/used-questions.json", self.used_questions)

        except Exception as e:
            print(f"Error moving question to used: {e}")
            import traceback
            traceback.print_exc()

    async def handle_quiz_callback(self, interaction: discord.Interaction, correct: bool, correct_answer: str):
        user_id = str(interaction.user.id)
        
        self.data["current_quiz"]["answers"][user_id] = {
            "correct": correct,
            "timestamp": datetime.now().isoformat()
        }
        
        if correct:
            if user_id not in self.data["points"]:
                self.data["points"][user_id] = 0
            self.data["points"][user_id] += 1
        
        SaveJson("DataFiles/quiz-data.json", self.data)
        await interaction.response.send_message(
            "✅ Correct!" if correct else f"❌ Wrong! The correct answer is: {correct_answer}", ephemeral=True, delete_after=60)

    async def reveal_answers(self):
        if not self.data["current_quiz"] or not self.data["quiz_channel_id"]:
            return

        channel = self.client.get_channel(self.data["quiz_channel_id"])
        if not channel:
            return

        correct_answer = self.data["current_quiz"]["choices"][self.data["current_quiz"]["correct_index"]]
        correct_users = [user_id for user_id, data in self.data["current_quiz"]["answers"].items() if data["correct"]]

        await channel.send(
            f"📊 **Quiz Results**\n"
            f"Question: {self.data['current_quiz']['question']}\n"
            f"Correct Answer: {correct_answer}\n"
            f"Number of correct answers: {len(correct_users)}\n"
            "\nCongratulations to everyone who got it right! 🎉"
        )

        self.data["current_quiz"]["revealed"] = True
        SaveJson("DataFiles/quiz-data.json", self.data)
        # Reset current quiz after reveal
        self.data["current_quiz"] = {}
        SaveJson("DataFiles/quiz-data.json", self.data)

    @app_commands.command(name="set_quiz_channel", description="Set the channel for daily quizzes")
    @commands.has_permissions(administrator=True)
    async def set_quiz_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.data["quiz_channel_id"] = channel.id
        SaveJson("DataFiles/quiz-data.json", self.data)
        await interaction.response.send_message(f"Quiz channel set to {channel.mention}", ephemeral=True, delete_after=5)

    @app_commands.command(name="set_quiz_time", description="Set the daily quiz start time (24-hour format, HH:MM)")
    @commands.has_permissions(administrator=True)
    async def set_quiz_time(self, interaction: discord.Interaction, start_time: str, end_time: str):
        try:
            # Parse start time and set seconds and microseconds to 0
            start_time_obj = datetime.strptime(start_time, "%H:%M").replace(second=0, microsecond=0)
            self.data["quiz_time"] = start_time_obj.strftime("%H:%M")  # Store the time as a string

            # Parse end time and set seconds and microseconds to 0
            end_time_obj = datetime.strptime(end_time, "%H:%M").replace(second=0, microsecond=0)
            self.data["reveal_time"] = end_time_obj.strftime("%H:%M")  # Store the time as a string

            # Save the updated data
            SaveJson("DataFiles/quiz-data.json", self.data)
            
            # Send a confirmation message
            await interaction.response.send_message(f"Daily quiz time set to {start_time} and results reveal time set to {end_time}", ephemeral=True, delete_after=10)
        except ValueError:
            await interaction.response.send_message("Invalid time format. Please use HH:MM (24-hour format)")

    @app_commands.command(name="start_quiz", description="start the daily quiz")
    @commands.has_permissions(administrator=True)
    async def start_quiz_command(self, interaction: discord.Interaction):
        # Initial state reset
        self.data["quiz_started"] = True
        SaveJson("DataFiles/quiz-data.json", self.data)
        
        try:
            success = await self.start_quiz()
            if success:
                await interaction.response.send_message("✅ Quiz started successfully!", ephemeral=True, delete_after=5)
                self.data["quiz_finished_today"] = False
                SaveJson("DataFiles/quiz-data.json", self.data)
            else:
                # Get failure reason
                failure_reason = self.get_failure_reason()
                await interaction.response.send_message(
                    f"❌ Failed to start quiz:\n{failure_reason}",
                    ephemeral=True,
                    delete_after=15
                )
        finally:
            if not self.data.get("current_quiz"):
                self.data["quiz_started"] = False
                SaveJson("DataFiles/quiz-data.json", self.data)

    def get_failure_reason(self) -> str:
        """Returns detailed failure explanation"""
        # Channel checks
        if not self.data.get("quiz_channel_id"):
            return "• No quiz channel set\nUse `/set_quiz_channel` first"
        
        channel = self.client.get_channel(self.data["quiz_channel_id"])
        if not channel:
            return "• Invalid channel ID\nRe-set with `/set_quiz_channel`"
        
        # Permission check
        if channel and not channel.permissions_for(channel.guild.me).send_messages:
            return "• Missing Send Messages permission\nCheck channel permissions"
        
        # Question checks
        enabled_categories = self.data.get("enabled_categories", [])
        if not enabled_categories:
            return "• No enabled categories\nUse `/enable_category`"
        
        total_questions = sum(len(self.questions.get(cat, [])) for cat in enabled_categories)
        if total_questions == 0:
            return "• No questions in enabled categories\nAdd questions or reset with `/reset_questions`"
        
        return "• Unknown error\nCheck console logs"


    @app_commands.command(name="points", description="Check your quiz points")
    async def show_points(self, interaction: discord.Interaction):
        """Displays the user's accumulated quiz points."""
        user_id = str(interaction.user.id)
        points = self.data["points"].get(user_id, 0)
        await interaction.response.send_message(f"🎉 You currently have **{points}** quiz points!", ephemeral=True)

    @app_commands.command(name="reset_questions", description="Reset all used questions back to active pool")
    @commands.has_permissions(administrator=True)
    async def reset_questions(self, interaction: discord.Interaction):
        # Move all used questions back to their categories
        for category in self.used_questions:
            if category not in self.questions:
                self.questions[category] = []
            self.questions[category].extend(self.used_questions[category])
        
        # Clear used questions
        self.used_questions = {category: [] for category in self.used_questions}
        
        SaveJson("DataFiles/questions.json", self.questions)
        SaveJson("DataFiles/used-questions.json", self.used_questions)
        
        await interaction.response.send_message("All questions have been reset!", ephemeral=True)

    @app_commands.command(name="force_reset_quiz", description="Emergency reset command")
    @commands.has_permissions(administrator=True)
    async def force_reset_quiz(self, interaction: discord.Interaction):
        """Emergency reset command"""
        self.data["quiz_started"] = False
        self.data["current_quiz"] = {}
        SaveJson("DataFiles/quiz-data.json", self.data)
        await interaction.response.send_message("✅ Quiz state forcibly reset", ephemeral=True)

async def setup(client):
    await client.add_cog(Quiz(client))
    print("Quiz System Online")
