import json
import logging

logger = logging.getLogger(__name__)

def load_translations():
    try:
        with open('translations.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading translations: {e}")
        return {}

translations = load_translations()

def get_translated_text(key, language='en'):
    try:
        return translations.get(language, {}).get(key, translations['en'].get(key, key))
    except Exception as e:
        logger.error(f"Error getting translation for {key}: {e}")
        return key
