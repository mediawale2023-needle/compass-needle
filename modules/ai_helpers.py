"""
Shared AI helper functions for CSR modules.
Centralizes OpenAI client initialization and chat completion calls.
"""
import os
from openai import OpenAI


def get_openai_client():
    """Safely initialize OpenAI client. Returns None if API key is missing."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, timeout=60.0)


def ask_openai(prompt, temperature=0.7):
    """Send a prompt to GPT-4o-mini and return the response text."""
    client = get_openai_client()
    if not client:
        return " OpenAI API Key not configured. Please check Railway Variables."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {e}"
