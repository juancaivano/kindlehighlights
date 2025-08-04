import requests
import random
import os
import logging
import sys
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('readwise_slack.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ReadwiseSlackBot:
    def __init__(self, date_filter=None, age_random=False):
        self.readwise_token = os.getenv('READWISE_TOKEN')
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.date_filter = date_filter  # 'recent', 'old', or None
        self.age_random = age_random  # True for age-normalized random selection
        self.validate_environment()
    
    def validate_environment(self):
        """Validate that required environment variables are set"""
        if not self.readwise_token:
            raise ValueError("READWISE_TOKEN environment variable is required")
        if not self.slack_webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL environment variable is required")
        logger.info("Environment variables validated successfully")
    
    def get_readwise_highlights(self, limit: int = None) -> List[Dict]:
        """Fetch highlights from Readwise API with pagination support"""
        url = "https://readwise.io/api/v2/highlights/"
        headers = {"Authorization": f"Token {self.readwise_token}"}
        params = {"page_size": 1000}  # API max is 1000
        
        all_highlights = []
        
        try:
            page = 1
            while url:
                logger.info(f"Fetching highlights page {page}")
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                highlights = data.get("results", [])
                all_highlights.extend(highlights)
                
                # Check for next page
                url = data.get("next")
                params = {}  # Clear params for subsequent requests
                page += 1
                
                logger.info(f"Fetched {len(highlights)} highlights. Total: {len(all_highlights)}")
                
                # Stop if we have enough highlights and a limit is set
                if limit and len(all_highlights) >= limit:
                    all_highlights = all_highlights[:limit]
                    break
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching highlights: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching highlights: {e}")
            return []
        
        logger.info(f"Successfully fetched {len(all_highlights)} total highlights")
        return all_highlights
    
    def get_readwise_books(self) -> Dict[int, str]:
        """Fetch books from Readwise API with pagination support"""
        url = "https://readwise.io/api/v2/books/"
        headers = {"Authorization": f"Token {self.readwise_token}"}
        params = {"page_size": 1000}
        
        all_books = {}
        
        try:
            while url:
                logger.info(f"Fetching books from: {url}")
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                books = data.get("results", [])
                
                for book in books:
                    all_books[book["id"]] = book["title"]
                
                # Check for next page
                url = data.get("next")
                params = {}  # Clear params for subsequent requests
                
                logger.info(f"Fetched {len(books)} books. Total: {len(all_books)}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching books: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching books: {e}")
            return {}
        
        logger.info(f"Successfully fetched {len(all_books)} total books")
        return all_books
    
    def format_highlight_for_slack(self, highlight: Dict, book_title: str, book_info: Dict = None) -> Dict:
        """Format a highlight for Slack message with rich information"""
        text = highlight.get("text", "No text available").strip()
        note = highlight.get("note", "").strip()
        
        # Truncate very long highlights
        if len(text) > 1000:
            text = text[:997] + "..."
        
        # Get additional info
        author = book_info.get("author", "") if book_info else ""
        category = book_info.get("category", "") if book_info else ""
        source_url = book_info.get("source_url", "") if book_info else ""
        cover_image_url = book_info.get("cover_image_url", "") if book_info else ""
        
        # Build book title with author
        book_display = f"*{book_title}*"
        if author:
            book_display += f" by {author}"
        
        # Add category/genre if available
        if category and category.lower() not in ['books', 'articles']:
            book_display += f" • _{category}_"
        
        # Build the main highlight section
        highlight_text = f"{book_display}\n> {text}"
        
        # Build the message blocks
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📖 Random Readwise Highlight*"
                }
            }
        ]
        
        # Add cover image if available
        if cover_image_url:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": highlight_text
                },
                "accessory": {
                    "type": "image",
                    "image_url": cover_image_url,
                    "alt_text": f"Cover of {book_title}"
                }
            })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": highlight_text
                }
            })
        
        # Add note if it exists
        if note:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*💭 Your Note:* _{note}_"
                }
            })
        
        # Build context information
        context_elements = []
        
        # Add creation date
        created_at = highlight.get("created_at", "")
        if created_at:
            try:
                date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime("%B %d, %Y")
                days_ago = (datetime.now() - date_obj.replace(tzinfo=None)).days
                
                if days_ago == 0:
                    date_context = f"Highlighted today ({formatted_date})"
                elif days_ago == 1:
                    date_context = f"Highlighted yesterday ({formatted_date})"
                elif days_ago < 30:
                    date_context = f"Highlighted {days_ago} days ago ({formatted_date})"
                elif days_ago < 365:
                    months_ago = days_ago // 30
                    date_context = f"Highlighted {months_ago} month{'s' if months_ago > 1 else ''} ago ({formatted_date})"
                else:
                    years_ago = days_ago // 365
                    date_context = f"Highlighted {years_ago} year{'s' if years_ago > 1 else ''} ago ({formatted_date})"
                
                context_elements.append({
                    "type": "mrkdwn",
                    "text": f"📅 {date_context}"
                })
            except ValueError:
                pass
        
        # Add location in book if available
        location = highlight.get("location", 0)
        if location and location > 0:
            context_elements.append({
                "type": "mrkdwn", 
                "text": f"📍 Location {location}"
            })
        
        # Add tags if available
        tags = highlight.get("tags", [])
        if tags:
            tag_text = ", ".join([f"#{tag['name']}" for tag in tags if tag.get('name')])
            if tag_text:
                context_elements.append({
                    "type": "mrkdwn",
                    "text": f"🏷️ {tag_text}"
                })
        
        # Add readwise URL for easy access
        highlight_id = highlight.get("id")
        if highlight_id:
            context_elements.append({
                "type": "mrkdwn",
                "text": f"<https://readwise.io/bookreview/{highlight.get('book_id', '')}/highlight/{highlight_id}|View in Readwise>"
            })
        
        # Add context block if we have any context elements
        if context_elements:
            blocks.append({
                "type": "context",
                "elements": context_elements
            })
        
        # Add divider for clean separation
        blocks.append({"type": "divider"})
        
        # Add actions/buttons for interaction
        action_elements = []
        
        # Link to full book in Readwise
        book_id = highlight.get("book_id")
        if book_id:
            action_elements.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "📚 View Book",
                    "emoji": True
                },
                "url": f"https://readwise.io/bookreview/{book_id}"
            })
        
        # Link to source if available
        if source_url and source_url.startswith(('http://', 'https://')):
            action_elements.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "🔗 Read Source",
                    "emoji": True
                },
                "url": source_url
            })
        
        if action_elements:
            blocks.append({
                "type": "actions",
                "elements": action_elements
            })
        
        return {"blocks": blocks}
    
    def send_to_slack(self, message: Dict) -> bool:
        """Send a message to Slack"""
        try:
            response = requests.post(
                self.slack_webhook_url,
                json=message,
                timeout=30
            )
            response.raise_for_status()
            logger.info("Successfully sent message to Slack")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message to Slack: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to Slack: {e}")
            return False
    
    def filter_highlights_by_date(self, highlights: List[Dict]) -> List[Dict]:
        """Filter highlights based on date preferences"""
        if not self.date_filter:
            return highlights
        
        now = datetime.now()
        filtered = []
        
        for highlight in highlights:
            created_at = highlight.get("created_at", "")
            if not created_at:
                continue
                
            try:
                # Parse the date
                date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_obj = date_obj.replace(tzinfo=None)  # Remove timezone for comparison
                
                if self.date_filter == 'recent':
                    # Last 2 years
                    if (now - date_obj).days <= 730:
                        filtered.append(highlight)
                elif self.date_filter == 'old':
                    # Older than 2 years
                    if (now - date_obj).days > 730:
                        filtered.append(highlight)
                        
            except ValueError:
                continue  # Skip highlights with invalid dates
        
        logger.info(f"Date filter '{self.date_filter}' reduced {len(highlights)} to {len(filtered)} highlights")
        return filtered
    
    def age_normalized_random_selection(self, highlights: List[Dict]) -> Dict:
        """
        Select a highlight with age-normalized randomness.
        This ensures equal probability across all time periods, regardless of 
        how many highlights exist in each period.
        """
        if not highlights:
            return None
            
        # Group highlights by time periods (quarters)
        time_buckets = {}
        now = datetime.now()
        
        for highlight in highlights:
            created_at = highlight.get("created_at", "")
            try:
                date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_obj = date_obj.replace(tzinfo=None)
                
                # Create time bucket key (year-quarter)
                quarter = (date_obj.month - 1) // 3 + 1
                bucket_key = f"{date_obj.year}-Q{quarter}"
                
                if bucket_key not in time_buckets:
                    time_buckets[bucket_key] = []
                time_buckets[bucket_key].append(highlight)
                
            except ValueError:
                # For highlights without valid dates, put in special bucket
                if 'no-date' not in time_buckets:
                    time_buckets['no-date'] = []
                time_buckets['no-date'].append(highlight)
        
        if not time_buckets:
            return random.choice(highlights)
        
        # Step 1: Randomly select a time bucket (each period has equal chance)
        selected_bucket_key = random.choice(list(time_buckets.keys()))
        selected_bucket = time_buckets[selected_bucket_key]
        
        # Step 2: Randomly select a highlight from that bucket
        selected_highlight = random.choice(selected_bucket)
        
        # Log the selection process
        bucket_size = len(selected_bucket)
        total_buckets = len(time_buckets)
        
        logger.info(f"Age-normalized selection:")
        logger.info(f"  Selected time bucket: {selected_bucket_key} ({bucket_size} highlights)")
        logger.info(f"  Total time buckets: {total_buckets}")
        logger.info(f"  Bucket probability: {100/total_buckets:.1f}%")
        
        # Show bucket distribution
        logger.info(f"  Time bucket distribution:")
        for bucket_key in sorted(time_buckets.keys()):
            count = len(time_buckets[bucket_key])
            logger.info(f"    {bucket_key}: {count} highlights")
        
        return selected_highlight
    def filter_highlights_by_quality(self, highlights: List[Dict]) -> List[Dict]:
        """Filter highlights to exclude very short or empty ones"""
        filtered = []
        for highlight in highlights:
            text = highlight.get("text", "").strip()
            if len(text) >= 20:  # Minimum 20 characters
                filtered.append(highlight)
        
        logger.info(f"Quality filter reduced {len(highlights)} highlights down to {len(filtered)} quality highlights")
        return filtered
    
    def analyze_highlight_distribution(self, highlights: List[Dict]) -> None:
        """Analyze and log the time distribution of highlights"""
        if not highlights:
            return
            
        dates = []
        now = datetime.now()
        
        for highlight in highlights:
            created_at = highlight.get("created_at", "")
            try:
                date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                dates.append(date_obj.replace(tzinfo=None))
            except ValueError:
                continue
        
        if not dates:
            return
        
        dates.sort()
        oldest = dates[0]
        newest = dates[-1]
        
        # Count highlights by year
        year_counts = {}
        for date in dates:
            year = date.year
            year_counts[year] = year_counts.get(year, 0) + 1
        
        logger.info(f"Highlight distribution analysis:")
        logger.info(f"  Date range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
        logger.info(f"  Total span: {(newest - oldest).days} days")
        
        # Show yearly breakdown
        for year in sorted(year_counts.keys()):
            percentage = (year_counts[year] / len(dates)) * 100
            logger.info(f"  {year}: {year_counts[year]} highlights ({percentage:.1f}%)")
        
        # Recent vs old split
        recent_count = sum(1 for d in dates if (now - d).days <= 730)
        old_count = len(dates) - recent_count
        
        logger.info(f"  Recent (≤2 years): {recent_count} highlights ({(recent_count/len(dates)*100):.1f}%)")
        logger.info(f"  Older (>2 years): {old_count} highlights ({(old_count/len(dates)*100):.1f}%)")
    
    def select_and_send_random_highlight(self) -> bool:
        """Main function to fetch highlights, select a random one, and send to Slack"""
        logger.info("Starting random highlight selection process")
        
        # Fetch all highlights (remove limit to get everything)
        highlights = self.get_readwise_highlights()
        if not highlights:
            logger.warning("No highlights found")
            return False
        
        # Analyze distribution before filtering
        self.analyze_highlight_distribution(highlights)
        
        books = self.get_readwise_books()
        
        # Apply date filter if specified
        if self.date_filter:
            highlights = self.filter_highlights_by_date(highlights)
            if not highlights:
                logger.warning(f"No highlights found matching date filter: {self.date_filter}")
                return False
        
        # Filter highlights for quality
        quality_highlights = self.filter_highlights_by_quality(highlights)
        if not quality_highlights:
            logger.warning("No quality highlights found after filtering")
            return False
        
        # Select highlight using age-normalized randomness if enabled
        if self.age_random:
            random_highlight = self.age_normalized_random_selection(quality_highlights)
        else:
            random_highlight = random.choice(quality_highlights)
            
        book_id = random_highlight.get("book_id")
        book_info = books.get(book_id, {})
        book_title = book_info.get("title", "Unknown Book")
        
        # Log selection details
        created_at = random_highlight.get("created_at", "")
        if created_at:
            try:
                date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                logger.info(f"Selected highlight from '{book_title}' created on {date_obj.strftime('%Y-%m-%d')}")
            except ValueError:
                logger.info(f"Selected highlight from '{book_title}'")
        else:
            logger.info(f"Selected highlight from '{book_title}'")
        
        # Format and send message with rich book info
        message = self.format_highlight_for_slack(random_highlight, book_title, book_info)
        success = self.send_to_slack(message)
        
        if success:
            logger.info("Successfully completed random highlight sharing")
        else:
            logger.error("Failed to share random highlight")
        
        return success

def main():
    """Main entry point with command line arguments"""
    parser = argparse.ArgumentParser(description='Send random Readwise highlights to Slack')
    parser.add_argument('--date-filter', choices=['recent', 'old'], 
                       help='Filter highlights by age: recent (≤2 years) or old (>2 years)')
    parser.add_argument('--age-random', action='store_true',
                       help='Use age-normalized random selection (equal chance for each time period)')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Only analyze highlight distribution without sending to Slack')
    parser.add_argument('--test-format', action='store_true',
                       help='Send a test highlight to see the new formatting')
    
    args = parser.parse_args()
    
    try:
        bot = ReadwiseSlackBot(date_filter=args.date_filter, age_random=args.age_random)
        
        if args.analyze_only:
            # Just fetch and analyze highlights
            highlights = bot.get_readwise_highlights()
            bot.analyze_highlight_distribution(highlights)
            logger.info("Analysis complete. Use without --analyze-only to send a highlight.")
            sys.exit(0)
        
        if args.test_format:
            logger.info("Running in test format mode - will send one highlight to preview new formatting")
        
        success = bot.select_and_send_random_highlight()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
