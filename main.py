import asyncio
import time
import json
import os
from database import init_db, article_exists, add_article_base, update_article_translation, get_todays_articles_content
from rss_reader import get_latest_articles
from scraper import scrape_article_content
from ai_handler import is_article_unique, translate_content, clean_ads_from_content
from telegraph_client import create_telegraph_page
from telegram_bot import send_for_moderation, run_bot, stop_bot

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
            debug_dir = "debug_files"
            os.makedirs(debug_dir, exist_ok=True)
            
            # 1. Get latest articles from RSS
            print("📡 Fetching RSS feed (last 5 articles)...")
            from config import RSS_FEEDS, RSS_ARTICLES_COUNT
            articles = get_latest_articles(RSS_FEEDS, RSS_ARTICLES_COUNT)
            
            if not articles:
                print("📭 No articles found in RSS feed")
                return
                
            print(f"📊 Found {len(articles)} article(s) to check")
            
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
                rss_file = f"{debug_dir}/rss_data_article_{i}.json"
                with open(rss_file, 'w', encoding='utf-8') as f:
                    json.dump(article, f, indent=2, ensure_ascii=False)
                print(f"💾 Saved RSS data to: {rss_file}")
                
                # 2. Scrape article content
                print("🕷️ Scraping article content...")
                scraped_content = scrape_article_content(link)
                if not scraped_content:
                    print(f"❌ Failed to scrape content")
                    continue
            
                print(f"✅ Content scraped successfully ({len(scraped_content['content_html'])} chars)")
                
                # 2. Save raw HTML data (original from website)
                raw_html_file = f"{debug_dir}/raw_html_article_{i}.html"
                with open(raw_html_file, 'w', encoding='utf-8') as f:
                    f.write(f"<!-- Title: {scraped_content['title']} -->\n")
                    f.write(f"<!-- URL: {link} -->\n")
                    f.write(f"<!-- Image: {scraped_content.get('image_url', 'None')} -->\n")
                    f.write(f"<!-- This is the ORIGINAL HTML from the website -->\n\n")
                    f.write(scraped_content['raw_html'])
                print(f"💾 Saved raw HTML to: {raw_html_file}")
                
                # 3. Check for semantic uniqueness with AI FIRST (before expensive operations)
                print("🤖 Checking for duplicates with AI...")
                todays_articles = get_todays_articles_content()
                if not is_article_unique(scraped_content['content_html'], todays_articles):
                    print("⚠️ Article appears to be a semantic duplicate, skipping...")
                    continue
                
                print("✅ Article is unique!")
                
                # 4. Clean ads from content using AI (only for unique articles)
                print("🧹 Cleaning ads and promotional content...")
                cleaned_content = clean_ads_from_content(scraped_content['content_html'])
                scraped_content['content_html'] = cleaned_content
                print(f"✅ Content cleaned ({len(cleaned_content)} chars after cleanup)")
                
                # 5. Save to database
                print("💾 Saving to database...")
                article_id = add_article_base(link, scraped_content['title'], scraped_content['content_html'])
                if not article_id:
                    print("❌ Failed to save article to database")
                    continue

                # 6. Translate the content
                print(f"🌐 Translating to Ukrainian...")
                translation = translate_content(
                    scraped_content['title'], 
                    scraped_content['content_html'],
                    scraped_content.get('short_description', '')
                )
                translated_title = translation['translated_title']
                translated_html = translation['translated_content_html']
                translated_description = translation.get('translated_short_description', scraped_content.get('short_description', ''))
                print(f"✅ Translation complete: '{translated_title}'")

                # 7. Save content BEFORE translation (to check if AI truncates)
                before_translation_file = f"{debug_dir}/before_translation_article_{i}.html"
                with open(before_translation_file, 'w', encoding='utf-8') as f:
                    f.write(f"<!-- Original Title: {scraped_content['title']} -->\n")
                    f.write(f"<!-- URL: {link} -->\n")
                    f.write(f"<!-- Content Length: {len(scraped_content['content_html'])} chars -->\n")
                    f.write(f"<!-- Short Description: {scraped_content.get('short_description', '')} -->\n\n")
                    f.write(scraped_content['content_html'])
                print(f"💾 Saved content BEFORE translation to: {before_translation_file}")

                # 8. Save Telegraph-ready data AFTER translation
                telegraph_file = f"{debug_dir}/after_translation_article_{i}.html"
                with open(telegraph_file, 'w', encoding='utf-8') as f:
                    f.write(f"<!-- Original Title: {scraped_content['title']} -->\n")
                    f.write(f"<!-- Translated Title: {translated_title} -->\n")
                    f.write(f"<!-- URL: {link} -->\n")
                    f.write(f"<!-- Original Length: {len(scraped_content['content_html'])} chars -->\n")
                    f.write(f"<!-- Translated Length: {len(translated_html)} chars -->\n")
                    f.write(f"<!-- Length Change: {len(translated_html) - len(scraped_content['content_html']):+d} chars -->\n\n")
                    f.write(translated_html)
                print(f"💾 Saved content AFTER translation to: {telegraph_file}")
                
                # Check if content was truncated during translation
                original_paragraphs = len([p for p in scraped_content['content_html'].split('<p>') if p.strip()])
                translated_paragraphs = len([p for p in translated_html.split('<p>') if p.strip()])
                
                if translated_paragraphs < original_paragraphs * 0.8:  # If lost more than 20% of paragraphs
                    print(f"⚠️ WARNING: Possible content truncation during translation!")
                    print(f"   Original: {original_paragraphs} paragraphs, Translated: {translated_paragraphs} paragraphs")
                else:
                    print(f"✅ Translation preserved content: {original_paragraphs} → {translated_paragraphs} paragraphs")

                # 9. Create Telegraph page
                print("📄 Creating Telegraph page...")
                telegraph_url = create_telegraph_page(translated_title, translated_html)
                if not telegraph_url:
                    print("❌ Failed to create Telegraph page")
                    continue
                    
                print(f"✅ Telegraph page created: {telegraph_url}")
                
                # 10. Update database with translation and Telegraph URL
                update_article_translation(article_id, translated_html, telegraph_url)

                # 11. Send to Telegram for moderation
                print("📱 Sending to Telegram for moderation...")
                try:
                    await send_for_moderation(telegraph_url, translated_title, link, article_id, translated_description)
                    print("✅ Sent to moderation channel successfully!")
                except Exception as e:
                    print(f"❌ Error sending to Telegram: {e}")

                print(f"🎉 Article processing completed successfully!")
                print(f"📊 Telegraph URL: {telegraph_url}")
                
                processed_count += 1
                
                # Small delay between processing multiple articles
                if i < len(articles):
                    print("⏱️ Waiting 5 seconds before next article...")
                    time.sleep(5)
            
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
        
        # Check for news every 60 seconds
        if current_time - last_check >= 60:
            await check_news_job()
            last_check = current_time
        
        # Heartbeat every 30 seconds
        if current_time - last_heartbeat >= 30:
            await heartbeat()
            last_heartbeat = current_time
        
        # Sleep for 1 second to prevent busy waiting
        await asyncio.sleep(1)

async def main():
    """Main function that sets up the bot and scheduler."""
    print("🚀 Starting News Bot...")
    
    # Initialize database
    print("💾 Initializing database...")
    init_db()
    
    # Start Telegram bot
    print("🤖 Starting Telegram bot...")
    await run_bot()
    
    print("⏰ Setting up scheduler (every 1 minute)...")
    print("✅ Scheduler started. Will check for news every minute.")
    
    # Run initial check
    print("🔄 Running initial check...")
    await check_news_job()
    
    # Start the scheduler loop
    try:
        await scheduler_loop()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        await stop_bot()

if __name__ == "__main__":
    asyncio.run(main())