import os
import requests
import json
import logging
import threading
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
ZOHO_CONFIG = {
    "CLIENT_ID": os.getenv("ZOHO_CLIENT_ID"),
    "CLIENT_SECRET": os.getenv("ZOHO_CLIENT_SECRET"),
    "REFRESH_TOKEN": os.getenv("ZOHO_REFRESH_TOKEN"),
    "ACCOUNTS_URL": "https://accounts.zoho.com",
    "API_BASE_URL": os.getenv("ZOHO_API_BASE_URL")
}

# --- Thread-Safe Token Management ---
token_store = {"access_token": None, "expires_at": None}
_token_lock = threading.Lock()

def get_access_token():
    """Fetches a new access token from Zoho using the refresh token."""
    logger.info("Attempting to refresh Zoho access token...")
    url = f"{ZOHO_CONFIG['ACCOUNTS_URL']}/oauth/v2/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": ZOHO_CONFIG["CLIENT_ID"],
        "client_secret": ZOHO_CONFIG["CLIENT_SECRET"],
        "refresh_token": ZOHO_CONFIG["REFRESH_TOKEN"],
    }
    try:
        response = requests.post(url, data=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "access_token" in data:
            expires_in = data.get("expires_in", 3600)
            token_store["access_token"] = data["access_token"]
            token_store["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 300)
            logger.info("✅ Successfully refreshed Zoho access token.")
            return True
        else:
            logger.error(f"❌ Zoho API did not return an access token. Response: {data}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Exception during token refresh: {e}")
        return False

def is_token_valid():
    """Checks if the current token exists and has not expired."""
    return token_store.get("access_token") and token_store.get("expires_at") and datetime.now() < token_store["expires_at"]

def ensure_valid_token():
    """Ensures a valid access token is available using a thread-safe lock."""
    if is_token_valid():
        return True
    with _token_lock:
        # Double-check after acquiring the lock, in case another thread just refreshed it.
        if is_token_valid():
            return True
        return get_access_token()

# --- Helper Function to Parse Ticket Details ---
def _parse_ticket_details(zoho_response):
    """Parses the full Zoho ticket JSON and returns a simplified dictionary."""
    request_data = zoho_response.get("request", {})
    
    status_info = request_data.get("status", {})
    technician_info = request_data.get("technician")
    resolution_info = request_data.get("resolution")

    simplified_ticket = {
        "ticket_id": request_data.get("id"),
        "status": status_info.get("name") if status_info else None,
        "technician_assigned": technician_info.get("name") if technician_info else "Unassigned",
        "technician_contact_email": technician_info.get("email_id") if technician_info else None,
        "technician_comments": resolution_info.get("content") if resolution_info else None
    }
    return simplified_ticket

# --- Flask Application ---
app = Flask(__name__)

@app.route("/", methods=['GET'])
def health_check():
    """Health check endpoint to verify service status."""
    return jsonify({"status": "running", "service": "Zoho Ticket API", "token_valid": is_token_valid()})

@app.route("/requests/<string:request_id>", methods=['GET'])
def get_ticket(request_id):
    """Fetches and returns simplified details for a single ticket."""
    logger.info(f"Received GET request for ticket ID: {request_id}")
    if not ensure_valid_token():
        return jsonify({"error": "API authentication failed"}), 503

    api_url = f"{ZOHO_CONFIG['API_BASE_URL']}/api/v3/requests/{request_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token_store['access_token']}",
        "Accept": "application/vnd.manageengine.sdp.v3+json"
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        full_ticket_data = response.json()
        simplified_ticket = _parse_ticket_details(full_ticket_data)
        
        logger.info(f"Successfully fetched and parsed ticket ID: {request_id}")
        return jsonify(simplified_ticket), 200
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error fetching ticket {request_id}: {e.response.text}")
        return jsonify({"error": "Failed to fetch ticket", "details": e.response.json()}), e.response.status_code
    except Exception as e:
        logger.error(f"Unexpected error getting ticket {request_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route("/requests", methods=['POST'])
def create_ticket():
    """Creates a new ticket, handling data transformation for the client."""
    logger.info("Received POST request to create a new ticket.")
    if not ensure_valid_token():
        return jsonify({"error": "API authentication failed."}), 503
        
    client_data = request.get_json()
    if not client_data:
        return jsonify({"error": "Invalid or empty JSON body provided"}), 400

    zoho_data = client_data.copy()
    if 'requester_email' in zoho_data:
        email = zoho_data.pop('requester_email')
        zoho_data['requester'] = {'email_id': email}

    zoho_request_wrapper = {"request": zoho_data}
    payload = {'input_data': json.dumps(zoho_request_wrapper)}

    api_url = f"{ZOHO_CONFIG['API_BASE_URL']}/api/v3/requests"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token_store['access_token']}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/vnd.manageengine.sdp.v3+json"
    }

    try:
        response = requests.post(api_url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        ticket_id = response_data.get("request", {}).get("id")
        logger.info(f"✅ Ticket created successfully - ID: {ticket_id}")
        return jsonify({"message": "Ticket created successfully", "zoho_ticket_id": ticket_id}), 201
    except requests.exceptions.HTTPError as e:
        logger.error(f"API request failed: {e.response.text}")
        return jsonify({"error": "Failed to create ticket", "details": e.response.json()}), e.response.status_code
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500

if __name__ == '__main__':
    with app.app_context():
        if not ensure_valid_token():
            logger.critical("CRITICAL: Could not obtain initial Zoho token.")
    
    logger.info("🎯 Starting Zoho Ticket API server...")
    # The app.run() block is for development only.
    # For production, use a WSGI server like Gunicorn.
    app.run(host='0.0.0.0', port=5000, debug=False)