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
SCRIPT_DIR = Path(__file__).parent.resolve()
POSTS_JSON = SCRIPT_DIR / "posts.json"
DEST_MEDIA_BASE = SCRIPT_DIR / "chats" / "chat_562952438021324" / "topic_1176"


def resolve_export_dir():
    """Resolve export directory from CLI argument or search local dirs."""
    if len(sys.argv) > 1:
        custom_dir = Path(sys.argv[1]).resolve()
        if custom_dir.exists():
            return custom_dir
        print(f"❌ Specified export directory does not exist: {custom_dir}")
        sys.exit(1)

    # Search in script directory first
    local_exports = sorted([d for d in SCRIPT_DIR.glob("ChatExport_*") if d.is_dir()])
    if local_exports:
        return local_exports[-1]

    # Search in Downloads
    dl_dir = Path(os.path.expanduser("~/Downloads/Telegram Desktop"))
    if dl_dir.exists():
        dl_exports = sorted([d for d in dl_dir.glob("ChatExport_*") if d.is_dir()])
        if dl_exports:
            return dl_exports[-1]

    print("❌ No ChatExport directory found.")
    sys.exit(1)


def find_media_base(export_dir):
    """Find topic directory containing photos/video_files."""
    candidates = list(export_dir.glob("chats/*/topic_*"))
    if candidates:
        return candidates[0]
    return export_dir / "chats" / "chat_562952438021324" / "topic_1176"


def copy_media_files(media_base):
    """Copy all media (photos, videos, stickers) from export to project directory."""
    copied = 0
    skipped = 0

    for subdir in ["photos", "video_files", "stickers"]:
        src_dir = media_base / subdir
        dst_dir = DEST_MEDIA_BASE / subdir

        if not src_dir.exists():
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


def normalize_path(p):
    """Ensure path starts with chats/ and uses the correct structure."""
    if p.startswith("chats/"):
        return p
    return p


def fix_media_paths(posts):
    """Fix media paths in posts to ensure they are relative to project root."""
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


def parse_export_html(html_file):
    """Parse messages.html using TelegramParser."""
    print(f"📖 Reading {html_file}...")
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    print("🔍 Parsing messages...")
    parser = TelegramParser()
    parser.feed(html_content)
    parser.finalize()

    posts = parser.posts
    print(f"  📊 Extracted {len(posts)} posts from export")

    fix_media_paths(posts)
    return posts


def merge_into_existing(new_posts):
    """Merge new posts into existing posts.json, deduplicating by ID."""
    print(f"\n📂 Loading existing {POSTS_JSON}...")
    with open(POSTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_posts = data.get("posts", [])
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

    for p in added:
        topics_str = ", ".join(t["subcategory"] for t in p.get("topics", []))
        imgs = len(p.get("images", []))
        vids = len(p.get("videos", []))
        print(f"    📌 {p['id']} | {p['author'][:20]:20s} | {p['date'][:10]} | imgs:{imgs} vids:{vids} | [{topics_str}]")
        print(f"       {p['text'][:80]}...")

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
    data["taxonomy"] = build_taxonomy_tree()

    with open(POSTS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Total posts after merge: {len(all_posts)}")
    print(f"✅ Written to {POSTS_JSON}")
    return len(added)


def main():
    print("=" * 60)
    print("  Астро Архив — Добавление новых постов")
    print("=" * 60)

    export_dir = resolve_export_dir()
    print(f"📂 Selected export directory: {export_dir}")

    html_file = export_dir / "messages.html"
    if not html_file.exists():
        print(f"❌ messages.html not found in {export_dir}")
        sys.exit(1)

    media_base = find_media_base(export_dir)

    # 1. Copy media files
    print("\n📁 Step 1: Copying media files...")
    copy_media_files(media_base)

    # 2. Parse new HTML
    print("\n📖 Step 2: Parsing export messages...")
    new_posts = parse_export_html(html_file)

    # 3. Merge into existing posts.json
    print("\n🔀 Step 3: Merging into existing posts.json...")
    added = merge_into_existing(new_posts)

    print(f"\n{'=' * 60}")
    print(f"  Done! Added {added} new posts.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
