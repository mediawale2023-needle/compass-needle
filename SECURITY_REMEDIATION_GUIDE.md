# Security Remediation Guide

## Quick Start - Critical Fixes (Do These First)

### Step 1: Rotate All Credentials (IMMEDIATELY)

```bash
# 1. Generate new API keys from each service:
# - OpenAI: https://platform.openai.com/api-keys
# - Gemini: https://aistudio.google.com/app/apikey
# - Twilio: https://www.twilio.com/console/account/keys
# - Database: Create new user in Railway

# 2. Update .env with NEW credentials (never commit)
# 3. Delete old credentials from all services
# 4. Verify old keys are revoked
```

### Step 2: Remove Secrets from Git History

```bash
cd /Users/sanketjadhav/Desktop/compass-needle

# Install git-filter-repo
pip install git-filter-repo

# Remove .env from history
git filter-repo --invert-paths --path .env

# Remove hardcoded secrets from files
git filter-repo --invert-paths --path twilio_client.py
git filter-repo --invert-paths --path backups/modules/settings.py
git filter-repo --invert-paths --path check_models.py
git filter-repo --invert-paths --path restore_belgaum.py

# Force push (WARNING: This rewrites history)
git push origin --force-with-lease
```

### Step 3: Create `.env.example` (Safe Template)

```bash
# .env.example - DO NOT COMMIT REAL VALUES
OPENAI_API_KEY=your_key_here
DATABASE_URL=postgresql://user:password@host:port/db
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
GEMINI_API_KEY=your_key_here
JWT_SECRET=your_secret_here
```

### Step 4: Update `.gitignore`

```bash
# Add to .gitignore
.env
.env.local
.env.*.local
*.key
*.pem
secrets/
```

---

## Detailed Fixes by Severity

### 🔴 CRITICAL: SQL Injection Fixes

**File: `api_router.py`**

Replace this:
```python
# VULNERABLE
where = " AND ".join(conditions)
cases = _q(f"""
    SELECT c.id, c.user_phone, c.category, c.status, c.raw_message,
           c.case_metadata, c.is_critical, c.created_at, c.updated_at,
           c.response_to_citizen, c.notes_for_staff
    FROM cases c WHERE {where}
    ORDER BY c.created_at DESC
    LIMIT :lim OFFSET :off
""", {**params, "lim": limit, "off": offset})
```

With this:
```python
# SECURE - Use parameterized queries
def build_cases_query(tid, status=None, category=None, categories=None):
    query = text("""
        SELECT c.id, c.user_phone, c.category, c.status, c.raw_message,
               c.case_metadata, c.is_critical, c.created_at, c.updated_at,
               c.response_to_citizen, c.notes_for_staff
        FROM cases c 
        WHERE c.tenant_id = :tid
    """)
    params = {"tid": tid}
    
    if status:
        query = query.where(text("c.status = :status"))
        params["status"] = status
    
    if category:
        query = query.where(text("c.category = :category"))
        params["category"] = category
    
    if categories:
        placeholders = ", ".join(f":cat_{i}" for i in range(len(categories)))
        query = query.where(text(f"c.category IN ({placeholders})"))
        for i, cat in enumerate(categories):
            params[f"cat_{i}"] = cat
    
    query = query.order_by(text("c.created_at DESC"))
    return query, params
```

---

### 🔴 CRITICAL: Password Security Fixes

**File: `api_router.py`**

Replace this:
```python
# VULNERABLE
stored_hash = user.get("password_hash", "")
valid = False

try:
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        valid = bcrypt.checkpw(req.password.encode(), stored_hash.encode())
except Exception:
    pass

# Fallback: legacy plaintext
if not valid:
    valid = (stored_hash == req.password)  # PLAINTEXT COMPARISON!
```

With this:
```python
# SECURE
import bcrypt
from fastapi import HTTPException

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash. No plaintext fallback."""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

@router.post("/auth/login")
def login(req: LoginRequest):
    user = _q_one("SELECT * FROM users WHERE username = :u", {"u": req.username})
    if not user:
        raise HTTPException(401, "Invalid credentials")
    
    stored_hash = user.get("password_hash", "")
    if not stored_hash or not verify_password(req.password, stored_hash):
        raise HTTPException(401, "Invalid credentials")
    
    # ... rest of login logic
```

---

### 🔴 CRITICAL: JWT Security Fixes

**File: `api_router.py`**

