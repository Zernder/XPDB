import copy
import discord
from discord.ui import Button, View
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
import random
import datetime
from typing import Dict

def LoadJson(filename: str) -> dict:
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return {}

def SaveJson(filename: str, data: dict) -> None:
    folder = os.path.dirname(filename)
    if folder:
        os.makedirs(folder, exist_ok=True)  # Creates folders if missing, no errors
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class RPGView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This menu is not for you!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Explore", style=discord.ButtonStyle.primary)
    async def explore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        response = await self.cog.explore_action(interaction)
        await interaction.response.edit_message(content=response, embed=None, view=self)

    @discord.ui.button(label="Battle", style=discord.ButtonStyle.danger)
    async def battle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = self.cog.get_user(self.user_id)
        if "current_monster" not in user:
            await interaction.response.edit_message(content="❌ No monster to fight! Use Explore first!", view=self)
            return
        battle_view = BattleView(self.cog, self.user_id)
        await battle_view.create_embed()
        await interaction.response.edit_message(
            content=None,
            embed=battle_view.embed,
            view=battle_view
        )

    @discord.ui.button(label="Shop", style=discord.ButtonStyle.success)
    async def shop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        shop_view = ShopView(self.cog, self.user_id)
        await shop_view.create_embed()
        await interaction.response.edit_message(
            content=None,
            embed=shop_view.embed,
            view=shop_view
        )

    @discord.ui.button(label="Inventory", style=discord.ButtonStyle.secondary)
    async def inventory_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = self.cog.get_user(self.user_id)
        embed = discord.Embed(title="Inventory", color=0x00ff00)
        if not user["inventory"]:
            embed.description = "Your inventory is empty!"
        else:
            for item, qty in user["inventory"].items():
                embed.add_field(name=item.capitalize(), value=f"Quantity: {qty}", inline=True)
        await interaction.response.edit_message(content=None, embed=embed, view=self)

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = self.cog.get_user(self.user_id)
        embed = discord.Embed(title=f"{interaction.user.display_name}'s Stats", color=0x00ff00)
        embed.add_field(name="Level", value=user["level"], inline=True)
        embed.add_field(name="Health", value=f"{user['health']}/{user['max_health']}", inline=True)
        embed.add_field(name="Attack", value=user["attack"], inline=True)
        embed.add_field(name="Defense", value=user["defense"], inline=True)
        embed.add_field(name="Experience", value=f"{user['experience']}/{user['level']*100}", inline=True)
        embed.add_field(name="Gold", value=user["gold"], inline=True)
        await interaction.response.edit_message(content=None, embed=embed, view=self)

class BattleView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=30)
        self.cog = cog
        self.user_id = user_id
        self.embed = None
        self.add_item(Button(label="Skills", style=discord.ButtonStyle.blurple, row=1))

    async def create_embed(self):
        user = self.cog.get_user(self.user_id)
        monster = user.get("current_monster", {})
        embed = discord.Embed(title="⚔️ Battle", color=0xff0000)
        embed.add_field(
            name=f"🦖 {monster.get('name', 'Unknown').capitalize()}",
            value=f"❤️ Health: {monster.get('health', 0)}",
            inline=False
        )
        embed.add_field(
            name="Your Health",
            value=f"❤️ {user['health']}/{user['max_health']}",
            inline=False
        )
        self.embed = embed

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger)
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        response = await self.cog.process_attack(interaction)
        user = self.cog.get_user(self.user_id)
        if "current_monster" not in user:
            await interaction.response.edit_message(content=response, embed=None, view=None)
        else:
            await self.create_embed()
            await interaction.response.edit_message(content=response, embed=self.embed, view=self)

    @discord.ui.button(label="Skills", style=discord.ButtonStyle.blurple)
    async def skills_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = self.cog.get_user(self.user_id)
        if not user["skills"]:
            await interaction.response.send_message("❌ You have no learned skills!", ephemeral=True)
            return

        # Show available skills
        view = SkillMenuView(self.cog, self.user_id)
        await interaction.response.edit_message(view=view)

    @discord.ui.button(label="Flee", style=discord.ButtonStyle.grey)
    async def flee_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = self.cog.get_user(self.user_id)
        if random.random() < 0.5:  # 50% chance to flee
            del user["current_monster"]
            SaveJson("DataFiles/rpgFiles/players.json", self.cog.user_data)
            await interaction.response.edit_message(
                content="🏃♂️ You successfully fled!",
                embed=None,
                view=None
            )
        else:
            monster = user.get("current_monster", {})
            damage = max(0, monster.get("attack", 0) - random.randint(0, user["defense"]))
            user["health"] -= damage
            response = f"🏃♂️ You failed to flee! The {monster.get('name')} hit you for {damage} damage!"
            if user["health"] <= 0:
                response = "💀 You were defeated!"
                del user["current_monster"]
            SaveJson("DataFiles/rpgFiles/players.json", self.cog.user_data)
            await self.create_embed()
            await interaction.response.edit_message(content=response, embed=self.embed, view=self)

