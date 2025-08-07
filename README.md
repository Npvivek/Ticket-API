# Zoho Ticket API

A simple API gateway to create and view tickets in Zoho ServiceDesk. This service handles Zoho's OAuth 2.0 authentication, providing a clean, stable interface for your applications.

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
    ZOHO_API_BASE_URL="[https://support.quatrrobss.com](https://support.quatrrobss.com)"
    ```

## Running the API

* **For development:**
    ```bash
    python zoho_ticket_api.py
    ```
    The API will be running at `http://127.0.0.1:5000`.

* **For production:**
    Use a production-ready WSGI server like Gunicorn.
    ```bash
    gunicorn --workers 4 --bind 0.0.0.0:5000 zoho_ticket_api:app
    ```

## API Endpoints

### Health Check

Check if the service is running and the Zoho token is valid.

* **Endpoint:** `GET /`
* **Success Response (200 OK):**
    ```json
    {
        "status": "running",
        "service": "Zoho Ticket API",
        "token_valid": true
    }
    ```

### Create a Ticket

Creates a new ticket in Zoho.

* **Endpoint:** `POST /create_ticket`
* **Request Body:**
    The API requires `subject`, `description`, and `requester_email`. You must also include any other fields that are mandatory for your specific Zoho `template`.

    ```json
    {
      "subject": "AI Hub Testing",
      "description": "Please cancel/resolve this ticket. This is only for testing purpose.",
      "requester_email": "vivek.nakka@continuserve.com",
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

* **Success Response (201 Created):**
    ```json
    {
        "message": "Ticket created successfully",
        "zoho_ticket_id": "131260000176191749"
    }
    ```

### Get a Ticket

Fetches a simplified summary of a single ticket by its ID.

* **Endpoint:** `GET /requests/<request_id>`
* **Example:** `GET /requests/131260000176191749`
* **Success Response (200 OK):**
    Returns a clean summary of the ticket as defined in the code's parsing logic.
    ```json
    {
        "ticket_id": "131260000176191749",
        "status": "Open",
        "technician_assigned": "Unassigned",
        "technician_contact_email": null,
        "technician_comments": null
    }
    ```