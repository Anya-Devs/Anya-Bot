import os
import discord
from PIL import Image, ImageDraw
from discord.ext import commands

from Imports.log_imports import logger
import asyncio


class AvatarChanger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emojis_folder = "Data/Emojis"  # Path to the folder containing image files
        self.output_folder = "Data/Emojis/output"  # Path for output grid images

        # Ensure the emojis and output directories exist
        os.makedirs(self.emojis_folder, exist_ok=True)
        os.makedirs(self.output_folder, exist_ok=True)

    async def compose_grid(self, images, output_filename, ctx, grid_index):
        try:
            images_per_row = 5  # Number of images per row
            spacing = 10  # Spacing between images
            img_width, img_height = 512, 512  # Image size for high resolution

            # Calculate total rows needed
            total_rows = (len(images) + images_per_row - 1) // images_per_row

            # Calculate composite image size
            composite_width = img_width * images_per_row + spacing * (
                images_per_row - 1
            )
            composite_height = img_height * total_rows + spacing * (total_rows - 1)
            composite_image = Image.new(
                "RGBA", (composite_width, composite_height), color=(255, 255, 255, 0)
            )

            # Paste images onto the composite image with circular masks
            x_offset, y_offset = 0, 0
            for i, img_path in enumerate(images):
                img = Image.open(os.path.join(self.emojis_folder, img_path)).resize(
                    (img_width, img_height), Image.LANCZOS
                )
                img = img.convert("RGBA")

                # Create a circular mask
                mask = Image.new("L", (img_width, img_height), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, img_width, img_height), fill=255)

                # Apply the circular mask to the image
                img = Image.composite(
                    img, Image.new("RGBA", img.size, (255, 255, 255, 0)), mask
                )

                # Position the image in the composite grid
                composite_image.paste(img, (x_offset, y_offset))

                # Update offsets for the next image
                x_offset += img_width + spacing
                if (i + 1) % images_per_row == 0:
                    x_offset = 0
                    y_offset += img_height + spacing

            # Save the composite grid image
            composite_image.save(
                os.path.join(self.output_folder, output_filename), "PNG"
            )

            # Send the grid image with navigation buttons if there are more than 5 images
            if len(images) > 5:
                view = discord.ui.View()
                if grid_index > 1:
                    prev_button = discord.ui.Button(
                        label="Previous", style=discord.ButtonStyle.primary
                    )
                    prev_button.callback = self.create_grid_callback(
                        ctx, grid_index - 1
                    )
                    view.add_item(prev_button)

                next_button = discord.ui.Button(
                    label="Next", style=discord.ButtonStyle.primary
                )
                next_button.callback = self.create_grid_callback(ctx, grid_index + 1)
                view.add_item(next_button)

                grid_message = await ctx.send(
                    file=discord.File(
                        os.path.join(self.output_folder, output_filename)
                    ),
                    view=view,
                )
            else:
                grid_message = await ctx.send(
                    file=discord.File(os.path.join(self.output_folder, output_filename))
                )

            # Add reactions for navigation if there are more than 0 images
            if len(images) > 0:
                for i in range(len(images)):
                    await grid_message.add_reaction(
                        f"{i+1}\N{COMBINING ENCLOSING KEYCAP}"
                    )

            return grid_message

        except Exception as e:
            logger.error(f"An error occurred while composing grid: {e}")
            raise  # Re-raise the exception to propagate it to the caller

    def create_grid_callback(self, ctx, grid_index):
        async def callback(interaction):
            try:
                # Check if the interaction is from the correct user and message
                if (
                    interaction.user != ctx.author
                    or interaction.message.id != interaction.message.id
                ):
                    logger.debug(
                        f"Ignoring interaction from user {interaction.user.id} because it does not match the context."
                    )
                    return

                # Determine the action based on the custom_id of the interaction
                custom_id = interaction.data["custom_id"]
                if custom_id == "previous":
                    grid_index -= 1
                elif custom_id == "next":
                    grid_index += 1

                # Ensure grid_index stays within valid bounds
                images = [
                    f
                    for f in os.listdir(self.emojis_folder)
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
                ]
                total_images = len(images)
                total_pages = (
                    total_images + 4
                ) // 5  # Calculate total pages (5 images per page)

                if grid_index < 1:
                    grid_index = 1
                elif grid_index > total_pages:
                    grid_index = total_pages

                logger.debug(
                    f"Current grid index: {grid_index}, Total pages: {total_pages}"
                )

                # Calculate which images to display for the current page
                start_index = (grid_index - 1) * 5
                end_index = min(grid_index * 5, total_images)
                grid_images = images[start_index:end_index]

                logger.debug(f"Images to display: {grid_images}")

                # Compose the grid with the current page's images
                output_filename = f"grid_output_{grid_index}.png"
                await self.compose_grid(grid_images, output_filename, ctx, grid_index)

                # Respond to the interaction (acknowledge it)
                await interaction.response.defer()

                logger.debug("Interaction acknowledged successfully.")

                # Update the grid message with navigation buttons for the current page
                if len(images) > 5:
                    await self.update_grid_message(ctx, grid_index, total_pages)

                # Update reactions on the message for pagination
                await self.update_grid_reactions(
                    interaction.message, grid_index, total_pages
                )

            except Exception as e:
                logger.error(f"Error in grid callback: {e}")
                await interaction.response.send_message(
                    "An error occurred while processing your request."
                )

        return callback

    async def update_grid_message(self, ctx, grid_index, total_pages):
        # Update the existing grid message with new navigation buttons
        try:
            images = [
                f
                for f in os.listdir(self.emojis_folder)
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
            ]
            images.sort()  # Sort filenames alphabetically

            images_per_page = 5  # Number of images per page
            img_width, img_height = 256, 256  # Image size for high resolution
            spacing = 10  # Spacing between images

            start_index = (grid_index - 1) * images_per_page
            end_index = min(start_index + images_per_page, len(images))
            grid_images = images[start_index:end_index]

            # Create composite grid image
            output_filename = f"grid_output_{grid_index}.png"
            await self.compose_grid(grid_images, output_filename, ctx, grid_index)

            # Retrieve the grid message
            message = await ctx.fetch_message(ctx.message.id)

            # Edit the grid message with updated navigation buttons
            if len(images) > 5:
                view = discord.ui.View()
                if grid_index > 1:
                    prev_button = discord.ui.Button(
                        label="Previous", style=discord.ButtonStyle.primary
                    )
                    prev_button.callback = self.create_grid_callback(
                        ctx, grid_index - 1
                    )
                    view.add_item(prev_button)

                next_button = discord.ui.Button(
                    label="Next", style=discord.ButtonStyle.primary
                )
                next_button.callback = self.create_grid_callback(ctx, grid_index + 1)
                view.add_item(next_button)

                await message.edit(view=view)

        except Exception as e:
            logger.error(f"An error occurred while updating grid message: {e}")
            raise

    async def update_grid_reactions(self, message, grid_index, total_pages):
        try:
            # Add reactions for image selection if there are any images
            if total_pages > 1:
                for i in range(total_pages):
                    await message.add_reaction(f"{i+1}\N{COMBINING ENCLOSING KEYCAP}")

        except Exception as e:
            logger.error(
                f"An error occurred while updating reactions on the grid message: {e}"
            )
            raise

    def check_reaction(self, reaction, user):
        def inner_check(reaction, user):
            # Only process reactions from the original command author
            return user == self.ctx.author and str(reaction.emoji) in [
                f"{i+1}\N{COMBINING ENCLOSING KEYCAP}" for i in range(5)
            ]

        return inner_check

    @commands.command(name="grid", hidden=True)
    @commands.is_owner()
    async def grid_command(self, ctx):
        try:
            images = [
                f
                for f in os.listdir(self.emojis_folder)
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
            ]
            images.sort()  # Sort filenames alphabetically

            if not images:
                await ctx.send("No images found in the folder.")
                return

            images_per_page = 5  # Number of images per page
            total_pages = (
                len(images) + images_per_page - 1
            ) // images_per_page  # Calculate total pages

            grid_index = 1
            start_index = (grid_index - 1) * images_per_page
            end_index = min(start_index + images_per_page, len(images))
            grid_images = images[start_index:end_index]

            output_filename = f"grid_output_{grid_index}.png"
            grid_message = await self.compose_grid(
                grid_images, output_filename, ctx, grid_index
            )

            # Store the grid message in the context for later use
            ctx.grid_message = grid_message

            # Add reactions for pagination
            await self.update_grid_reactions(grid_message, grid_index, total_pages)

            # Wait for reaction
            def check_reaction(reaction, user):
                return user == ctx.author and str(reaction.emoji) in [
                    f"{i+1}\N{COMBINING ENCLOSING KEYCAP}" for i in range(5)
                ]

            while True:
                try:
                    reaction, user = await self.bot.wait_for(
                        "reaction_add", timeout=60.0, check=check_reaction
                    )
                    reaction_index = int(reaction.emoji[0]) - 1

                    # Get the selected image based on the reaction index
                    selected_image_index = (
                        grid_index - 1
                    ) * images_per_page + reaction_index
                    if selected_image_index < len(images):
                        selected_image = images[selected_image_index]

                        # Prepare the embed with the selected image as an attachment
                        embed = discord.Embed(
                            title="Select an image",
                            description=f"Avatar changed to {selected_image}",
                            color=discord.Color.blurple(),
                        )
                        embed.set_thumbnail(url="attachment://grid_output.png")

                        # Send embed with the grid image as attachment
                        file = discord.File(
                            os.path.join(self.output_folder, output_filename)
                        )
                        await grid_message.edit(
                            content=None, embed=embed, attachments=[file]
                        )
                        await grid_message.clear_reactions()

                    else:
                        await ctx.send("Invalid selection. Please try again.")

                except asyncio.TimeoutError:
                    await ctx.send("Reaction timeout. Please try again.")
                    break
                except Exception as e:
                    logger.error(
                        f"An error occurred while processing the reaction: {e}"
                    )
                    await ctx.send(
                        "An error occurred while processing your reaction. Please try again."
                    )
                    break

        except Exception as e:
            logger.error(f"An error occurred while executing grid command: {e}")
            await ctx.send("An error occurred while generating the grid.")


async def setup(bot):
    await bot.add_cog(AvatarChanger(bot))
