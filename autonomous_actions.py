import webbrowser
import random
import requests

def get_autonomous_action_prompt():
    actions = [read_subreddit, open_youtube_search]
    action = random.choice(actions)
    return action()

def read_subreddit():
    subreddits = ['mildlyinteresting', 'anime', 'Vocaloid', 'todayilearned', 'Showerthoughts', 'ProgrammerHumor']
    sub = random.choice(subreddits)
    try:
        # Fetch a random hot post
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SkikaiBot'}
        r = requests.get(f'https://www.reddit.com/r/{sub}/hot.json?limit=10', headers=headers, timeout=5)
        if r.status_code == 200:
            posts = r.json()['data']['children']
            post = random.choice(posts[2:]) # Skip stickies
            title = post['data']['title']
            return f"You got bored and autonomously browsed r/{sub}. You saw a post titled: '{title}'. Bring this up to Adam and give your sarcastic take on it."
    except Exception as e:
        pass
    return "You got bored and tried to browse Reddit, but the wifi is acting up. Complain to Adam about his terrible internet."

def open_youtube_search():
    topics = ['breakcore mix', 'touhou lunatic gameplay', 'serial experiments lain analysis', 'indie horror games']
    topic = random.choice(topics)
    try:
        webbrowser.open(f"https://www.youtube.com/results?search_query={topic.replace(' ', '+')}")
        return f"You got bored, so you autonomously opened a new tab on Adam's computer and searched YouTube for '{topic}'. Tell him what you did and demand he watch it with you."
    except:
        return "You got bored and wanted to open YouTube, but failed. Just insult Adam for being boring."
