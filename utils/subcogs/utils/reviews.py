import os
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from data.local.const import primary_color


class ReviewUtils:
    def __init__(self, mongo):
        self.mongo = mongo
        self.view_utils = Review_View()
        self.utils = Review_Utils()

    async def get_overview(self, ctx, member):
        return await self.view_utils.select.get_overview(ctx, member, self.mongo)

    async def add_review(self, ctx, member):
        return await self.utils.action.add_review(ctx, member, self.mongo)

    async def edit_review(self, ctx, member):
        return await self.utils.action.edit_review(ctx, member, self.mongo)

    async def remove_review(self, ctx, member):
        return await self.utils.action.remove_review(ctx, member, self.mongo)

    @staticmethod
    def get_add_embed(member):
        return discord.Embed(
            title="Review Added",
            description=f"Your review for {member.mention} has been added successfully.",
            color=primary_color()
        )

    @staticmethod
    def get_edit_embed(member):
        return discord.Embed(
            title="Review Edited",
            description=f"Your review for {member.mention} has been updated successfully.",
            color=primary_color()
        )

    @staticmethod
    def get_remove_embed(member):
        return discord.Embed(
            title="Review Removed",
            description=f"Your review for {member.mention} has been removed successfully.",
            color=discord.Color.red()
        )


class MongoManager:
    def __init__(self):
        self.mongo_url = os.getenv("MONGO_URI")
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client["Commands"]
        self.collection = self.db["reviews"]

    async def add_review(self, reviewer_id, target_id, stars, review):
        doc = {
            "reviewer_id": reviewer_id,
            "target_id": target_id,
            "stars": stars,
            "review": review,
            "upvotes": 0,
            "downvotes": 0,
            "timestamp": datetime.utcnow()
        }
        await self.collection.insert_one(doc)

    async def get_reviews_for_user(self, target_id):
        reviews = await self.collection.find({"target_id": target_id}).to_list(None)
        reviews.sort(key=lambda r: r.get("upvotes", 0), reverse=True)
        return reviews

    async def get_average_rating(self, target_id):
        reviews = await self.get_reviews_for_user(target_id)
        if not reviews:
            return 0
        return sum(r["stars"] for r in reviews) / len(reviews)

    async def vote_review(self, review_id, up=True):
        field = "upvotes" if up else "downvotes"
        await self.collection.update_one({"_id": review_id}, {"$inc": {field: 1}})


class Review_View:
    def __init__(self):
        self.select = ReviewerSelectView()


class Review_Utils:
    def __init__(self):
        self.action = ReviewActions()


class ReviewerSelect(discord.ui.Select):
    def __init__(self, members_with_reviews=None):
        options = []
        if members_with_reviews:
            for member in members_with_reviews:
                options.append(discord.SelectOption(label=member.display_name, value=str(member.id)))
        else:
            options = [discord.SelectOption(label="No reviews found", value="none", default=True, description="No members with reviews")]
        super().__init__(
            placeholder="Select a member to view reviews",
            min_values=1,
            max_values=1,
            options=options
        )
        self.members_with_reviews = members_with_reviews or []

    async def callback(self, interaction: discord.Interaction):
        selected_member_id = int(self.values[0])
        member = interaction.guild.get_member(selected_member_id)
        if not member:
            await interaction.response.send_message("Member not found.", ephemeral=True)
            return
        reviews = await self.view.mongo.get_reviews_for_user(member.id)
        if not reviews:
            embed = discord.Embed(title=f"No reviews found for {member.display_name}", color=discord.Color.greyple())
        else:
            self_review = next((r for r in reviews if r["reviewer_id"] == member.id), None)
            main_review = self_review or reviews[0]
            avg_rating = await self.view.mongo.get_average_rating(member.id)
            embed = discord.Embed(
                title=f"Reviews for {member.display_name}",
                description=f"Average Rating: {avg_rating:.2f} ⭐\n\n**Highlighted Review:**\n{main_review['review']}",
                color=primary_color()
            )
            embed.set_footer(text=f"Upvotes: {main_review.get('upvotes',0)} | Downvotes: {main_review.get('downvotes',0)}")
        await interaction.response.edit_message(embed=embed, view=self.view)


