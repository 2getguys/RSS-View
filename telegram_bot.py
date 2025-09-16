import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, PUBLISH_NEWS_CHANNEL_ID, PREVIEW_NEWS_CHANNEL_ID
from ai_handler import find_best_word_for_link

# Initialize the bot application
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def send_for_moderation(telegraph_url: str, title: str, original_url: str, article_id: int, short_description: str = ""):
    """Sends a message with a Telegraph link and a 'Publish' button to the moderation channel."""
    keyboard = [
        [InlineKeyboardButton("Опублікувати", callback_data=f"pub_{article_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Використовуємо LLM для вибору найкращого слова для посилання
    print("🤖 Вибираємо найкраще слово для посилання...")
    best_word = find_best_word_for_link(title, short_description)
    print(f"🎯 Обрано слово для посилання: '{best_word}'")
    
    # Замінюємо обране слово на посилання в тексті
    title_with_link = title
    description_with_link = short_description
    
    if best_word in title:
        title_with_link = title.replace(best_word, f'<a href="{telegraph_url}">{best_word}</a>', 1)
    elif best_word in short_description:
        description_with_link = short_description.replace(best_word, f'<a href="{telegraph_url}">{best_word}</a>', 1)
    else:
        # Якщо слово не знайдено, додаємо посилання до першого слова заголовка
        words = title.split()
        if words:
            title_with_link = f'<a href="{telegraph_url}">{words[0]}</a> ' + ' '.join(words[1:])
    
    # Формат: Заголовок (з посиланням на Telegraph)
    # Короткий опис
    # Джерело
    message_text = f"<b>{title_with_link}</b>\n\n{description_with_link}\n\n<a href='{original_url}'>Джерело</a>"

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
                await query.edit_message_text(
                    text=f"{query.message.text_html}\n\n<b>❌ Помилка: стаття не знайдена</b>",
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
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
            await application.bot.send_message(
                chat_id=PUBLISH_NEWS_CHANNEL_ID,
                text=publish_text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            print(f"Published article: {telegraph_url}")

            # Edit the original message in the moderation channel
            await query.edit_message_text(
                text=f"{query.message.text_html}\n\n<b>✅ Опубліковано</b>",
                parse_mode='HTML',
                disable_web_page_preview=False
            )

        except ValueError:
            print(f"Invalid article ID in callback data: {callback_data}")
            await query.edit_message_text(
                text=f"{query.message.text_html}\n\n<b>❌ Помилка: невірний ID статті</b>",
                parse_mode='HTML',
                disable_web_page_preview=False
            )
        except Exception as e:
            print(f"Error during publishing: {e}")
            await query.edit_message_text(
                text=f"{query.message.text_html}\n\n<b>❌ Помилка публікації:</b> {e}",
                parse_mode='HTML',
                disable_web_page_preview=False
            )

# Add the callback handler to the application
application.add_handler(CallbackQueryHandler(handle_publish_callback, pattern=r'^pub_'))

async def run_bot():
    """Starts the bot to listen for callbacks."""
    print("🤖 Initializing Telegram bot...")
    await application.initialize()
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

