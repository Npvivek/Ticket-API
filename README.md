# Zoho Ticket API

A simple API gateway to create and view tickets in Zoho ServiceDesk. It handles Zoho's authentication so you don't have to.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd <repo-folder>
    ```

2.  **Set up a virtual environment:**
    ```bash
    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate

    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create your environment file:**
    Create a file named `.env` in the project root and add your Zoho credentials. The `.gitignore` file is already set up to keep this file private.

    ```env
    # .env
    ZOHO_CLIENT_ID="your_client_id_from_zoho"
    ZOHO_CLIENT_SECRET="your_client_secret_from_zoho"
    ZOHO_REFRESH_TOKEN="your_refresh_token_from_zoho"
    ZOHO_API_BASE_URL="https://servicedeskplus.zoho.com" # Or your specific Zoho domain
    ```

## Running the API

*   **For development:**
    ```bash
    python zoho_ticket_api.py
    ```
    The API will be running at `http://127.0.0.1:5000`.

*   **For production:**
    Use a production-ready server like Gunicorn.
    ```bash
    gunicorn --bind 0.0.0.0:5000 "zoho_ticket_api:app"
    ```

## API Endpoints

### Health Check

Check if the service is running and the Zoho token is valid.

*   **Endpoint:** `GET /`
*   **Success Response (200 OK):**
    ```json
    {
        "service": "Zoho Ticket API",
        "status": "running",
        "token_valid": true
    }
    ```

### Create a Ticket

Creates a new ticket in Zoho.

*   **Endpoint:** `POST /requests`
*   **Request Body:**
    The `subject`, `description`, and `requester_email` fields are required. You can include any other standard Zoho fields like `urgency`, `category`, etc.

    ```json
    {
      "subject": "AI Hub Testing",
      "description": "Please cancel/resolve this ticket. This is only for testing purpose.",
      "requester_email": "nischay.thakur@continuserve.com",
      "template": {
        "name": "*Other / Misc. Issues"
      },
      "urgency": {
        "name": "U4 Low"
      },
      "category": {
        "name": "Other"
      },
      "subcategory": {
        "name": "Other"
      },
      "item": {
        "name": "Other"
      },
      "udf_fields": {
        "udf_char2": ["E mail", "Mobile Phone"]
      }
    }
    ```

*   **Success Response (201 Created):**
    ```json
    {
        "message": "Ticket created successfully",
        "zoho_ticket_id": "123456789012345678"
    }
    ```

### Get a Ticket

Fetches the details of a single ticket by its ID.

*   **Endpoint:** `GET /requests/<request_id>`
*   **Example:** `GET /requests/123456789012345678`
*   **Success Response (200 OK):**
    Returns the full ticket object directly from the Zoho API.
    ```json
    {
        "request": {
            "id": "123456789012345678",
            "subject": "Cannot access shared drive",
            "status": {
                "name": "Open",
                "id": "1"
            }
        }
    }
    ```