"""
Unit tests for the refactored Zoho ServiceDesk API
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from zoho_ticket_api import (
    TicketService, 
    ZohoTokenManager, 
    ZohoServiceDeskClient,
    TicketRequest,
    ApiResponse,
    Config
)


class TestZohoTokenManager(unittest.TestCase):
    """Test cases for ZohoTokenManager"""

    def setUp(self):
        self.token_manager = ZohoTokenManager()

    @patch('refactored_zoho_ticket_api.requests.post')
    def test_refresh_token_success(self, mock_post):
        """Test successful token refresh"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test_token',
            'expires_in': 3600
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = self.token_manager.refresh_token()

        self.assertTrue(result)
        self.assertEqual(self.token_manager._access_token, 'test_token')

    @patch('refactored_zoho_ticket_api.requests.post')
    def test_refresh_token_failure(self, mock_post):
        """Test failed token refresh"""
        mock_post.side_effect = Exception("Network error")

        result = self.token_manager.refresh_token()

        self.assertFalse(result)
        self.assertIsNone(self.token_manager._access_token)


class TestTicketService(unittest.TestCase):
    """Test cases for TicketService"""

    def setUp(self):
        self.mock_api_client = Mock()
        self.ticket_service = TicketService(self.mock_api_client)

    def test_validate_ticket_data_success(self):
        """Test successful validation"""
        data = {
            'subject': 'Test Subject',
            'description': 'Test Description', 
            'requester_email': 'test@example.com'
        }

        result = self.ticket_service._validate_ticket_data(data)

        self.assertTrue(result.success)

    def test_validate_ticket_data_missing_fields(self):
        """Test validation with missing fields"""
        data = {
            'subject': 'Test Subject'
            # Missing description and requester_email
        }

        result = self.ticket_service._validate_ticket_data(data)

        self.assertFalse(result.success)
        self.assertIn('Missing required fields', result.error)

    def test_validate_ticket_data_invalid_email(self):
        """Test validation with invalid email"""
        data = {
            'subject': 'Test Subject',
            'description': 'Test Description',
            'requester_email': 'invalid_email'
        }

        result = self.ticket_service._validate_ticket_data(data)

        self.assertFalse(result.success)
        self.assertIn('Invalid email format', result.error)

    def test_create_ticket_success(self):
        """Test successful ticket creation"""
        data = {
            'subject': 'Test Subject',
            'description': 'Test Description',
            'requester_email': 'test@example.com'
        }

        self.mock_api_client.create_ticket.return_value = ApiResponse(
            success=True,
            data={'zoho_ticket_id': '123456'},
            status_code=201
        )

        result = self.ticket_service.create_ticket(data)

        self.assertTrue(result.success)
        self.assertEqual(result.data['zoho_ticket_id'], '123456')


class TestZohoServiceDeskClient(unittest.TestCase):
    """Test cases for ZohoServiceDeskClient"""

    def setUp(self):
        self.mock_token_manager = Mock()
        self.mock_token_manager.get_access_token.return_value = 'test_token'
        self.client = ZohoServiceDeskClient(self.mock_token_manager)

    def test_build_request_payload(self):
        """Test request payload building"""
        ticket_data = TicketRequest(
            subject='Test Subject',
            description='Test Description',
            requester_email='test@example.com',
            urgency={'name': 'High'}
        )

        payload = self.client._build_request_payload(ticket_data)

        expected = {
            'request': {
                'subject': 'Test Subject',
                'description': 'Test Description',
                'requester': {'email_id': 'test@example.com'},
                'urgency': {'name': 'High'}
            }
        }

        self.assertEqual(payload, expected)

    @patch('refactored_zoho_ticket_api.requests.post')
    def test_create_ticket_success(self, mock_post):
        """Test successful ticket creation"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'request': {'id': '123456'}
        }
        mock_post.return_value = mock_response

        ticket_data = TicketRequest(
            subject='Test Subject',
            description='Test Description', 
            requester_email='test@example.com'
        )

        result = self.client.create_ticket(ticket_data)

        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 201)


if __name__ == '__main__':
    unittest.main()
