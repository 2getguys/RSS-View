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
    user_content = f"НОВА СТАТТЯ:\n{new_article_content}\n\nІСНУЮЧІ СТАТТІ:\n{existing_content_block}"

    try:
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_content}
            ],
        )
        answer = response.choices[0].message.content.strip().upper()
        return "UNIQUE" in answer

    except Exception as e:
        print(f"Error checking article uniqueness with OpenAI: {e}")
        return True


def process_and_translate_article(main_content: str, additional_context: str = "") -> str:
    """
    Process, clean, and translate article content in one step using LLM.
    """
    prompt_template = load_prompt("article_processing")
    if not prompt_template:
        return main_content
    
    # Prepare the content for analysis
    user_message = f"ОСНОВНИЙ КОНТЕНТ СТАТТІ:\n{main_content}"
    
    if additional_context.strip():
        user_message += f"\n\nДОДАТКОВИЙ КОНТЕКСТ (використовуй тільки релевантні частини):\n{additional_context}"
    
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_message}
            ],
        )
        
        processed_content = response.choices[0].message.content.strip()
        
        # Remove any markdown code blocks if present
        if processed_content.startswith('```html'):
            processed_content = processed_content[7:]
        if processed_content.endswith('```'):
            processed_content = processed_content[:-3]
        
        return processed_content.strip()
        
    except Exception as e:
        print(f"❌ Error processing article with OpenAI: {e}")
        return main_content  # Return original if processing fails


def generate_title_and_description(article_content: str) -> dict:
    """
    Generate Ukrainian title and description with embedded Telegraph link placeholder.
    """
    prompt_template = load_prompt("title_description_generation")
    if not prompt_template:
        return {
            "title": "Новина",
            "description": "Цікава стаття"
        }
    
    user_message = f"КОНТЕНТ СТАТТІ:\n{article_content}"
    
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Clean any trailing punctuation just in case
        if 'title' in result:
            result['title'] = result['title'].rstrip('.,;:!?-–—').strip()
        if 'description' in result:
            result['description'] = result['description'].rstrip('.,;:!?-–—').strip()
        
        return result
        
    except Exception as e:
        print(f"❌ Error generating title and description with OpenAI: {e}")
        return {
            "title": "Новина",
            "description": "Цікава стаття"
        }