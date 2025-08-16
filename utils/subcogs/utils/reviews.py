import os
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from bson import ObjectId
from data.local.const import primary_color

class ReviewUtils:
    def __init__(self, mongo):
        self.mongo = mongo
        self.view_utils = Review_Select()
        self.actions = ReviewActions(self)

    async def get_overview(self, ctx, member):
        return await self.view_utils.get_overview(ctx, member, self.mongo)

    async def add_review(self, ctx, member):
        return await self.actions.add_review(ctx, member, self.mongo)

    async def edit_review(self, ctx, member):
        return await self.actions.edit_review(ctx, member, self.mongo)

    async def remove_review(self, ctx, member):
        return await self.actions.remove_review(ctx, member, self.mongo)

    # ───────── embed factories ─────────
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

class Review_View(discord.ui.View):
    def __init__(self, mode=None, m=None, ctx_message=None):
        super().__init__(timeout=180)
        self.select = Review_Select()
        self.paginator = Review_Paginator()
        self.mode = mode
        self.modal = m
        if mode and m:
            self.add_item(ReviewButton(mode, m))
            self.add_item(CancelButton(ctx_message))



class ReviewButton(discord.ui.Button):
    def __init__(self, mode: str, modal=None):
        super().__init__(
            label="Add Review" if mode == 'add' else "Edit Review",
            style=discord.ButtonStyle.green if mode == 'add' else discord.ButtonStyle.blurple
        )
        self.modal = modal

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(self.modal)


class CancelButton(discord.ui.Button):
    def __init__(self, ctx_message):
        super().__init__(label="Cancel", style=discord.ButtonStyle.red)
        self.ctx_message = ctx_message

    async def callback(self, interaction: discord.Interaction):
        if self.ctx_message:
            await self.ctx_message.delete()
        await interaction.message.delete()

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


# ────────────────────────────────────────────────
#  Select-menu + Paginator
# ────────────────────────────────────────────────
class ReviewUserSelect(discord.ui.Select):
    def __init__(self, reviews, member, mongo, guild):
        options = []
        self.reviews = reviews
        self.member = member
        self.mongo = mongo
        self.guild = guild

        for r in reviews:
            reviewer = guild.get_member(int(r["reviewer_id"]))
            if reviewer:
                options.append(discord.SelectOption(
                    label=reviewer.display_name,
                    value=str(reviewer.id)
                ))

        super().__init__(
            placeholder="Select a reviewer to see their review…",
            min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]
        reviewer = self.guild.get_member(int(selected_id))
        review = next((r for r in self.reviews if r["reviewer_id"] == selected_id), None)

        if not review:
            await interaction.response.send_message(
                f"{reviewer.mention} has not reviewed {self.member.display_name}.", ephemeral=True
            )
            return

        star_txt = "⭐" * review["stars"]
        emb = discord.Embed(
            title=f"Review by {reviewer.display_name}",
            description=f"{star_txt}\n\n{review['review']}",
            color=primary_color()
        )
        emb.set_thumbnail(url=reviewer.display_avatar.url)
        emb.set_footer(text=f"👍 {review['upvotes']} | 👎 {review['downvotes']}", icon_url=interaction.user.display_avatar.url)

        view = discord.ui.View()
        btn_up = VoteButton(review["_id"], True, self.mongo)
        btn_down = VoteButton(review["_id"], False, self.mongo)

        user_vote = review.get("votes", {}).get(str(interaction.user.id))
        if user_vote == "up":
            btn_up.style = discord.ButtonStyle.green
        elif user_vote == "down":
            btn_down.style = discord.ButtonStyle.red

        view.add_item(btn_up)
        view.add_item(btn_down)

        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)


class Review_Select:
    async def get_overview(self, ctx, member, mongo: MongoManager):
        reviews = await mongo.get_reviews_for_user(str(member.id))
        if not reviews:
            emb = discord.Embed(
                title=f"{member.display_name}'s Reviews",
                description="No reviews yet.",
                color=primary_color()
            )
            emb.set_thumbnail(url=member.avatar.url)
            return emb, None

        avg = await mongo.get_average_rating(str(member.id))
        emb = discord.Embed(
            title=f"{member.display_name}'s Reviews",
            description=f"⭐ **{avg:.2f}** average from **{len(reviews)}** review(s).",
            color=primary_color()
        )
        emb.set_thumbnail(url=member.avatar.url)


        view = discord.ui.View()
        view.add_item(ReviewUserSelect(reviews, member, mongo, ctx.guild))
        if len(reviews) > 25:
            view.add_item(OtherReviewsButton(reviews, member, mongo))
        return emb, view


