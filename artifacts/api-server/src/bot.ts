import {
  ActionRowBuilder,
  AttachmentBuilder,
  ButtonBuilder,
  ButtonStyle,
  ChannelType,
  Client,
  EmbedBuilder,
  Events,
  GatewayIntentBits,
  PermissionFlagsBits,
  PermissionsBitField,
  StringSelectMenuBuilder,
  type Guild,
  type GuildMember,
  type Interaction,
  type Message,
  type TextChannel,
} from "discord.js";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { logger } from "./lib/logger";

const MAX_BET = 1_000_000;
const PREFIX = "!";
const STORE_PATH = path.resolve(process.cwd(), "data/discord-bot.json");

type GuildConfig = {
  supportRoleId?: string;
  matchesEnabled: boolean;
  channelEmojis: boolean;
};

type SlipPick = {
  matchId: string;
  match: string;
  market: string;
  odds: number;
};

type BotStore = {
  configs: Record<string, GuildConfig>;
  slips: Record<string, SlipPick[]>;
};

const defaultConfig = (): GuildConfig => ({
  matchesEnabled: true,
  channelEmojis: true,
});

function loadStore(): BotStore {
  if (!existsSync(STORE_PATH)) return { configs: {}, slips: {} };
  try {
    return JSON.parse(readFileSync(STORE_PATH, "utf8")) as BotStore;
  } catch (error) {
    logger.warn(
      { error },
      "Could not read Discord bot data; starting with empty state",
    );
    return { configs: {}, slips: {} };
  }
}

const store = loadStore();

function saveStore() {
  const directory = path.dirname(STORE_PATH);
  if (!existsSync(directory)) mkdirSync(directory, { recursive: true });
  writeFileSync(STORE_PATH, JSON.stringify(store, null, 2));
}

function configFor(guildId: string) {
  store.configs[guildId] ??= defaultConfig();
  return store.configs[guildId];
}

function nextMatches() {
  const leagues = [
    ["Premier League", "Arsenal", "Chelsea"],
    ["La Liga", "Barcelona", "Atlético Madrid"],
    ["Serie A", "Inter Milan", "Napoli"],
    ["Bundesliga", "Bayern Munich", "Dortmund"],
    ["Ligue 1", "PSG", "Lyon"],
    ["Champions League", "Real Madrid", "Manchester City"],
    ["Europa League", "Roma", "Leverkusen"],
    ["Premier League", "Liverpool", "Tottenham"],
    ["La Liga", "Real Sociedad", "Sevilla"],
    ["Serie A", "Juventus", "AC Milan"],
  ];
  const start = new Date();
  start.setMinutes(0, 0, 0);
  return leagues.map(([league, home, away], index) => ({
    id: `M${index + 1}`,
    league,
    home,
    away,
    kickoff: new Date(start.getTime() + (index + 1) * 3_600_000 * 8),
  }));
}

const marketOptions = [
  ["1", "Match winner — Home", 1.85],
  ["2", "Match winner — Draw", 3.4],
  ["3", "Match winner — Away", 4.2],
  ["4", "Double chance — 1X", 1.25],
  ["5", "Double chance — X2", 1.9],
  ["6", "Goals — Over 1.5", 1.28],
  ["7", "Goals — Under 1.5", 3.1],
  ["8", "Goals — Over 2.5", 1.8],
  ["9", "Goals — Under 2.5", 1.95],
  ["10", "Goals — Over 3.5", 2.65],
  ["11", "Goals — Under 3.5", 1.45],
  ["12", "Both teams to score — Yes", 1.7],
  ["13", "Both teams to score — No", 2.05],
  ["14", "First half — Over 0.5 goals", 1.35],
  ["15", "First half — Under 0.5 goals", 2.75],
  ["16", "Corners — Over 8.5", 1.8],
  ["17", "Corners — Under 8.5", 1.9],
  ["18", "Cards — Over 3.5", 1.75],
  ["19", "Cards — Under 3.5", 1.95],
] as const;

