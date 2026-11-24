"""
backend/pipeline/rules.py
─────────────────────────
Keyword-based rule engine for fast, deterministic classification.

A rule maps one-or-more keywords (checked against lower-cased OCR text) to a
(category, subcategory, content_type) triple.  Rules are tested in order;
the first match wins.  If nothing matches the functions return None so the
caller can fall back to CLIP zero-shot classification.
"""

from __future__ import annotations

import re
import string
from typing import TypedDict


# ─────────────────────────────────────────────────────────────────────────────
# Type alias
# ─────────────────────────────────────────────────────────────────────────────

class RuleMatch(TypedDict):
    category: str
    subcategory: str
    content_type: str
    matched_keyword: str


# ─────────────────────────────────────────────────────────────────────────────
# Rule table
# Each entry: (keywords_tuple, category, subcategory, content_type)
# Keywords are matched as substrings of the lower-cased OCR text.
# ─────────────────────────────────────────────────────────────────────────────

_RULES: list[tuple[tuple[str, ...], str, str, str]] = [

    # ══════════════════════════════════════════════════════════════════════════
    # FINANCE
    # ══════════════════════════════════════════════════════════════════════════

    # ── Payment Apps (must come BEFORE generic UPI rule) ─────────────────────
    (
        ("phonepe", "phone pe"),
        "Finance", "Payment Apps", "transaction",
    ),
    (
        ("google pay", "gpay", "g pay"),
        "Finance", "Payment Apps", "transaction",
    ),
    (
        ("paytm",),
        "Finance", "Payment Apps", "transaction",
    ),
    (
        ("mobikwik", "mobiquik", "mobiqwik"),
        "Finance", "Payment Apps", "transaction",
    ),
    (
        ("bhim upi", "bhim app"),
        "Finance", "Payment Apps", "transaction",
    ),
    (
        ("razorpay",),
        "Finance", "Payment Apps", "transaction",
    ),
    (
        ("paypal",),
        "Finance", "Payment Apps", "transaction",
    ),
    (
        ("freecharge", "free charge"),
        "Finance", "Payment Apps", "transaction",
    ),
    (
        ("amazon pay",),
        "Finance", "Payment Apps", "transaction",
    ),

    # ── UPI / Generic Digital Payments ────────────────────────────────────────
    (
        ("upi", "neft", "imps", "rtgs",
         "transferred to", "debited from", "credited to",
         "transaction id", "txn id", "ref no", "reference number",
         "payment successful", "payment failed", "payment done",
         "paid successfully", "transfer successful", "money sent",
         "money received", "amount debited", "amount credited",
         "rs.", "₹", "inr"),
        "Finance", "UPI Transactions", "transaction",
    ),

    # ── Receipts & Invoices ───────────────────────────────────────────────────
    (
        ("invoice", "tax invoice", "gst invoice",
         "receipt", "payment receipt",
         "subtotal", "grand total", "total amount", "amount due",
         "gst", "cgst", "sgst", "igst", "vat",
         "bill no", "bill number", "bill date",
         "order id", "order no", "booking id",
         "gstin", "pan no", "hsn code"),
        "Finance", "Receipts & Invoices", "receipt",
    ),

    # ── Bank Statements ────────────────────────────────────────────────────────
    (
        ("account balance", "account statement", "bank statement",
         "closing balance", "opening balance", "available balance",
         "ifsc", "micr", "account number", "savings account",
         "current account", "passbook"),
        "Finance", "Bank Statements", "document",
    ),

    # ── Shopping / E-commerce ─────────────────────────────────────────────────
    (
        ("order placed", "order confirmed", "order shipped", "out for delivery",
         "delivery by", "estimated delivery", "track order",
         "add to cart", "add to bag", "buy now", "place order",
         "flipkart", "amazon.in", "meesho", "myntra", "ajio",
         "nykaa", "snapdeal", "blinkit", "swiggy instamart", "zepto",
         "bigbasket", "jiomart"),
        "Finance", "Shopping", "receipt",
    ),

    # ── Budget / Personal Finance ──────────────────────────────────────────────
    (
        ("budget", "expense", "income", "savings", "spent", "salary",
         "emi", "loan", "insurance premium", "mutual fund", "sip",
         "investment", "portfolio", "net worth"),
        "Finance", "Budgets", "document",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # SOCIAL MEDIA — ordered from most-specific to least-specific
    # ══════════════════════════════════════════════════════════════════════════

    # ── Instagram DMs / Chats (most specific — before generic Instagram) ──────
    (
        ("instagram", "direct", "message request",
         "you sent", "seen", "active now", "voice message",
         "react to message", "reply", "unsend"),
        "Social & Content", "Instagram Chats", "chat",
    ),

    # ── Instagram Posts / Feed ────────────────────────────────────────────────
    (
        ("instagram", "like", "comment", "share", "save",
         "explore", "reels", "tagged"),
        "Social & Content", "Instagram Posts", "post",
    ),

    # ── Instagram Stories / Reels ─────────────────────────────────────────────
    (
        ("instagram", "story", "reel", "add to story", "close friends",
         "swipe up", "15s", "30s"),
        "Social & Content", "Instagram Stories & Reels", "post",
    ),

    # ── Generic Instagram (catch-all) ─────────────────────────────────────────
    (
        ("instagram", "followers", "following", "ig ", "@instagram"),
        "Social & Content", "Instagram", "post",
    ),

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    (
        ("whatsapp", "wa.me", "whatsapp business",
         "typing...", "recording...", "end-to-end encrypted"),
        "Personal", "WhatsApp Chats", "chat",
    ),

    # ── Telegram ──────────────────────────────────────────────────────────────
    (
        ("telegram", "t.me", "telegram group", "telegram channel",
         "forwarded from"),
        "Personal", "Telegram Chats", "chat",
    ),

    # ── Twitter / X ───────────────────────────────────────────────────────────
    (
        ("twitter", "tweet", "retweet", "x.com",
         "quote tweet", "thread", "trending", "spaces",
         "bookmarks", "for you", "following feed"),
        "Social & Content", "Twitter/X Posts", "post",
    ),

    # ── LinkedIn Posts ────────────────────────────────────────────────────────
    (
        ("linkedin", "connections", "1st •", "2nd •", "3rd •",
         "open to work", "hiring", "endorse", "recommendation",
         "linkedin premium", "linkedin learning"),
        "Social & Content", "LinkedIn Posts", "post",
    ),

    # ── YouTube ───────────────────────────────────────────────────────────────
    (
        ("youtube", "subscribe", "subscribers", "views", "watch later",
         "youtube premium", "youtube shorts", "live stream",
         "notification bell"),
        "Social & Content", "YouTube", "post",
    ),

    # ── Reddit ────────────────────────────────────────────────────────────────
    (
        ("reddit", "r/", "subreddit", "upvote", "downvote",
         "karma", "op said", "posted by u/"),
        "Social & Content", "Reddit", "post",
    ),

    # ── Snapchat ──────────────────────────────────────────────────────────────
    (
        ("snapchat", "snap", "streak", "bitmoji", "my eyes only"),
        "Social & Content", "Snapchat", "post",
    ),

    # ── Facebook ──────────────────────────────────────────────────────────────
    (
        ("facebook", "fb", "marketplace", "news feed", "facebook group",
         "messenger"),
        "Social & Content", "Facebook", "post",
    ),

    # ── Quotes / Motivation ───────────────────────────────────────────────────
    (
        ("inspiration", "motivation", "believe in yourself",
         "success is", "never give up", "dream big"),
        "Social & Content", "Quotes & Inspiration", "quote",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # TECHNOLOGY
    # ══════════════════════════════════════════════════════════════════════════

    (
        ("def ", "import ", "class ", "return ", "function(",
         "const ", "let ", "var ", "async ", "await ",
         "print(", "console.log", "traceback", "exception",
         "stack overflow", "github.com", "gitlab", "bitbucket",
         "stackoverflow", "#include", "public static void",
         "<!doctype", "<html", "SELECT ", "INSERT INTO"),
        "Technology", "Code & Development", "code",
    ),
    (
        ("pull request", "merge request", "git commit", "git push",
         "git clone", "npm install", "pip install", "docker", "kubernetes",
         "deployment", "ci/cd", "github actions", "build failed",
         "build passed", "pipeline", "devops"),
        "Technology", "Code & Development", "code",
    ),
    (
        ("gpt", "chatgpt", "gemini", "claude", "llm", "large language model",
         "machine learning", "deep learning", "neural network", "ai model",
         "hugging face", "openai", "anthropic", "stable diffusion",
         "midjourney", "dall-e", "copilot", "cursor", "perplexity"),
        "Technology", "AI & Machine Learning", "article",
    ),
    (
        ("hacktoberfest", "open source", "open-source", "contributor",
         "maintainer", "issue tracker", "fork", "star this repo"),
        "Technology", "Open Source", "post",
    ),
    (
        ("tutorial", "how to", "step by step", "beginner guide",
         "getting started", "cheatsheet", "cheat sheet", "roadmap",
         "learn", "explained"),
        "Technology", "Tutorials", "article",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # LEARNING
    # ══════════════════════════════════════════════════════════════════════════

    (
        ("udemy", "coursera", "edx", "skillshare", "pluralsight",
         "linkedin learning", "lesson", "module", "quiz", "assignment",
         "certificate", "enroll", "complete the course"),
        "Learning", "Courses", "article",
    ),
    (
        ("medium.com", "substack", "newsletter", "blog post",
         "read more", "min read", "published in", "hashnode", "dev.to"),
        "Learning", "Articles & Blogs", "article",
    ),
    (
        ("note:", "notes:", "summary:", "key points", "takeaway",
         "remember:", "todo:", "to do:", "action items"),
        "Learning", "Notes", "note",
    ),
    (
        ("book", "isbn", "kindle", "goodreads",
         "highlights", "paperback", "epub", "pdf book"),
        "Learning", "Books & Reading", "document",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # PERSONAL
    # ══════════════════════════════════════════════════════════════════════════

    (
        ("reminder", "alarm", "set for", "don't forget", "follow up",
         "due date", "deadline", "meet", "meeting at"),
        "Personal", "Reminders", "reminder",
    ),
    (
        ("calendar", "event", "rsvp", "invite", "schedule",
         "monday", "tuesday", "wednesday", "thursday", "friday",
         "saturday", "sunday", "google calendar", "outlook"),
        "Personal", "Calendar & Events", "calendar",
    ),
    (
        ("contact", "phone number", "saved contact", "mobile no"),
        "Personal", "Contacts", "contact",
    ),

    # ── Generic Chat (catch-all after platform-specific ones) ─────────────────
    (
        ("typing...", "delivered", "read", "yesterday",
         "online", "last seen", "message", "chat"),
        "Personal", "Chats & Messages", "chat",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # PEOPLE & FACES (keyword signals — CLIP will handle visual detection)
    # ══════════════════════════════════════════════════════════════════════════

    (
        ("selfie", "profile photo", "profile picture", "dp",
         "display picture", "avatar", "photo of me"),
        "People & Faces", "Profile Pictures", "photo",
    ),
    (
        ("group photo", "group picture", "team photo",
         "family photo", "wedding photo", "graduation photo",
         "event photo", "party photo"),
        "People & Faces", "Group Photos", "photo",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # MAPS & PLACES
    # ══════════════════════════════════════════════════════════════════════════

    (
        ("google maps", "apple maps", "directions", "navigate",
         "km away", "min away", "eta", "turn left", "turn right",
         "route", "destination", "current location",
         "uber", "ola", "rapido", "namma yatri"),
        "Maps & Places", "Navigation", "map",
    ),
    (
        ("zomato", "swiggy", "restaurant", "food delivery",
         "order food", "near me", "rating", "reviews"),
        "Maps & Places", "Food & Restaurants", "place",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # MEDIA & ENTERTAINMENT
    # ══════════════════════════════════════════════════════════════════════════

    (
        ("netflix", "prime video", "disney+", "hotstar", "jiocinema",
         "episode", "season", "watch now", "streaming", "zee5",
         "sonyliv", "mxplayer", "voot"),
        "Media & Entertainment", "Movies & Shows", "media",
    ),
    (
        ("spotify", "apple music", "gaana", "jio saavn", "wynk",
         "now playing", "album", "artist", "song", "lyrics"),
        "Media & Entertainment", "Music", "media",
    ),
    (
        ("game", "gaming", "player", "score", "level", "leaderboard",
         "pubg", "bgmi", "free fire", "cod", "clash of clans",
         "clash royale", "minecraft", "steam", "play store game"),
        "Media & Entertainment", "Gaming", "media",
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # HEALTH & FITNESS
    # ══════════════════════════════════════════════════════════════════════════

    (
        ("steps", "calories", "heart rate", "sleep", "workout",
         "health", "fitness", "bmi", "weight",
         "google fit", "apple health", "fitbit", "samsung health"),
        "Health & Fitness", "Activity Tracking", "health",
    ),
    (
        ("prescription", "medicine", "tablet", "dose", "doctor",
         "hospital", "clinic", "appointment", "medical report",
         "blood pressure", "sugar level", "hemoglobin"),
        "Health & Fitness", "Medical", "document",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Stop-words (skipped when building tags)
# ─────────────────────────────────────────────────────────────────────────────

_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "shall",
    "this", "that", "these", "those", "it", "its", "i", "you", "he",
    "she", "we", "they", "my", "your", "our", "their", "me", "him",
    "her", "us", "them", "not", "no", "so", "if", "as", "up", "out",
    "about", "into", "than", "then", "now", "also", "just", "more",
    "how", "what", "when", "where", "who", "which", "click", "tap",
    "see", "get", "new", "one", "two", "all", "any", "each",
})


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def classify_by_rules(text: str) -> RuleMatch | None:
    """
    Test the OCR text against every rule and return the first match.

    Returns None when no rule is triggered (caller should use CLIP).
    """
    if not text or not text.strip():
        return None

    lower = text.lower()

    for keywords, category, subcategory, content_type in _RULES:
        for kw in keywords:
            if kw in lower:
                return RuleMatch(
                    category=category,
                    subcategory=subcategory,
                    content_type=content_type,
                    matched_keyword=kw,
                )

    return None


def extract_tags(text: str, max_tags: int = 10, min_len: int = 3) -> list[str]:
    """
    Extract meaningful single-word tags from OCR text.

    Steps:
    1. Tokenise on whitespace / punctuation.
    2. Lower-case, strip punctuation edges.
    3. Drop stopwords, short tokens, and purely numeric tokens.
    4. Deduplicate while preserving first-occurrence order.
    5. Return up to *max_tags* tags.
    """
    if not text:
        return []

    # Tokenise
    raw_tokens = re.split(r"[\s\n\r\t,;:.!?()\[\]{}<>\"'`|/\\@#$%^&*=+~]+", text)

    seen: set[str] = set()
    tags: list[str] = []

    for token in raw_tokens:
        token = token.strip(string.punctuation).lower()

        if (
            len(token) >= min_len
            and not token.isnumeric()
            and token not in _STOPWORDS
            and token not in seen
        ):
            seen.add(token)
            tags.append(token)

        if len(tags) >= max_tags:
            break

    return tags

