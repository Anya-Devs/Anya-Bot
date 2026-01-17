"""
Cover Art Collection View with Help Button
"""

import discord
from typing import Optional

class CoverCollectionView(discord.ui.View):
    """View for cover art collection with help button"""
    
    def __init__(self):
        super().__init__(timeout=180)
        self.message: Optional[discord.Message] = None
    
    async def on_timeout(self):
        """Disable buttons when view times out"""
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
    
    @discord.ui.button(label="❓ Help", style=discord.ButtonStyle.primary, custom_id="help_button")
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show help information about cover art system"""
        
        help_embed = discord.Embed(
            title="🎨 Cover Art System - Help",
            description="**How to manage your cover art collection:**",
            color=discord.Color.blue()
        )
        
        help_embed.add_field(
            name="📖 Viewing Your Collection",
            value="Use `.cover collection` to see all your purchased cover art.\n"
                  "Each embed shows one cover art with its image and details.",
            inline=False
        )
        
        help_embed.add_field(
            name="✅ Setting Active Cover Art",
            value="Use `.cover set <UID> <cover_id>` to set a cover as active.\n"
                  "**Example:** `.cover set B9EB6DCF ken_kaneki_176196`\n\n"
                  "Active covers will display when you use `.draw view <UID>`!",
            inline=False
        )
        
        help_embed.add_field(
            name="💸 Releasing Cover Art (10% Refund)",
            value="Use `.cover release <cover_id>` to delete a cover art.\n"
                  "**Example:** `.cover release ken_kaneki_176196`\n\n"
                  "You'll receive **10% of the original cost** back as a refund.\n"
                  "⚠️ This action is permanent and cannot be undone!",
            inline=False
        )
        
        help_embed.add_field(
            name="🔍 Image Sources",
            value="Cover art images are sourced from:\n"
                  "• **Safebooru.org** - Safe-for-work anime art\n"
                  "• **Konachan.net** - High-quality anime wallpapers\n\n"
                  "All sources are strictly SFW and character-searchable.",
            inline=False
        )
        
        help_embed.add_field(
            name="💰 Pricing",
            value="• **Common:** 100 pts\n"
                  "• **Uncommon:** 200 pts\n"
                  "• **Rare:** 500 pts\n"
                  "• **Epic:** 1,000 pts\n"
                  "• **Legendary:** 2,000 pts",
            inline=False
        )
        
        help_embed.set_footer(text="Use the commands shown in each embed's footer to manage your covers!")
        
        await interaction.response.send_message(embed=help_embed, ephemeral=True)
