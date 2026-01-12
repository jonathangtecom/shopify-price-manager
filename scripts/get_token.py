#!/usr/bin/env python3
"""
Shopify OAuth Helper - Get Admin API Access Token

This script helps you get an access token for your Shopify app.
"""
import asyncio
import httpx
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
import threading

# =========================================
# FILL IN YOUR APP CREDENTIALS HERE
# =========================================
CLIENT_ID = "your_client_id_here"  # Found in Dev Dashboard -> App -> Settings (also called API Key)
CLIENT_SECRET = "your_client_secret_here"  # Your client secret
SHOP_DOMAIN = "your-store.myshopify.com"  # Your store domain
SCOPES = "read_orders,read_products,write_products"  # Required scopes
REDIRECT_URI = "http://localhost:3456/callback"  # Local redirect URI
# =========================================

authorization_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global authorization_code
        
        if self.path.startswith('/callback'):
            # Parse the query string
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            if 'code' in params:
                authorization_code = params['code'][0]
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'''
                    <html>
                    <head><title>Success!</title></head>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1 style="color: green;">Authorization Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </body>
                    </html>
                ''')
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                error = params.get('error', ['Unknown error'])[0]
                self.wfile.write(f'<h1>Error: {error}</h1>'.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging


async def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for access token"""
    url = f"https://{SHOP_DOMAIN}/admin/oauth/access_token"
    
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
        )
        return response.json()


def main():
    global authorization_code
    
    print("\n" + "="*60)
    print("  Shopify OAuth - Get Admin API Access Token")
    print("="*60)
    
    if CLIENT_ID == "YOUR_CLIENT_ID_HERE":
        print("\n❌ ERROR: You need to set your CLIENT_ID in this script!")
        print("\nFind your Client ID (API Key) in:")
        print("  Dev Dashboard → Your App → Settings → Client credentials")
        print("\nIt looks like: a1b2c3d4e5f6g7h8")
        return
    
    # Build OAuth URL
    oauth_url = (
        f"https://{SHOP_DOMAIN}/admin/oauth/authorize?"
        f"client_id={CLIENT_ID}&"
        f"scope={SCOPES}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"state=nonce123"
    )
    
    print(f"\nShop: {SHOP_DOMAIN}")
    print(f"Scopes: {SCOPES}")
    print(f"\nStarting local server for OAuth callback...")
    
    # Start local server
    server = HTTPServer(('localhost', 3456), OAuthHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()
    
    print("\n" + "-"*60)
    print("Opening browser for authorization...")
    print("-"*60)
    print(f"\nIf browser doesn't open, go to this URL manually:\n")
    print(oauth_url)
    print()
    
    # Open browser
    webbrowser.open(oauth_url)
    
    # Wait for callback
    print("Waiting for authorization...")
    server_thread.join(timeout=120)
    server.server_close()
    
    if authorization_code:
        print(f"\n✅ Got authorization code!")
        print("\nExchanging code for access token...")
        
        result = asyncio.run(exchange_code_for_token(authorization_code))
        
        print("\n" + "="*60)
        print("  RESULT")
        print("="*60)
        
        if "access_token" in result:
            access_token = result["access_token"]
            print(f"\n✅ SUCCESS! Your Admin API Access Token:\n")
            print(f"   {access_token}")
            print(f"\nScopes granted: {result.get('scope', 'N/A')}")
            print("\n" + "-"*60)
            print("Save this token! You'll use it to connect your Shopify store.")
            print("-"*60 + "\n")
        else:
            print(f"\n❌ ERROR: {result}")
    else:
        print("\n❌ Timeout: No authorization code received.")
        print("Make sure to click 'Install app' in the browser.")


if __name__ == "__main__":
    main()
