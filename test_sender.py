import asyncio
import sqlite3
from telegram_bot import send_for_moderation, application

async def main():
    """
    Fetches the last 5 articles from the database and resends them for moderation.
    """
    print("Initializing Telegram bot application for the test sender...")
    # Initialize the telegram bot application, required for send_for_moderation
    await application.initialize()

    # Connect to the database
    conn = sqlite3.connect('news.db')
    # Use Row factory to access columns by name
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()

    # Fetch the last 5 articles that have a telegraph_url
    cursor.execute("""
        SELECT id, title, original_url, telegraph_url, translated_content 
        FROM articles 
        WHERE telegraph_url IS NOT NULL AND translated_content IS NOT NULL
        ORDER BY id DESC 
        LIMIT 5
    """)
    articles = cursor.fetchall()
    conn.close()

    if not articles:
        print("No processed articles found in the database to send for testing.")
        print("Please make sure at least one article has been fully processed (has a telegraph_url).")
        return

    print(f"Found {len(articles)} articles. Resending them for moderation...")

    for article in articles:
        article_id = article['id']
        title_with_link = article['title'] # In the DB, the title already has the link
        original_url = article['original_url']
        
        # The description is not stored directly, but we can use the start of the content.
        # Let's generate a mock description.
        short_description = "Це тестова відправка для перевірки публікації."
        
        print(f"Sending article ID {article_id} ('{title_with_link[:50]}...') for moderation...")
        try:
            await send_for_moderation(
                title=title_with_link,
                short_description=short_description,
                original_url=original_url,
                article_id=article_id
            )
            print(f"✅ Article {article_id} sent successfully.")
        except Exception as e:
            print(f"❌ Failed to send article {article_id}: {e}")
        
        await asyncio.sleep(1) # Sleep a bit to avoid hitting Telegram rate limits

    print("\nDone sending test articles for moderation.")
    print("Check your moderation channel.")
    
    # We need to stop the application gracefully
    await application.shutdown()


if __name__ == "__main__":
    # Ensure you have a .env file with your bot token and channel IDs
    print("--- Starting Test Sender ---")
    asyncio.run(main())
    print("--- Test Sender Finished ---")