function rouletteSvg(number: number, color: string) {
  const accent =
    color === "red" ? "#ef4444" : color === "black" ? "#111827" : "#16a34a";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">
    <defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#0b1220"/><stop offset="1" stop-color="#172554"/></linearGradient></defs>
    <rect width="900" height="520" rx="34" fill="url(#g)"/>
    <circle cx="450" cy="235" r="170" fill="#0f172a" stroke="#d4af37" stroke-width="10"/>
    <circle cx="450" cy="235" r="128" fill="${accent}" opacity=".95" stroke="#f8fafc" stroke-width="4"/>
    <circle cx="450" cy="235" r="90" fill="#0b1220" stroke="#d4af37" stroke-width="5"/>
    <text x="450" y="260" text-anchor="middle" font-family="Arial,sans-serif" font-size="130" font-weight="800" fill="#fff">${number}</text>
    <text x="450" y="76" text-anchor="middle" font-family="Arial,sans-serif" font-size="28" letter-spacing="7" fill="#f8fafc">ROULETTE RESULT</text>
    <text x="450" y="455" text-anchor="middle" font-family="Arial,sans-serif" font-size="42" font-weight="700" fill="#fff">${color.toUpperCase()}</text>
  </svg>`;
}

function isAdmin(member: GuildMember | null) {
  return Boolean(
    member?.permissions.has(PermissionsBitField.Flags.Administrator),
  );
}

function emojiName(name: string) {
  const lower = name.toLowerCase();
  const emoji = lower.includes("ticket")
    ? "🎫"
    : lower.includes("support")
      ? "🛟"
      : lower.includes("roulette")
        ? "🎰"
        : lower.includes("match") || lower.includes("sport")
          ? "🏟️"
          : lower.includes("bet") || lower.includes("slip")
            ? "🎟️"
            : lower.includes("admin") || lower.includes("staff")
              ? "🛡️"
              : lower.includes("general") || lower.includes("chat")
                ? "💬"
                : "📌";
  return name.startsWith(emoji)
    ? name
    : `${emoji}-${name.replace(/^[^\p{L}\p{N}]+/u, "")}`;
}

async function syncChannelNames(guild: Guild) {
  const config = configFor(guild.id);
  if (!config.channelEmojis) return;
  for (const channel of guild.channels.cache.values()) {
    if (!channel.isTextBased()) continue;
    const nextName = emojiName(channel.name);
    if (nextName !== channel.name && channel.manageable) {
      await channel
        .setName(nextName, "Apply configured channel emojis")
        .catch((error) =>
          logger.warn(
            { error, channelId: channel.id },
            "Unable to rename Discord channel",
          ),
        );
    }
  }
}

async function sendMatches(message: Message, config: GuildConfig) {
  if (!config.matchesEnabled) {
    await message.reply(
      "The match list has been disabled by an administrator.",
    );
    return;
  }
  const lines = nextMatches().map(
    (match) =>
      `**${match.id}** · ${match.league}\n${match.home} vs ${match.away} · <t:${Math.floor(match.kickoff.getTime() / 1000)}:F>`,
  );
  await message.reply({
    embeds: [
      new EmbedBuilder()
        .setColor(0xd4af37)
        .setTitle("🏟️ Next 10 matches")
        .setDescription(
          `${lines.join("\n\n")}\n\nUse \`!betbuilder M1\` to build a slip for a match.`,
        ),
    ],
  });
}

async function openBetBuilder(message: Message, matchId: string) {
  const match = nextMatches().find((item) => item.id === matchId.toUpperCase());
  if (!match) {
    await message.reply(
      "I couldn't find that match. Run `!matches` first and use an ID such as `M1`.",
    );
    return;
  }
  const menu = new StringSelectMenuBuilder()
    .setCustomId(`betbuilder:${match.id}`)
    .setPlaceholder("Choose a market and odds")
    .addOptions(
      marketOptions.map(([value, label, odds]) => ({
        value,
        label: label.slice(0, 100),
        description: `${match.home} vs ${match.away} · Odds ${odds.toFixed(2)}`,
      })),
    );
  await message.reply({
    embeds: [
      new EmbedBuilder()
        .setColor(0x2563eb)
        .setTitle(`🎯 Bet builder · ${match.id}`)
        .setDescription(
          `**${match.home} vs ${match.away}**\nPick any supported market below. Your selection is added to your sharable slip.`,
        )
        .addFields({
          name: "Markets included",
          value:
            "1X2, double chance, over/under goals, both teams to score, first-half goals, corners, and cards.",
        }),
    ],
    components: [
      new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu),
    ],
  });
}

