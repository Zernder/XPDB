const fs = require('node:fs');
const path = require('node:path');
const axios = require('axios');
const { Client, Collection, Events, GatewayIntentBits } = require('discord.js');
require('dotenv').config();

const url = process.env.OllamaURL;
const Token = process.env.BotToken;
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.DirectMessages,
    ],
    partials: ['CHANNEL'] // Enable Channel partial
});

const BotNames = ['tamachat']; // Assuming this is your list of channels or keywords

console.log('Registering messageCreate event handler...');
client.on('messageCreate', async (message) => {
    console.log('messageCreate event fired!');
    try {
        if (message.content.startsWith('!')) { // Check if the message starts with '!'
            await client.processCommands(message); // Process the command
            return;
        }
        if (message.author.bot) { // Ignore messages from bots
            return;
        }
        else { // Check if the message is in 'tamachat' channel or is a DM
            console.log("Sending Message!");
            const payload = {
                model: "Tamaki",
                messages: [{ role: "user", content: message.content }],
                stream: false,
            }; // Parameters for the POST request
            const response = await axios.post(url, payload, {
                headers: { 'Content-Type': 'application/json' },
            }); // Send the POST request using axios
            const response_data = response.data; // Get the text response from the API call
            const response_text = response_data.message.content;
            await message.channel.send(response_text); // Send the text response
        }
    } catch (e) {
        console.error(`Error in on_message: ${e}`);
    }
});




client.on(Events.InteractionCreate, interaction => {
	console.log(interaction);
});


client.on(Events.InteractionCreate, async interaction => {
	if (!interaction.isChatInputCommand()) return;

	const command = interaction.client.commands.get(interaction.commandName);

	if (!command) {
		console.error(`No command matching ${interaction.commandName} was found.`);
		return;
	}

	try {
		await command.execute(interaction);
	} catch (error) {
		console.error(error);
		if (interaction.replied || interaction.deferred) {
			await interaction.followUp({ content: 'There was an error while executing this command!', ephemeral: true });
		} else {
			await interaction.reply({ content: 'There was an error while executing this command!', ephemeral: true });
		}
	}
});


client.commands = new Collection();

const foldersPath = path.join(__dirname, 'commands');
const commandFolders = fs.readdirSync(foldersPath);

for (const folder of commandFolders) {
	const commandsPath = path.join(foldersPath, folder);
	const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));
	for (const file of commandFiles) {
		const filePath = path.join(commandsPath, file);
		const command = require(filePath);
		// Set a new item in the Collection with the key as the command name and the value as the exported module
		if ('data' in command && 'execute' in command) {
			client.commands.set(command.data.name, command);
		} else {
			console.log(`[WARNING] The command at ${filePath} is missing a required "data" or "execute" property.`);
		}
	}
}



client.once(Events.ClientReady, readyClient => {
	console.log(`Ready! Logged in as ${readyClient.user.tag}`);
});


client.once('ready', () => {
    console.log('Bot is ready!');
});

// Log in to Discord with your client's token
client.login(Token);



