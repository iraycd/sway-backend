import json
import httpx
from typing import List, Dict, Any

from app.core.config import settings


class ResponseProcessor:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.api_endpoint = settings.OPENROUTER_API_ENDPOINT
        # Using a smaller model for processing
        self.model_name = "anthropic/claude-3-haiku"

        print(
            f"ResponseProcessor: Initialized with API key: {self.api_key[:5]}...")

    async def process_response(
        self, raw_response: str, analysis: Dict[str, Any], user_message: str
    ) -> List[str]:
        """
        Process a raw AI response into multiple natural messages.

        Args:
            raw_response: The raw AI response to process
            analysis: The conversation analysis from the ConversationAnalyzer
            user_message: The original user message

        Returns:
            A list of processed messages
        """
        print("ResponseProcessor: Processing response...")

        # For simple queries with concise approach, just return the raw response as a single message
        if analysis["queryType"] == "SIMPLE" and analysis["recommendedApproach"] == "CONCISE":
            print(
                "ResponseProcessor: Simple query with concise approach, returning raw response")
            return [raw_response]

        try:
            # Prepare the system prompt for processing
            system_prompt = """
You are an AI assistant specialized in processing therapeutic responses into multiple natural messages.
Your task is to take a raw AI response and break it down into 2-4 separate messages that feel more natural and conversational.

GUIDELINES:
1. Break the response into 2-4 separate messages (depending on length and complexity)
2. Each message should be self-contained and make sense on its own
3. The messages should flow naturally as if they were sent sequentially in a conversation
4. Preserve all the therapeutic content and advice from the original response
5. Make the messages feel more human-like and less formal/clinical when appropriate
6. Shorter messages (1-3 sentences) are often more natural than very long paragraphs
7. The first message should acknowledge the user's concern
8. The last message might include a gentle question or invitation to continue the conversation

OUTPUT FORMAT:
Your response MUST be a valid JSON array of strings, with no additional text before or after the JSON.
The JSON array should contain 2-4 separate messages:

["First message", "Second message", "Third message", "Fourth message (if needed)"]

IMPORTANT: Do not include any explanations, markdown formatting, or any text outside the JSON array.
Your entire response should be parseable as JSON. Do not include ```json``` code blocks or any other text.
"""

            # Prepare the messages for the API request
            message_history = []

            # Add system prompt
            message_history.append(
                {"role": "system", "content": system_prompt})

            # Add context about the user's message and the raw response
            message_history.append({
                "role": "user",
                "content": f"""
USER'S MESSAGE:
{user_message}

CONVERSATION CONTEXT:
{analysis['conversationSummary']}

USER'S EMOTIONAL STATE:
{analysis['emotionalState']}

RAW AI RESPONSE TO PROCESS:
{raw_response}

Please process this into multiple natural messages.
"""
            })

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
                        "temperature": 0.3,  # Slightly higher temperature for more natural variation
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    print(
                        f"ResponseProcessor: API request failed with status: {response.status_code}")
                    print(f"ResponseProcessor: Response body: {response.text}")
                    raise Exception(
                        f"API request failed with status: {response.status_code}")

                response_data = response.json()
                processed_text = response_data["choices"][0]["message"]["content"]

                print(
                    f"ResponseProcessor: Received processed response: {processed_text}")
                print(
                    f"ResponseProcessor: Response length: {len(processed_text)} characters")

                # Try to extract the JSON array using multiple methods
                messages = self._extract_messages_from_response(processed_text)

                if messages:
                    print(
                        f"ResponseProcessor: Successfully extracted {len(messages)} messages from JSON")
                    return messages

                print(
                    "ResponseProcessor: JSON extraction failed, using fallback message splitter")
                messages = self._split_message_with_fallback(raw_response)

                print(
                    f"ResponseProcessor: Processing completed with {len(messages)} messages using fallback splitter")
                return messages

        except Exception as e:
            print(f"ResponseProcessor ERROR: {str(e)}")
            # Use fallback message splitter instead of returning raw response
            print("ResponseProcessor: Using fallback message splitter due to error")
            return self._split_message_with_fallback(raw_response)

    def _extract_messages_from_response(self, processed_text: str) -> List[str]:
        """
        Attempts to extract messages from the API response using multiple methods
        """
        try:
            # Method 1: Try to find a JSON array using regex
            import re
            json_array_regex = re.compile(
                r'\[\s*"[^"\\]*(?:\\.[^"\\]*)*"(?:\s*,\s*"[^"\\]*(?:\\.[^"\\]*)*")*\s*\]')
            match = json_array_regex.search(processed_text)

            if match:
                json_str = match.group(0)
                processed_messages = json.loads(json_str)
                return [msg for msg in processed_messages]

            # Method 2: Try to find the JSON array using bracket matching
            json_start = processed_text.find('[')
            json_end = processed_text.rfind(']') + 1

            if json_start != -1 and json_end > json_start:
                json_str = processed_text[json_start:json_end]
                try:
                    processed_messages = json.loads(json_str)
                    return [msg for msg in processed_messages]
                except json.JSONDecodeError:
                    print(
                        f"ResponseProcessor: Failed to parse JSON with bracket matching")

                    # Try to clean the JSON string before parsing
                    try:
                        cleaned_json_str = self._clean_json_string(json_str)
                        processed_messages = json.loads(cleaned_json_str)
                        print(
                            "ResponseProcessor: Successfully parsed JSON after cleaning")
                        return [msg for msg in processed_messages]
                    except json.JSONDecodeError:
                        print(
                            "ResponseProcessor: Failed to parse JSON even after cleaning")

            # Method 3: Look for code blocks that might contain JSON
            code_block_regex = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')
            print("ResponseProcessor: Checking for code blocks in response")
            code_block_match = code_block_regex.search(processed_text)

            if code_block_match and code_block_match.group(1):
                code_content = code_block_match.group(1)
                if code_content.strip().startswith('[') and code_content.strip().endswith(']'):
                    try:
                        processed_messages = json.loads(code_content.strip())
                        return [msg for msg in processed_messages]
                    except json.JSONDecodeError:
                        print(
                            "ResponseProcessor: Failed to parse JSON from code block")

                        # Try to clean the JSON string before parsing
                        try:
                            cleaned_json_str = self._clean_json_string(
                                code_content.strip())
                            processed_messages = json.loads(cleaned_json_str)
                            print(
                                "ResponseProcessor: Successfully parsed JSON from code block after cleaning")
                            return [msg for msg in processed_messages]
                        except json.JSONDecodeError:
                            print(
                                "ResponseProcessor: Failed to parse JSON from code block even after cleaning")

            # Method 4: Try to extract an array by looking for message patterns
            print("ResponseProcessor: Trying to extract messages by pattern matching")
            messages = self._extract_messages_by_pattern(processed_text)
            if messages:
                print(
                    f"ResponseProcessor: Successfully extracted {len(messages)} messages by pattern matching")
                return messages

            return []
        except Exception as e:
            print(
                f"ResponseProcessor: Error in _extract_messages_from_response: {str(e)}")
            return []

    def _clean_json_string(self, json_str: str) -> str:
        """
        Cleans a JSON string to make it more likely to parse correctly
        """
        # Replace escaped quotes with temporary markers
        cleaned = json_str.replace('\\"', '##QUOTE##')

        # Replace any unescaped internal quotes with escaped quotes
        import re
        cleaned = re.sub(
            r'(?<=\[|\,)\s*"(.*?)(?<!\\)"(?=.*?(?:\,|\]))',
            lambda match: '"' + match.group(1).replace('"', '\\"') + '"',
            cleaned
        )

        # Restore the originally escaped quotes
        cleaned = cleaned.replace('##QUOTE##', '\\"')

        return cleaned

    def _extract_messages_by_pattern(self, text: str) -> List[str]:
        """
        Extracts messages by looking for patterns that indicate separate messages
        """
        # If the text doesn't look like it contains multiple messages, return empty
        if '"' not in text and "message" not in text:
            return []

        # Try to find message patterns like "Message 1: content" or "1. content"
        messages = []

        # Pattern 1: Look for numbered messages with colons
        import re
        numbered_messages_regex = re.compile(
            r'(?:^|\n)(?:Message\s*)?(\d+)[:.]\s*(.*?)(?=(?:\n(?:Message\s*)?(?:\d+)[:.]\s*)|$)',
            re.IGNORECASE | re.DOTALL
        )

        matches = numbered_messages_regex.findall(text)
        if len(matches) >= 2:
            # At least 2 messages to be worth extracting
            for _, content in matches:
                content = content.strip()
                if content:
                    messages.append(content)

            if len(messages) >= 2:
                return messages

        # Pattern 2: Look for quoted messages
        quoted_messages_regex = re.compile(
            r'"([^"\\]*(?:\\.[^"\\]*)*)"', re.DOTALL)
        quoted_matches = quoted_messages_regex.findall(text)

        if len(quoted_matches) >= 2:
            # At least 2 messages to be worth extracting
            messages = []
            for content in quoted_matches:
                content = content.strip()
                if content:
                    messages.append(content)

            if len(messages) >= 2:
                return messages

        # Pattern 3: Look for paragraphs that might be separate messages
        paragraphs = re.split(r'\n\s*\n', text)
        if 2 <= len(paragraphs) <= 4:
            return [p.strip() for p in paragraphs if p.strip()]

        return []

    def _split_message_with_fallback(self, raw_message: str) -> List[str]:
        """
        Splits a message into multiple messages using natural language processing techniques
        """
        if not raw_message:
            return [raw_message]

        # If the message is short, don't split it
        if len(raw_message) < 200:
            return [raw_message]

        # Split by double newlines (paragraphs)
        import re
        paragraphs = re.split(r'\n\s*\n', raw_message)

        # If we have 2-4 paragraphs, use them directly
        if 2 <= len(paragraphs) <= 4:
            return [p.strip() for p in paragraphs if p.strip()]

        # If we have more than 4 paragraphs, combine some to get 3-4 messages
        if len(paragraphs) > 4:
            from math import min
            return self._combine_into_batches(paragraphs, min(4, len(paragraphs) // 2))

        # If we only have one paragraph, try to split by sentences at logical points
        sentences = re.split(r'(?<=[.!?])\s+', raw_message)

        if len(sentences) >= 3:
            # Try to create 2-3 balanced messages
            from math import min
            return self._combine_into_batches(sentences, min(3, len(sentences) // 3))

        # If all else fails, just return the original message
        return [raw_message]

    def _combine_into_batches(self, segments: List[str], num_batches: int) -> List[str]:
        """
        Combines a list of text segments into a specified number of batches
        """
        if not segments or num_batches <= 0:
            return []

        if num_batches == 1 or len(segments) == 1:
            return ["\n\n".join(segments)]

        from math import ceil, min
        result = []
        segments_per_batch = ceil(len(segments) / num_batches)

        for i in range(num_batches):
            start = i * segments_per_batch
            end = min(start + segments_per_batch, len(segments))

            if start < len(segments):
                batch = "\n\n".join(segments[start:end])
                if batch.strip():
                    result.append(batch)

        return result
