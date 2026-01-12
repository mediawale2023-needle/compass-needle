import os

def fix_script():
    file_name = "restore_belgaum.py"
    print(f"🔧 PATCHING {file_name}...")
    
    if not os.path.exists(file_name):
        print(f"❌ Error: {file_name} not found.")
        return

    with open(file_name, "r") as f:
        content = f.read()

    # 1. Fix the Column Name Error
    # We replace "password," with "password_hash," inside the SQL query logic
    new_content = content.replace(
        "INSERT INTO users (username, password, role", 
        "INSERT INTO users (username, password_hash, role"
    )

    # 2. Safety check: Ensure database URL is used
    if "os.getenv" not in new_content:
        new_content = "import os\n" + new_content

    if content == new_content:
        print("⚠️ No changes needed (or pattern not found).")
    else:
        with open(file_name, "w") as f:
            f.write(new_content)
        print("✅ SUCCESS: 'password' column fixed to 'password_hash'.")

if __name__ == "__main__":
    fix_script()