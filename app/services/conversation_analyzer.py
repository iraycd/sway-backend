import json
import httpx
from typing import List, Dict, Any

from app.core.config import settings
from app.models.message import Message


class ConversationAnalyzer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.api_endpoint = settings.OPENROUTER_API_ENDPOINT
        # Using a smaller model for analysis
        self.model_name = "anthropic/claude-3-haiku"

        print(
            f"ConversationAnalyzer: Initialized with API key: {self.api_key[:5]}...")

    async def analyze_conversation(
        self, message: str, conversation_history: List[Message]
    ) -> Dict[str, Any]:
        """
        Analyze a conversation to determine the appropriate response approach.

        Args:
            message: The current user message to analyze
            conversation_history: The history of previous messages

        Returns:
            A dictionary with analysis results
        """
        print("ConversationAnalyzer: Analyzing conversation...")

        try:
            # Prepare the system prompt for analysis
            system_prompt = """
You are an AI assistant specialized in analyzing conversations to determine the appropriate response approach.
Your task is to analyze the conversation history and the current message to determine:
1. The type of query (SIMPLE or THERAPEUTIC)
2. The recommended approach (CONCISE or DETAILED)
3. The user's emotional state
4. A summary of the conversation context

GUIDELINES:
- SIMPLE queries are informational, factual, or casual questions that don't involve emotional support or therapeutic guidance.
- THERAPEUTIC queries involve emotional support, mental health concerns, or requests for guidance on personal issues.
- CONCISE responses are brief, direct answers (2-4 sentences).
- DETAILED responses are longer, more supportive, and include validation and therapeutic elements.

OUTPUT FORMAT:
Return a JSON object with the following fields:
{
  "queryType": "SIMPLE" or "THERAPEUTIC",
  "recommendedApproach": "CONCISE" or "DETAILED",
  "emotionalState": "Brief description of user's emotional state",
  "conversationSummary": "Brief summary of the conversation context"
}
"""

            # Prepare conversation history for the API request
            message_history = []

            # Add system prompt
            message_history.append(
                {"role": "system", "content": system_prompt})

            # Add conversation history (limited to last 5 messages to avoid token limits)
            history_limit = 5
            start_idx = max(0, len(conversation_history) - history_limit)

            for i in range(start_idx, len(conversation_history)):
                history_message = conversation_history[i]
                message_history.append({
                    "role": "user" if history_message.is_user else "assistant",
                    "content": history_message.content
                })

            # Add current user message if not already in history
            if (not conversation_history or
                conversation_history[-1].content != message or
                    not conversation_history[-1].is_user):
                message_history.append({"role": "user", "content": message})

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
                        "temperature": 0.2,  # Low temperature for more consistent analysis
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    print(
                        f"ConversationAnalyzer: API request failed with status: {response.status_code}")
                    print(
                        f"ConversationAnalyzer: Response body: {response.text}")
                    raise Exception(
                        f"API request failed with status: {response.status_code}")

                response_data = response.json()
                analysis_text = response_data["choices"][0]["message"]["content"]

                print(
                    f"ConversationAnalyzer: Received analysis: {analysis_text}")

                # Extract the JSON object from the response
                # The response might contain markdown or other formatting, so we need to extract just the JSON
                try:
                    # First try to parse the entire response as JSON
                    analysis = json.loads(analysis_text)
                except json.JSONDecodeError:
                    # If that fails, try to extract JSON from the text
                    json_start = analysis_text.find("{")
                    json_end = analysis_text.rfind("}") + 1

                    if json_start == -1 or json_end == 0:
                        print(
                            "ConversationAnalyzer: Failed to extract JSON from response")
                        # Return a default analysis if JSON extraction fails
                        return {
                            "queryType": "THERAPEUTIC",
                            "recommendedApproach": "DETAILED",
                            "emotionalState": "Unknown",
                            "conversationSummary": "Conversation analysis failed",
                        }

                    json_str = analysis_text[json_start:json_end]
                    analysis = json.loads(json_str)

                print("ConversationAnalyzer: Analysis completed successfully")
                return analysis

        except Exception as e:
            print(f"ConversationAnalyzer ERROR: {str(e)}")
            # Return a default analysis if an error occurs
            return {
                "queryType": "THERAPEUTIC",
                "recommendedApproach": "DETAILED",
                "emotionalState": "Unknown",
                "conversationSummary": "Conversation analysis failed due to an error",
            }
