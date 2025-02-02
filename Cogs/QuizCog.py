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
import aiohttp
import html

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
        self.category_mapping = {}

        if not self.data:
            self.data = {
                "current_quiz": {},
                "points": {},
                "quiz_time": "06:00",
                "reveal_time": "18:00",
                "quiz_channel_id": None,
                "quiz_started": False,
                "quiz_finished_today": False,
                "enabled_categories": ["General Knowledge"],
                "session_token": None
            }
            SaveJson("DataFiles/quiz-data.json", self.data)
        else:
            if self.data.get("quiz_started") and not self.data.get("current_quiz"):
                self.data["quiz_started"] = False
                SaveJson("DataFiles/quiz-data.json", self.data)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()
        print("Quiz System Online")
        await self.build_category_mapping()
        self.check_quiz_time.start()


    @tasks.loop(minutes=1)
    async def check_quiz_time(self):
        try:
            # Get the current time in Arizona time (MST)
            arizona_tz = pytz.timezone("US/Arizona")
            current_time = datetime.now(arizona_tz)

            # Set quiz start time to 6:00 AM
            quiz_time_str = self.data["quiz_time"]
            quiz_time = datetime.strptime(quiz_time_str, "%H:%M")
            start_time_today = current_time.replace(hour=quiz_time.hour, minute=quiz_time.minute, second=0, microsecond=0)
            # Parse quiz and reveal times as timezone-aware datetimes
            quiz_time = datetime.strptime(self.data["quiz_time"], "%H:%M").time()
            start_time_today = current_time.replace(
                hour=quiz_time.hour, minute=quiz_time.minute, second=0, microsecond=0
            )

            # Set quiz reveal time to 6:00 PM
            reveal_time_str = self.data["reveal_time"]
            reveal_time = datetime.strptime(reveal_time_str, "%H:%M")
            reveal_time_today = current_time.replace(hour=reveal_time.hour, minute=reveal_time.minute, second=0, microsecond=0)
            reveal_time = datetime.strptime(self.data["reveal_time"], "%H:%M").time()
            reveal_time_today = current_time.replace(
                hour=reveal_time.hour, minute=reveal_time.minute, second=0, microsecond=0
            )

            # Reset quiz_finished_today flag at the start of the new day (midnight)
            # Reset daily flags at midnight
            if current_time.hour == 0 and current_time.minute == 0:
                self.data["quiz_finished_today"] = False
                SaveJson("DataFiles/quiz-data.json", self.data)

            # Skip the logic if the quiz is finished today
            if self.data.get("quiz_finished_today", True):
                return

            # Check if it's time to start the quiz (6 AM)
            if current_time >= start_time_today and self.data.get("quiz_started") == False:
                # Quiz Start Logic
                if (current_time >= start_time_today 
                    and not self.data["quiz_started"]
                    and not self.data["quiz_finished_today"]):
                    
                    self.data["quiz_started"] = True
                    await self.start_quiz()

            # Check if it's time to reveal answers (6 PM)
            if current_time >= reveal_time_today and self.data.get("quiz_started") == True:
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
                await self.reveal_answers()
                SaveJson("DataFiles/quiz-data.json", self.data)

        except Exception as e:
            print(f"Error in check_quiz_time: {e}")
            print(f"Critical error in check_quiz_time: {e}")
            # Full state reset on critical failure
            self.data["quiz_started"] = False
            self.data["quiz_finished_today"] = False
            SaveJson("DataFiles/quiz-data.json", self.data)
            import traceback
            traceback.print_exc()

    async def build_category_mapping(self):
        """Fetches category IDs from API"""
        url = "https://opentdb.com/api_category.php"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
                    self.category_mapping = {category["name"]: category["id"] for category in data["trivia_categories"]}
        except Exception as e:
            print(f"Error fetching categories: {e}")

    async def get_session_token(self) -> str:
        """Retrieves new session token"""
        url = "https://opentdb.com/api_token.php?command=request"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if data.get("response_code") == 0:
                    return data["token"]
                raise Exception("Failed to retrieve session token")

    async def reset_session_token(self, token: str) -> str:
        """Resets existing session token"""
        url = f"https://opentdb.com/api_token.php?command=reset&token={token}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if data.get("response_code") == 0:
                    return data["token"]
                raise Exception("Failed to reset token")

    async def fetch_questions_from_api(self) -> bool:
        """Fetches 50 questions from API with enhanced debugging"""
        print("Starting question fetch...")
        
        if not self.data.get("session_token"):
            try:
                print("No session token found, requesting new one...")
                self.data["session_token"] = await self.get_session_token()
                SaveJson("DataFiles/quiz-data.json", self.data)
            except Exception as e:
                print(f"Error getting session token: {e}")
                return False

        url = "https://opentdb.com/api.php"
        params = {
            "amount": 50,
            "token": self.data["session_token"]
        }

        try:
            async with aiohttp.ClientSession() as session:
                print(f"Fetching questions from {url}")
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    print(f"API Response Code: {data['response_code']}")

                    if data["response_code"] == 1:
                        print("API Error: No results.")
                        return False
                    elif data["response_code"] == 3:
                        print("Token expired, requesting new one...")
                        self.data["session_token"] = await self.get_session_token()
                        SaveJson("DataFiles/quiz-data.json", self.data)
                        return await self.fetch_questions_from_api()
                    elif data["response_code"] == 4:
                        print("Token empty, resetting...")
                        self.data["session_token"] = await self.reset_session_token(self.data["session_token"])
                        SaveJson("DataFiles/quiz-data.json", self.data)
                        return await self.fetch_questions_from_api()
                    elif data["response_code"] != 0:
                        print(f"Unknown API error: {data['response_code']}")
                        return False

                    raw_questions = data.get("results", [])
                    if not raw_questions:
                        print("No questions received from API")
                        return False

                    enabled_categories = self.data.get("enabled_categories", ["General Knowledge"])
                    print(f"Enabled categories: {enabled_categories}")
                    new_questions = []

                    for q in raw_questions:
                        category = html.unescape(q["category"])
                        print(f"Processing question from category: {category}")
                        
                        if category not in enabled_categories:
                            print(f"Skipping question - category {category} not enabled")
                            continue

                        question_text = html.unescape(q["question"])
                        correct_answer = html.unescape(q["correct_answer"])
                        incorrect_answers = [html.unescape(a) for a in q["incorrect_answers"]]

                        # Check for duplicates
                        is_duplicate = False
                        if category in self.used_questions:
                            for used_q in self.used_questions[category]:
                                if used_q["question"] == question_text:
                                    is_duplicate = True
                                    print(f"Skipping duplicate question: {question_text[:30]}...")
                                    break
                        if is_duplicate:
                            continue

                        choices = incorrect_answers + [correct_answer]
                        random.shuffle(choices)
                        correct_index = choices.index(correct_answer)

                        new_question = {
                            "question": question_text,
                            "choices": choices,
                            "correct_index": correct_index,
                            "category": category
                        }
                        new_questions.append((category, new_question))
                        print(f"Added new question from category {category}")

                    # Add new questions to existing ones
                    for category, q in new_questions:
                        if category not in self.questions:
                            self.questions[category] = []
                        self.questions[category].append(q)
                    
                    print(f"Added {len(new_questions)} new questions")
                    print(f"Current question counts by category:")
                    for cat, questions in self.questions.items():
                        print(f"- {cat}: {len(questions)} questions")

                    SaveJson("DataFiles/questions.json", self.questions)
                    return len(new_questions) > 0

        except Exception as e:
            print(f"API fetch error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_random_question(self):
        """Gets a random question from enabled categories"""
        enabled_categories = self.data.get("enabled_categories", [])
        available_categories = [cat for cat in enabled_categories if cat in self.questions and self.questions[cat]]
        
        if not available_categories:
            return None, None
            
        category = random.choice(available_categories)
        if not self.questions[category]:  # Extra safety check
            return None, None
            
        question = random.choice(self.questions[category])
        return category, question

    async def start_quiz(self) -> bool:
        try:
            self.data["current_quiz"] = {"answers": {}, "revealed": False}
            channel_id = self.data.get("quiz_channel_id")
            
            if not channel_id:
                return False

            channel = self.client.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return False

            # Check for available questions before fetching
            enabled_categories = self.data.get("enabled_categories", [])
            total_questions = sum(len(self.questions.get(cat, [])) for cat in enabled_categories)

            # Only fetch new questions if we're running low (e.g., less than 5)
            if total_questions < 5:
                print("Low on questions. Fetching from API...")
                success = await self.fetch_questions_from_api()
                if not success and total_questions == 0:  # Only fail if we have no questions at all
                    return False

            category, question = self.get_random_question()
            if not question:
                return False

            self.data["current_quiz"].update({
                "question": question["question"],
                "choices": question["choices"],
                "correct_index": question["correct_index"],
                "category": category
            })
            SaveJson("DataFiles/quiz-data.json", self.data)

            view = QuizView(
                question["question"],
                question["choices"],
                question["correct_index"],
                self.handle_quiz_callback
            )
            await channel.send("🎯 **Daily Quiz Time!**\n" + question["question"], view=view)
            
            # Move question to used AFTER successfully sending it
            self.move_question_to_used(question, category)
            return True

        except Exception as e:
            print(f"CRITICAL FAILURE in start_quiz: {str(e)}")
            return False

    def move_question_to_used(self, question: dict, category: str):
        """Moves a used question from active pool to used-questions.json"""
        try:
            # Remove from active questions
            if category in self.questions and question in self.questions[category]:
                self.questions[category].remove(question)
            
            # Add to used questions
            if category not in self.used_questions:
                self.used_questions[category] = []
            if question not in self.used_questions[category]:  # Prevent duplicates
                self.used_questions[category].append(question)
            
            # Save both files
            SaveJson("DataFiles/questions.json", self.questions)
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

    @app_commands.command(name="list_categories", description="List all available quiz categories")
    async def list_categories(self, interaction: discord.Interaction):
        """Shows all available categories and their status"""
        enabled_categories = self.data.get("enabled_categories", [])
        
        # Get question counts
        category_counts = {}
        for category in self.questions:
            category_counts[category] = len(self.questions[category])
        
        # Create embed
        embed = discord.Embed(title="Quiz Categories", color=discord.Color.blue())
        
        # Add fields for enabled and available categories
        enabled_text = ""
        for category in enabled_categories:
            count = category_counts.get(category, 0)
            enabled_text += f"• {category} ({count} questions)\n"
        
        embed.add_field(
            name="📚 Enabled Categories",
            value=enabled_text if enabled_text else "No categories enabled",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="enable_category", description="Enable a quiz category")
    @commands.has_permissions(administrator=True)
    async def enable_category(self, interaction: discord.Interaction, category: str):
        """Enable a specific category for quizzes"""
        if "enabled_categories" not in self.data:
            self.data["enabled_categories"] = []
        
        if category not in self.data["enabled_categories"]:
            self.data["enabled_categories"].append(category)
            SaveJson("DataFiles/quiz-data.json", self.data)
            await interaction.response.send_message(f"Enabled category: {category}", ephemeral=True)
        else:
            await interaction.response.send_message(f"Category {category} is already enabled", ephemeral=True)

    @app_commands.command(name="quiz_status", description="Show current leaderboard and question status")
    async def quiz_status(self, interaction: discord.Interaction):
        """Display current leaderboard and answer statistics"""
        embed = discord.Embed(title="Quiz Status", color=discord.Color.blue())
        
        # Leaderboard Section
        points_data = self.data["points"]
        sorted_users = sorted(points_data.items(), key=lambda x: x[1], reverse=True)[:10]  # Top 10
        
        leaderboard = []
        for idx, (user_id, points) in enumerate(sorted_users, 1):
            user = interaction.guild.get_member(int(user_id))
            leaderboard.append(f"{idx}. {user.mention if user else 'Unknown User'} - {points} pts")
        
        embed.add_field(
            name="🏆 Leaderboard",
            value="\n".join(leaderboard) if leaderboard else "No points yet!",
            inline=False
        )

        # Current Question Section
        current_quiz = self.data.get("current_quiz", {})
        if current_quiz:
            question_status = [
                f"**Question:** {current_quiz.get('question', 'N/A')}",
                f"**Category:** {current_quiz.get('category', 'N/A')}"
            ]
            
            # Format choices with letters
            choices = current_quiz.get("choices", [])
            for i, choice in enumerate(choices):
                question_status.append(f"{chr(65 + i)}) {choice}")
            
            # Show correct answer if revealed
            if current_quiz.get("revealed", False):
                correct_answer = choices[current_quiz["correct_index"]]
                question_status.append(f"\n✅ **Correct Answer:** {correct_answer}")
            
            embed.add_field(
                name="📚 Current Question",
                value="\n".join(question_status),
                inline=False
            )

            # Answer Statistics
            correct_users = []
            wrong_users = []
            
            for user_id, answer in current_quiz.get("answers", {}).items():
                user = interaction.guild.get_member(int(user_id))
                if user:
                    name = user.display_name
                    if answer["correct"]:
                        correct_users.append(name)
                    else:
                        wrong_users.append(name)

            embed.add_field(
                name="✅ Correct Answers",
                value="\n".join(correct_users) if correct_users else "No correct answers yet",
                inline=True
            )
            
            embed.add_field(
                name="❌ Incorrect Answers",
                value="\n".join(wrong_users) if wrong_users else "No wrong answers yet",
                inline=True
            )
        else:
            embed.add_field(
                name="📚 Current Question",
                value="No active quiz at the moment!",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

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
