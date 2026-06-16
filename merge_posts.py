#!/usr/bin/env python3
"""
merge_posts.py — Объединение разделённых постов в posts.json

Найденные группы постов-продолжений:
1. message530465 + message530625  (Сатурн, ЧАСТЬ 2)
2. message553201 + message553831  (Галактики + фото без текста)
3. message1037738 + message1038620 (Ио + фото без текста)
4. message663568 + message664312 + message665446 (Сверхновые, 3 части)
5. message1257591 + message1259097 + message1264328 + message1267783 (Наука, 4 части)
6. message1303150 + message1303165 (Горящая тема + P.S.)
7. message1364138 + message1364141 (Мегаимпакт Венеры + Ещё кое-что)
"""

import json
import shutil
from pathlib import Path

POSTS_JSON = Path(__file__).parent / "posts.json"
BACKUP_JSON = Path(__file__).parent / "posts_original.json"

# Define merge groups: first element is the "main" post, rest are continuations
MERGE_GROUPS = [
    ["message530465", "message530625"],
    ["message553201", "message553831"],
    ["message663568", "message664312", "message665446"],
    ["message1257591", "message1259097", "message1264328", "message1267783"],
    ["message1303150", "message1303165"],
    ["message1364138", "message1364141"],
    # ── New merge groups from ChatExport_2026-06-07 ──
    ["message1479696", "message1479895"],                                    # Спутники Юпитера + Сатурна
    ["message1497327", "message1497345"],                                    # Экзопланеты часть 1 + 2
    # Note: Apollo (message1507591+) and Solar flare (message1565766+) are already
    # auto-merged by the parser since their continuations are 'joined' messages in HTML
]


def merge_reactions(reactions_list):
    """Sum up reactions from multiple posts."""
    combined = {}
    for reactions in reactions_list:
        for r in reactions:
            emoji = r["emoji"]
            combined[emoji] = combined.get(emoji, 0) + r["count"]
    return [{"emoji": k, "count": v} for k, v in combined.items()]


def merge_topics(topics_list):
    """Deduplicate topics from multiple posts."""
    seen = set()
    result = []
    for topics in topics_list:
        for t in topics:
            key = (t["category"], t["subcategory"])
            if key not in seen:
                seen.add(key)
                result.append(t)
    return result


def merge_posts(posts_in_group):
    """Merge a group of posts into one."""
    main = posts_in_group[0].copy()
    
    # Merge html
    html_parts = [p["html"] for p in posts_in_group if p.get("html", "").strip()]
    main["html"] = "<br><br><hr><br>".join(html_parts)
    
    # Merge text
    text_parts = [p["text"] for p in posts_in_group if p.get("text", "").strip()]
    main["text"] = "\n\n---\n\n".join(text_parts)
    
    # Merge images
    all_images = []
    for p in posts_in_group:
        all_images.extend(p.get("images", []))
    main["images"] = all_images
        
    # Merge videos
    all_videos = []
    for p in posts_in_group:
        all_videos.extend(p.get("videos", []))
    main["videos"] = all_videos
    
    # Merge reactions
    main["reactions"] = merge_reactions([p.get("reactions", []) for p in posts_in_group])
    
    # Keep only the topics of the main post
    main["topics"] = posts_in_group[0].get("topics", [])
    
    return main


def main():
    # Backup
    if not BACKUP_JSON.exists():
        shutil.copy2(POSTS_JSON, BACKUP_JSON)
        print(f"✅ Backup created: {BACKUP_JSON.name}")
    else:
        print(f"ℹ️  Backup already exists: {BACKUP_JSON.name}")

    with open(POSTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    posts = data["posts"]
    print(f"📊 Original post count: {len(posts)}")

    # Build lookup: id -> post
    post_map = {p["id"]: p for p in posts}

    # Build set of IDs to remove (continuations)
    continuation_ids = set()
    for group in MERGE_GROUPS:
        for cid in group[1:]:
            continuation_ids.add(cid)

    # Perform merges
    merged_count = 0
    for group in MERGE_GROUPS:
        group_posts = []
        for pid in group:
            if pid in post_map:
                group_posts.append(post_map[pid])
            else:
                print(f"⚠️  Post {pid} not found, skipping group")
                break
        else:
            merged = merge_posts(group_posts)
            post_map[group[0]] = merged
            merged_count += 1
            imgs = len(merged["images"])
            vids = len(merged["videos"])
            print(f"  🔗 Merged {len(group)} posts -> {group[0]} (images: {imgs}, videos: {vids})")

    # Rebuild posts list, removing continuations
    new_posts = []
    for p in posts:
        if p["id"] in continuation_ids:
            continue
        if p["id"] in post_map:
            new_posts.append(post_map[p["id"]])
        else:
            new_posts.append(p)

    data["posts"] = new_posts
    print(f"📊 New post count: {len(new_posts)} (merged {merged_count} groups, removed {len(posts) - len(new_posts)} continuations)")

    with open(POSTS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Updated {POSTS_JSON.name}")


if __name__ == "__main__":
    main()