class OtherReviewsButton(discord.ui.Button):
    def __init__(self, reviews, member, mongo):
        super().__init__(label="See All Reviews", style=discord.ButtonStyle.blurple)
        self.reviews = reviews
        self.member = member
        self.mongo = mongo

    async def callback(self, interaction: discord.Interaction):
        view = Review_PaginatorView(self.reviews, self.member, interaction.user)
        await view.start(interaction)


class VoteButton(discord.ui.Button):
    def __init__(self, review_id, up: bool, mongo: MongoManager):
        super().__init__(emoji="👍" if up else "👎", style=discord.ButtonStyle.secondary)
        self.review_id = ObjectId(review_id)
        self.up = up
        self.mongo = mongo

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        review = await self.mongo.collection.find_one({"_id": self.review_id})
        if not review:
            return

        votes = review.get("votes", {})
        if user_id in votes:
            if (self.up and votes[user_id] == "up") or (not self.up and votes[user_id] == "down"):
                del votes[user_id]
            else:
                votes[user_id] = "up" if self.up else "down"
        else:
            votes[user_id] = "up" if self.up else "down"

        upvotes = sum(1 for v in votes.values() if v == "up")
        downvotes = sum(1 for v in votes.values() if v == "down")

        await self.mongo.collection.update_one(
            {"_id": self.review_id},
            {"$set": {"votes": votes, "upvotes": upvotes, "downvotes": downvotes}}
        )

        emb = discord.Embed(
            title=f"Vote Results for Review",
            description=review["review"],
            color=primary_color()
        )
        reviewer = interaction.guild.get_member(int(review["reviewer_id"]))
        if reviewer:
            emb.set_thumbnail(url=reviewer.display_avatar.url)
        emb.set_footer(text=f"👍 {upvotes} | 👎 {downvotes}", icon_url=interaction.user.display_avatar.url)

        view = discord.ui.View()
        btn_up = VoteButton(self.review_id, True, self.mongo)
        btn_down = VoteButton(self.review_id, False, self.mongo)

        user_vote = votes.get(user_id)
        if user_vote == "up":
            btn_up.style = discord.ButtonStyle.green
        elif user_vote == "down":
            btn_down.style = discord.ButtonStyle.red

        view.add_item(btn_up)
        view.add_item(btn_down)
        await interaction.response.edit_message(embed=emb, view=view)

class Review_Paginator:
    async def start(self, ctx, reviews, member):
        pages = self._build_pages(member, reviews)
        if not pages:
            await ctx.send("No reviews found.")
            return
        view = PaginatorView(pages, ctx.author)
        view.message = await ctx.send(embed=pages[0], view=view)

    def _build_pages(self, member, reviews):
        pages = []
        for rev in reviews:
            emb = discord.Embed(
                title=f"Review for {member.display_name}",
                description=rev["review"],
                color=primary_color()
            ).set_footer(
                text=f"👍 {rev['upvotes']} | 👎 {rev['downvotes']}"
            )
            pages.append(emb)
        return pages


class Review_PaginatorView(discord.ui.View):
    def __init__(self, reviews, member, owner):
        super().__init__(timeout=60)
        self.reviews = reviews
        self.member = member
        self.owner = owner
        self.pages = self._build_pages()
        self.current = 0
        self.message = None

    def _build_pages(self):
        pages = []
        for rev in self.reviews:
            emb = discord.Embed(
                title=f"Review for {self.member.display_name}",
                description=rev["review"],
                color=primary_color()
            ).set_footer(
                text=f"👍 {rev['upvotes']} | 👎 {rev['downvotes']}"
            )
            pages.append(emb)
        return pages

    async def start(self, interaction):
        self.message = await interaction.response.send_message(embed=self.pages[0], view=self, ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner.id

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.blurple)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = max(self.current - 1, 0)
        await interaction.response.edit_message(embed=self.pages[self.current])

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = min(self.current + 1, len(self.pages) - 1)
        await interaction.response.edit_message(embed=self.pages[self.current])

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)


class PaginatorView(discord.ui.View):
    def __init__(self, pages, owner):
        super().__init__(timeout=60)
        self.pages = pages
        self.owner = owner
        self.current = 0
        self.message = None
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner.id

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.blurple)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = max(self.current - 1, 0)
        await interaction.response.edit_message(embed=self.pages[self.current])

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = min(self.current + 1, len(self.pages) - 1)
        await interaction.response.edit_message(embed=self.pages[self.current])

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)


