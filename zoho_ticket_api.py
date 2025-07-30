
"""
Zoho ServiceDesk Ticket API - Refactored with OOP Design Patterns
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import requests
import json
import logging
from flask import Flask, request, jsonify
from dataclasses import dataclass
from datetime import datetime
import time


# Configuration Management (Singleton Pattern)
class Config:
    """Singleton configuration class to manage application settings"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.ZOHO_CONFIG = {
            "CLIENT_ID": "1000.RES8HX16XVF2J5CNIWJ74KQHPCKU2O",
            "CLIENT_SECRET": "1a477e636ee5601709724e944853b49f3c0d9aa0e9",
            "REFRESH_TOKEN": "1000.7adcea1f467d20ba083238aa1adac669.612fdd21defcd6cd48f51444cc0ff652",
            "ACCOUNTS_URL": "https://accounts.zoho.com",
            "API_BASE_URL": "https://support.quatrrobss.com/app/itdesk"
        }


# Data Models (Data Classes)
@dataclass
class TicketRequest:
    """Data class for ticket request"""
    subject: str
    description: str
    requester_email: str
    template: Optional[Dict[str, str]] = None
    urgency: Optional[Dict[str, str]] = None
    category: Optional[Dict[str, str]] = None
    subcategory: Optional[Dict[str, str]] = None
    item: Optional[Dict[str, str]] = None
    udf_fields: Optional[Dict[str, Any]] = None


