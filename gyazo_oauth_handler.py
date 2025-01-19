import os
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import requests
from qgis.PyQt.QtCore import QCoreApplication

class GyazoOAuthHandler:
    def __init__(self, client_id, client_secret, redirect_uri, scope):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.token_url = "https://gyazo.com/oauth/token"
        self.auth_url = "https://gyazo.com/oauth/authorize"

    def start_auth_flow(self):
        # Step 1: Open the browser for user login and authorization
        auth_request_url = (
            f"{self.auth_url}?"
            f"client_id={self.client_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"response_type=code&"
            f"scope={self.scope}"
        )
        webbrowser.open(auth_request_url)

        # Step 2: Start a local HTTP server to receive the callback
        server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
        print("Waiting for authorization response...")
        server.handle_request()  # Blocks until the callback is received

        # Step 3: Extract the authorization code
        auth_code = OAuthCallbackHandler.auth_code
        if not auth_code:
            raise Exception("Authorization failed. No code received.")

        # Step 4: Exchange authorization code for access token
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }
        response = requests.post(self.token_url, data=data)
        response_data = response.json()

        if "access_token" in response_data:
            print("Access token obtained successfully!")
            return response_data["access_token"]
        else:
            raise Exception(f"Failed to obtain access token: {response_data}")

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        # Parse the URL to extract the authorization code
        query = urlparse(self.path).query
        params = parse_qs(query)
        OAuthCallbackHandler.auth_code = params.get("code", [None])[0]

        # Respond to the browser
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Authorization Successful!</h1></body></html>")

        # Stop the server after handling the request
        raise KeyboardInterrupt  # To break the HTTPServer's event loop

# Example usage in a QGIS plugin
class GyazoUploader:
    def __init__(self):
        self.client_id = "YOUR_CLIENT_ID"
        self.client_secret = "YOUR_CLIENT_SECRET"
        self.redirect_uri = "http://localhost:8080"
        self.scope = "upload"

    def run(self):
        # Run the OAuth authentication flow
        handler = OAuthHandler(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope
        )
        try:
            access_token = handler.start_auth_flow()
            print(f"Access Token: {access_token}")
            # Save the access token securely and use it for future API requests
        except Exception as e:
            print(f"Error during OAuth flow: {e}")
