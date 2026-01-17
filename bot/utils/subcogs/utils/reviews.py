import os
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from bson import ObjectId
from data.local.const import primary_color
import math

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
    def __init__(self, mode=None, m=None, ctx_message=None, target=None):
        super().__init__(timeout=180)
        self.select = Review_Select()
        self.paginator = Review_Paginator()
        self.mode = mode
        self.modal = m
        self.ctx_message = ctx_message
        self.target=target
        if mode and m:
            self.add_item(ReviewButton(mode, m, ctx_message, target))
            self.add_item(CancelButton(ctx_message))


class ReviewButton(discord.ui.Button):
    def __init__(self, mode: str, modal_cls, ctx_message, target):
        super().__init__(
            label="Add Review" if mode == "add" else "Edit Review",
            style=discord.ButtonStyle.green if mode == "add" else discord.ButtonStyle.blurple
        )
        self.mode = mode
        self.modal_cls = modal_cls
        self.ctx_message = ctx_message
        self.target = target

    async def callback(self, interaction: discord.Interaction):
        if self.ctx_message:
            try:
                await self.ctx_message.delete()
            except:
                pass

        target_member = self.target if self.target else interaction.user

        modal = await self.modal_cls.create(
            title=f"{self.mode.title()} Review",
            target_member=target_member,
            mongo=self.modal_cls.mongo,
            is_edit=self.mode == "edit",
            reviewer_id=interaction.user.id if self.mode == "edit" else None
        )
        await interaction.response.send_modal(modal)


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

    async def add_review(self, reviewer_id, target_id, stars, review, guild_id):
        doc = {
            "reviewer_id": reviewer_id,
            "target_id": target_id,
            "stars": stars,
            "review": review,
            "upvotes": 0,
            "downvotes": 0,
            "timestamp": datetime.utcnow(),
            "guild_id": guild_id
        }
        await self.collection.insert_one(doc)

    async def get_reviews_for_user(self, target_id, guild_id):
     reviews = await self.collection.find({
        "target_id": target_id,
        "guild_id": guild_id
     }).to_list(None)
     reviews.sort(key=lambda r: r.get("upvotes", 0), reverse=True)
     return reviews

    async def get_average_rating(self, target_id, guild_id):
     reviews = await self.get_reviews_for_user(target_id, guild_id)
     if not reviews:
        return 0
     return sum(r["stars"] for r in reviews) / len(reviews)

    async def vote_review(self, review_id, guild_id, up=True):
     review = await self.collection.find_one({"_id": ObjectId(review_id), "guild_id": guild_id})
     if not review:
        return
     field = "upvotes" if up else "downvotes"
     await self.collection.update_one({"_id": ObjectId(review_id)}, {"$inc": {field: 1}})

    async def get_leaderboard_data(self, guild_id, min_reviews=1, limit=200):
        """
        Updated leaderboard scoring that prioritizes users with high vote counts
        while still considering rating quality.
        
        Formula: score = average_rating * (log10(review_count + 1) * 10 + sqrt(review_count) * 0.5)
        This ensures users with many votes rank higher than users with few votes,
        even if the latter have slightly higher ratings.
        """
        pipeline = [
            {"$match": {"guild_id": guild_id}},
            {"$group": {
                "_id": "$target_id",
                "total_stars": {"$sum": "$stars"},
                "review_count": {"$sum": 1}
            }},
            {"$match": {"review_count": {"$gte": min_reviews}}},
            {"$addFields": {
                "avg": {"$divide": ["$total_stars", "$review_count"]},
                # New scoring system that heavily weights review count
                "log_component": {
                    "$multiply": [
                        {"$log10": {"$add": ["$review_count", 1]}},
                        10  # Scale factor to make log more impactful
                    ]
                },
                "sqrt_component": {
                    "$multiply": [
                        {"$sqrt": "$review_count"},  # Square root for diminishing returns but still significant impact
                        0.5  # Weight factor
                    ]
                },
                "score": {
                    "$multiply": [
                        {"$divide": ["$total_stars", "$review_count"]},  # average rating
                        {"$add": [
                            {"$multiply": [
                                {"$log10": {"$add": ["$review_count", 1]}},
                                10
                            ]},
                            {"$multiply": [
                                {"$sqrt": "$review_count"},
                                0.5
                            ]}
                        ]}
                    ]
                }
            }},
            {"$sort": {"score": -1}},
            {"$limit": limit},
            {"$project": {"avg": 1, "review_count": 1, "score": 1, "_id": 1}}
        ]
        
        try:
            cursor = self.collection.aggregate(pipeline)
            data = await cursor.to_list(None)
            # Always return 4-tuple format: (user_id, avg_rating, review_count, score)
            return [(doc["_id"], doc["avg"], doc["review_count"], doc["score"]) for doc in data]
        except Exception as e:
            print(f"Error in get_leaderboard_data: {e}")
            # Fallback to simple aggregation if advanced pipeline fails
            simple_pipeline = [
                {"$match": {"guild_id": guild_id}},
                {"$group": {
                    "_id": "$target_id",
                    "total_stars": {"$sum": "$stars"},
                    "review_count": {"$sum": 1}
                }},
                {"$match": {"review_count": {"$gte": min_reviews}}},
                {"$addFields": {
                    "avg": {"$divide": ["$total_stars", "$review_count"]}
                }},
                {"$sort": {"avg": -1}},
                {"$limit": limit}
            ]
            cursor = self.collection.aggregate(simple_pipeline)
            data = await cursor.to_list(None)
            # Calculate score in Python if MongoDB aggregation fails
            result = []
            for doc in data:
                avg = doc["avg"]
                count = doc["review_count"]
                # Calculate score using Python math functions
                log_comp = math.log10(count + 1) * 10
                sqrt_comp = math.sqrt(count) * 0.5
                score = avg * (log_comp + sqrt_comp)
                result.append((doc["_id"], avg, count, score))
            # Sort by score descending
            result.sort(key=lambda x: x[3], reverse=True)
            return result[:limit]


