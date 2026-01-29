import sqlite3
import pandas as pd

def test_login():
    print("--- 🔐 LOGIN DEBUGGER ---")
    u_input = input("Type Username exactly as you do on the screen: ")
    p_input = input("Type Password exactly as you do on the screen: ")

    conn = sqlite3.connect("sansadx.db")
    cursor = conn.cursor()

    # 1. Search for EXACT match (What the dashboard does)
    query = "SELECT * FROM users WHERE username = ? AND password_hash = ?"
    cursor.execute(query, (u_input, p_input))
    result = cursor.fetchone()

    if result:
        print("\n✅ SUCCESS! The dashboard SHOULD let you in.")
        print(f"   User Found: {result[2]} (Role: {result[4]})")
    else:
        print("\n❌ LOGIN FAILED.")
        
        # 2. Detective Work: Why did it fail?
        # Check Username case-insensitive
        cursor.execute("SELECT username, password_hash FROM users WHERE username = ? COLLATE NOCASE", (u_input,))
        user_found = cursor.fetchone()

        if user_found:
            real_user, real_pass = user_found
            print(f"   ⚠️  MATCH FOUND but details are wrong.")
            
            if real_user != u_input:
                print(f"   👉 CASE SENSITIVITY ISSUE!")
                print(f"      You typed:   '{u_input}'")
                print(f"      Database has: '{real_user}'")
                print("      -> Try typing it exactly as stored.")
            
            if real_pass != p_input:
                print(f"   👉 PASSWORD MISMATCH!")
                print(f"      You typed:   '{p_input}'")
                print(f"      Database has: '{real_pass}'")
                print("      -> Check for spaces or typos.")
        else:
            print("   ❌ User does not exist at all.")

    conn.close()

if __name__ == "__main__":
    test_login()