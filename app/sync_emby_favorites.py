import requests
import time

# 配置区：请根据你的环境修改
SOURCE_EMBY = {
    'url': 'http://192.168.2.40:8096',
    'api_key': 'c9eb2ec6cddc4fe1bb67da7164f8aa30',
    'user_id': 'f1a696591cfb4f79b23757f7cc573b81',
}

TARGET_EMBY = {
    'url': 'http://192.168.2.88:8096',
    'api_key': '8690f73558834e34aa5d85ba77c76052',
    'user_id': 'd6307e6064a343e8b14e683ae85b4ddf',
}


def get_favorite_songs(emby):
    """从 Emby 获取收藏的音频"""
    url = f"{emby['url']}/Users/{emby['user_id']}/Items"
    params = {
        "SortBy": "Random",
        "SortOrder": "Ascending",
        "IncludeItemTypes": "Audio",
        "Recursive": "true",
        "Fields": "SortName,MediaSources,AudioInfo,DateCreated,ProductionYear",
        "ImageTypeLimit": "1",
        "EnableImageTypes": "Backdrop",
        "StartIndex": "0",
        "isFavorite": "true",
    }
    headers = {
        'X-Emby-Token': emby['api_key']
    }
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    return r.json().get('Items', [])


def search_song_on_target(emby, title, artist):
    """在目标服务器搜索歌曲"""
    url = f"{emby['url']}/Items"
    params = {
        'IncludeItemTypes': 'Audio',
        'SearchTerm': title,
        'Recursive': 'true',
    }
    headers = {
        'X-Emby-Token': emby['api_key']
    }
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    for item in r.json().get('Items', []):
        if artist in item.get('Artists', []):
            return item['Id']
    return None


def mark_favorite(emby, item_id):
    """标记收藏"""
    url = f"{emby['url']}/Users/{emby['user_id']}/FavoriteItems/{item_id}"
    headers = {
        'X-Emby-Token': emby['api_key']
    }
    r = requests.post(url, headers=headers)
    r.raise_for_status()
    return r.status_code == 204


def sync_favorites():
    print("🔍 正在获取源服务器的收藏歌曲...")
    source_songs = get_favorite_songs(SOURCE_EMBY)
    print(f"共获取到 {len(source_songs)} 首收藏歌曲。")

    synced = 0
    for song in source_songs:
        title = song.get('Name')
        artists = song.get('Artists', [])
        if not artists:
            continue
        artist = artists[0]

        print(f"🎵 正在同步：《{title}》 - {artist}")

        target_id = search_song_on_target(TARGET_EMBY, title, artist)
        if target_id:
            try:
                mark_favorite(TARGET_EMBY, target_id)
                synced += 1
                print("✅ 已标记为收藏。")
            except Exception as e:
                print(f"❌ 收藏失败: {e}")
        else:
            print("⚠️ 未在目标服务器找到匹配歌曲。")

        time.sleep(0.2)  # 限速，避免请求过快

    print(f"✅ 同步完成：共同步 {synced} 首歌曲。")


if __name__ == '__main__':
    sync_favorites()
