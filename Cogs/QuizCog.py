import discord
from discord.ext import commands, tasks
import random
import asyncio
import json
from discord import app_commands
from typing import List, Dict, Optional, Set

class QuizView(discord.ui.View):
    def __init__(self, question: str, choices: List[str], correct_index: int, add_points_callback, timeout: int = 300):
        super().__init__(timeout=timeout)  # 5 minute timeout
        self.question = question
        self.choices = choices
        self.correct_index = correct_index
        self.add_points_callback = add_points_callback
        self.answered_users: Dict[int, int] = {}  # {user_id: chosen_answer}
        self.is_active = True
        
        # Create buttons dynamically
        for i, choice in enumerate(choices):
            button = discord.ui.Button(
                label=choice,
                style=discord.ButtonStyle.primary,
                custom_id=f"choice_{i}"
            )
            button.callback = lambda interaction, idx=i: self.handle_response(interaction, idx)
            self.add_item(button)

    async def handle_response(self, interaction: discord.Interaction, chosen_index: int) -> None:
        if not self.is_active:
            await interaction.response.send_message("This quiz has expired!", ephemeral=True)
            return

        if interaction.user.id in self.answered_users:
            await interaction.response.send_message("You've already answered this question!", ephemeral=True)
            return

        self.answered_users[interaction.user.id] = chosen_index
        
        # Get user's current points
        user_points = await self.add_points_callback(interaction.user.id, 0, get_only=True)
        
        if chosen_index == self.correct_index:
            await self.add_points_callback(interaction.user.id, 1)
            await interaction.response.send_message(
                f"You are Correct! The correct answer was {self.choices[self.correct_index]}! Your current points: {user_points + 1}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"You got it Wrong! The correct answer was {self.choices[self.correct_index]}! Your current points: {user_points}",
                ephemeral=True
            )

    async def on_timeout(self) -> None:
        self.is_active = False
        
        # Create result summary
        correct_users = []
        incorrect_users = []
        
        for user_id, chosen_answer in self.answered_users.items():
            user = self.message.guild.get_member(user_id)
            if user:
                if chosen_answer == self.correct_index:
                    correct_users.append(user.mention)
                else:
                    incorrect_users.append(user.mention)

        result_message = "⏰ Time's up! Here are the results:\n\n"
        if correct_users:
            result_message += f"**Got it right:** {', '.join(correct_users)}\n"
        if incorrect_users:
            result_message += f"**Need more practice:** {', '.join(incorrect_users)}\n"
        result_message += f"\nThe correct answer was: {self.choices[self.correct_index]}"

        for child in self.children:
            child.disabled = True

        await self.message.edit(content=result_message, view=self)

class Quiz(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.questions: List[Dict] = []
        self.points: Dict[str, int] = {}
        self.quiz_channel_id = 1308181674785247313
        self.load_data()
        self.quiz_task.start()

    def load_data(self) -> None:
        """Load questions and points from JSON files."""
        try:
            with open('questions.json', 'r') as f:
                self.questions = json.load(f)
        except FileNotFoundError:
            self.questions = []

        try:
            with open('points.json', 'r') as f:
                self.points = json.load(f)
        except FileNotFoundError:
            self.points = {}

    def save_data(self) -> None:
        """Save questions and points to JSON files."""
        with open('questions.json', 'w') as f:
            json.dump(self.questions, f, indent=4)
        with open('points.json', 'w') as f:
            json.dump(self.points, f, indent=4)

    async def add_points(self, user_id: int, points: int, get_only: bool = False) -> int:
        """Add points to a user and save the updated points. If get_only is True, just return current points."""
        user_id_str = str(user_id)
        current_points = self.points.get(user_id_str, 0)
        
        if not get_only:
            self.points[user_id_str] = current_points + points
            self.save_data()
            return current_points + points
        
        return current_points

    async def send_quiz(self, channel: discord.TextChannel) -> None:
        """Send a quiz to the specified channel."""
        if not self.questions:
            await channel.send("❌ No questions available!")
            return

        question = random.choice(self.questions)
        view = QuizView(
            question=question["question"],
            choices=question["choices"],
            correct_index=question["correct_index"],
            add_points_callback=self.add_points
        )
        
        embed = discord.Embed(
            title="📝 Quiz Time!",
            description=question["question"],
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Instructions", 
            value="Click the button with your answer! Everyone can answer independently. Results will be revealed in 5 minutes.", 
            inline=False
        )
        
        message = await channel.send(embed=embed, view=view)
        view.message = message

    @tasks.loop(hours=24)
    async def quiz_task(self) -> None:
        """Send daily quiz to the designated channel."""
        channel = self.client.get_channel(self.quiz_channel_id)
        if channel:
            await self.send_quiz(channel)
        else:
            print(f"Error: Could not find channel with ID {self.quiz_channel_id}")

    @quiz_task.before_loop
    async def before_quiz_task(self) -> None:
        """Wait for the bot to be ready before starting the task."""
        await self.client.wait_until_ready()

    @app_commands.command(name="quiz", description="Start a quiz manually")
    async def start_quiz(self, interaction: discord.Interaction) -> None:
        """Manually start a quiz in the current channel."""
        await interaction.response.defer()
        await self.send_quiz(interaction.channel)

    @app_commands.command(name="submitquestion", description="Submit a new quiz question")
    @app_commands.describe(
        question="The question text",
        correct_option="The correct answer option (1-4)",
        option1="First answer choice",
        option2="Second answer choice",
        option3="Third answer choice",
        option4="Fourth answer choice"
    )
    async def submit_question(
        self,
        interaction: discord.Interaction,
        question: str,
        correct_option: app_commands.Range[int, 1, 4],
        option1: str,
        option2: str,
        option3: str,
        option4: str
    ) -> None:
        """Submit a new question for the quiz."""
        new_question = {
            "question": question,
            "choices": [option1, option2, option3, option4],
            "correct_index": correct_option - 1
        }
        
        self.questions.append(new_question)
        self.save_data()
        
        embed = discord.Embed(
            title="✅ Question Submitted",
            description="Your question has been added to the quiz pool!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="points", description="Check your quiz points")
    async def check_points(self, interaction: discord.Interaction) -> None:
        """Check your current points."""
        user_points = self.points.get(str(interaction.user.id), 0)
        await interaction.response.send_message(
            f"You currently have **{user_points}** points!",
            ephemeral=True
        )

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Quiz(client))