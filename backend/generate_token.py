import os
from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("KITE_API_KEY")
api_secret = os.getenv("KITE_API_SECRET")

kite = KiteConnect(api_key=api_key)

# Step 1 — print login URL
print("=" * 60)
print("STEP 1 — Open this URL in your browser and log in:")
print("=" * 60)
print(kite.login_url())
print("=" * 60)
print()

# Step 2 — paste request token
request_token = input("STEP 2 — Paste the request_token from the redirected URL: ").strip()

# Step 3 — generate access token
session = kite.generate_session(request_token, api_secret=api_secret)
access_token = session["access_token"]

print()
print("=" * 60)
print("SUCCESS! Your access token:")
print(access_token)
print("=" * 60)
print()
print(f"KITE_ACCESS_TOKEN={access_token}")