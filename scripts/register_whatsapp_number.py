#!/usr/bin/env python3
"""
Register a pending WhatsApp Cloud API phone number.

Usage:
    python scripts/register_whatsapp_number.py

The script reads META_ACCESS_TOKEN and the phone number ID from env,
calls POST /{phone_number_id}/register, and prints the full response.

Meta docs:
  https://developers.facebook.com/docs/whatsapp/cloud-api/reference/registration
"""

import os
import sys
import json
import requests

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

def check_phone_status(phone_number_id: str, token: str) -> dict:
    resp = requests.get(
        f"{GRAPH_BASE}/{phone_number_id}",
        params={
            "fields": "display_phone_number,verified_name,code_verification_status,quality_rating,platform_type,throughput,id",
            "access_token": token,
        },
        timeout=10,
    )
    return resp.status_code, resp.json()

def register_phone(phone_number_id: str, token: str, pin: str) -> tuple:
    resp = requests.post(
        f"{GRAPH_BASE}/{phone_number_id}/register",
        headers={"Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "pin": pin,
        },
        params={"access_token": token},
        timeout=15,
    )
    return resp.status_code, resp.json()

def check_token_permissions(token: str) -> tuple:
    resp = requests.get(
        f"{GRAPH_BASE}/me/permissions",
        params={"access_token": token},
        timeout=10,
    )
    return resp.status_code, resp.json()

def main():
    token = os.getenv("META_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID")

    if not token:
        print("ERROR: META_ACCESS_TOKEN not set in environment")
        sys.exit(1)
    if not phone_number_id:
        print("ERROR: WHATSAPP_PHONE_NUMBER_ID not set in environment")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Phone Number ID : {phone_number_id}")
    print(f"Token (first 20): {token[:20]}...")
    print(f"{'='*60}\n")

    # Step 1: Check token permissions
    print("[1/3] Checking token permissions...")
    status, data = check_token_permissions(token)
    if status == 200:
        perms = [p["permission"] for p in data.get("data", []) if p.get("status") == "granted"]
        print(f"  Granted permissions: {', '.join(perms)}")
        critical = {"whatsapp_business_messaging", "whatsapp_business_management"}
        missing = critical - set(perms)
        if missing:
            print(f"  WARNING: Missing critical permissions: {missing}")
            print("  -> This token may not be able to register the phone number.")
            print("     You need a System User token from your Tech Provider Business Manager.")
        else:
            print("  OK — all critical permissions present")
    else:
        print(f"  Could not check permissions: {status} {data}")

    # Step 2: Check current phone number status
    print("\n[2/3] Checking phone number status...")
    status, data = check_phone_status(phone_number_id, token)
    if status == 200:
        print(f"  Display number      : {data.get('display_phone_number', 'N/A')}")
        print(f"  Verified name       : {data.get('verified_name', 'N/A')}")
        print(f"  Code verify status  : {data.get('code_verification_status', 'N/A')}")
        print(f"  Quality rating      : {data.get('quality_rating', 'N/A')}")
        print(f"  Platform type       : {data.get('platform_type', 'N/A')}")
        code_status = data.get("code_verification_status", "").upper()
        if code_status == "VERIFIED":
            print("  -> Phone number OTP is VERIFIED. Attempting registration...")
        elif code_status == "NOT_VERIFIED":
            print("  -> OTP not yet verified. You must request OTP first:")
            print("     POST /{phone_id}/request_code {code_method: SMS, language: en}")
            print("     Then POST /{phone_id}/verify_code {code: '123456'}")
        else:
            print(f"  -> Unknown status '{code_status}'. Will attempt registration anyway.")
    else:
        print(f"  ERROR: {status}")
        print(f"  Response: {json.dumps(data, indent=2)}")
        if data.get("error", {}).get("code") == 190:
            print("\n  Token is EXPIRED or INVALID. Generate a new System User token:")
            print("  business.facebook.com → Settings → System Users → Generate Token")
        sys.exit(1)

    # Step 3: Attempt registration
    print("\n[3/3] Registering phone number...")
    # Pin is the 2-step verification PIN set on the number (default 000000 if never set)
    pin = os.getenv("WHATSAPP_TWO_STEP_PIN", "000000")
    print(f"  Using 2-step PIN: {pin} (set WHATSAPP_TWO_STEP_PIN env var to override)")
    status, data = register_phone(phone_number_id, token, pin)
    print(f"  HTTP status: {status}")
    print(f"  Response   : {json.dumps(data, indent=2)}")

    if status == 200 and data.get("success"):
        print("\n  SUCCESS: Phone number registered! Messages should start flowing.")
        print("  Verify in WhatsApp Manager — status should change from Pending to Active.")
    else:
        err = data.get("error", {})
        code = err.get("code")
        msg = err.get("message", "")
        sub = err.get("error_subcode")
        print(f"\n  FAILED — Error {code} (subcode {sub}): {msg}")

        if code == 100 and "nonexisting field" in msg:
            print("\n  DIAGNOSIS: The token doesn't have permission to call the register endpoint.")
            print("  This typically means:")
            print("  (a) You're using the client business manager token, not the tech provider token.")
            print("  (b) The System User token lacks 'whatsapp_business_management' permission.")
            print("\n  FIX:")
            print("  1. Go to your META DEVELOPER APP's Business Settings")
            print("  2. System Users → your system user → Generate New Token")
            print("  3. Select permissions: whatsapp_business_messaging + whatsapp_business_management")
            print("  4. Update META_ACCESS_TOKEN in your Railway env vars")
            print("  5. Re-run this script")
        elif code == 190:
            print("\n  DIAGNOSIS: Token expired.")
            print("  Generate a permanent System User token (not a page/user token).")
        elif code == 200:
            print("\n  DIAGNOSIS: Permissions error.")
            print("  The WABA may not be connected to your app. Ensure embedded signup is complete.")
        else:
            print("\n  See: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/registration")

    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
