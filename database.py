import sqlite3
from datetime import datetime

DB_NAME = 'news.db'

def init_db():
    """Initializes the database and creates the articles table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            original_content TEXT,
            translated_content TEXT,
            telegraph_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized.")

def add_article_base(original_url: str, title: str, original_content: str) -> int | None:
    """Adds a new article with its original content and returns the new row's ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO articles (original_url, title, original_content)
            VALUES (?, ?, ?)
        ''', (original_url, title, original_content))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        print(f"Article with URL {original_url} already exists.")
        return None
    finally:
        conn.close()

def update_article_translation(article_id: int, translated_content: str, telegraph_url: str):
    """Updates an article with its translated content and Telegraph URL."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE articles
        SET translated_content = ?, telegraph_url = ?
        WHERE id = ?
    ''', (translated_content, telegraph_url, article_id))
    conn.commit()
    conn.close()

def article_exists(original_url: str) -> bool:
    """Checks if an article with the given URL already exists."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM articles WHERE original_url = ?', (original_url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_todays_articles_content() -> list[str]:
    """Retrieves the original content of the last 5 articles published today."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT original_content FROM articles 
        WHERE DATE(created_at, 'localtime') = ? 
        AND original_content IS NOT NULL
        ORDER BY created_at DESC 
        LIMIT 5
    """, (today_str,))
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

def get_article_by_telegraph_url(telegraph_url: str) -> dict | None:
    """Retrieves article data by its telegraph_url."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT title, telegraph_url FROM articles WHERE telegraph_url = ?', (telegraph_url,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"title": result[0], "telegraph_url": result[1]}
    return None

def get_article_by_id(article_id: int) -> dict | None:
    """Retrieves article data by its ID, including its content."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    cursor = conn.cursor()
    # Fetch the translated_content as it's the final, processed version
    cursor.execute('SELECT id, title, telegraph_url, translated_content FROM articles WHERE id = ?', (article_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        # Convert the sqlite3.Row object to a dictionary
        return dict(result)
    return None