class SkillMenuView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=15)
        self.cog = cog
        self.user_id = user_id
        user = cog.get_user(user_id)
        
        # Add buttons for each learned skill
        for skill_name in user["skills"]:
            skill_data = next(
                s for level in cog.SKILLS.values() 
                for s in level if s["name"] == skill_name
            )
            self.add_item(Button(
                label=f"{skill_name} ({skill_data['cost']} {skill_data['cost_type']})",
                style=discord.ButtonStyle.primary
            ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle_view = BattleView(self.cog, self.user_id)
        await battle_view.create_embed()
        await interaction.response.edit_message(view=battle_view)

class ShopView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=30)
        self.cog = cog
        self.user_id = user_id
        self.embed = None
        self.add_item(Button(label="Back to Menu", style=discord.ButtonStyle.grey, custom_id="back"))
        self._populate_buttons()

    def _populate_buttons(self):
        for idx, item in enumerate(self.cog.shop_data["items"]):
            self.add_item(
                Button(
                    label=f"Buy {item['name'].capitalize()} ({item['price']}g)",
                    style=discord.ButtonStyle.green,
                    custom_id=f"buy_{idx}",
                    disabled=item["stock"] <= 0
                )
            )

    async def create_embed(self):
        user = self.cog.get_user(self.user_id)
        self.embed = discord.Embed(title="🛒 RPG Shop", color=0x2b2d31)
        self.embed.set_footer(text=f"Your Gold: {user['gold']} 💰")
        
        for item in self.cog.shop_data["items"]:
            self.embed.add_field(
                name=f"{item['name'].capitalize()} ({item['stock']} left)",
                value=f"Price: {item['price']}g\nType: {item['type']}",
                inline=True
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This shop isn't for you!", ephemeral=True)
            return False
        return True

class SkillChoiceView(discord.ui.View):
    def __init__(self, cog, user_id, skills):
        super().__init__(timeout=30)
        self.cog = cog
        self.user_id = user_id
        self.skills = skills
        for skill in skills:
            self.add_button(skill["name"], skill["description"])

    def add_button(self, label, description):
        button = Button(label=label, style=discord.ButtonStyle.primary)
        button.callback = lambda i, l=label: self.select_skill(i, l)
        self.add_item(button)

    async def select_skill(self, interaction: discord.Interaction, skill_name: str):
        user = self.cog.get_user(self.user_id)
        user["skills"].append(skill_name)
        SaveJson("DataFiles/rpgFiles/players.json", self.cog.user_data)
        await interaction.response.edit_message(
            content=f"✅ Learned **{skill_name}**!",
            view=None
        )

class RPG(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.user_data: Dict = LoadJson("DataFiles/rpgFiles/players.json")
        self.shop_data: Dict = LoadJson("DataFiles/rpgFiles/shop-items.json")
        self.monsters: Dict = LoadJson("DataFiles/rpgFiles/monsters.json")
        self.regen_task = None

        self.SKILLS = {
            2: [
                {"name": "Power Strike", "cost_type": "stamina", "cost": 20, "effect": {"attack_multiplier": 1.5}},
                {"name": "Mana Shield", "cost_type": "mana", "cost": 30, "effect": {"defense_bonus": 5}}
            ],
            4: [
                {"name": "Fireball", "cost_type": "mana", "cost": 40, "effect": {"damage_boost": 10}},
                {"name": "Dodge", "cost_type": "stamina", "cost": 25, "effect": {"evasion_chance": 0.3}}
            ]
        }

        self.items = {
            "potion": {"type": "heal", "value": 30},
            "sword": {"type": "weapon", "value": 5},
            "shield": {"type": "armor", "value": 5}
        }

        if not self.shop_data:
            self.shop_data = {
                "items": [
                    {"name": "potion", "price": 50, "stock": 10, "type": "heal"},
                    {"name": "sword", "price": 100, "stock": 5, "type": "weapon"},
                    {"name": "shield", "price": 80, "stock": 5, "type": "armor"},
                    {"name": "rare_artifact", "price": 500, "stock": 1, "type": "special"}
                ]
            }
            SaveJson("DataFiles/rpgFiles/shop-items.json", self.shop_data)

        if not self.monsters:
            self.monsters = [
                {"name": "Goblin", "min_level": 1, "max_level": 5, "health": 50, "attack": 5},
                {"name": "Rat", "min_level": 1, "max_level": 3, "health": 20, "attack": 2},
                {"name": "Giant Spider", "min_level": 1, "max_level": 4, "health": 25, "attack": 3},
                {"name": "Skeleton", "min_level": 2, "max_level": 5, "health": 35, "attack": 4},
                {"name": "Slime", "min_level": 1, "max_level": 3, "health": 30, "attack": 2},
                {"name": "Wolf", "min_level": 2, "max_level": 5, "health": 40, "attack": 5},
                {"name": "Kobold", "min_level": 1, "max_level": 5, "health": 45, "attack": 4},
                {"name": "Giant Bat", "min_level": 1, "max_level": 4, "health": 22, "attack": 3},
                {"name": "Zombie", "min_level": 2, "max_level": 6, "health": 50, "attack": 4},
                {"name": "Imp", "min_level": 1, "max_level": 4, "health": 25, "attack": 3},

                {"name": "Orc", "min_level": 3, "max_level": 8, "health": 80, "attack": 8},
                {"name": "Hobgoblin", "min_level": 5, "max_level": 10, "health": 70, "attack": 7},
                {"name": "Wight", "min_level": 6, "max_level": 12, "health": 85, "attack": 8},
                {"name": "Ogre", "min_level": 7, "max_level": 14, "health": 100, "attack": 10},
                {"name": "Troll", "min_level": 8, "max_level": 15, "health": 120, "attack": 12},

                {"name": "Dragon", "min_level": 10, "max_level": 20, "health": 200, "attack": 15},
                {"name": "Lich", "min_level": 15, "max_level": 20, "health": 180, "attack": 14},
                {"name": "Kraken", "min_level": 20, "max_level": 25, "health": 250, "attack": 18}
            ]

            SaveJson("DataFiles/rpgFiles/monsters.json", self.monsters)  # Fix path

    def get_user(self, user_id: str) -> dict:
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                "level": 1,
                "health": 100,
                "max_health": 100,
                "stamina": 100,
                "max_stamina": 100,
                "mana": 100,
                "max_mana": 100,
                "attack": 10,
                "defense": 5,
                "experience": 0,
                "gold": 0,
                "inventory": {},
                "cooldowns": {},
                "skills": []
            }
        else:
            # Ensure existing users' stats don't exceed max values
            user = self.user_data[user_id]
            user["health"] = min(user["health"], user["max_health"])
            user["stamina"] = min(user["stamina"], user["max_stamina"])
            user["mana"] = min(user["mana"], user["max_mana"])
        return self.user_data[user_id]

    async def cog_load(self):
        """Start the regeneration task when cog loads"""
        self.regen_task = asyncio.create_task(self.regen_resources())

    def cog_unload(self):
        """Cancel regeneration task on cog unload"""
        if self.regen_task and not self.regen_task.done():
            self.regen_task.cancel()

    async def restock_shop(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await asyncio.sleep(60)
            # Loop through each user's shop and restock their first item
            for user_shop in self.shop_data.values():
                # Ensure the user's shop has items and stock exists
                if "items" in user_shop and len(user_shop["items"]) > 0:
                    user_shop["items"][0]["stock"] += 1
            SaveJson("DataFiles/rpgFiles/shop-items.json", self.shop_data)

    async def regen_resources(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await asyncio.sleep(60)
            # Regenerate stamina and mana for each user
            for user in self.user_data.values():
                user["stamina"] = min(user["max_stamina"], user["stamina"] + 10)
                user["mana"] = min(user["max_mana"], user["mana"] + 10)
            SaveJson("DataFiles/rpgFiles/players.json", self.user_data)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            if interaction.type == discord.InteractionType.component:
                custom_id = interaction.data.get("custom_id")
                if custom_id == "back":
                    view = RPGView(self, str(interaction.user.id))
                    await interaction.response.edit_message(
                        content="🔮 Adventure Menu - Choose an action:",
                        embed=None,
                        view=view
                    )
                elif custom_id and custom_id.startswith("buy_"):
                    await self.handle_purchase(interaction, custom_id)
        except Exception as e:
            print(f"Interaction error: {e}")

    async def regen_resources(self):
        """Regenerate 10 stamina/mana every minute"""
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await asyncio.sleep(60)
            for user in self.user_data.values():
                user["stamina"] = min(user["max_stamina"], user["stamina"] + 10)
                user["mana"] = min(user["max_mana"], user["mana"] + 10)
            SaveJson("DataFiles/rpgFiles/players.json", self.user_data)

    async def handle_purchase(self, interaction: discord.Interaction, custom_id: str):
        user_id = str(interaction.user.id)
        user = self.get_user(user_id)
        item_idx = int(custom_id.split("_")[1])
        
        try:
            item_data = self.shop_data["items"][item_idx]
        except IndexError:
            await interaction.response.send_message("❌ Item no longer available!", ephemeral=True)
            return

        if item_data["stock"] <= 0:
            await interaction.response.send_message("❌ This item is out of stock!", ephemeral=True)
            return

        if user["gold"] < item_data["price"]:
            await interaction.response.send_message("❌ You don't have enough gold!", ephemeral=True)
            return

        # Process purchase
        user["gold"] -= item_data["price"]
        user["inventory"][item_data["name"]] = user["inventory"].get(item_data["name"], 0) + 1
        self.shop_data["items"][item_idx]["stock"] -= 1

        # Save changes
        SaveJson("DataFiles/rpgFiles/players.json", self.user_data)
        SaveJson("DataFiles/rpgFiles/shop-items.json", self.shop_data)

        # Update view
        shop_view = ShopView(self, user_id)
        await shop_view.create_embed()
        await interaction.response.edit_message(
            content=f"✅ Successfully bought {item_data['name']} for {item_data['price']}g!",
            embed=shop_view.embed,
            view=shop_view
        )

    @app_commands.command(name="register", description="Start your RPG adventure!")
    async def register(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.user_data:
            await interaction.response.send_message("❌ You're already registered! Use `/playrpg` to start playing!", ephemeral=True)
            return
        
        self.get_user(user_id)
        SaveJson("DataFiles/rpgFiles/players.json", self.user_data)
        await interaction.response.send_message("🎉 Welcome to the RPG! Use `/playrpg` to access your adventure menu!", ephemeral=True)

    @app_commands.command(name="playrpg", description="Access your RPG menu")
    async def playrpg(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id not in self.user_data:
            await interaction.response.send_message("❌ You need to register first with `/register`!", ephemeral=True)
            return
        
        view = RPGView(self, user_id)
        await interaction.response.send_message(
            "🔮 Adventure Menu - Choose an action:",
            view=view,
            ephemeral=True
        )

    async def explore_action(self, interaction: discord.Interaction) -> str:
            user_id = str(interaction.user.id)
            user = self.get_user(user_id)
            current_time = datetime.datetime.now().timestamp()
            
            if current_time - user["cooldowns"].get("explore", 0) < 5:
                remaining = 5 - (current_time - user["cooldowns"].get("explore", 0))
                return f"⏳ You need to wait {remaining:.1f}s before exploring again!"
            
            outcome = random.choice(["gold", "item", "monster", "nothing"])
            response = ""
            
            if outcome == "gold":
                gold_found = random.randint(10, 50)
                user["gold"] += gold_found
                response = f"💰 You found {gold_found} gold!"
            elif outcome == "item":
                item = random.choice(list(self.items.keys()))
                user["inventory"][item] = user["inventory"].get(item, 0) + 1
                response = f"🎁 You found a {item}!"
            elif outcome == "monster":
                if not self.monsters:
                    return "❌ No monsters are defined in the game!" 
                monster = copy.deepcopy(random.choice(self.monsters))  # Fix shared monster instance
                user["current_monster"] = monster
                response = f"🐉 You encountered a {monster['name']}! Use the Battle menu to fight it!"
            else:
                response = "🌲 You explored but found nothing..."
            
            user["cooldowns"]["explore"] = current_time
            SaveJson("DataFiles/rpgFiles/players.json", self.user_data)
            return response

    async def process_attack(self, interaction: discord.Interaction, skill_name: str = None) -> str:
        user = self.get_user(str(interaction.user.id))
        
        # Check if user has a current monster before accessing it
        if "current_monster" not in user:
            return "❌ No monster to fight!"
        monster = user["current_monster"]
        
        if skill_name:
            # Handle skill lookup safely
            skills = [s for level in self.SKILLS.values() for s in level]
            skill_data = next((s for s in skills if s["name"] == skill_name), None)
            if not skill_data:
                return f"❌ Skill {skill_name} not found!"
            
            # Check if user has enough resources
            if user[skill_data["cost_type"]] < skill_data["cost"]:
                return f"❌ Not enough {skill_data['cost_type']} to use {skill_name}!"
            
            # Deduct the cost
            user[skill_data["cost_type"]] -= skill_data["cost"]
            
            # Calculate player damage based on skill effect
            if "attack_multiplier" in skill_data["effect"]:
                base_damage = user["attack"] - random.randint(0, monster["attack"])
                player_damage = int(base_damage * skill_data["effect"]["attack_multiplier"])
            elif "damage_boost" in skill_data["effect"]:
                player_damage = user["attack"] - random.randint(0, monster["attack"]) + skill_data["effect"]["damage_boost"]
            else:
                player_damage = user["attack"] - random.randint(0, monster["attack"])
            # Ensure damage is non-negative
            player_damage = max(0, player_damage)
        else:
            # Basic attack damage calculation
            player_damage = max(0, user["attack"] - random.randint(0, monster["attack"]))
        
        # Calculate monster damage
        monster_damage = max(0, monster["attack"] - random.randint(0, user["defense"]))
        
        # Apply damage to both parties
        user["health"] -= monster_damage
        monster["health"] -= player_damage
        
        if monster["health"] <= 0:
            # Handle monster defeat (exp, gold, cooldown, level up)
            exp_gain = monster["attack"] * 5
            gold_gain = random.randint(10, 30)
            user["experience"] += exp_gain
            user["gold"] += gold_gain
            response = f"⚔️ You defeated the {monster['name']}!\n🏆 Gained {exp_gain} XP and {gold_gain} gold!"
            del user["current_monster"]
            current_time = datetime.datetime.now().timestamp()
            user["cooldowns"]["battle"] = current_time
            
            # Check for level up
            if user["experience"] >= user["level"] * 100:
                user["level"] += 1
                user["max_health"] += 20
                user["attack"] += 2
                user["defense"] += 1
                user["health"] = user["max_health"]
                response += f"\n🎉 Level up! You're now level {user['level']}!"
                if (user["level"] - 1) % 2 == 0:
                    await self.offer_skills(interaction, user["level"] - 1)
        else:
            response = (
                f"⚔️ You attacked the {monster['name']} for {player_damage} damage!\n"
                f"💔 The {monster['name']} hit you for {monster_damage} damage!\n"
                f"❤️ Your health: {user['health']}/{user['max_health']}"
            )
            if user["health"] <= 0:
                response = "💀 You were defeated... Use a potion or visit the shop to heal!"
                del user["current_monster"]

        SaveJson("DataFiles/rpgFiles/players.json", self.user_data)
        return response


    async def offer_skills(self, interaction: discord.Interaction, level: int):
        skills = self.SKILLS.get(level, [])
        if not skills:
            return
        view = SkillChoiceView(self, str(interaction.user.id), skills)
        await interaction.followup.send(
            f"🔮 Choose a skill for reaching level {level + 1}:",
            view=view,
            ephemeral=True
    )

    @app_commands.command(name="stats", description="Check your character stats")
    async def stats(self, interaction: discord.Interaction):
        user = self.get_user(str(interaction.user.id))
        embed = discord.Embed(title=f"{interaction.user.display_name}'s Stats", color=0x00ff00)
        embed.add_field(name="Level", value=user["level"], inline=True)
        embed.add_field(name="Health", value=f"{user['health']}/{user['max_health']}", inline=True)
        embed.add_field(name="Stamina", value=f"{user['stamina']}/{user['max_stamina']}", inline=True)
        embed.add_field(name="Mana", value=f"{user['mana']}/{user['max_mana']}", inline=True)
        embed.add_field(name="Attack", value=user["attack"], inline=True)
        embed.add_field(name="Defense", value=user["defense"], inline=True)
        embed.add_field(name="Experience", value=f"{user['experience']}/{user['level']*100}", inline=True)
        embed.add_field(name="Gold", value=user["gold"], inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="use", description="Use an item from your inventory")
    async def use(self, interaction: discord.Interaction, item: str):
        user_id = str(interaction.user.id)
        user = self.get_user(user_id)
        item = item.lower()
        
        if user["inventory"].get(item, 0) <= 0:
            await interaction.response.send_message(f"You don't have any {item}!", ephemeral=True)
            return
        
        item_data = self.items.get(item)
        if not item_data:
            await interaction.response.send_message("That item doesn't exist!", ephemeral=True)
            return
        
        user["inventory"][item] -= 1
        if user["inventory"][item] == 0:
            del user["inventory"][item]
        
        if item_data["type"] == "heal":
            user["health"] = min(user["max_health"], user["health"] + item_data["value"])
            response = f"❤️ Healed for {item_data['value']} HP!"
        elif item_data["type"] == "weapon":
            user["attack"] += item_data["value"]
            response = f"⚔️ Attack increased by {item_data['value']}!"
        elif item_data["type"] == "armor":
            user["defense"] += item_data["value"]
            response = f"🛡️ Defense increased by {item_data['value']}!"
        
        SaveJson("DataFiles/rpgFiles/players.json", self.user_data)
        await interaction.response.send_message(response, ephemeral=True)

async def setup(client):
    await client.add_cog(RPG(client))
    print("RPG System Online")