# ────────────────────────────────────────────────
#  Review_Utils.action  (add/edit/remove modals)
# ────────────────────────────────────────────────

class Review_Utils:
    def __init__(self):
        self.action = ReviewActions()
        self.response_template = {
            "add": "Your review for {member.mention} has been added successfully.",
            "edit": "Your review for {member.mention} has been updated successfully.",
            "remove": "Your review for {member.mention} has been removed successfully."
        }
        self.embed_template = {
            "add": lambda member: discord.Embed(
                title="Add A Review",
                description=self.response_template["add"].format(member=member),
                color=primary_color()
            ),  
            "edit": lambda member: discord.Embed(
                title="Edit A Review",
                description=self.response_template["edit"].format(member=member),  
                color=primary_color()
            )
        }



class ReviewActions:
    def __init__(self, utils: ReviewUtils):
        self.utils = utils
        self.embed_types = {
            "add": lambda member: discord.Embed(
                title="Add A Review",
                description=f"Creating a new review for {member.mention}…",
                color=primary_color()
            ),
            "edit": lambda member: discord.Embed(
                title="Edit A Review",
                description=f"Editing your review for {member.mention}…",
                color=primary_color()
            )
        }

    async def add_review(self, ctx, member, mongo: MongoManager):
        # Enforce max 1 review per user per member
        existing_reviews = await mongo.collection.find({
            "reviewer_id": str(ctx.author.id),
            "target_id": str(member.id)
        }).to_list(None)

        if existing_reviews:
            await ctx.reply(
                f"You already have a review for {member.mention}. You can edit it instead.",
                ephemeral=True
            )
            return

        modal = await ReviewModal.create("Add Review", member, mongo, is_edit=False)
        view = Review_View(mode='add', m=modal, ctx_message=ctx.message)
        await ctx.reply(embed=self.embed_types["add"](member), view=view)

    async def edit_review(self, ctx, member, mongo: MongoManager):
        modal = await ReviewModal.create(
            "Edit Review",
            member,
            mongo,
            is_edit=True,
            reviewer_id=ctx.author.id
        )
        view = Review_View(mode='edit', m=modal, ctx_message=ctx.message)
        await ctx.reply(embed=self.embed_types["edit"](member), view=view)
        
        
# ────────────────────────────────────────────────
#  Modal for add/edit
# ────────────────────────────────────────────────
class ReviewModal(ui.Modal):
    def __init__(self, title, target_member, mongo, is_edit=False, existing=None):
        super().__init__(title=title)
        self.target_member = target_member
        self.mongo = mongo
        self.is_edit = is_edit

        self.stars = ui.TextInput(
            label="Rating (1-5)",
            style=TextStyle.short,  # single-line
            placeholder="e.g. 4",
            default=str(existing.get("stars", "")) if existing else "",
            min_length=1,
            max_length=1
        )

        self.review = ui.TextInput(
            label="Review text",
            style=TextStyle.paragraph,  # multi-line
            placeholder="Write your review here...",
            default=str(existing.get("review", "")) if existing else "",
            max_length=1500
        )

        self.add_item(self.stars)
        self.add_item(self.review)

    @classmethod
    async def create(cls, title, target_member, mongo, is_edit=False, reviewer_id=None):
        existing = None
        if is_edit and reviewer_id:
            cursor = mongo.collection.find({
                "reviewer_id": str(reviewer_id),
                "target_id": str(target_member.id)
            })
            reviews = await cursor.to_list(None)
            existing = reviews[0] if reviews else None
        return cls(title, target_member, mongo, is_edit=is_edit, existing=existing)

    async def on_submit(self, interaction):
        try:
            stars = int(self.stars.value)
            if stars < 1 or stars > 5:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Stars must be 1-5.", ephemeral=True)
            return

        reviewer_id = str(interaction.user.id)
        target_id = str(self.target_member.id)

        if self.is_edit:
            await self.mongo.collection.update_one(
                {"reviewer_id": reviewer_id, "target_id": target_id},
                {"$set": {"stars": stars, "review": self.review.value}}
            )
            emb = ReviewUtils.get_edit_embed(self.target_member)
        else:
            await self.mongo.add_review(reviewer_id, target_id, stars, self.review.value)
            emb = ReviewUtils.get_add_embed(self.target_member)

        await interaction.response.send_message(embed=emb, ephemeral=True)
        
        
        
        
        
        