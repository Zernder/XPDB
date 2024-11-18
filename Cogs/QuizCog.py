import discord
from discord.ext import commands, tasks
import random
import asyncio
import json
from discord import app_commands

class Quiz(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.quiz_channel = None  # You can set a specific channel later
        self.pending_submissions = []  # Temporary list for storing submitted questions
        self.admin_ids = [175421668850794506, 435239674886488075]  # Replace with your actual admin user IDs
        self.load_questions()
        self.load_points()  # Load user points
        self.quiz_task.start()

    # Load questions from the JSON file when the bot starts
    def load_questions(self):
        try:
            with open('questions.json', 'r') as f:
                self.questions = json.load(f)
        except FileNotFoundError:
            self.questions = []  # If no file exists, start with an empty list

    # Save questions to the JSON file
    def save_questions(self):
        with open('questions.json', 'w') as f:
            json.dump(self.questions, f, indent=4)

    # Load user points from the points file
    def load_points(self):
        try:
            with open('points.json', 'r') as f:
                self.points = json.load(f)
        except FileNotFoundError:
            self.points = {}  # If no file exists, start with an empty dictionary

    # Save user points to the points file
    def save_points(self):
        with open('points.json', 'w') as f:
            json.dump(self.points, f, indent=4)

    # This method will send the Quiz of the Day in a specific channel at a fixed time
    @tasks.loop(hours=24)  # Adjust timing as per your need
    async def quiz_task(self):
        if self.quiz_channel is None:
            self.quiz_channel = self.client.get_channel(1308181674785247313)  # Replace with your channel ID
        
        # Check if there are any questions left to ask
        if not self.questions:
            await self.quiz_channel.send("No more questions left for the day.")
            return

        # Select a random question
        question = random.choice(self.questions)
        question_text = question["question"]
        correct_answer = question["answer"]

        # Send the question to the channel
        message = await self.quiz_channel.send(f"**Quiz of the Day!**\n\n{question_text}\n\nReply with your answer!")

        def check(msg):
            return msg.channel == self.quiz_channel and msg.author != self.client.user

        try:
            # Wait for a user to reply with the answer
            response = await self.client.wait_for('message', check=check, timeout=7200.0)  # Timeout after 2 hours
            user_answer = response.content.lower()

            if user_answer == correct_answer:
                await message.edit(content=f"**Quiz of the Day!**\n\n{question_text}\n\n**Correct!** {response.author.mention} got it right!")
                self.add_points(response.author.id, 1)  # Add points for correct answer
            else:
                await message.edit(content=f"**Quiz of the Day!**\n\n{question_text}\n\n**Incorrect!**. {response.author.mention} got it wrong!")

            # Show current points after answer
            current_points = self.points.get(response.author.id, 0)
            await response.author.send(f"Your current points: {current_points}")

            # Move the question to used_questions and remove it from available questions
            self.questions.remove(question)
            self.save_questions()  # Save the updated questions list
            self.save_points()  # Save updated points

        except asyncio.TimeoutError:
            await message.edit(content=f"**Quiz of the Day!**\n\n{question_text}\n\n**Time's up!** No one answered in time.")

    # Function to add points to a user
    def add_points(self, user_id, points):
        if user_id in self.points:
            self.points[user_id] += points
        else:
            self.points[user_id] = points

    # Start the quiz task when the bot is ready
    @commands.Cog.listener()
    async def on_ready(self):
        self.quiz_task.start()

    @app_commands.command(name="setquizchannel", description="Set the channel for the daily quiz.")
    async def set_quiz_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.quiz_channel = channel
        await interaction.response.send_message(f"Quiz channel has been set to {channel.mention}.")

    @app_commands.command(name="quiz", description="Start a quiz manually.")
    async def start_quiz(self, interaction: discord.Interaction):
        # Check if there are any questions left to ask
        if not self.questions:
            await interaction.response.send_message("No more questions left to ask.")
            return

        # Select a random question
        question = random.choice(self.questions)
        question_text = question["question"]
        correct_answer = question["answer"]

        # Send the question to the channel where the command is invoked
        message = await interaction.response.send_message(f"**Quiz of the Day!**\n\n{question_text}\n\nReply with your answer!")

        def check(msg):
            return msg.channel == interaction.channel and msg.author != self.client.user

        try:
            # Wait for a user to reply with the answer
            response = await self.client.wait_for('message', check=check, timeout=30.0)  # Timeout after 30 seconds
            user_answer = response.content.lower()

            if user_answer == correct_answer:
                await message.edit(content=f"**Quiz of the Day!**\n\n{question_text}\n\n**Correct!** {response.author.mention} got it right!")
                self.add_points(response.author.id, 1)  # Add points for correct answer
            else:
                await message.edit(content=f"**Quiz of the Day!**\n\n{question_text}\n\n**Incorrect!** The correct answer was: {correct_answer}. {response.author.mention} got it wrong!")

            # Show current points after answer
            current_points = self.points.get(response.author.id, 0)
            await response.author.send(f"Your current points: {current_points}")

            # Move the question to used_questions and remove it from available questions
            self.questions.remove(question)
            self.save_questions()  # Save the updated questions list
            self.save_points()  # Save updated points

        except asyncio.TimeoutError:
            await message.edit(content=f"**Quiz of the Day!**\n\n{question_text}\n\n**Time's up!** No one answered in time.")

    # Command for users to submit questions and answers
    @app_commands.command(name="submitquestion", description="Submit a new quiz question and answer for review.")
    async def submit_question(self, interaction: discord.Interaction, question: str, answer: str):
        # Add the submitted question to the pending list for review
        self.pending_submissions.append({"question": question, "answer": answer, "author": interaction.user})
        await interaction.response.send_message(f"Your question has been submitted for review! Thank you, {interaction.user.mention}.")

    # Command for reviewing submitted questions (only for admins)
    @app_commands.command(name="reviewsubmissions", description="Review all submitted questions.")
    async def review_submissions(self, interaction: discord.Interaction):
        # Check if the user is in the admin list
        if interaction.user.id not in self.admin_ids:
            await interaction.response.send_message("You do not have permission to review submissions.")
            return
        
        if not self.pending_submissions:
            await interaction.response.send_message("No questions pending for review.")
            return

        review_message = "**Pending Quiz Question Submissions:**\n\n"
        for idx, submission in enumerate(self.pending_submissions):
            review_message += f"**{idx+1}.** Question: {submission['question']}\nAnswer: {submission['answer']}\nSubmitted by: {submission['author']}\n\n"

        # Provide a way to approve or reject questions (you can implement reactions for approval/rejection)
        await interaction.response.send_message(review_message)

    # Command for admins to approve a question and add it to the quiz pool
    @app_commands.command(name="approvequestion", description="Approve a submitted question and add it to the quiz pool.")
    async def approve_question(self, interaction: discord.Interaction, question_number: int):
        if interaction.user.id not in self.admin_ids:
            await interaction.response.send_message("You do not have permission to approve questions.")
            return

        # Check if the question number is valid
        if question_number < 1 or question_number > len(self.pending_submissions):
            await interaction.response.send_message("Invalid question number.")
            return

        question_to_add = self.pending_submissions.pop(question_number - 1)
        self.questions.append(question_to_add)
        self.save_questions()  # Save the updated questions list
        await interaction.response.send_message(f"Question '{question_to_add['question']}' has been approved and added to the quiz pool.")

    # Command for admins to reject a question
    @app_commands.command(name="rejectquestion", description="Reject a submitted question.")
    async def reject_question(self, interaction: discord.Interaction, question_number: int):
        if interaction.user.id not in self.admin_ids:
            await interaction.response.send_message("You do not have permission to reject questions.")
            return

        # Check if the question number is valid
        if question_number < 1 or question_number > len(self.pending_submissions):
            await interaction.response.send_message("Invalid question number.")
            return

        rejected_question = self.pending_submissions.pop(question_number - 1)
        await interaction.response.send_message(f"Question '{rejected_question['question']}' has been rejected.")

async def setup(client):
    await client.add_cog(Quiz(client))
