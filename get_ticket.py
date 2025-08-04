import requests


API_BASE_URL = "https://support.quatrrobss.com/app/itdesk"
ACCESS_TOKEN = "1000.d095719cbe4e09bbfee57ace343c58dd.337900238e48e2a9da25a1c27971f306"   
REQUEST_ID = "131260000174674420"      


url = f"{API_BASE_URL}/api/v3/requests/{REQUEST_ID}"

headers = {
    "Authorization": f"Zoho-oauthtoken {ACCESS_TOKEN}",
    "Accept": "application/vnd.manageengine.sdp.v3+json"
}

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}\n")
    if response.ok:
        # Pretty print JSON response
        import json
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print("Error response body:\n", response.text)
except Exception as e:
    print(f"Exception occurred: {e}")