# ────────────────────────────────────────────────
#  NEW: Leaderboard-style comment select menu
# ────────────────────────────────────────────────
class CommenterSelectMenu(discord.ui.Select):
    def __init__(self, reviews, guild, mongo, guild_id):
        self.reviews = reviews
        self.guild = guild
        self.mongo = mongo
        self.guild_id = guild_id

        options = []
        for review in reviews:
            reviewer = guild.get_member(int(review["reviewer_id"]))
            reviewer_name = reviewer.name if reviewer else f"User_{review['reviewer_id']}"
            comment_preview = review["review"][:40]

            options.append(discord.SelectOption(
                label=f"{reviewer_name} | {comment_preview}",
                value=str(review["_id"])
            ))

        super().__init__(
            placeholder="Select a commenter to read their review...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        review_id = ObjectId(self.values[0])
        review = await self.mongo.collection.find_one(
            {"_id": review_id, "guild_id": self.guild_id}
        )
        if not review:
            await interaction.response.send_message("Review not found.", ephemeral=True)
            return

        reviewer = self.guild.get_member(int(review["reviewer_id"]))
        star_txt = "⭐" * review["stars"]

        emb = discord.Embed(
            title=f"Review by {reviewer.name if reviewer else 'Unknown User'}",
            description=f"{star_txt}\n\n{review['review']}",
            color=primary_color()
        )
        if reviewer:
            emb.set_thumbnail(url=reviewer.display_avatar.url)
        emb.set_footer(
            text=f"👍 {review.get('upvotes', 0)} | 👎 {review.get('downvotes', 0)}",
            icon_url=interaction.user.display_avatar.url
        )

        # Vote buttons
        view = discord.ui.View()
        btn_up = VoteButton(review["_id"], True, self.mongo, self.guild_id)
        btn_down = VoteButton(review["_id"], False, self.mongo, self.guild_id)

        user_vote = review.get("votes", {}).get(str(interaction.user.id))
        if user_vote == "up":
            btn_up.style = discord.ButtonStyle.green
        elif user_vote == "down":
            btn_down.style = discord.ButtonStyle.red

        view.add_item(btn_up)
        view.add_item(btn_down)

        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)