@dataclass
class ApiResponse:
    """Data class for API responses"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: int = 200


# Abstract Base Classes (Strategy Pattern)
class TokenManager(ABC):
    """Abstract base class for token management"""

    @abstractmethod
    def get_access_token(self) -> Optional[str]:
        """Get access token"""
        pass

    @abstractmethod
    def refresh_token(self) -> bool:
        """Refresh access token"""
        pass


class ApiClient(ABC):
    """Abstract base class for API clients"""

    @abstractmethod
    def create_ticket(self, ticket_data: TicketRequest) -> ApiResponse:
        """Create a ticket"""
        pass


# Concrete Implementations
class ZohoTokenManager(TokenManager):
    """Concrete implementation for Zoho token management"""

    def __init__(self):
        self.config = Config()
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self.logger = logging.getLogger(__name__)

    def get_access_token(self) -> Optional[str]:
        """Get current access token, refresh if needed"""
        if self._is_token_expired():
            if not self.refresh_token():
                return None
        return self._access_token

    def refresh_token(self) -> bool:
        """Refresh the access token using refresh token"""
        url = f"{self.config.ZOHO_CONFIG['ACCOUNTS_URL']}/oauth/v2/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.config.ZOHO_CONFIG["CLIENT_ID"],
            "client_secret": self.config.ZOHO_CONFIG["CLIENT_SECRET"],
            "refresh_token": self.config.ZOHO_CONFIG["REFRESH_TOKEN"],
        }

        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()

            token_data = response.json()
            self._access_token = token_data.get("access_token")

            # Set token expiry (typically 1 hour from now)
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = datetime.now().timestamp() + expires_in - 60  # 60s buffer

            self.logger.info("Successfully refreshed access token")
            return True

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error refreshing access token: {e}")
            self._access_token = None
            self._token_expiry = None
            return False

    def _is_token_expired(self) -> bool:
        """Check if current token is expired"""
        if not self._access_token or not self._token_expiry:
            return True
        return datetime.now().timestamp() >= self._token_expiry


class ZohoServiceDeskClient(ApiClient):
    """Concrete implementation for Zoho ServiceDesk API client"""

    def __init__(self, token_manager: TokenManager):
        self.config = Config()
        self.token_manager = token_manager
        self.logger = logging.getLogger(__name__)

    def create_ticket(self, ticket_data: TicketRequest) -> ApiResponse:
        """Create a ticket in Zoho ServiceDesk"""
        access_token = self.token_manager.get_access_token()
        if not access_token:
            return ApiResponse(
                success=False,
                error="Failed to obtain access token",
                status_code=503
            )

        # Build the request payload according to ServiceDesk API format
        request_payload = self._build_request_payload(ticket_data)

        api_url = f"{self.config.ZOHO_CONFIG['API_BASE_URL']}/api/v3/requests"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Accept": "application/vnd.manageengine.sdp.v3+json",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # The API expects input_data as form data, not JSON
        payload = {'input_data': json.dumps(request_payload)}

        try:
            response = requests.post(api_url, headers=headers, data=payload, timeout=30)

            # Handle token expiry
            if response.status_code == 401:
                self.logger.info("Token expired, refreshing and retrying...")
                if self.token_manager.refresh_token():
                    headers["Authorization"] = f"Zoho-oauthtoken {self.token_manager.get_access_token()}"
                    response = requests.post(api_url, headers=headers, data=payload, timeout=30)
                else:
                    return ApiResponse(
                        success=False,
                        error="Failed to refresh token",
                        status_code=401
                    )

            response_data = response.json()

            if response.status_code == 201:
                ticket_id = response_data.get("request", {}).get("id")
                return ApiResponse(
                    success=True,
                    data={
                        "message": "Ticket created successfully in Zoho Service Desk",
                        "zoho_ticket_id": ticket_id
                    },
                    status_code=201
                )
            else:
                error_msg = self._extract_error_message(response_data)
                return ApiResponse(
                    success=False,
                    error=f"API Error: {error_msg}",
                    status_code=response.status_code
                )

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            return ApiResponse(
                success=False,
                error=f"Request failed: {str(e)}",
                status_code=500
            )

    def _build_request_payload(self, ticket_data: TicketRequest) -> Dict[str, Any]:
        """Build the request payload according to ServiceDesk API format"""
        request_data = {
            "request": {
                "subject": ticket_data.subject,
                "description": ticket_data.description,
                "requester": {
                    "email_id": ticket_data.requester_email
                }
            }
        }

        # Add optional fields if provided
        if ticket_data.template:
            request_data["request"]["template"] = ticket_data.template

        if ticket_data.urgency:
            request_data["request"]["urgency"] = ticket_data.urgency

        if ticket_data.category:
            request_data["request"]["category"] = ticket_data.category

        if ticket_data.subcategory:
            request_data["request"]["subcategory"] = ticket_data.subcategory

        if ticket_data.item:
            request_data["request"]["item"] = ticket_data.item

        if ticket_data.udf_fields:
            request_data["request"]["udf_fields"] = ticket_data.udf_fields

        return request_data

    def _extract_error_message(self, response_data: Dict[str, Any]) -> str:
        """Extract error message from API response"""
        try:
            response_status = response_data.get("response_status", {})
            messages = response_status.get("messages", [])
            if messages:
                return messages[0].get("message", "Unknown error")
            return response_status.get("status", "Unknown error")
        except (KeyError, IndexError):
            return str(response_data)


# Service Layer (Business Logic)
class TicketService:
    """Service layer for ticket operations"""

    def __init__(self, api_client: ApiClient):
        self.api_client = api_client
        self.logger = logging.getLogger(__name__)

    def create_ticket(self, ticket_data: Dict[str, Any]) -> ApiResponse:
        """Create a ticket with validation"""
        # Validate required fields
        validation_result = self._validate_ticket_data(ticket_data)
        if not validation_result.success:
            return validation_result

        # Create ticket request object
        ticket_request = TicketRequest(
            subject=ticket_data['subject'],
            description=ticket_data['description'],
            requester_email=ticket_data['requester_email'],
            template=ticket_data.get('template'),
            urgency=ticket_data.get('urgency'),
            category=ticket_data.get('category'),
            subcategory=ticket_data.get('subcategory'),
            item=ticket_data.get('item'),
            udf_fields=ticket_data.get('udf_fields')
        )

        # Create ticket via API client
        result = self.api_client.create_ticket(ticket_request)

        # Log the operation
        if result.success:
            self.logger.info(f"Ticket created successfully: {result.data}")
        else:
            self.logger.error(f"Failed to create ticket: {result.error}")

        return result

    def _validate_ticket_data(self, data: Dict[str, Any]) -> ApiResponse:
        """Validate ticket data"""
        required_fields = ['subject', 'description', 'requester_email']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return ApiResponse(
                success=False,
                error=f"Missing required fields: {', '.join(missing_fields)}",
                status_code=400
            )

        # Validate email format (basic validation)
        email = data.get('requester_email', '')
        if '@' not in email or '.' not in email.split('@')[-1]:
            return ApiResponse(
                success=False,
                error="Invalid email format",
                status_code=400
            )

        return ApiResponse(success=True)


# Factory Pattern for creating services
class ServiceFactory:
    """Factory for creating service instances"""

    @staticmethod
    def create_ticket_service() -> TicketService:
        """Create a configured ticket service"""
        token_manager = ZohoTokenManager()
        api_client = ZohoServiceDeskClient(token_manager)
        return TicketService(api_client)


# Flask Application (Controller Layer)
class TicketController:
    """Controller for ticket-related endpoints"""

    def __init__(self, ticket_service: TicketService):
        self.ticket_service = ticket_service

    def create_ticket_endpoint(self):
        """Flask endpoint for creating tickets"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No JSON data provided"}), 400

            result = self.ticket_service.create_ticket(data)

            if result.success:
                return jsonify(result.data), result.status_code
            else:
                return jsonify({"error": result.error}), result.status_code

        except Exception as e:
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# Application Factory Pattern
class FlaskAppFactory:
    """Factory for creating Flask application"""

    @staticmethod
    def create_app() -> Flask:
        """Create and configure Flask application"""
        app = Flask(__name__)

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Create services
        ticket_service = ServiceFactory.create_ticket_service()
        ticket_controller = TicketController(ticket_service)

        # Register routes
        app.add_url_rule(
            '/create_ticket',
            'create_ticket',
            ticket_controller.create_ticket_endpoint,
            methods=['POST']
        )

        # Health check endpoint
        @app.route('/health')
        def health_check():
            return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

        return app


# Application entry point
def create_app():
    """Application factory function"""
    return FlaskAppFactory.create_app()


if __name__ == '__main__':
    app = create_app()

    # Initialize token on startup
    token_manager = ZohoTokenManager()
    if token_manager.refresh_token():
        print("Successfully initialized access token")
    else:
        print("Failed to initialize access token")

    app.run(host='0.0.0.0', port=5000, debug=True)
