#!/usr/bin/env python3
"""
add_new_posts.py — Add new posts from a new Telegram HTML export into the existing posts.json.

Steps:
1. Parse the new messages.html using the same TelegramParser from parse_data.py
2. Copy media files (photos, videos, GIFs) into the project's chats/ directory
3. Fix media paths in parsed posts to be relative to the project root
4. Deduplicate: skip posts already present in posts.json (by message ID)
5. Merge new posts into posts.json, sorted by date
"""

import json
import shutil
import os
import sys
from pathlib import Path
from datetime import datetime

# Import the parser and classifier from parse_data.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_data import TelegramParser, classify_post, html_to_text, build_taxonomy_tree

# ── Configuration ──
SCRIPT_DIR = Path(__file__).parent
POSTS_JSON = SCRIPT_DIR / "posts.json"

# New export directory
NEW_EXPORT_DIR = Path(os.path.expanduser(
    "~/Downloads/Telegram Desktop/ChatExport_2026-06-07 (1)"
))
NEW_HTML = NEW_EXPORT_DIR / "messages.html"

# Media source in new export
NEW_MEDIA_BASE = NEW_EXPORT_DIR / "chats" / "chat_562952438021324" / "topic_1176"

# Media destination in project
DEST_MEDIA_BASE = SCRIPT_DIR / "chats" / "chat_562952438021324" / "topic_1176"


def copy_media_files():
    """Copy all media (photos, videos) from new export to project directory."""
    copied = 0
    skipped = 0
    
    for subdir in ["photos", "video_files", "stickers"]:
        src_dir = NEW_MEDIA_BASE / subdir
        dst_dir = DEST_MEDIA_BASE / subdir
        
        if not src_dir.exists():
            print(f"  ⚠️  Source directory not found: {src_dir}")
            continue
            
        dst_dir.mkdir(parents=True, exist_ok=True)
        
        for f in src_dir.iterdir():
            if f.is_file():
                dst_file = dst_dir / f.name
                if dst_file.exists():
                    skipped += 1
                else:
                    shutil.copy2(f, dst_file)
                    copied += 1
    
    print(f"  📁 Media: {copied} copied, {skipped} already existed")
    return copied


def fix_media_paths(posts):
    """
    Fix media paths in posts: the parser outputs paths relative to the HTML file location.
    We need them relative to the project root (same as existing posts).
    
    New export paths look like: chats/chat_562952438021324/topic_1176/photos/...
    Existing project paths look like: chats/chat_562952438021324/topic_1176/photos/...
    
    They should be the same structure, but let's make sure.
    """
    for post in posts:
        for img in post.get("images", []):
            if "full" in img:
                img["full"] = normalize_path(img["full"])
            if "thumb" in img:
                img["thumb"] = normalize_path(img["thumb"])
        for vid in post.get("videos", []):
            if "src" in vid:
                vid["src"] = normalize_path(vid["src"])
            if "thumb" in vid:
                vid["thumb"] = normalize_path(vid["thumb"])


def normalize_path(p):
    """Ensure path starts with chats/ and uses the correct structure."""
    # Paths from the parser are already relative to the HTML file
    # They should look like: chats/chat_562952438021324/topic_1176/photos/xxx
    if p.startswith("chats/"):
        return p
    return p


def parse_new_html():
    """Parse the new messages.html file."""
    print(f"📖 Reading {NEW_HTML}...")
    with open(NEW_HTML, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    print("🔍 Parsing messages...")
    parser = TelegramParser()
    parser.feed(html_content)
    parser.finalize()
    
    posts = parser.posts
    print(f"  📊 Extracted {len(posts)} posts from new export")
    
    # Fix media paths
    fix_media_paths(posts)
    
    return posts


def merge_into_existing(new_posts):
    """Merge new posts into existing posts.json, deduplicating by ID."""
    print(f"\n📂 Loading existing {POSTS_JSON}...")
    with open(POSTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    existing_posts = data["posts"]
    existing_ids = {p["id"] for p in existing_posts}
    print(f"  📊 Existing posts: {len(existing_posts)}")
    
    # Filter out duplicates
    added = []
    for post in new_posts:
        if post["id"] in existing_ids:
            print(f"  ⚠️  Skipping duplicate: {post['id']} ({post['text'][:50]}...)")
        else:
            added.append(post)
            existing_ids.add(post["id"])
    
    print(f"\n  ✅ New posts to add: {len(added)}")
    
    # Print summary of new posts
    for p in added:
        topics_str = ", ".join(t["subcategory"] for t in p.get("topics", []))
        imgs = len(p.get("images", []))
        vids = len(p.get("videos", []))
        print(f"    📌 {p['id']} | {p['author'][:20]:20s} | {p['date'][:10]} | imgs:{imgs} vids:{vids} | [{topics_str}]")
        print(f"       {p['text'][:80]}...")
    
    # Add new posts and sort by date
    all_posts = existing_posts + added
    
    def sort_key(post):
        iso = post.get("dateISO", "")
        if iso:
            try:
                return datetime.fromisoformat(iso)
            except:
                pass
        return datetime.min
    
    all_posts.sort(key=sort_key)
    
    data["posts"] = all_posts
    
    # Write back
    with open(POSTS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n📊 Total posts after merge: {len(all_posts)}")
    print(f"✅ Written to {POSTS_JSON}")
    return len(added)


def main():
    print("=" * 60)
    print("  Астро Архив — Добавление новых постов")
    print("=" * 60)
    
    # 1. Copy media files
    print("\n📁 Step 1: Copying media files...")
    copy_media_files()
    
    # 2. Parse new HTML
    print("\n📖 Step 2: Parsing new messages...")
    new_posts = parse_new_html()
    
    # 3. Merge into existing
    print("\n🔀 Step 3: Merging into existing posts.json...")
    added = merge_into_existing(new_posts)
    
    print(f"\n{'=' * 60}")
    print(f"  Done! Added {added} new posts.")
    print(f"  Next step: run merge_posts.py to merge continuation posts.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