Replace this:
```python
# VULNERABLE
JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("COOKIE_SECRET", "needle-dev-secret-change-me"))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72
```

With this:
```python
# SECURE
import secrets
from datetime import datetime, timedelta, timezone

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is required")

# Validate secret strength
if len(JWT_SECRET) < 32:
    raise ValueError("JWT_SECRET must be at least 32 characters")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 1  # Reduced from 72 hours
JWT_REFRESH_EXPIRE_DAYS = 7

# Token blacklist for logout
TOKEN_BLACKLIST = set()

def create_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create JWT token with expiration."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and validate user from JWT token."""
    token = credentials.credentials
    
    # Check if token is blacklisted (logged out)
    if token in TOKEN_BLACKLIST:
        raise HTTPException(401, "Token has been revoked")
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(401, "Invalid token")
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(401, "Token expired")
        
        user = _q_one("SELECT * FROM users WHERE username = :u", {"u": username})
        if not user:
            raise HTTPException(401, "User not found")
        return user
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

@router.post("/auth/logout")
def logout(user=Depends(get_current_user), credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout user by blacklisting token."""
    TOKEN_BLACKLIST.add(credentials.credentials)
    return {"success": True}
```

---

### 🔴 CRITICAL: CORS Security Fixes

**File: `main.py`**

Replace this:
```python
# VULNERABLE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

With this:
```python
# SECURE
import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not ALLOWED_ORIGINS or ALLOWED_ORIGINS == [""]:
    ALLOWED_ORIGINS = ["https://yourdomain.com"]

# Allow localhost only in development
if os.getenv("ENV") == "development":
    ALLOWED_ORIGINS.extend([
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)
```

---

### 🔴 CRITICAL: Admin Endpoint Security

**File: `main.py`**

Replace this:
```python
# VULNERABLE
@app.get("/seed-test-cases")
def seed_test_cases(key: str = "", tid: int = 0):
    if key != "needle-demo-2024":
        return {"error": "unauthorized"}
    # ... can seed arbitrary data
```

With this:
```python
# SECURE
@app.get("/seed-test-cases")
def seed_test_cases(user=Depends(get_current_user), tid: int = 0):
    # Verify user is admin
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    
    # Log admin action
    log_audit(user.get("username"), "SEED_TEST_CASES", "cases", "success")
    
    # ... rest of logic
```

---

### 🟠 HIGH: Input Validation

**File: `api_router.py`**

Add validation to all request models:

```python
from pydantic import BaseModel, validator, Field
import re

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('Invalid username format')
        return v

class AnalyseRequest(BaseModel):
    document_text: str = Field(..., max_length=1000000)
    filename: str = Field(default="document", max_length=255)
    language: str = Field(default="English")
    depth: str = Field(default="Quick Scan")
    
    @validator('document_text')
    def validate_document(cls, v):
        if not v.strip():
            raise ValueError('Document cannot be empty')
        return v.strip()
    
    @validator('filename')
    def validate_filename(cls, v):
        # Prevent path traversal
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid filename')
        return v
```

---

### 🟠 HIGH: Rate Limiting

**File: `api_router.py`**

```bash
pip install slowapi
```

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"}
    )

# Apply rate limits
@router.post("/auth/login")
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest):
    # ... login logic

@router.post("/copilot/chat")
@limiter.limit("30/minute")
def copilot_chat(request: Request, req: CopilotRequest, user=Depends(get_current_user)):
    # ... chat logic
```

---

### 🟠 HIGH: Audit Logging

**File: `db.py`**

Add audit log model:

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, index=True)  # LOGIN, CREATE_CASE, UPDATE_CASE, etc.
    resource_type = Column(String)  # cases, users, etc.
    resource_id = Column(Integer, nullable=True)
    status = Column(String)  # success, failure
    ip_address = Column(String)
    user_agent = Column(String)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
```

**File: `api_router.py`**

```python
from fastapi import Request

