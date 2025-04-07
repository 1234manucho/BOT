import os
from dotenv import load_dotenv
import google.generativeai as genai # type: ignore
from storage.database import add_bad_word # type: ignore
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configure the generative AI model
api_key = os.getenv("BAD_WORDS")
if not api_key:
    raise ValueError("API key for BAD_WORDS is not set in the environment variables.")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-2.5-pro-exp-03-25")

def is_offensive_with_gemini(text: str) -> bool:
    """
    Checks if the given text contains offensive words using the Gemini model.

    Args:
        text (str): The input text to check.

    Returns:
        bool: True if offensive words are detected, False otherwise.
    """
    try:
        prompt = f"""
Is there any offensive word in this message? If yes, return only the most offensive word used (even in disguised form), otherwise return "None".

Message: "{text}"
"""
        response = model.generate_content(prompt)
        result = response.text.strip().lower()

        if result and result != "none":
            add_bad_word(result)
            logging.info(f"Detected offensive word: {result}")
            return True
        return False
    except Exception as e:
        logging.error(f"Error while checking offensive words: {e}")
        return False