# ────────────────────────────────────────────────
#  NEW: Comments pagination view (25 per page)
# ────────────────────────────────────────────────
class CommentsPaginationView(discord.ui.View):
    def __init__(self, reviews, member, mongo, guild_id, guild):
        super().__init__(timeout=180)
        self.reviews = reviews
        self.member = member
        self.mongo = mongo
        self.guild_id = guild_id
        self.guild = guild
        self.current_page = 0
        self.per_page = 25
        self.total_pages = (len(reviews) + self.per_page - 1) // self.per_page

        self.update_components()

    def update_components(self):
        self.clear_items()

        # Get current page reviews
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.reviews))
        page_reviews = self.reviews[start_idx:end_idx]

        # Add select menu for commenters on this page
        select = CommenterSelectMenu(page_reviews, self.guild, self.mongo, self.guild_id)
        self.add_item(select)

        # Add navigation buttons if multiple pages
        if self.total_pages > 1:
            prev_btn = discord.ui.Button(
                label="<",
                style=discord.ButtonStyle.primary,
                disabled=self.current_page == 0,
                row=1
            )
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)

            next_btn = discord.ui.Button(
                label=">",
                style=discord.ButtonStyle.primary,
                disabled=self.current_page >= self.total_pages - 1,
                row=1
            )
            next_btn.callback = self.next_page
            self.add_item(next_btn)

    async def prev_page(self, interaction: discord.Interaction):
        self.current_page = max(0, self.current_page - 1)
        self.update_components()
        emb = self.build_embed()
        await interaction.response.edit_message(embed=emb, view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_components()
        emb = self.build_embed()
        await interaction.response.edit_message(embed=emb, view=self)

    def build_embed(self):
        avg = sum(r["stars"] for r in self.reviews) / len(self.reviews) if self.reviews else 0

        # Build list of commenters on this page
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.reviews))
        page_reviews = self.reviews[start_idx:end_idx]

        commenter_list = []
        for review in page_reviews:
            reviewer = self.guild.get_member(int(review["reviewer_id"]))
            reviewer_name = reviewer.name if reviewer else f"User_{review['reviewer_id']}"
            commenter_list.append(f"• {reviewer_name}")

        emb = discord.Embed(
            title=f"{self.member.display_name}'s Reviews",
            description=(
                f"⭐ **{avg:.2f}** average from **{len(self.reviews)}** review(s).\n\n"
                f"**Commenters on this page:**\n" + "\n".join(commenter_list)
            ),
            color=primary_color()
        )
        emb.set_thumbnail(url=self.member.avatar.url)
        emb.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} | Select a commenter below to read")

        return emb


class Review_Select:
    async def get_overview(self, ctx, member, mongo: MongoManager):
        reviews = await mongo.get_reviews_for_user(str(member.id), str(ctx.guild.id))
        if not reviews:
            emb = discord.Embed(
                title=f"{member.display_name}'s Reviews",
                description="No reviews yet.",
                color=primary_color()
            )
            emb.set_thumbnail(url=member.avatar.url)
            return emb, None

        # Use new pagination view with embed + select menu
        view = CommentsPaginationView(reviews, member, mongo, str(ctx.guild.id), ctx.guild)
        emb = view.build_embed()

        return emb, view


