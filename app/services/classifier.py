import json
import logging
import time
import requests
from typing import Dict, Tuple
from ..config import settings

logger = logging.getLogger(__name__)

CATEGORIES = ["Network", "Software", "Hardware", "Cloud", "General"]
PRIORITIES = ["High", "Medium", "Low"]

def hf_request_post(url: str, json_payload: dict, headers: dict, timeout: int = 5, max_retries: int = 2) -> requests.Response:
    """Helper function to perform POST requests to Hugging Face Inference API with a retry mechanism on transient network errors."""
    attempt = 0
    backoff = 0.5  # seconds
    while True:
        try:
            attempt += 1
            response = requests.post(url, json=json_payload, headers=headers, timeout=timeout)
            # If server indicates overloaded/loading (503 Service Unavailable), retry once
            if response.status_code == 503 and attempt < max_retries:
                logger.warning(f"Hugging Face API returned 503 (model loading) on attempt {attempt}/{max_retries}. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries:
                logger.warning(f"Transient connection error '{e}' on attempt {attempt}/{max_retries}. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            raise e

def query_huggingface_zero_shot(text: str, candidate_labels: list) -> Tuple[str, str]:
    """
    Queries Hugging Face Inference API for Zero-Shot Classification models (e.g. bart-large-mnli).
    Returns: Tuple of (best_matching_label, processing_source)
    """
    if not settings.HF_TOKEN or settings.HF_TOKEN.strip() == "" or "your_huggingface_access_token" in settings.HF_TOKEN:
        return "", "Fallback Rules (No Token)"

    url = f"https://api-inference.huggingface.co/models/{settings.HF_MODEL}"
    headers = {"Authorization": f"Bearer {settings.HF_TOKEN}"}
    payload = {
        "inputs": text,
        "parameters": {"candidate_labels": candidate_labels}
    }

    try:
        response = hf_request_post(url, payload, headers, timeout=5)
        
        # Handle model loading (503 Service Unavailable)
        if response.status_code == 503:
            logger.warning("Hugging Face model is currently loading (503) after retries. Using local fallback.")
            return "", "Fallback Rules (Model Loading)"
            
        response.raise_for_status()
        result = response.json()
        
        if "labels" in result and len(result["labels"]) > 0:
            best_label = result["labels"][0]
            logger.info(f"Hugging Face successfully classified: '{best_label}'")
            return best_label, f"Hugging Face ({settings.HF_MODEL})"
            
        logger.warning(f"Unexpected HF response format: {result}. Using local fallback.")
        return "", "Fallback Rules (Invalid Response)"
        
    except Exception as e:
        logger.error(f"Failed to query Hugging Face API: {str(e)}. Using local fallback.")
        return "", "Fallback Rules (API Error)"


def query_huggingface_chat(text: str) -> Tuple[str, str, str]:
    """
    Queries Hugging Face Serverless Inference API for Conversational LLMs (e.g. Llama/Qwen).
    Returns: Tuple of (category, priority, processing_source)
    """
    if not settings.HF_TOKEN or settings.HF_TOKEN.strip() == "" or "your_huggingface_access_token" in settings.HF_TOKEN:
        return "", "", "Fallback Rules (No Token)"

    url = f"https://api-inference.huggingface.co/models/{settings.HF_MODEL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.HF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    You are an expert IT support ticket routing agent. 
    Analyze the following IT support ticket title and description, and output a valid JSON containing classification details.
    
    Allowed Categories: Network, Software, Hardware, Cloud, General
    Allowed Priorities: High, Medium, Low
    
    IT Ticket to analyze:
    {text}
    
    You MUST output ONLY a valid JSON object matching this schema, with no other text, comments, markdown blocks, or explanations:
    {{
      "category": "chosen_category",
      "priority": "chosen_priority"
    }}
    """
    
    payload = {
        "model": settings.HF_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 120,
        "temperature": 0.1
    }
    
    try:
        response = hf_request_post(url, payload, headers, timeout=5)
        
        # Handle model loading (503 Service Unavailable)
        if response.status_code == 503:
            logger.warning(f"Hugging Face model {settings.HF_MODEL} is loading (503) after retries. Using local fallback.")
            return "", "", "Fallback Rules (Model Loading)"
            
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"].strip()
            
            # Clean up potential markdown formatting (e.g. ```json ... ```)
            if content.startswith("```"):
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1]
                else:
                    content = parts[0]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            # Parse output
            data = json.loads(content)
            cat = data.get("category", "").strip()
            pri = data.get("priority", "").strip()
            
            # Validation
            if cat in CATEGORIES and pri in PRIORITIES:
                logger.info(f"Hugging Face LLM successfully classified: Category={cat}, Priority={pri}")
                return cat, pri, f"Hugging Face LLM ({settings.HF_MODEL})"
            else:
                logger.warning(f"LLM returned invalid classification values: {cat}, {pri}. Using local fallback.")
                return "", "", "Fallback Rules (Invalid Values)"
                
        logger.warning(f"Unexpected HF response format: {result}. Using local fallback.")
        return "", "", "Fallback Rules (Invalid Response)"
    except Exception as e:
        logger.error(f"Failed to query Hugging Face LLM API: {str(e)}. Using local fallback.")
        return "", "", "Fallback Rules (API/Parse Error)"


def local_fallback_classify_category(title: str, description: str) -> str:
    """Local keyword-based classification rule engine for category detection."""
    text = (title + " " + description).lower()
    
    # 1. Network Keywords
    network_words = ['vpn', 'network', 'firewall', 'wi-fi', 'wifi', 'dns', 'connection', 'internet', 'router', 'switch', 'dhcp', 'ip address', 'offline']
    if any(word in text for word in network_words):
        return "Network"
        
    # 2. Cloud Keywords
    cloud_words = ['cloud', 'aws', 'azure', 'gcp', 's3', 'ec2', 'kubernetes', 'k8s', 'docker', 'hosting', 'devops', 'pipeline', 'deployment']
    if any(word in text for word in cloud_words):
        return "Cloud"
        
    # 3. Hardware Keywords
    hardware_words = ['laptop', 'desktop', 'hardware', 'printer', 'monitor', 'broken', 'keyboard', 'mouse', 'screen', 'charger', 'battery', 'device', 'usb', 'headset', 'pc']
    if any(word in text for word in hardware_words):
        return "Hardware"
        
    # 4. Software Keywords
    software_words = ['software', 'app', 'application', 'install', 'license', 'excel', 'outlook', 'office', 'windows', 'macos', 'linux', 'browser', 'chrome', 'adobe', 'update', 'bug', 'crash', 'word', 'powerpoint']
    if any(word in text for word in software_words):
        return "Software"
        
    return "General"


def local_fallback_classify_priority(title: str, description: str) -> str:
    """Local keyword-based classification rule engine for priority detection."""
    text = (title + " " + description).lower()
    
    # Urgent/Critical triggers High priority
    high_words = ['urgent', 'critical', 'down', 'outage', 'emergency', 'asap', 'broken', 'stop', 'blocked', 'crash', 'fail', 'cannot work']
    if any(word in text for word in high_words):
        return "High"
        
    # Standard issues trigger Medium priority
    medium_words = ['slow', 'issue', 'problem', 'help', 'need', 'error', 'warning', 'renew', 'access', 'request', 'ticket']
    if any(word in text for word in medium_words):
        return "Medium"
        
    return "Low"


def classify_ticket(title: str, description: str) -> Dict[str, str]:
    """
    Aggregated classification service analyzing a ticket's category and priority.
    Returns: Dict containing 'category', 'category_source', 'priority', 'priority_source'
    """
    ticket_text = f"Title: {title}\nDescription: {description}"
    
    # Check if the configured model is a zero-shot classification model
    # (typically contains "bart-large", "zero-shot", "nli")
    is_zero_shot = any(k in settings.HF_MODEL.lower() for k in ["bart-large", "zero-shot", "nli"])
    
    if is_zero_shot:
        # Route to Zero-Shot Classification API
        hf_category, cat_source = query_huggingface_zero_shot(ticket_text, CATEGORIES)
        category = hf_category if hf_category else local_fallback_classify_category(title, description)
        
        hf_urgency, pri_source = query_huggingface_zero_shot(ticket_text, ["High Urgency", "Medium Urgency", "Low Urgency"])
        if hf_urgency:
            priority_map = {"High Urgency": "High", "Medium Urgency": "Medium", "Low Urgency": "Low"}
            priority = priority_map.get(hf_urgency, "Medium")
        else:
            priority = local_fallback_classify_priority(title, description)
    else:
        # Route to Chat Completions LLM API
        llm_cat, llm_pri, source = query_huggingface_chat(ticket_text)
        if llm_cat and llm_pri:
            category = llm_cat
            priority = llm_pri
            cat_source = source
            pri_source = source
        else:
            category = local_fallback_classify_category(title, description)
            priority = local_fallback_classify_priority(title, description)
            cat_source = source
            pri_source = source
            
    return {
        "category": category,
        "category_source": cat_source,
        "priority": priority,
        "priority_source": pri_source
    }


def query_huggingface_resolution(title: str, description: str, category: str) -> Tuple[list, str, str]:
    """
    Queries Hugging Face LLM API to analyze the issue, suggest troubleshooting solutions, and draft a response.
    Returns: Tuple of (solutions_list, draft_reply_str, processing_source)
    """
    if not settings.HF_TOKEN or settings.HF_TOKEN.strip() == "" or "your_huggingface_access_token" in settings.HF_TOKEN:
        return [], "", "Fallback Rules (No Token)"

    is_zero_shot = any(k in settings.HF_MODEL.lower() for k in ["bart-large", "zero-shot", "nli"])
    if is_zero_shot:
        return [], "", "Fallback Rules (Zero-Shot model does not support Chat)"

    url = f"https://api-inference.huggingface.co/models/{settings.HF_MODEL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.HF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    You are an expert IT support specialist.
    Analyze the following IT support ticket:
    Category: {category}
    Title: {title}
    Description: {description}
    
    Provide:
    1. A list of 3 troubleshooting steps or possible solutions.
    2. A professional, helpful draft email/message reply to resolve this ticket.
    
    You MUST output ONLY a valid JSON object matching this schema, with no other text, comments, markdown blocks, or explanations:
    {{
      "solutions": ["Step 1...", "Step 2...", "Step 3..."],
      "draft_reply": "Hello, ..."
    }}
    """
    
    payload = {
        "model": settings.HF_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 300,
        "temperature": 0.2
    }
    
    try:
        response = hf_request_post(url, payload, headers, timeout=5)
        if response.status_code == 503:
            logger.warning(f"Hugging Face model {settings.HF_MODEL} is loading (503) after retries. Using local fallback.")
            return [], "", "Fallback Rules (Model Loading)"
            
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"].strip()
            
            # Clean up potential markdown formatting (e.g. ```json ... ```)
            if content.startswith("```"):
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1]
                else:
                    content = parts[0]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            # Parse output
            data = json.loads(content)
            solutions = data.get("solutions", [])
            draft_reply = data.get("draft_reply", "")
            
            if isinstance(solutions, list) and isinstance(draft_reply, str):
                return solutions, draft_reply, f"Hugging Face LLM ({settings.HF_MODEL})"
                
        return [], "", "Fallback Rules (Invalid Response Format)"
    except Exception as e:
        logger.error(f"Failed to query Hugging Face LLM API for resolution: {str(e)}")
        return [], "", "Fallback Rules (API/Parse Error)"


def local_fallback_resolution(category: str) -> Tuple[list, str]:
    """Generates a detailed fallback resolution plan based on ticket category."""
    cat = category.strip() if category else "General"
    
    if cat == "Network":
        solutions = [
            "Flush DNS resolver cache (run 'ipconfig /flushdns' on Windows or 'sudo killall -HUP mDNSResponder' on macOS).",
            "Verify profile settings on the corporate VPN client and attempt re-authentication.",
            "Inspect physical router connections or switch Wi-Fi adapter off and on to clear channel conflicts."
        ]
        draft_reply = "Hello,\n\nI have reviewed your network connectivity ticket. Please try flushing your local DNS cache and restarting your VPN client with the official corporate profile. Let us know if the connection stabilizes.\n\nBest regards,\nIT Support Team"
    elif cat == "Software":
        solutions = [
            "Clear the application local configuration directory and run standard app repair diagnostics.",
            "Verify software registry licensing keys against the corporate software registry portal.",
            "Install pending software patches or updates and reboot the computer."
        ]
        draft_reply = "Hello,\n\nI have analyzed the software behavior you described. Please clear the application data cache and run the built-in repair utility. If license key issues persist, let us know.\n\nBest regards,\nIT Support Team"
    elif cat == "Hardware":
        solutions = [
            "Perform a hard power cycle (unplug power cable, hold physical power button for 10 seconds, then restart).",
            "Examine physical HDMI/USB-C connection ports and cable integrity.",
            "Run hardware diagnostics during system startup (e.g., Apple Diagnostics or Dell ePSA scan)."
        ]
        draft_reply = "Hello,\n\nRegarding the hardware symptom reported, please perform a complete power cycle and inspect the interface cables. If this does not resolve it, we can schedule an on-site hardware inspection.\n\nBest regards,\nIT Support Team"
    elif cat == "Cloud":
        solutions = [
            "Verify IAM permission scopes and check validity of user access credentials keys.",
            "Check cloud provider status dashboards (AWS/Azure/GCP status page) for regional outages.",
            "Check pod logs and verify deployment manifest configurations."
        ]
        draft_reply = "Hello,\n\nThank you for reaching out. I have checked the cloud resources for your workspace. Please verify your active IAM token permissions. We are monitoring region services for any transient outages.\n\nBest regards,\nIT Support Team"
    else:
        solutions = [
            "Restart your laptop/workstation to clear stuck processes and free up active memory.",
            "Verify corporate Single Sign-On (SSO) credentials status in the employee directory portal.",
            "Submit detail logs to Tier-2 system engineers if symptoms persist."
        ]
        draft_reply = "Hello,\n\nI have received your support request. Please restart your workstation to reset background handlers and verify your SSO login status. Let us know if the issue continues.\n\nBest regards,\nIT Support Team"
        
    return solutions, draft_reply


def analyze_ticket_resolution(title: str, description: str, category: str) -> dict:
    """Main aggregated service endpoint to generate resolution analysis."""
    solutions, draft_reply, source = query_huggingface_resolution(title, description, category)
    if not solutions or not draft_reply:
        solutions, draft_reply = local_fallback_resolution(category)
        source = "Fallback Rules (Local Database)"
        
    return {
        "solutions": solutions,
        "draft_reply": draft_reply,
        "source": source
    }

