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
    # ── Finance ──────────────────────────────────────────────────────────────
    (
        ("invoice", "receipt", "subtotal", "grand total", "gst", "vat",
         "bill no", "bill number", "tax invoice"),
        "Finance", "Receipts & Invoices", "receipt",
    ),
    (
        ("upi", "paytm", "gpay", "phonepe", "neft", "imps", "rtgs",
         "transferred to", "debited", "credited", "transaction id",
         "txn id", "payment successful", "payment failed"),
        "Finance", "UPI Transactions", "transaction",
    ),
    (
        ("account balance", "account statement", "bank statement",
         "closing balance", "opening balance", "ifsc", "micr"),
        "Finance", "Bank Statements", "document",
    ),
    (
        ("budget", "expense", "income", "savings", "spent", "salary",
         "emi", "loan", "insurance premium"),
        "Finance", "Budgets", "document",
    ),
    (
        ("price", "offer", "sale", "discount", "% off", "buy now",
         "add to cart", "add to bag", "order placed", "order confirmed",
         "delivery by", "flipkart", "amazon", "meesho", "myntra"),
        "Finance", "Shopping", "receipt",
    ),

    # ── Technology ───────────────────────────────────────────────────────────
    (
        ("def ", "import ", "class ", "return ", "function(",
         "const ", "let ", "var ", "async ", "await ",
         "print(", "console.log", "traceback", "exception",
         "stack overflow", "github.com", "gitlab", "bitbucket"),
        "Technology", "Code & Development", "code",
    ),
    (
        ("pull request", "merge request", "git commit", "git push",
         "git clone", "npm install", "pip install", "docker", "kubernetes",
         "deployment", "ci/cd", "workflow", "action failed", "build passed"),
        "Technology", "Code & Development", "code",
    ),
    (
        ("gpt", "chatgpt", "gemini", "claude", "llm", "large language model",
         "machine learning", "deep learning", "neural network", "ai model",
         "hugging face", "openai", "anthropic", "stable diffusion",
         "midjourney", "dall-e"),
        "Technology", "AI & Machine Learning", "article",
    ),
    (
        ("hacktoberfest", "open source", "open-source", "contributor",
         "maintainer", "pull request", "issue tracker", "fork"),
        "Technology", "Open Source", "post",
    ),
    (
        ("tutorial", "how to", "step by step", "beginner guide",
         "getting started", "cheatsheet", "cheat sheet"),
        "Technology", "Tutorials", "article",
    ),

    # ── Social & Content ─────────────────────────────────────────────────────
    (
        ("linkedin", "connections", "1st", "2nd", "3rd",
         "follow", "connect", "endorse"),
        "Social & Content", "LinkedIn", "post",
    ),
    (
        ("twitter", "tweet", "retweet", "x.com", "trending", "#",
         "quote tweet", "thread"),
        "Social & Content", "Twitter/X", "post",
    ),
    (
        ("instagram", "reel", "story", "explore", "dm", "direct message",
         "followers", "following", "likes"),
        "Social & Content", "Instagram", "post",
    ),
    (
        ("youtube", "subscribe", "subscribers", "views", "watch later",
         "playlist", "channel"),
        "Social & Content", "YouTube", "post",
    ),
    (
        ('"', "— ", "said:", "quote:", "inspiration", "motivation",
         "believe in", "success is"),
        "Social & Content", "Quotes & Inspiration", "quote",
    ),

    # ── Learning ─────────────────────────────────────────────────────────────
    (
        ("udemy", "coursera", "edx", "skillshare", "pluralsight",
         "lesson", "module", "chapter", "quiz", "assignment",
         "certificate", "enroll"),
        "Learning", "Courses", "article",
    ),
    (
        ("medium.com", "substack", "newsletter", "blog post",
         "read more", "min read", "published in"),
        "Learning", "Articles & Blogs", "article",
    ),
    (
        ("note:", "notes:", "summary:", "key points", "takeaway",
         "remember:", "todo:", "to do:"),
        "Learning", "Notes", "note",
    ),
    (
        ("book", "chapter", "author", "isbn", "kindle", "goodreads",
         "highlights", "page ", "paperback"),
        "Learning", "Books & Reading", "document",
    ),

    # ── Personal ─────────────────────────────────────────────────────────────
    (
        ("whatsapp", "telegram", "typing...", "delivered", "read",
         "yesterday", "online", "last seen", "message", "chat"),
        "Personal", "Chats & Messages", "chat",
    ),
    (
        ("reminder", "alarm", "set for", "don't forget", "follow up",
         "due date", "deadline", "meet", "meeting at"),
        "Personal", "Reminders", "reminder",
    ),
    (
        ("calendar", "event", "rsvp", "invite", "schedule",
         "monday", "tuesday", "wednesday", "thursday", "friday"),
        "Personal", "Calendar & Events", "calendar",
    ),
    (
        ("contact", "phone number", "email:", "address:", "saved contact"),
        "Personal", "Contacts", "contact",
    ),

    # ── Maps & Places ────────────────────────────────────────────────────────
    (
        ("google maps", "directions", "navigate", "km away",
         "min away", "eta", "turn left", "turn right", "route"),
        "Maps & Places", "Navigation", "map",
    ),

    # ── Media & Entertainment ─────────────────────────────────────────────────
    (
        ("netflix", "prime video", "disney+", "hotstar", "jiocinema",
         "episode", "season", "watch now", "streaming"),
        "Media & Entertainment", "Movies & Shows", "media",
    ),
    (
        ("spotify", "apple music", "gaana", "jio saavn",
         "now playing", "playlist", "album", "artist"),
        "Media & Entertainment", "Music", "media",
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
