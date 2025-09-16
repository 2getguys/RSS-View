import os
import json
from openai import OpenAI
from typing import List
from config import OPENAI_API_KEY

# Configure the OpenAI client with the new syntax
client = OpenAI(api_key=OPENAI_API_KEY)

def load_prompt(prompt_name: str) -> str:
    """Load prompt from file in prompts/ directory."""
    prompt_path = os.path.join("prompts", f"{prompt_name}.txt")
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: Prompt file {prompt_path} not found")
        return ""

def clean_ads_from_content(content_html: str) -> str:
    """
    Uses OpenAI to remove advertising and promotional content from the article.
    """
    prompt_template = load_prompt("ad_cleanup")
    if not prompt_template:
        return content_html
    
    prompt = prompt_template.format(content_html=content_html)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ти експерт з очищення новинного контенту від реклами та промоційних матеріалів."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        cleaned_content = response.choices[0].message.content.strip()
        return cleaned_content if cleaned_content else content_html
        
    except Exception as e:
        print(f"Error cleaning ads with OpenAI: {e}")
        return content_html  # Return original on failure

def is_article_unique(new_article_content: str, existing_articles_content: List[str]) -> bool:
    """
    Uses OpenAI to determine if a new article is semantically unique compared to existing ones.
    """
    if not existing_articles_content:
        return True # No articles to compare against

    prompt_template = load_prompt("duplicate_check")
    if not prompt_template:
        return True
    
    existing_content_block = "\n\n---\n\n".join(existing_articles_content)
    prompt = prompt_template.format(
        new_content=new_article_content,
        existing_content=existing_content_block
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that detects duplicate news articles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10
        )
        answer = response.choices[0].message.content.strip().upper()
        return "UNIQUE" in answer

    except Exception as e:
        print(f"Error checking article uniqueness with OpenAI: {e}")
        return True

def translate_content(title: str, content_html: str, short_description: str = "") -> dict:
    """
    Translates the article title and content into Ukrainian using OpenAI, preserving HTML tags.
    """
    prompt_template = load_prompt("translation")
    if not prompt_template:
        return {
            "translated_title": title,
            "translated_short_description": short_description,
            "translated_content_html": content_html
        }
    
    prompt = prompt_template.format(
        title=title,
        short_description=short_description,
        content_html=content_html
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that translates text to Ukrainian, preserving HTML structure. Always translate the COMPLETE content without truncation."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=16000  # Allow longer responses to prevent truncation
        )
        
        translation_data = json.loads(response.choices[0].message.content)
        
        # Додаткове очищення перекладених текстів від кінцевих розділових знаків
        if 'translated_title' in translation_data:
            translation_data['translated_title'] = translation_data['translated_title'].rstrip('.,;:!?-–—').strip()
        if 'translated_short_description' in translation_data:
            translation_data['translated_short_description'] = translation_data['translated_short_description'].rstrip('.,;:!?-–—').strip()
        
        return translation_data

    except Exception as e:
        print(f"Error translating content with OpenAI: {e}")
        return {
            "translated_title": title, # Return original on failure
            "translated_short_description": short_description,
            "translated_content_html": content_html
        }

def find_best_word_for_link(title: str, short_description: str) -> str:
    """
    Uses OpenAI to find the best word in the title or description to hide the Telegraph link.
    """
    prompt_template = load_prompt("link_word_selection")
    if not prompt_template:
        return "стаття"
    
    prompt = prompt_template.format(
        title=title,
        short_description=short_description
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ти експерт з вибору ключових слів для посилань."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=10
        )
        best_word = response.choices[0].message.content.strip()
        return best_word if best_word else "стаття"

    except Exception as e:
        print(f"Error finding best word with OpenAI: {e}")
        return "стаття"  # Default fallback