class ReviewerSelectView(discord.ui.View):
    def __init__(self, mongo=None, guild=None):
        super().__init__()
        self.mongo = mongo
        self.guild = guild
        self.members_with_reviews = []
        self.select = None

    async def setup(self):
        all_reviews = await self.mongo.collection.find().to_list(None)
        member_ids = set(r["target_id"] for r in all_reviews)
        self.members_with_reviews = [self.guild.get_member(mid) for mid in member_ids if self.guild.get_member(mid)]
        self.select = ReviewerSelect(self.members_with_reviews)
        self.select.view = self
        self.add_item(self.select)

    async def get_overview(self, ctx, member, mongo):
        self.mongo = mongo
        self.guild = ctx.guild
        await self.setup()
        reviews = await mongo.get_reviews_for_user(member.id)
        if not reviews:
            embed = discord.Embed(title=f"No reviews found for {member.display_name}", color=discord.Color.greyple())
        else:
            self_review = next((r for r in reviews if r["reviewer_id"] == member.id), None)
            main_review = self_review or reviews[0]
            avg_rating = await mongo.get_average_rating(member.id)
            embed = discord.Embed(
                title=f"Reviews for {member.display_name}",
                description=f"Average Rating: {avg_rating:.2f} ⭐\n\n**Highlighted Review:**\n{main_review['review']}",
                color=primary_color()
            )
            embed.set_footer(text=f"Upvotes: {main_review.get('upvotes',0)} | Downvotes: {main_review.get('downvotes',0)}")
        return await ctx.send(embed=embed, view=self, ephemeral=True)


class ReviewActions:
    async def add_review(self, ctx, member, mongo: MongoManager):
        modal = AddReviewModal(member, mongo)
        await ctx.send_modal(modal)

    async def edit_review(self, ctx, member, mongo: MongoManager):
        modal = EditReviewModal(member, mongo)
        await ctx.send_modal(modal)

    async def remove_review(self, ctx, member, mongo: MongoManager):
        review = await mongo.collection.find_one({"reviewer_id": ctx.author.id, "target_id": member.id})
        if review:
            await mongo.collection.delete_one({"_id": review["_id"]})
        embed = ReviewUtils.get_remove_embed(member)
        await ctx.send(embed=embed, ephemeral=True)


class AddReviewModal(discord.ui.Modal, title="Add Review"):
    def __init__(self, member, mongo: MongoManager):
        super().__init__()
        self.member = member
        self.mongo = mongo
        self.add_item(discord.ui.InputText(label="Stars (1-5)", placeholder="Enter rating"))
        self.add_item(discord.ui.InputText(label="Review", style=discord.InputTextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        stars = int(self.children[0].value)
        review_text = self.children[1].value
        await self.mongo.add_review(interaction.user.id, self.member.id, stars, review_text)
        embed = ReviewUtils.get_add_embed(self.member)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditReviewModal(discord.ui.Modal, title="Edit Review"):
    def __init__(self, member, mongo: MongoManager):
        super().__init__()
        self.member = member
        self.mongo = mongo
        self.add_item(discord.ui.InputText(label="Stars (1-5)", placeholder="Enter new rating"))
        self.add_item(discord.ui.InputText(label="Review", style=discord.InputTextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        stars = int(self.children[0].value)
        review_text = self.children[1].value
        await self.mongo.collection.update_one(
            {"reviewer_id": interaction.user.id, "target_id": self.member.id},
            {"$set": {"stars": stars, "review": review_text, "timestamp": datetime.utcnow()}}
        )
        embed = ReviewUtils.get_edit_embed(self.member)
        await interaction.response.send_message(embed=embed, ephemeral=True)