def log_audit(
    request: Request,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int = None,
    status: str = "success",
    details: dict = None
):
    """Log audit event to database."""
    try:
        with _engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO audit_logs 
                (user_id, action, resource_type, resource_id, status, ip_address, user_agent, details, created_at)
                VALUES (:uid, :action, :rtype, :rid, :status, :ip, :ua, :details, NOW())
            """), {
                "uid": user_id,
                "action": action,
                "rtype": resource_type,
                "rid": resource_id,
                "status": status,
                "ip": request.client.host,
                "ua": request.headers.get("user-agent", ""),
                "details": json.dumps(details) if details else None,
            })
    except Exception as e:
        logger.error(f"Audit log failed: {e}")

# Use in endpoints
@router.post("/auth/login")
def login(request: Request, req: LoginRequest):
    user = _q_one("SELECT * FROM users WHERE username = :u", {"u": req.username})
    
    if not user or not verify_password(req.password, user.get("password_hash", "")):
        log_audit(request, None, "LOGIN_FAILED", "users", None, "failure", {"username": req.username})
        raise HTTPException(401, "Invalid credentials")
    
    log_audit(request, user.get("id"), "LOGIN_SUCCESS", "users", user.get("id"), "success")
    # ... rest of login
```

---

### 🟠 HIGH: Secure File Upload

**File: `api_router.py`**

```python
import magic
import os

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MIME_TYPES = {"application/pdf"}
UPLOAD_DIR = "/tmp/uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/copilot/upload")
async def copilot_upload(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Upload and validate PDF file."""
    
    # Check filename
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")
    
    # Read file
    content = await file.read()
    
    # Check size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large (max 10MB)")
    
    # Validate PDF signature
    if not content.startswith(b"%PDF"):
        raise HTTPException(400, "Invalid PDF file")
    
    # Check MIME type
    mime = magic.from_buffer(content, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Invalid file type: {mime}")
    
    # Save to temporary location
    import uuid
    temp_filename = f"{uuid.uuid4()}.pdf"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)
    
    with open(temp_path, "wb") as f:
        f.write(content)
    
    try:
        import pymupdf
        doc = pymupdf.open(temp_path)
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append({"page": i + 1, "text": text})
        doc.close()
        
        return {"filename": file.filename, "pages": len(pages), "content": pages}
    finally:
        # Clean up temp file
        os.remove(temp_path)
```

---

### 🟠 HIGH: Security Headers

**File: `main.py`**

```python
from fastapi.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # HSTS
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # CSP
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

### 🟡 MEDIUM: CSRF Protection

```bash
pip install fastapi-csrf-protect
```

**File: `api_router.py`**

```python
from fastapi_csrf_protect import CsrfProtect
from pydantic import BaseModel

class CsrfSettings(BaseModel):
    secret_key: str = os.getenv("JWT_SECRET")

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()

@router.post("/auth/login")
async def login(request: Request, req: LoginRequest, csrf_protect: CsrfProtect = Depends()):
    await csrf_protect.validate_csrf(request)
    # ... login logic
```

---

## Environment Variables Template

Create `.env` (never commit):

```bash
# Security
ENV=production
JWT_SECRET=<generate-with-secrets.token_urlsafe(32)>
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@host:port/db

# API Keys
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...

# Logging
LOG_LEVEL=INFO
SENTRY_DSN=https://...

# Features
ENABLE_DEBUG=false
```

---

## Testing Security Fixes

```bash
# 1. Install security testing tools
pip install bandit safety pip-audit

# 2. Run static analysis
bandit -r . -ll

# 3. Check dependencies
safety check
pip-audit

# 4. Test SQL injection
pytest tests/test_sql_injection.py

# 5. Test authentication
pytest tests/test_auth.py

# 6. Test rate limiting
pytest tests/test_rate_limiting.py
```

---

## Deployment Checklist

- [ ] All credentials rotated
- [ ] Secrets removed from git history
- [ ] `.env` file added to `.gitignore`
- [ ] SQL injection vulnerabilities fixed
- [ ] Password hashing implemented
- [ ] JWT security improved
- [ ] CORS properly configured
- [ ] Admin endpoints secured
- [ ] Input validation added
- [ ] Rate limiting implemented
- [ ] Audit logging added
- [ ] Security headers added
- [ ] HTTPS enforced
- [ ] Database connection pooling configured
- [ ] Error handling improved
- [ ] Dependencies scanned for vulnerabilities
- [ ] Security tests passing
- [ ] Code review completed
- [ ] Penetration testing scheduled

---

## Ongoing Security Practices

1. **Regular Updates:** Update dependencies monthly
2. **Monitoring:** Set up alerts for suspicious activity
3. **Backups:** Daily encrypted backups
4. **Incident Response:** Have a plan for security incidents
5. **Training:** Security training for all developers
6. **Code Review:** Mandatory security review for all PRs
7. **Penetration Testing:** Annual professional testing
8. **Compliance:** Regular compliance audits