async function showSlip(message: Message, args: string[]) {
  const key = `${message.guildId}:${message.author.id}`;
  const picks = store.slips[key] ?? [];
  if (args[0]?.toLowerCase() === "clear") {
    delete store.slips[key];
    saveStore();
    await message.reply("Your betting slip has been cleared.");
    return;
  }
  if (args[0]?.toLowerCase() === "stake") {
    const stake = Number(args[1]);
    if (!Number.isFinite(stake) || stake <= 0) {
      await message.reply(
        "Enter a valid stake, for example `!slip stake 5000`.",
      );
      return;
    }
    if (stake > MAX_BET) {
      await message.reply("The maximum stake is **₦1,000,000** per slip.");
      return;
    }
    await message.reply(
      `Stake set to **₦${stake.toLocaleString("en-NG")}**. Maximum allowed: ₦1,000,000.`,
    );
    return;
  }
  if (!picks.length) {
    await message.reply(
      "Your slip is empty. Use `!matches`, then `!betbuilder M1` to add a pick.",
    );
    return;
  }
  const totalOdds = picks.reduce((total, pick) => total * pick.odds, 1);
  await message.reply({
    embeds: [
      new EmbedBuilder()
        .setColor(0x16a34a)
        .setTitle(
          `🎟️ Betting slip · ${picks.length} pick${picks.length === 1 ? "" : "s"}`,
        )
        .setDescription(
          picks
            .map(
              (pick, index) =>
                `${index + 1}. **${pick.match}**\n${pick.market} · **${pick.odds.toFixed(2)}**`,
            )
            .join("\n\n"),
        )
        .addFields(
          { name: "Combined odds", value: totalOdds.toFixed(2), inline: true },
          { name: "Max stake", value: "₦1,000,000", inline: true },
        )
        .setFooter({
          text: "Share this message with your friends • !slip clear to reset",
        }),
    ],
  });
}

async function createTicket(
  guild: Guild,
  userId: string,
  username: string,
  config: GuildConfig,
  parentId?: string,
) {
  const supportRole = config.supportRoleId
    ? guild.roles.cache.get(config.supportRoleId)
    : undefined;
  const channel = await guild.channels.create({
    name: `ticket-${username}`
      .toLowerCase()
      .replace(/[^a-z0-9-]/g, "")
      .slice(0, 70),
    type: ChannelType.GuildText,
    parent: parentId,
    permissionOverwrites: [
      { id: guild.id, deny: [PermissionFlagsBits.ViewChannel] },
      {
        id: userId,
        allow: [
          PermissionFlagsBits.ViewChannel,
          PermissionFlagsBits.SendMessages,
          PermissionFlagsBits.ReadMessageHistory,
        ],
      },
      ...(supportRole
        ? [
            {
              id: supportRole.id,
              allow: [
                PermissionFlagsBits.ViewChannel,
                PermissionFlagsBits.SendMessages,
                PermissionFlagsBits.ReadMessageHistory,
              ],
            },
          ]
        : []),
    ],
  });
  await channel.send({
    content: `<@${userId}> ${supportRole ? `and ${supportRole}` : ""} — support will respond here.`,
    components: [
      new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder()
          .setCustomId("ticket:close")
          .setLabel("Close ticket")
          .setStyle(ButtonStyle.Danger)
          .setEmoji("🔒"),
      ),
    ],
  });
  return channel;
}

async function handleInteraction(interaction: Interaction) {
  if (!interaction.isButton() && !interaction.isStringSelectMenu()) return;
  if (interaction.isButton() && interaction.customId === "ticket:create") {
    if (!interaction.guild || !interaction.member) return;
    const config = configFor(interaction.guild.id);
    const channel = await createTicket(
      interaction.guild,
      interaction.user.id,
      interaction.user.username,
      config,
      interaction.channel?.isTextBased() && "parentId" in interaction.channel
        ? (interaction.channel.parentId ?? undefined)
        : undefined,
    );
    await interaction.reply({
      content: `Your private support ticket is ready: ${channel}.`,
      ephemeral: true,
    });
    return;
  }
  if (interaction.isButton() && interaction.customId === "ticket:close") {
    const member = interaction.member as GuildMember;
    if (!isAdmin(member)) {
      await interaction.reply({
        content: "Only server administrators can close tickets.",
        ephemeral: true,
      });
      return;
    }
    if (interaction.channel?.isTextBased()) {
      await interaction.reply("🔒 Ticket closed by an administrator.");
      if ("delete" in interaction.channel)
        await interaction.channel.delete("Closed by administrator");
    }
    return;
  }
  if (
    interaction.isStringSelectMenu() &&
    interaction.customId.startsWith("betbuilder:")
  ) {
    const matchId = interaction.customId.split(":")[1];
    const match = nextMatches().find((item) => item.id === matchId);
    const option = marketOptions.find(
      ([value]) => value === interaction.values[0],
    );
    if (!match || !option || !interaction.guildId) return;
    const key = `${interaction.guildId}:${interaction.user.id}`;
    store.slips[key] ??= [];
    store.slips[key].push({
      matchId,
      match: `${match.home} vs ${match.away}`,
      market: option[1],
      odds: option[2],
    });
    saveStore();
    await interaction.reply({
      content: `Added **${option[1]}** at **${option[2].toFixed(2)}** to your slip. Use \`!slip\` to view and share it.`,
      ephemeral: true,
    });
  }
}