class VoteButton(discord.ui.Button):
    def __init__(self, review_id, up: bool, mongo: MongoManager, guild_id, user_id=None):
        super().__init__(emoji="👍" if up else "👎", style=discord.ButtonStyle.secondary)
        self.review_id = ObjectId(review_id)
        self.up = up
        self.mongo = mongo
        self.guild_id = guild_id
        self.user_id = str(user_id) if user_id else None

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        review = await self.mongo.collection.find_one(
            {"_id": self.review_id, "guild_id": self.guild_id}
        )
        if not review:
            await interaction.response.send_message("Review not found.", ephemeral=True)
            return

        votes = review.get("votes", {})

        # Toggle vote
        if user_id in votes:
            if (self.up and votes[user_id] == "up") or (not self.up and votes[user_id] == "down"):
                del votes[user_id]
            else:
                votes[user_id] = "up" if self.up else "down"
        else:
            votes[user_id] = "up" if self.up else "down"

        upvotes = sum(1 for v in votes.values() if v == "up")
        downvotes = sum(1 for v in votes.values() if v == "down")

        # Auto-delete bad reviews
        if downvotes > 6:
            await self.mongo.collection.delete_one({"_id": self.review_id})
            await interaction.response.edit_message(
                content="Review deleted due to excessive downvotes.", embed=None, view=None
            )
            return

        await self.mongo.collection.update_one(
            {"_id": self.review_id},
            {"$set": {"votes": votes, "upvotes": upvotes, "downvotes": downvotes}}
        )

        reviewer = interaction.guild.get_member(int(review["reviewer_id"]))
        star_txt = "⭐" * review["stars"]

        emb = discord.Embed(
            title=f"Review by {reviewer.name if reviewer else 'Unknown User'}",
            description=f"{star_txt}\n\n{review['review']}",
            color=primary_color()
        )
        if reviewer:
            emb.set_thumbnail(url=reviewer.display_avatar.url)
        emb.set_footer(text=f"👍 {upvotes} | 👎 {downvotes}",
                       icon_url=interaction.user.display_avatar.url)

        # Rebuild buttons
        view = discord.ui.View()
        btn_up = VoteButton(self.review_id, True, self.mongo, self.guild_id)
        btn_down = VoteButton(self.review_id, False, self.mongo, self.guild_id)
        if votes.get(user_id) == "up":
            btn_up.style = discord.ButtonStyle.green
        elif votes.get(user_id) == "down":
            btn_down.style = discord.ButtonStyle.red
        view.add_item(btn_up)
        view.add_item(btn_down)

        await interaction.response.edit_message(embed=emb, view=view)


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
        existing = await mongo.collection.find_one({
            "reviewer_id": str(ctx.author.id),
            "target_id": str(member.id)
        })
        if existing:
            await ctx.reply(
                f"You already have a review for {member.mention}. Use Edit instead.",
                ephemeral=True
            )
            return

        modal = await ReviewModal.create("Add Review", member, mongo, is_edit=False)
        view = Review_View(mode='add', m=modal, ctx_message=ctx.message, target=member)
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

    # ─── add remove_review method ───
    async def remove_review(self, ctx, member, mongo: MongoManager):
        existing = await mongo.collection.find_one({
            "reviewer_id": str(ctx.author.id),
            "target_id": str(member.id)
        })
        if not existing:
            await ctx.reply(f"You have no review for {member.mention} to remove.", ephemeral=True)
            return

        await mongo.collection.delete_one({
            "reviewer_id": str(ctx.author.id),
            "target_id": str(member.id)
        })

        emb = discord.Embed(
            title="Review Removed",
            description=f"Your review for {member.mention} has been removed successfully.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=emb, ephemeral=True)


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
            style=TextStyle.short,
            placeholder="e.g. 4",
            default=str(existing.get("stars", "")) if existing else "",
            min_length=1,
            max_length=1
        )

        self.review = ui.TextInput(
            label="Review text",
            style=TextStyle.paragraph,
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
        guild_id = str(interaction.guild.id)

        if self.is_edit:
            await self.mongo.collection.update_one(
                {"reviewer_id": reviewer_id, "target_id": target_id, "guild_id": guild_id},
                {"$set": {"stars": stars, "review": self.review.value}}
            )
            msg = f"Review has been updated for {self.target_member.mention}."
        else:
            await self.mongo.add_review(reviewer_id, target_id, stars, self.review.value, guild_id)
            msg = f"Review has been made for {self.target_member.mention}."

        try:
            if interaction.message:
                await interaction.message.delete()
        except:
            pass

        await interaction.response.send_message(msg, ephemeral=True)


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
#  MODIFIED: LeaderboardView with new requirements
# ────────────────────────────────────────────────
class LeaderboardView(discord.ui.View):
    def __init__(self, cog, pages_data, member_dict, ctx, per_page=6):
        super().__init__(timeout=300)
        self.cog = cog
        self.pages_data = pages_data
        self.member_dict = member_dict
        self.prefix = ctx.prefix
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = len(pages_data)
        self.view_more_clicked = False

        self._normalize_pages_data()
        self._setup_initial_view()

    def _normalize_pages_data(self):
        """Normalize pages data to ensure consistent 4-tuple format"""
        normalized = []
        for page in self.pages_data:
            norm_page = []
            for entry in page:
                if len(entry) == 4:
                    norm_page.append(entry)
                elif len(entry) == 2:
                    mid, avg = entry
                    norm_page.append((mid, avg, 1, avg))
                else:
                    mid = entry[0]
                    avg = entry[1] if len(entry) > 1 else 0.0
                    count = entry[2] if len(entry) > 2 else 1
                    score = entry[3] if len(entry) > 3 else avg
                    norm_page.append((mid, avg, count, score))
            normalized.append(norm_page[:self.per_page])
        self.pages_data = normalized

    def _setup_initial_view(self):
        """Setup the initial view with navigation buttons and view more button"""
        self.clear_items()
        
        # Navigation buttons
        prev_btn = discord.ui.Button(
            label="<", 
            style=discord.ButtonStyle.primary,
            disabled=self.current_page == 0
        )
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label=">", 
            style=discord.ButtonStyle.primary,
            disabled=self.current_page >= self.total_pages - 1
        )
        next_btn.callback = self.next_page
        self.add_item(next_btn)

        # View More button
        view_more_btn = discord.ui.Button(
            label="View More", 
            style=discord.ButtonStyle.secondary
        )
        view_more_btn.callback = self.view_more
        self.add_item(view_more_btn)

    def _setup_expanded_view(self):
        """Setup the expanded view with select menu and navigation"""
        self.clear_items()
        
        # Add select menu for page navigation
        self.select = discord.ui.Select(
            placeholder="Go to page...", 
            min_values=1, 
            max_values=1
        )
        self.select.callback = self.select_callback
        self._update_select_options()
        self.add_item(self.select)
        
        # Navigation buttons
        prev_btn = discord.ui.Button(
            label="<", 
            style=discord.ButtonStyle.primary,
            disabled=self.current_page == 0
        )
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label=">", 
            style=discord.ButtonStyle.primary,
            disabled=self.current_page >= self.total_pages - 1
        )
        next_btn.callback = self.next_page
        self.add_item(next_btn)

    def _update_select_options(self):
        """Update select menu options with logical navigation"""
        if not hasattr(self, 'select'):
            return
            
        options = []
        # Show a reasonable range of pages around current page
        start = max(0, self.current_page - 12)
        end = min(self.total_pages, start + 25)
        
        # Adjust if we're near the end
        if end - start < 25 and self.total_pages > 25:
            start = max(0, end - 25)
        
        for i in range(start, end):
            page = self.pages_data[i]
            # Create description with member names
            names = []
            for mid, _, _, _ in page:
                member = self.member_dict.get(str(mid))
                name = member.name if member else f"User_{mid}"
                names.append(name)
            
            desc = ", ".join(names)
            if len(desc) > 97:
                desc = desc[:97] + "..."
            
            label = f"Page {i+1}"
            if i == self.current_page:
                label += " (current)"
            
            options.append(discord.SelectOption(
                label=label, 
                value=str(i), 
                description=desc
            ))
        
        self.select.options = options

    async def prev_page(self, interaction: discord.Interaction):
        """Handle previous page navigation"""
        if self.current_page > 0:
            self.current_page -= 1
            await self._update_view(interaction)

    async def next_page(self, interaction: discord.Interaction):
        """Handle next page navigation"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self._update_view(interaction)

    async def view_more(self, interaction: discord.Interaction):
        """Handle view more button click"""
        self.view_more_clicked = True
        self._setup_expanded_view()
        await self._update_view(interaction)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle select menu page selection"""
        self.current_page = int(interaction.data['values'][0])
        self._update_select_options()
        await self._update_view(interaction)

    async def _update_view(self, interaction: discord.Interaction):
        """Update the view with current page and proper button states"""
        embed = self.build_embed()
        
        # Update button states
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label == "<":
                    item.disabled = self.current_page == 0
                elif item.label == ">":
                    item.disabled = self.current_page >= self.total_pages - 1
        
        # Update select options if in expanded view
        if self.view_more_clicked:
            self._update_select_options()
        
        await interaction.response.edit_message(embed=embed, view=self)

    def build_embed(self):
     if not self.pages_data or self.current_page >= len(self.pages_data):
        return discord.Embed(title="Review Leaderboard",description="No reviews yet.\nBe the first to start recognizing others!",color=primary_color())
     page=self.pages_data[self.current_page];lines=[];start_rank=self.current_page*self.per_page+1
     for idx,(mid,avg,count,score) in enumerate(page):
        if count==0:continue
        rank=start_rank+idx
        medal="🥇 1st"if rank==1 else"🥈 2nd"if rank==2 else"🥉 3rd"if rank==3 else f"#{rank}"
        member=self.member_dict.get(str(mid));name=member.name if member else f"<@{mid}>"
        if avg>0:
            full=int(avg);half="⯪"if avg%1>=0.5 else"";empty=5-full-(1 if half else 0)
            stars="★"*full+half+"☆"*empty
        else:stars="No rating"
        lines.append(f"{medal} **{name}** — {stars} (`{count}` reviews)")
     if not lines:return discord.Embed(title="Review Leaderboard",description="No reviews yet. Start sharing feedback to appear here!",color=primary_color())
     desc="\n".join(lines[:20]); 
     if len(lines)>20:desc+=f"\n... and {len(lines)-20} more"
     total_users=sum(len(p)for p in self.pages_data);per_page_text=f"{self.per_page} per page"if not self.view_more_clicked else"25 per page"
     embed=discord.Embed(title="Review Leaderboard",description=("✦ **The top members shine the brightest.** ✦\n\nThis board ranks members by their *average rating* and *total number of reviews.*\nEach star reflects community feedback — the more you’re reviewed, the higher you climb!\n\n> 💬 Encourage others by leaving honest reviews — help your friends shine!\n\n**Command:** `"+self.prefix+"review @user`\n\n"+desc),color=primary_color())
     embed.set_footer(text=f"Page {self.current_page+1}/{self.total_pages} | {total_users} ranked • {per_page_text}")
     return embed


    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx):
        try:
            mongo = MongoManager()
            data = await mongo.get_leaderboard_data(str(ctx.guild.id), min_reviews=1, limit=200)
            
            if not data:
                return await ctx.reply(embed=discord.Embed(
                    title="Review Leaderboard",
                    description="No reviews found for this server.",
                    color=primary_color()
                ), mention_author=False)

            members = {str(m.id): m for m in ctx.guild.members}
            
            # Start with 6 per page initially
            per_page = 6
            pages = [data[i:i + per_page] for i in range(0, len(data), per_page)]
            
            view = LeaderboardView(self, pages, members, ctx, per_page)
            await ctx.reply(embed=view.build_embed(), view=view, mention_author=False)
            
        except Exception as e:
            await ctx.reply(f"Error loading leaderboard: `{e}`", mention_author=False)