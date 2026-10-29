import os
import json
import logging

logger = logging.getLogger(__name__)

# Try importing the Gemini SDK
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google.generativeai not found. LLM extraction will be disabled.")

def get_api_key():
    """Retrieve the Gemini API key from environment variables.

    The function checks several common environment variable names and returns
    the first one found. It no longer provides a hardcoded fallback key — a
    valid key must be provided via the environment or a local backend/.env file.
    """
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("gemini_api_key")
        or os.environ.get("google_api_key")
    )

def is_llm_available():
    """Check if the LLM service is fully available and configured."""
    return GEMINI_AVAILABLE and bool(get_api_key())

def extract_information_with_llm(text, doc_type="Unknown"):
    """
    Use Google Gemini to extract structured JSON data from OCR text.
    Fallback to None if failed or not configured, allowing the standard NLP pipeline to take over.
    """
    if not is_llm_available():
        return None

    try:
        api_key = get_api_key()
        genai.configure(api_key=api_key)
        
        # Use a stable Gemini model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        You are an enterprise AI document extraction system.
        Analyze the following OCR text from a '{doc_type}' document.
        Extract the key entities into a highly structured JSON format.
        
        Guidelines:
        1. Only return valid JSON. Do not include markdown formatting like ```json.
        2. Extract fields such as Document Type, Date, Reference Number/Invoice Number, Total Amount, Name, Company, Address, Email, Phone.
        3. If a field is not found, omit it or set it to null.
        4. Include a short 'summary' field (1-2 sentences) summarizing the document.
        
        OCR Text:
        {text}
        """

        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Clean up possible markdown wrappers
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        result_json = json.loads(result_text.strip())
        
        # Normalize keys to title case for consistency with existing UI
        normalized_data = {}
        for k, v in result_json.items():
            normalized_key = k.replace("_", " ").title()
            normalized_data[normalized_key] = v
            
        return normalized_data

    except Exception as e:
        logger.error(f"LLM Extraction Error: {e}")
        return None