export function startDiscordBot() {
  const token = process.env.DISCORD_TOKEN;
  if (!token) {
    logger.warn("DISCORD_TOKEN is not configured; Discord bot is disabled");
    return;
  }
  const client = new Client({
    intents: [
      GatewayIntentBits.Guilds,
      GatewayIntentBits.GuildMessages,
      GatewayIntentBits.MessageContent,
    ],
  });
  client.once(Events.ClientReady, async (readyClient) => {
    logger.info(
      { user: readyClient.user.tag },
      "Discord betting bot connected",
    );
    for (const guild of readyClient.guilds.cache.values())
      await syncChannelNames(guild);
  });
  client.on(
    Events.InteractionCreate,
    (interaction) => void handleInteraction(interaction),
  );
  client.on(Events.MessageCreate, async (message) => {
    if (
      message.author.bot ||
      !message.guild ||
      !message.content.startsWith(PREFIX)
    )
      return;
    const [command, ...args] = message.content
      .slice(PREFIX.length)
      .trim()
      .split(/\s+/);
    const config = configFor(message.guild.id);
    if (command === "matches") await sendMatches(message, config);
    else if (command === "betbuilder")
      await openBetBuilder(message, args[0] ?? "M1");
    else if (command === "slip") await showSlip(message, args);
    else if (command === "panel") {
      if (!isAdmin(message.member))
        return void message.reply(
          "Only server administrators can publish the ticket panel.",
        );
      await message.channel.send({
        embeds: [
          new EmbedBuilder()
            .setColor(0x0f766e)
            .setTitle("🛟 Need help?")
            .setDescription(
              "Click the button to open a private support ticket. Only support staff and you can see it.",
            ),
        ],
        components: [
          new ActionRowBuilder<ButtonBuilder>().addComponents(
            new ButtonBuilder()
              .setCustomId("ticket:create")
              .setLabel("Open support ticket")
              .setStyle(ButtonStyle.Primary)
              .setEmoji("🎫"),
          ),
        ],
      });
    } else if (command === "roulette") {
      const number = Math.floor(Math.random() * 37);
      const color = number === 0 ? "green" : number % 2 ? "red" : "black";
      const attachment = new AttachmentBuilder(
        Buffer.from(rouletteSvg(number, color)),
        { name: "roulette-result.svg" },
      );
      await message.reply({
        content: `🎰 The wheel landed on **${number} ${color}**.`,
        files: [attachment],
      });
    } else if (command === "config") {
      if (!isAdmin(message.member))
        return void message.reply(
          "Only server administrators can change bot settings.",
        );
      if (args[0] === "support-role") {
        const role = message.mentions.roles.first();
        if (!role)
          return void message.reply(
            "Mention a role, for example `!config support-role @Support`.",
          );
        config.supportRoleId = role.id;
        saveStore();
        await message.reply(`Support tickets will now tag ${role}.`);
      } else if (args[0] === "matches") {
        config.matchesEnabled = args[1]?.toLowerCase() !== "off";
        saveStore();
        await message.reply(
          `\`!matches\` is now **${config.matchesEnabled ? "enabled" : "disabled"}**.`,
        );
      } else if (args[0] === "emojis") {
        config.channelEmojis = args[1]?.toLowerCase() !== "off";
        saveStore();
        await syncChannelNames(message.guild);
        await message.reply(
          `Channel emoji naming is now **${config.channelEmojis ? "enabled" : "disabled"}**.`,
        );
      } else {
        await message.reply(
          "Admin settings: `!config support-role @Role`, `!config matches on|off`, `!config emojis on|off`.",
        );
      }
    }
  });
  client
    .login(token)
    .catch((error) => logger.error({ error }, "Discord bot login failed"));
}
