import requests
import json
import logging
import threading
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('zoho_api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration ---
ZOHO_CONFIG = {
    "CLIENT_ID": "1000.RES8HX16XVF2J5CNIWJ74KQHPCKU2O",
    "CLIENT_SECRET": "1a477e636ee5601709724e944853b49f3c0d9aa0e9",
    "REFRESH_TOKEN": "1000.7adcea1f467d20ba083238aa1adac669.612fdd21defcd6cd48f51444cc0ff652",
    "ACCOUNTS_URL": "https://accounts.zoho.com",
    "API_BASE_URL": "https://support.quatrrobss.com/app/itdesk"  
}

# Token storage with expiry tracking
token_store = {
    "access_token": None,
    "expires_at": None
}

# Thread lock to prevent race conditions during token refresh
_token_lock = threading.Lock()

def get_access_token():
    """Get fresh access token with proper error handling and expiry tracking"""
    logger.info("Attempting to refresh access token...")

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

        # CRITICAL: Check if the token was actually in the response to prevent KeyError
        if "access_token" in data:
            token_store["access_token"] = data["access_token"]
            # Calculate expiry time (typically 1 hour, but add buffer)
            expires_in = data.get("expires_in", 3600)  # Default 1 hour
            token_store["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 300)  # 5 min buffer

            logger.info("✅ Successfully refreshed access token")
            logger.debug(f"Access token: {token_store['access_token']}")
            logger.debug(f"Token expires in: {expires_in} seconds")
            logger.debug(f"Token expires at: {token_store['expires_at']}")
            return True
        else:
            logger.error(f"❌ Failed to get access token. Zoho API response: {data}")
            token_store["access_token"] = None
            token_store["expires_at"] = None
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error refreshing access token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response content: {e.response.text}")
        token_store["access_token"] = None
        token_store["expires_at"] = None
        return False

def is_token_valid():
    """Check if current token is valid and not expired"""
    if not token_store.get("access_token"):
        return False

    if not token_store.get("expires_at"):
        return False

    return datetime.now() < token_store["expires_at"]

def ensure_valid_token():
    """
    Ensure we have a valid access token using a thread-safe, double-checked lock.
    """
    # First check is quick and avoids locking if the token is already valid.
    if is_token_valid():
        return True

    with _token_lock:
        # Second check after acquiring the lock, in case another thread just refreshed it.
        if is_token_valid():
            return True
        return get_access_token()

app = Flask(__name__)

@app.route("/", methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "service": "Zoho ServiceDesk Plus API",
        "token_valid": is_token_valid(),
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/create_ticket", methods=['POST'])
def create_zoho_ticket():
    """Create ticket in Zoho ServiceDesk Plus with proper error handling"""
    start_time = datetime.now()
    logger.info(f"🎫 Starting ticket creation at {start_time}")

    try:
        # Get and validate request data
        data = request.get_json()
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No JSON data received"}), 400

        logger.debug(f"Received request data: {json.dumps(data, indent=2)}")

        # Validate required fields
        base_required_fields = ['subject', 'description', 'requester_email']
        missing_fields = [field for field in base_required_fields if not data.get(field)]

        if missing_fields:
            logger.error(f"Missing base required fields: {', '.join(missing_fields)}")
            return jsonify({
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        # Ensure we have a valid token
        if not ensure_valid_token():
            logger.error("Failed to obtain valid access token")
            return jsonify({
                "error": "API authentication failed. Unable to obtain access token."
            }), 503

        # Prepare API request with CORRECT format for ServiceDesk Plus v3
        api_url = f"{ZOHO_CONFIG['API_BASE_URL']}/api/v3/requests"
        logger.info(f"API URL: {api_url}")

        #Correct headers for ServiceDesk Plus v3 API
        headers = {
            "Authorization": f"Zoho-oauthtoken {token_store['access_token']}",
            "Accept": "application/vnd.manageengine.sdp.v3+json",
            "Content-Type": "application/x-www-form-urlencoded"  
        }
        logger.debug(f"Request headers: {headers}")

        # Build the request data for Zoho by transforming the incoming JSON.
        request_data_for_zoho = data.copy()

        
        if 'requester_email' in request_data_for_zoho:
            email = request_data_for_zoho.pop('requester_email')
            request_data_for_zoho['requester'] = {'email_id': email}

        # The final payload must be wrapped in a 'request' object
        request_data = {
            "request": request_data_for_zoho
        }

        # CRITICAL: Prepare payload in correct format for ServiceDesk Plus
        payload = {
            'input_data': json.dumps(request_data)
        }
        logger.debug(f"Final payload structure: {json.dumps(payload, indent=2)}")

        # Make the API call with retry logic
        def make_api_request():
            logger.info("📤 Sending request to ServiceDesk Plus API...")
            response = requests.post(api_url, headers=headers, data=payload, timeout=30)
            logger.info(f"📥 API Response Status: {response.status_code}")  
            logger.debug(f"API Response Headers: {dict(response.headers)}")
            logger.debug(f"API Response Body: {response.text}")
            return response

        # First attempt
        response = make_api_request()

        # Handle token expiry with retry
        if response.status_code == 401:
            logger.warning("⚠️  Access token expired, refreshing and retrying...")
            if get_access_token():
                headers["Authorization"] = f"Zoho-oauthtoken {token_store['access_token']}"
                logger.info("🔄 Retrying with new token...")
                response = make_api_request()
            else:
                logger.error("❌ Failed to refresh token for retry")
                return jsonify({
                    "error": "Authentication failed. Unable to refresh access token."
                }), 401

        # Check for success
        if response.status_code not in [200, 201]:
            logger.error(f"❌ API request failed with status {response.status_code}")
            logger.error(f"Response content: {response.text}")

            # Try to parse more detailed error messages from Zoho
            try:
                error_data = response.json()
                response_status = error_data.get('response_status', {})
                messages = response_status.get('messages', [])
                
                if messages:
                    # Build a detailed error message from all available info
                    error_details = []
                    for msg in messages:
                        # Handle both single 'field' and plural 'fields' keys
                        fields = msg.get('fields', [])
                        if not fields and msg.get('field'):
                            fields = [msg.get('field')]

                        msg_type = msg.get('type')
                        message_text = msg.get('message')
                        status_code = msg.get('status_code')
                        
                        # Special handling for the most common validation error
                        if status_code == 4012 and fields:
                            detail_str = f"Mandatory fields are missing for the template: {', '.join(fields)}"
                        else:
                            # Generic handling for all other errors
                            error_parts = []
                            if fields:
                                error_parts.append(f"Field(s) '{', '.join(fields)}'")
                            if msg_type:
                                error_parts.append(f"({msg_type})")
                            if message_text:
                                error_parts.append(f": {message_text}")
                            detail_str = " ".join(part for part in error_parts if part)

                        if detail_str:
                            error_details.append(detail_str.strip())

                    error_message = " | ".join(error_details) if error_details else "An unspecified error occurred. See details."
                else:
                    # Fallback if there's no 'messages' array
                    error_message = response_status.get('status', 'Unknown error from Zoho')

                logger.error(f"Parsed Zoho API Error: {error_message}")
                return jsonify({
                    "error": f"ServiceDesk Plus API Error: {error_message}",
                    "details": error_data  # Return the full JSON error from Zoho
                }), response.status_code
            except json.JSONDecodeError:
                # This happens if the error response is not valid JSON (e.g., HTML from a proxy)
                return jsonify({
                    "error": f"API request failed with status {response.status_code} and non-JSON response",
                    "details": response.text
                }), response.status_code

        # Parse successful response
        try:
            response_data = response.json()
            logger.debug(f"Parsed response data: {json.dumps(response_data, indent=2)}")

            # Extract ticket ID from response
            ticket_id = None
            if 'request' in response_data:
                ticket_id = response_data['request'].get('id')
            elif 'requests' in response_data and len(response_data['requests']) > 0:
                ticket_id = response_data['requests'][0].get('id')

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info(f"✅ Ticket created successfully - ID: {ticket_id}, Duration: {duration:.2f}s")

            return jsonify({
                "message": "Ticket created successfully in Zoho ServiceDesk Plus",
                "zoho_ticket_id": ticket_id,
                "processing_time": f"{duration:.2f}s",
                "timestamp": datetime.now().isoformat()
            }), 201

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse API response as JSON: {e}")
            logger.error(f"Raw response: {response.text}")
            return jsonify({
                "error": "Invalid JSON response from ServiceDesk Plus API",
                "details": response.text
            }), 500

    except requests.exceptions.Timeout:
        logger.error("❌ API request timed out")
        return jsonify({
            "error": "Request to ServiceDesk Plus API timed out"
        }), 504

    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Connection error: {e}")
        return jsonify({
            "error": "Unable to connect to ServiceDesk Plus API. Check network connectivity."
        }), 503

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ API request failed: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response content: {e.response.text}")
            return jsonify({
                "error": f"ServiceDesk Plus API request failed: {str(e)}",
                "details": e.response.text
            }), 500
        return jsonify({
            "error": f"API request failed: {str(e)}"
        }), 500

    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error occurred while processing the request"
        }), 500

if __name__ == '__main__':
    # Initialize token on startup within the main execution block.
    # This prevents the token fetch from running twice when Flask's debug reloader is active.
    with app.app_context():
        get_access_token()
    logger.info("🎯 Starting ServiceDesk Plus API server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
