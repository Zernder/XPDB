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
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: {filename} is empty or invalid. Returning empty dictionary.")
        return {}

def SaveJson(filename: str, data: dict) -> None:
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

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
            # Now, the callback is correctly tied to the value of 'i' by passing 'i' explicitly to the handler
            button.callback = self.create_response_callback(i)
            self.add_item(button)

    def create_response_callback(self, idx: int):
        async def response_callback(interaction: discord.Interaction):
            await self.handle_response(interaction, idx)
        return response_callback

    async def handle_response(self, interaction: discord.Interaction, chosen_index: int):
        if interaction.user.id in self.answered_users:
            await interaction.response.send_message("You've already answered this question!", ephemeral=True)
            return

        self.answered_users[interaction.user.id] = chosen_index
        correct = chosen_index == self.correct_index
        await self.quiz_callback(interaction, correct, self.choices[self.correct_index])

class Quiz(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.data: Dict = LoadJson("DataFiles/quiz-data.json")
        self.questions: List[Dict] = LoadJson("DataFiles/questions.json")

        if not self.data:
            self.data = {
                "current_quiz": {},
                "points": {},
                "quiz_time": "06:00",  # When to run the quiz (24-hour format)
                "reveal_time": "18:00",  # When to reveal answers (24-hour format)
                "quiz_channel_id": None
            }
            SaveJson("DataFiles/quiz-data.json", self.data)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()
        print("Quiz System Online")
        self.check_quiz_time.start()
 
    @tasks.loop(minutes=1)
    async def check_quiz_time(self):
        try:
            # Get the current time in Arizona time (MST)
            arizona_tz = pytz.timezone("US/Arizona")
            current_time = datetime.now(arizona_tz)

            # Parse the scheduled quiz time
            quiz_time_str = self.data.get("quiz_time", "00:00")
            quiz_time = datetime.strptime(quiz_time_str, "%H:%M")  # Parse to datetime object

            # Combine the current date with the scheduled quiz time (use current date but set the time part)
            quiz_time_today = current_time.replace(hour=quiz_time.hour, minute=quiz_time.minute, second=0, microsecond=0)

            # Define the 10-minute window (±5 minutes)
            start_window = quiz_time_today - timedelta(minutes=5)
            end_window = quiz_time_today + timedelta(minutes=5)

            # Check if the current time is within the quiz time window
            if start_window <= current_time <= end_window:
                await self.start_quiz()

            # Check if it's time to reveal answers
            reveal_time_str = self.data.get("reveal_time", "18:00")
            reveal_time = datetime.strptime(reveal_time_str, "%H:%M")  # Parse to datetime object
            reveal_time_today = current_time.replace(hour=reveal_time.hour, minute=reveal_time.minute, second=0, microsecond=0)

            # If the current time is greater than or equal to the reveal time, and quiz answers are not revealed
            if current_time >= reveal_time_today and self.data["current_quiz"] and not self.data["current_quiz"].get("revealed", False):
                await self.reveal_answers()

        except Exception as e:
            print(f"Error in check_quiz_time: {e}")

    async def start_quiz(self):
        if not self.questions:
            print("Error: No questions available.")
            return

        if not self.data.get("quiz_channel_id"):
            print("Error: Quiz channel not set.")
            channel.send("Error: Quiz channel not set.", ephemeral=True, delete_after=5)
            return

        channel = self.client.get_channel(self.data["quiz_channel_id"])
        if not channel:
            print(f"Error: Invalid channel ID: {self.data['quiz_channel_id']}")
            return


        try:
            question = random.choice(self.questions)  # Randomly select a question
            channel.send(f"Selected question: {question['question']}", ephemeral=True, delete_after=10)

            # Saving the selected question data to the quiz state
            self.data["current_quiz"] = {
                "question": question["question"],
                "choices": question["choices"],
                "correct_index": question["correct_index"],
                "revealed": False,
                "answers": {}
            }
            SaveJson("DataFiles\quiz-data.json", self.data)  # Save updated quiz state

        except IndexError:
            print("Error: No questions available.")  # This will be raised if self.questions is empty.
        except Exception as e:
            print(f"Unexpected error occurred: {e}")  # Catch any other exceptions
            import traceback
            traceback.print_exc()  # This will print the full stack trace

        self.data["current_quiz"] = {
            "question": question["question"],
            "choices": question["choices"],
            "correct_index": question["correct_index"],
            "revealed": False,
            "answers": {}
        }
        SaveJson("DataFiles\quiz-data.json", self.data)

        print("Sending quiz to channel...")
        view = QuizView(
            question["question"],
            question["choices"],
            question["correct_index"],
            self.handle_quiz_callback
        )
        await channel.send("🎯 **Daily Quiz Time!**\n" + question["question"], view=view)

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
        
        SaveJson("DataFiles\quiz-data.json", self.data)
        await interaction.response.send_message(
            "✅ Correct!" if correct else f"❌ Wrong! The correct answer is: {correct_answer}", ephemeral=True, delete_after=True)

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
        SaveJson("DataFiles\quiz-data.json", self.data)
        # Reset current quiz after reveal
        self.data["current_quiz"] = {}
        SaveJson("DataFiles\quiz-data.json", self.data)

    @app_commands.command(name="set_quiz_channel", description="Set the channel for daily quizzes")
    @commands.has_permissions(administrator=True)
    async def set_quiz_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.data["quiz_channel_id"] = channel.id
        SaveJson("DataFiles\quiz-data.json", self.data)
        await interaction.response.send_message(f"Quiz channel set to {channel.mention}", ephemeral=True, delete_after=5)

    @app_commands.command(name="set_quiz_time", description="Set the daily quiz time (24-hour format, HH:MM)")
    @commands.has_permissions(administrator=True)
    async def set_quiz_time(self, interaction: discord.Interaction, time: str):
        try:
            datetime.strptime(time, "%H:%M")
            self.data["quiz_time"] = time
            SaveJson("DataFiles\quiz-data.json", self.data)
            await interaction.response.send_message(f"Daily quiz time set to {time}", ephemeral=True, delete_after=5)
        except ValueError:
            await interaction.response.send_message("Invalid time format. Please use HH:MM (24-hour format)")

    @app_commands.command(name="start_quiz", description="start the daily quiz")
    @commands.has_permissions(administrator=True)
    async def start_quiz_command(self, interaction: discord.Interaction):
        if not self.questions:
            print("Error: No questions available.")
            return

        if not self.data.get("quiz_channel_id"):
            print("Error: Quiz channel not set.")
            return

        channel = self.client.get_channel(self.data["quiz_channel_id"])
        if not channel:
            print(f"Error: Invalid channel ID: {self.data['quiz_channel_id']}")
            return

        print(f"Quiz channel found: {channel.name}")

        try:
            question = random.choice(self.questions)  # Randomly select a question
            print(f"Selected question: {question['question']}")
            print(f"Choices: {question['choices']}")

            # Saving the selected question data to the quiz state
            self.data["current_quiz"] = {
                "question": question["question"],
                "choices": question["choices"],
                "correct_index": question["correct_index"],
                "revealed": False,
                "answers": {}
            }
            SaveJson("DataFiles\quiz-data.json", self.data)  # Save updated quiz state

        except IndexError:
            print("Error: No questions available.")  # This will be raised if self.questions is empty.
        except Exception as e:
            print(f"Unexpected error occurred: {e}")  # Catch any other exceptions
            import traceback
            traceback.print_exc()  # This will print the full stack trace

        self.data["current_quiz"] = {
            "question": question["question"],
            "choices": question["choices"],
            "correct_index": question["correct_index"],
            "revealed": False,
            "answers": {}
        }
        SaveJson("DataFiles/quiz-data.json", self.data)

        await interaction.response.send_message(f"Sending quiz to channel...", ephemeral=True, delete_after=20)
        print("Sending quiz to channel...")
        view = QuizView(
            question["question"],
            question["choices"],
            question["correct_index"],
            self.handle_quiz_callback
        )
        await channel.send("🎯 **Daily Quiz Time!**\n" + question["question"], view=view)


async def setup(client):
    await client.add_cog(Quiz(client))
    print("Quiz System Online")
