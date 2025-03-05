import requests
import random
import os

def get_readwise_highlights():
    """Fetch highlights from Readwise API"""
    url = "https://readwise.io/api/v2/highlights/"
    headers = {"Authorization": f"Token {os.getenv('READWISE_TOKEN')}"}

    response = requests.get(url, headers=headers)
    return response.json().get("results", []) if response.status_code == 200 else []

def get_readwise_books():
    """Fetch books from Readwise API"""
    url = "https://readwise.io/api/v2/books/"
    headers = {"Authorization": f"Token {os.getenv('READWISE_TOKEN')}"}

    response = requests.get(url, headers=headers)
    return {b["id"]: b["title"] for b in response.json().get("results", [])} if response.status_code == 200 else {}

def send_to_slack(highlight):
    """Send a highlight to Slack"""
    book_title = highlight.get("book_title", "Unknown Book")
    text = highlight.get("text", "No Text Available")

    message = {
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*📖 Random Readwise Highlight:*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{book_title}*\n>{text}"}},
        ]
    }

    requests.post(os.getenv("SLACK_WEBHOOK_URL"), json=message)

def select_random_highlight():
    """Fetch highlights, select a random one, and send to Slack"""
    highlights = get_readwise_highlights()
    books = get_readwise_books()

    if not highlights:
        print("No highlights found.")
        return

    random_highlight = random.choice(highlights)
    random_highlight["book_title"] = books.get(random_highlight.get("book_id"), "Unknown Book")

    send_to_slack(random_highlight)

if __name__ == "__main__":
    select_random_highlight()
