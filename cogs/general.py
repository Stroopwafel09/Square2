from contextlib import suppress
from io import BytesIO
from re import compile
from typing import Optional
from urllib import parse

import discord
from discord import ApplicationContext

from core import Cog, GuildModel, humanize_time

PULL_HASH_REGEX = compile(
    r"(?:(?P<org>(?:[A-Za-z]|\d|-)+)/)?(?P<repo>(?:[A-Za-z]|\d|-)+)?(?:##)(?P<index>[0-9]+)"
)


class General(Cog):
    """General commands."""

    @discord.slash_command()
    @discord.guild_only()
    async def serverinfo(self, ctx: ApplicationContext):
        """View information/statistics about the server."""
        guild = ctx.guild
        assert guild
        creation = ((guild.id >> 22) + 1420070400000) // 1000
        boost_emoji = (
            "<:shiny_boost:1007971330332839996>"
            if guild.premium_subscription_count > 0
            else "<:boost:1007970712977420338>"
        )

        embed = (
            discord.Embed(
                title=guild.name,
                description=f"**ID:** {guild.id}\n\n**Features:**\n"
                + "\n".join(f"- {f.replace('_', ' ').title()}" for f in guild.features),
                color=0x0060FF,
            )
            .add_field(
                name="Members",
                value=f"Total: {guild.member_count}\nBots: {sum(m.bot for m in guild.members)}",
            )
            .add_field(
                name="Time of Creation",
                value=f"<t:{creation}>\n<t:{creation}:R>",
            )
            .add_field(
                name="Channels",
                value=f"Text: {len(guild.text_channels)}\nVoice: {len(guild.voice_channels)}"
                f"\nCategories: {len(guild.categories)}",
            )
            .add_field(
                name="Roles",
                value=f"{len(guild._roles)} roles\nHighest:\n{guild.roles[-1].mention}",
            )
            .add_field(
                name="Boost Status",
                value=f"Level {guild.premium_tier}\n"
                f"{boost_emoji}{guild.premium_subscription_count} boosts",
            )
            .set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )
        )
        if owner := guild.owner:
            embed.insert_field_at(0, name="Owner", value=f"{owner}\n{owner.mention}")
        if icon := guild.icon:
            embed.set_thumbnail(url=icon.url)
        await ctx.respond(embed=embed)

    @discord.slash_command()
    @discord.guild_only()
    @discord.option("suggestion", description="The suggestion.")
    async def suggest(self, ctx: ApplicationContext, *, suggestion: str):
        """Make a suggestion for the server. This will be sent to the channel set by the server managers."""
        if not (channel := await GuildModel.get_text_channel(ctx.guild, "suggestions")):
            return await ctx.respond("This server doesn't have a suggestions channel.")

        msg = await channel.send(
            embed=discord.Embed(
                description=suggestion,
                colour=discord.Color.blurple(),
            )
            .set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
            .set_footer(text=f"ID: {ctx.author.id}")
        )
        await msg.add_reaction("<:upvote:881521766231584848>")
        await msg.add_reaction("<:downvote:904068725475508274>")
        await ctx.respond(
            f"Your suggestion has been sent to {channel.mention}.", ephemeral=True
        )

    suggestions = discord.SlashCommandGroup(
        "suggestions",
        "Commands related to member suggestions.",
        guild_only=True,
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    @suggestions.command(name="set")
    @discord.option(
        "channel",
        description="The channel new member suggestions will be sent to.",
    )
    async def suggestions_set(
        self, ctx: ApplicationContext, channel: discord.TextChannel
    ):
        """Set the channel for member suggestions."""
        await GuildModel.update_or_create(
            id=ctx.guild_id, defaults={"suggestions": channel.id}
        )
        await ctx.respond(f"Member suggestions will now be sent to {channel.mention}.")

    @suggestions.command(name="disable")
    async def suggestions_disable(self, ctx: ApplicationContext):
        """Disable member suggestions."""
        if (
            guild := await GuildModel.filter(id=ctx.guild_id)
            .exclude(suggestions=0)
            .first()
        ):
            await guild.update_from_dict({"suggestions": 0}).save()
            return await ctx.respond(
                "Member suggestions have been disabled for this server."
            )
        await ctx.respond("Member suggestions are already disabled for this server.")

    @discord.slash_command()
    async def ping(self, ctx: ApplicationContext):
        """View the websocket latency of the bot."""
        await ctx.respond(f"Pong! `{self.bot.latency*1000:.2f}ms`")

    @discord.slash_command()
    @discord.option(
        "style",
        str,
        description="The style of the formatted timestamp.",
        choices=["f", "F", "d", "D", "t", "T", "R"],
        default=None,
    )
    async def timestamp(self, ctx: ApplicationContext, style: Optional[str]):
        """View the current timestamp."""
        time = discord.utils.utcnow()
        await ctx.respond(
            f"{discord.utils.format_dt(time, style=style)} (`{round(time.timestamp())}`)"
        )

    @discord.slash_command()
    @discord.option("query", description="The query to make.")
    async def search(self, ctx: ApplicationContext, *, query: str):
        """Get a search url from Bing, DuckDuckGo and Google."""
        param = parse.urlencode({"q": query})
        await ctx.respond(
            f"Use the buttons below to search for `{query}` on the internet.",
            view=discord.ui.View(
                discord.ui.Button(
                    label="Google", url=f"https://www.google.com/search?{param}"
                ),
                discord.ui.Button(
                    label="Bing", url=f"https://www.bing.com/search?{param}"
                ),
                discord.ui.Button(
                    label="DuckDuckGo", url=f"https://www.duckduckgo.com/?{param}"
                ),
            ),
        )

    emoji = discord.SlashCommandGroup(
        "emoji", "Commands related to emojis.", guild_only=True
    )

    @emoji.command(name="add")
    @discord.option("name", description="The name of the emoji.")
    @discord.option("url", description="The image url of the emoji.")
    async def emoji_add(self, ctx: ApplicationContext, name: str, url: str):
        """Add a custom emoji to this guild."""
        async with self.bot.http_session.get(url) as res:
            if 300 > res.status >= 200:
                emoji = await ctx.guild.create_custom_emoji(
                    name=name, image=BytesIO(await res.read()).getvalue()
                )
                await ctx.respond(f"{emoji} Successfully created emoji.")
            else:
                await ctx.respond(
                    f"An HTTP error has occured while fetching the image: {res.status} {res.reason}"
                )

    @emoji.command(name="delete")
    @discord.option("name", description="The name of the emoji to delete.")
    @discord.option(
        "reason", str, description="The reason to delete the emoji.", default=None
    )
    async def emoji_delete(
        self, ctx: ApplicationContext, name: str, reason: Optional[str]
    ):
        """Delete a custom emoji from this guild."""
        for emoji in ctx.guild.emojis:
            if emoji.name == name:
                await emoji.delete(reason=reason)
                return await ctx.respond(f"Successfully deleted `:{name}:`.")
        await ctx.respond(f'No emoji named "{name}" found.')

    @discord.slash_command()
    @discord.option(
        "reason",
        description="The message to show when you're mentioned.",
        default="_No reason specified._",
    )
    @discord.option(
        "change_nick",
        description="If True, your nickname will be prefixed with [AFK].",
        default=True,
    )
    async def afk(self, ctx: ApplicationContext, *, reason: str, change_nick: bool):
        """Become AFK."""
        await ctx.respond(f"Set your AFK: {reason}")
        self.bot.cache["afk"][ctx.author.id] = reason
        if change_nick and not ctx.author.display_name.startswith("[AFK] "):
            with suppress(discord.HTTPException):
                await ctx.author.edit(nick=f"[AFK] {ctx.author.display_name}")

    @Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # AFK
        if message.author.id in self.bot.cache["afk"].keys():
            del self.bot.cache["afk"][message.author.id]
            await message.add_reaction("\U0001f44b")
            if message.author.nick and message.author.nick.startswith("[AFK] "):
                with suppress(discord.HTTPException):
                    await message.author.edit(nick=message.author.nick[6:])
        for mention in message.mentions:
            if msg := self.bot.cache["afk"].get(mention.id):
                await message.channel.send(f"{mention.display_name} is AFK: {msg}")

        # Pull requests and issues
        def make_link(index, org=None, repo=None):
            org = org or "Pycord-Development"
            repo = repo or "pycord"
            return f"https://github.com/{org}/{repo}/pull/{index}"

        links = list(
            set(
                make_link(index, org, repo)
                for org, repo, index in PULL_HASH_REGEX.findall(message.content)
            )
        )[:15]
        if len(links) > 2:
            links = [f"<{link}>" for link in links]
        if links:
            await message.reply("\n".join(links))

    @discord.user_command(name="View Account Age")
    async def account_age(self, ctx, member: discord.Member):
        """View the age of an account."""
        age = discord.utils.utcnow() - member.created_at
        await ctx.respond(
            f"{member.mention} is {humanize_time(age)} old.", ephemeral=True
        )


def setup(bot):
    bot.add_cog(General(bot))
