import httpx
from typing import Dict, Any

from app.core.config import settings


class TranslationService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.api_endpoint = settings.OPENROUTER_API_ENDPOINT
        # Using a smaller model for translation
        self.model_name = "anthropic/claude-3-haiku"

        print(
            f"TranslationService: Initialized with API key: {self.api_key[:5]}...")

    async def translate(self, text: str, source_language: str, target_language: str) -> str:
        """
        Translate text from one language to another.

        Args:
            text: The text to translate
            source_language: The language code of the source text
            target_language: The language code to translate to

        Returns:
            The translated text
        """
        # Skip translation if source and target languages are the same
        if source_language == target_language:
            print(
                "TranslationService: Source and target languages are the same, skipping translation")
            return text

        print(
            f"TranslationService: Translating from {source_language} to {target_language}")

        try:
            # Prepare the system prompt for translation
            system_prompt = f"""
You are an AI assistant specialized in translating text between languages.
Your task is to translate the provided text from {source_language} to {target_language}.

GUIDELINES:
1. Translate the text accurately while preserving the meaning and tone
2. Maintain any formatting, such as paragraphs, bullet points, or emphasis
3. Preserve any technical terms or proper nouns that should not be translated
4. Ensure the translation is natural and fluent in the target language
5. If there are cultural references that don't translate well, provide appropriate equivalents
6. For therapeutic or mental health content, ensure the translation maintains the supportive tone

OUTPUT FORMAT:
Provide only the translated text without any explanations or notes.
"""

            # Prepare the messages for the API request
            message_history = []

            # Add system prompt
            message_history.append(
                {"role": "system", "content": system_prompt})

            # Add the text to translate
            message_history.append({"role": "user", "content": text})

            # Make API request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "messages": message_history,
                        "temperature": 0.1,  # Low temperature for more accurate translation
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    print(
                        f"TranslationService: API request failed with status: {response.status_code}")
                    print(
                        f"TranslationService: Response body: {response.text}")
                    raise Exception(
                        f"API request failed with status: {response.status_code}")

                response_data = response.json()
                translated_text = response_data["choices"][0]["message"]["content"]

                print("TranslationService: Translation completed successfully")
                return translated_text

        except Exception as e:
            print(f"TranslationService ERROR: {str(e)}")
            # Return the original text if translation fails
            return text
