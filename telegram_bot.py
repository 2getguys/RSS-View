import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, PUBLISH_NEWS_CHANNEL_ID, PREVIEW_NEWS_CHANNEL_ID, MAKE_WEBHOOK_URL
from ai_handler import generate_facebook_post

# Initialize the bot application
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def send_for_moderation(title: str, short_description: str, original_url: str, article_id: int):
    """Sends a message with embedded Telegraph link and a 'Publish' button to the moderation channel."""
    keyboard = [
        [InlineKeyboardButton("Опублікувати", callback_data=f"pub_{article_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    print("📝 Using AI-generated title and description with embedded link")
    
    # Title and description already have embedded Telegraph links from AI
    # Формат: Заголовок (з посиланням на Telegraph)
    # Короткий опис
    # Джерело
    message_text = f"<b>{title}</b>\n\n{short_description}\n\n<a href='{original_url}'>Джерело</a>"

    await application.bot.send_message(
        chat_id=PREVIEW_NEWS_CHANNEL_ID,
        text=message_text,
        reply_markup=reply_markup,
        parse_mode='HTML',
        disable_web_page_preview=False
    )
    print(f"Sent article '{title}' for moderation.")

async def handle_publish_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the 'Publish' button callback."""
    print(f"🔔 Received callback: {update.callback_query.data}")
    query = update.callback_query
    
    try:
        await query.answer()
    except Exception as e:
        if "too old" in str(e) or "timeout expired" in str(e):
            print("⚠️ Callback query is too old, but continuing with publication...")
        else:
            print(f"❌ Error answering callback: {e}")
            return

    # Extract the article ID from the callback data
    callback_data = query.data
    print(f"📋 Processing callback data: {callback_data}")
    if callback_data.startswith("pub_"):
        try:
            article_id = int(callback_data.replace("pub_", ""))
            
            # Get the Telegraph URL from database
            from database import get_article_by_id
            article = get_article_by_id(article_id)
            
            if not article or not article.get('telegraph_url'):
                print(f"Article {article_id} not found or has no Telegraph URL")
                try:
                    await query.edit_message_text(
                        text=f"{query.message.text_html}\n\n<b>❌ Помилка: стаття не знайдена</b>",
                        parse_mode='HTML',
                        disable_web_page_preview=False
                    )
                except Exception as e:
                    print(f"⚠️ Could not edit message: {e}")
                return
            
            telegraph_url = article['telegraph_url']
            
            # Отримуємо оригінальний текст з повідомлення модерації
            original_text = query.message.text_html
            
            # Видаляємо "Джерело" з кінця (останній рядок з посиланням)
            lines = original_text.split('\n')
            # Знаходимо останній рядок з "Джерело" і видаляємо його
            filtered_lines = []
            for line in lines:
                if not ('<a href=' in line and 'Джерело</a>' in line):
                    filtered_lines.append(line)
            
            # Формуємо фінальний текст для публікації
            publish_text = '\n'.join(filtered_lines).strip()
            
            # Send the formatted message to the public channel
            sent_message = await application.bot.send_message(
                chat_id=PUBLISH_NEWS_CHANNEL_ID,
                text=publish_text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            print(f"✅ Published article: {telegraph_url}")
            
            # --- Start Webhook Logic (async, with timeout protection) ---
            if MAKE_WEBHOOK_URL:
                try:
                    # 1. Get Telegram post link
                    if sent_message.chat.username:
                        post_url = f"https://t.me/{sent_message.chat.username}/{sent_message.message_id}"
                    else:
                        # For private channels, chat_id is a negative number.
                        # The link format is t.me/c/channel_id/message_id
                        chat_id_str = str(sent_message.chat.id).replace("-100", "")
                        post_url = f"https://t.me/c/{chat_id_str}/{sent_message.message_id}"
                    
                    print(f"🔗 Generated Telegram post link: {post_url}")
                    
                    # 2. Generate Facebook post content from the processed article content
                    article_content = article.get('translated_content', '')
                    
                    if not article_content:
                        print(f"⚠️ Warning: Article {article_id} has no content. AI generation might be inaccurate.")

                    print(f"🤖 Generating Facebook post...")
                    facebook_post_text = generate_facebook_post(article_content)
                    print(f"✅ Facebook post generated")

                    # 3. Send webhook to Make.com with timeout
                    webhook_payload = {
                        "facebook_post": facebook_post_text, # The AI prompt already includes the call to action
                        "telegram_post_url": post_url
                    }
                    
                    # Add image_url only if it exists
                    image_url = article.get('image_url')
                    if image_url:
                        webhook_payload["image_url"] = image_url
                        print(f"🖼️ Including image URL: {image_url}")
                    else:
                        print(f"📷 No image found for this article")
                    
                    print(f"📦 Sending webhook to Make.com...")

                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(MAKE_WEBHOOK_URL, json=webhook_payload)
                        response.raise_for_status() # Raise an exception for bad status codes
                    
                    print(f"✅ Successfully sent webhook to Make.com. Status: {response.status_code}")

                except httpx.TimeoutException as e:
                    print(f"⚠️ Webhook timeout (Make.com took too long): {e}")
                except httpx.RequestError as e:
                    print(f"❌ Error sending webhook to Make.com: {e}")
                except Exception as e:
                    print(f"❌ An unexpected error occurred in the webhook logic: {e}")
            # --- End Webhook Logic ---

            # Edit the original message in the moderation channel (with error handling)
            try:
                await query.edit_message_text(
                    text=f"{query.message.text_html}\n\n<b>✅ Опубліковано</b>",
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
            except Exception as e:
                print(f"⚠️ Could not edit moderation message (probably timeout): {e}")
                print("✅ Article was published successfully despite the error")

        except ValueError:
            print(f"Invalid article ID in callback data: {callback_data}")
            try:
                await query.edit_message_text(
                    text=f"{query.message.text_html}\n\n<b>❌ Помилка: невірний ID статті</b>",
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
            except Exception as e:
                print(f"⚠️ Could not edit message: {e}")
        except Exception as e:
            print(f"❌ Error during publishing: {e}")
            import traceback
            traceback.print_exc()
            try:
                await query.edit_message_text(
                    text=f"{query.message.text_html}\n\n<b>❌ Помилка публікації</b>",
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
            except Exception as edit_error:
                print(f"⚠️ Could not edit message: {edit_error}")

# Add the callback handler to the application
application.add_handler(CallbackQueryHandler(handle_publish_callback, pattern=r'^pub_'))

async def run_bot():
    """Starts the bot to listen for callbacks."""
    print("🤖 Initializing Telegram bot...")
    await application.initialize()

    # Delete any existing webhook to ensure polling works
    print("🗑️  Checking for and deleting any existing webhook...")
    if await application.bot.delete_webhook():
        print("✅ Webhook deleted successfully.")
    else:
        print("ℹ️  No webhook was active.")

    print("🚀 Starting Telegram bot...")
    await application.start()
    print("📡 Starting polling for updates...")
    await application.updater.start_polling(poll_interval=1, timeout=30)
    print("✅ Telegram bot is running and listening for callbacks!")

async def stop_bot():
    """Stops the bot gracefully."""
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    print("Telegram bot stopped.")

if __name__ == '__main__':
    # For testing the bot independently
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_bot())
    # Keep it running until manually stopped
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(stop_bot())

