import asyncio
import time
import json
import os
from database import init_db, article_exists, add_article_base, update_article_translation, get_todays_articles_content
from rss_reader import get_latest_articles
from scraper import scrape_article_content
from ai_handler import is_article_unique, process_and_translate_article, generate_title_and_description
from telegraph_client import create_telegraph_page
from telegram_bot import send_for_moderation, run_bot, stop_bot
from config import CHECK_INTERVAL_SECONDS

# Global lock to prevent concurrent execution
processing_lock = asyncio.Lock()

async def check_news_job():
    """Checks for new articles and processes them."""
    # Try to acquire lock, skip if already locked
    if processing_lock.locked():
        print("⏳ Previous job still running, skipping this check...")
        return
    
    async with processing_lock:
        try:
            print("\n🔍 --- Checking for new articles... ---")
            
            # Create debug directory if it doesn't exist
            # debug_dir = "debug_files"
            # os.makedirs(debug_dir, exist_ok=True)
            
            # 1. Get latest articles from RSS feeds
            print("📡 Fetching RSS feeds (last 5 articles per feed)...")
            from config import RSS_FEEDS, RSS_ARTICLES_COUNT
            
            # Collect articles from all RSS feeds
            articles = []
            for feed_url in RSS_FEEDS:
                print(f"📡 Fetching from feed: {feed_url}")
                feed_articles = get_latest_articles(feed_url, RSS_ARTICLES_COUNT)
                if feed_articles:
                    articles.extend(feed_articles)
                    print(f"✅ Found {len(feed_articles)} article(s) from this feed")
                else:
                    print(f"📭 No articles found in this feed")
            
            if not articles:
                print("📭 No articles found in any RSS feeds")
                return
                
            print(f"📊 Found {len(articles)} total article(s) to check from {len(RSS_FEEDS)} feed(s)")
            
            processed_count = 0
            
            for i, article in enumerate(articles, 1):
                title = article.get('title', 'No Title')
                link = article.get('link', '')
                
                print(f"\n📰 Article {i}/{len(articles)}: '{title}'")
                print(f"🔗 URL: {link}")
                
                # Check if article already exists
                if article_exists(link):
                    print("📋 Article already exists in database, skipping...")
                    continue
                    
                print("🆕 New article found! Starting processing...")
                
                # 1. Save RSS data
                # rss_file = f"{debug_dir}/rss_data_article_{i}.json"
                # with open(rss_file, 'w', encoding='utf-8') as f:
                #     json.dump(article, f, indent=2, ensure_ascii=False)
                # print(f"💾 Saved RSS data to: {rss_file}")
                
                # 2. Scrape article content
                print("🕷️ Scraping article content...")
                scraped_content = await asyncio.to_thread(scrape_article_content, link)
                if not scraped_content:
                    print(f"❌ Failed to scrape content")
                    continue
            
                print(f"✅ Content scraped successfully ({len(scraped_content['content_html'])} chars)")
                
                # 2. Save raw HTML data (original from website)
                # raw_html_file = f"{debug_dir}/raw_html_article_{i}.html"
                # with open(raw_html_file, 'w', encoding='utf-8') as f:
                #     f.write(f"<!-- Title: {scraped_content['title']} -->\n")
                #     f.write(f"<!-- URL: {link} -->\n")
                #     f.write(f"<!-- Image: {scraped_content.get('image_url', 'None')} -->\n")
                #     f.write(f"<!-- This is the ORIGINAL HTML from the website -->\n\n")
                #     f.write(scraped_content['raw_html'])
                # print(f"💾 Saved raw HTML to: {raw_html_file}")
                
                # 3. Check for semantic uniqueness with AI FIRST (before expensive operations)
                print("🤖 Checking for duplicates with AI...")
                todays_articles = await asyncio.to_thread(get_todays_articles_content)
                is_unique = await asyncio.to_thread(
                    is_article_unique, scraped_content['content_html'], todays_articles
                )
                if not is_unique:
                    print("⚠️ Article appears to be a semantic duplicate, skipping processing...")
                    # Add the article to the DB with a special marker in content
                    # to prevent it from being scraped and checked again in the future.
                    await asyncio.to_thread(add_article_base, link, title, "SEMANTIC_DUPLICATE_CHECKED", None)
                    print("📝 Saved as duplicate to prevent future checks.")
                    continue
                
                print("✅ Article is unique!")
                
                # 4. Process, clean, and translate article in one step
                print("🔧 Processing, cleaning, and translating article...")
                additional_context = scraped_content.get('additional_context', '')
                processed_content = await asyncio.to_thread(
                    process_and_translate_article, scraped_content['content_html'], additional_context
                )
                
                # Log processing stats
                original_paragraphs = scraped_content['content_html'].count('<p>')
                processed_paragraphs = processed_content.count('<p>')
                print(f"✅ Article processed: {original_paragraphs} → {processed_paragraphs} paragraphs")
                if additional_context:
                    print(f"📝 Used {len(additional_context)} chars of additional context")

                # 5. Generate title and description with a placeholder for the link
                print("📝 Generating title and description with placeholder...")
                title_data = await asyncio.to_thread(generate_title_and_description, processed_content)
                title_with_placeholder = title_data.get('title', 'Новина')
                description_with_placeholder = title_data.get('description', 'Цікава стаття')

                # Extract a clean title for the Telegraph page (by removing the placeholder link)
                import re
                clean_title_for_telegraph = re.sub(r'<a href="LINK_PLACEHOLDER">(.+?)</a>', r'\1', title_with_placeholder)
                
                # 6. Create Telegraph page using the clean title
                print("📝 Creating Telegraph page...")
                telegraph_url = await asyncio.to_thread(create_telegraph_page, clean_title_for_telegraph, processed_content)
                
                if not telegraph_url:
                    print("❌ Failed to create Telegraph page")
                    continue
                    
                print(f"✅ Telegraph page created: {telegraph_url}")

                # 7. Replace placeholder with the real Telegraph URL
                final_title = title_with_placeholder.replace('LINK_PLACEHOLDER', telegraph_url)
                final_description = description_with_placeholder.replace('LINK_PLACEHOLDER', telegraph_url)
                print(f"✅ Generated final title: '{final_title}'")
                print(f"✅ Generated final description: '{final_description}'")

                # 8. Save to database
                print("💾 Saving to database...")
                image_url = scraped_content.get('image_url')
                article_id = await asyncio.to_thread(add_article_base, link, final_title, processed_content, image_url)
                if not article_id:
                    print("❌ Failed to save article to database")
                    continue

                # 9. Save processed content for debugging
                # processed_file = f"{debug_dir}/processed_article_{i}.html"
                # with open(processed_file, 'w', encoding='utf-8') as f:
                #     f.write(f"<!-- Original Title: {scraped_content['title']} -->\n")
                #     f.write(f"<!-- Processed Title: {final_title} -->\n")
                #     f.write(f"<!-- URL: {link} -->\n")
                #     f.write(f"<!-- Original Length: {len(scraped_content['content_html'])} chars -->\n")
                #     f.write(f"<!-- Processed Length: {len(processed_content)} chars -->\n")
                #     f.write(f"<!-- Description: {final_description} -->\n")
                #     f.write(processed_content)
                # print(f"💾 Saved processed content to: {processed_file}")

                # 10. Update database with Telegraph URL
                await asyncio.to_thread(update_article_translation, article_id, processed_content, telegraph_url)

                # 11. Send to Telegram for moderation
                print("📱 Sending to Telegram for moderation...")
                try:
                    await send_for_moderation(final_title, final_description, link, article_id)
                    print("✅ Sent to moderation channel successfully!")
                except Exception as e:
                    print(f"❌ Error sending to Telegram: {e}")

                print(f"🎉 Article processing completed successfully!")
                print(f"📊 Telegraph URL: {telegraph_url}")
                
                processed_count += 1
                
                # Small delay between processing multiple articles
                if i < len(articles):
                    print("⏱️ Waiting 5 seconds before next article...")
                    await asyncio.sleep(5)
            
            if processed_count > 0:
                print(f"📈 Successfully processed {processed_count} new article(s)")
            else:
                print("📋 No new articles to process")

        except Exception as e:
            print(f"💥 Unexpected error during processing: {e}")
        finally:
            print("--- Finished checking articles. ---\n")

async def heartbeat():
    """Prints a heartbeat message to show the bot is running."""
    print("💓 Heartbeat... bot is running and monitoring RSS feed")

async def scheduler_loop():
    """Main scheduler loop that runs periodically."""
    last_check = 0
    last_heartbeat = 0
    
    while True:
        current_time = time.time()
        
        # Check for news every CHECK_INTERVAL_SECONDS
        if current_time - last_check >= CHECK_INTERVAL_SECONDS:
            await check_news_job()
            last_check = current_time
        
        # Heartbeat every 30 seconds
        if current_time - last_heartbeat >= 30:
            await heartbeat()
            last_heartbeat = current_time
        
        # Sleep for 1 second to prevent busy waiting
        await asyncio.sleep(1)

async def main():
    """Initializes and runs the bot and the news checking scheduler."""
    init_db()
    
    # Create tasks for the bot and the scheduler
    bot_task = asyncio.create_task(run_bot())
    scheduler_task = asyncio.create_task(scheduler_loop())
    
    # Run them concurrently
    await asyncio.gather(
        bot_task,
        scheduler_task
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n shutting down...")
        # Gracefully stop the bot
        loop = asyncio.get_event_loop()
        loop.run_until_complete(stop_bot())
        print("Shutdown complete.")