# Personal Finance Application Backend
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Depends, Cookie, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from etl_pipeline import TransactionETL
from finance_service import FinanceService

# Initialize FastAPI App
app = FastAPI(title="Personal Finance API", version="1.0.0")

DB_PATH = "personal_finance.db"
SCHEMA_PATH = "schema.sql"

# Password Hashing Helpers
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + pwd_hash.hex()

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return pwd_hash.hex() == hash_hex
    except Exception:
        return False

# Pydantic schemas for request validation
class UserAuthSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4)

class DebtAccountSchema(BaseModel):
    account_name: str
    institution: str
    debt_type: str
    total_credit_line: Optional[float] = None
    current_balance: float = 0.0
    monthly_payment: float = 0.0
    interest_rate: Optional[float] = None
    remaining_payments: Optional[int] = None
    original_amount: Optional[float] = None
    loan_length_months: Optional[int] = None
    lender_type: str = "N/A"

class SavingsAccountSchema(BaseModel):
    account_name: str
    account_type: str
    monthly_contribution: float = 0.0
    current_balance: float = 0.0
    annual_yield: float = 0.0

class IncomeSourceSchema(BaseModel):
    source_name: str
    recipient: str
    amount: float
    frequency: str

class FixedSpendingSchema(BaseModel):
    category: str
    subcategory: str
    monthly_amount: float
    linked_debt_id: Optional[int] = None
    actual_spent: float = 0.0

class DiscretionarySpendingSchema(BaseModel):
    category: str
    subcategory: str
    monthly_amount: float
    actual_spent: float = 0.0

class TransactionSchema(BaseModel):
    transaction_date: str
    description: str
    amount: float
    category: str = 'Uncategorized'
    account_id: Optional[int] = None

class RolloverRequestSchema(BaseModel):
    month: str
    savings_account_id: int
    amount: float

# Helper to get DB connection
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Ensure tables exist
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if not cursor.fetchone():
            with open(SCHEMA_PATH, "r") as f:
                conn.executescript(f.read())
        else:
            # Table already exists, make sure actual_spent column is present for migrations
            cursor.execute("PRAGMA table_info(fixed_spending)")
            columns = [row[1] for row in cursor.fetchall()]
            if columns and 'actual_spent' not in columns:
                cursor.execute("ALTER TABLE fixed_spending ADD COLUMN actual_spent REAL NOT NULL DEFAULT 0.0")
                conn.commit()
            
            cursor.execute("PRAGMA table_info(discretionary_spending)")
            columns = [row[1] for row in cursor.fetchall()]
            if columns and 'actual_spent' not in columns:
                cursor.execute("ALTER TABLE discretionary_spending ADD COLUMN actual_spent REAL NOT NULL DEFAULT 0.0")
                conn.commit()
    except Exception as e:
        print(f"Error ensuring database schema: {e}")
        
    return conn

# Database setup on startup
@app.on_event("startup")
def startup_event():
    with get_db() as conn:
        print("Database schema verified on startup.")

# Authentication Dependency
def get_current_user(session_token: Optional[str] = Cookie(None)):
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.user_id, u.username, s.expires_at 
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_id = ?
        """, (session_token,))
        row = cursor.fetchone()
        
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or invalid"
        )
    
    # Check expiry
    try:
        expires_at = datetime.fromisoformat(row['expires_at'])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session expiry format"
        )
        
    if datetime.utcnow() > expires_at:
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_token,))
            conn.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )
        
    return {"id": row['user_id'], "username": row['username']}

# Mock data seeding per user
def seed_user_mock_data(conn, user_id: int):
    cursor = conn.cursor()
    # 1. Debt Tracker Module
    cursor.executemany("""
        INSERT INTO debt_accounts 
        (user_id, account_name, institution, debt_type, total_credit_line, current_balance, monthly_payment, interest_rate, remaining_payments, original_amount, loan_length_months, lender_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (user_id, 'Capital One Quicksilver', 'Capital One', 'Credit Card', 5000.0, 1200.0, 35.0, 22.99, None, None, None, 'N/A'),
        (user_id, 'Affirm MacBook Pro', 'Affirm', 'BNPL', None, 480.0, 120.0, 0.0, 4, 1200.0, 10, 'N/A'),
        (user_id, 'Chase Auto Loan', 'Chase Bank', 'Car Loan', None, 18500.0, 350.0, 4.5, 24, 25000.0, 72, 'N/A'),
        (user_id, 'Family Loan', 'Uncle Robert', 'Personal Loan', None, 4000.0, 200.0, 2.0, 20, 10000.0, 50, 'Family'),
        (user_id, 'Wells Fargo Mortgage', 'Wells Fargo', 'Mortgage', None, 285000.0, 1800.0, 4.25, 300, 320000.0, 360, 'Institution')
    ])
    
    # Get mortgage ID to cross-link
    cursor.execute("SELECT id FROM debt_accounts WHERE user_id = ? AND account_name = 'Wells Fargo Mortgage'", (user_id,))
    mortgage_id = cursor.fetchone()[0]

    # 2. Fixed Spending Module
    cursor.executemany("""
        INSERT INTO fixed_spending (user_id, category, subcategory, monthly_amount, linked_debt_id)
        VALUES (?, ?, ?, ?, ?)
    """, [
        (user_id, 'Housing', 'Mortgage Payment', 1800.0, mortgage_id),
        (user_id, 'Connectivity', 'Cell Phone Plan', 80.0, None),
        (user_id, 'Connectivity', 'Home Wi-Fi', 60.0, None),
        (user_id, 'Utilities', 'Electricity', 120.0, None),
        (user_id, 'Utilities', 'Water', 50.0, None),
        (user_id, 'Utilities', 'Gas', 40.0, None),
        (user_id, 'Insurances', 'Health Insurance', 300.0, None),
        (user_id, 'Insurances', 'Auto Insurance', 150.0, None),
        (user_id, 'Insurances', 'Homeowners Insurance', 40.0, None),
        (user_id, 'Groceries', 'Estimated Grocery Budget', 600.0, None)
    ])
    
    # 3. Discretionary Spending Module
    cursor.executemany("""
        INSERT INTO discretionary_spending (user_id, category, subcategory, monthly_amount)
        VALUES (?, ?, ?, ?)
    """, [
        (user_id, 'Family Overseas', 'Remittance Stipend', 300.0),
        (user_id, 'Dining', 'Restaurants and Bars', 400.0),
        (user_id, 'Shopping', 'Retail and Clothing', 250.0),
        (user_id, 'Subscriptions', 'Netflix & Spotify', 25.0),
        (user_id, 'Subscriptions', 'Gym Membership', 50.0)
    ])
    
    # 4. Savings & Investment Module
    cursor.executemany("""
        INSERT INTO savings_accounts (user_id, account_name, account_type, monthly_contribution, current_balance, annual_yield)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (user_id, 'Vanguard Roth IRA', 'Roth IRA', 500.0, 24000.0, 7.5),
        (user_id, 'Standard Savings Account', 'Standard Savings', 300.0, 12000.0, 4.25)
    ])
    
    # 5. Income Module
    cursor.executemany("""
        INSERT INTO income_sources (user_id, source_name, recipient, amount, frequency)
        VALUES (?, ?, ?, ?, ?)
    """, [
        (user_id, 'Primary Salary', 'Self', 4200.0, 'bi-weekly'),
        (user_id, 'Wife Salary', 'Partner', 3500.0, 'monthly'),
        (user_id, 'Dividends and Side Hustle', 'Joint', 400.0, 'monthly')
    ])
    
    # Seed a few transaction logs as well
    cursor.executemany("""
        INSERT INTO transactions (user_id, transaction_date, description, amount, category, tx_hash, source_file)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (user_id, '2026-06-15', 'Netflix Subscription', -15.99, 'Subscriptions', 'seed_h1_' + str(user_id), 'system_seed'),
        (user_id, '2026-06-18', 'Trader Joes Supermarket', -142.50, 'Groceries', 'seed_h2_' + str(user_id), 'system_seed'),
        (user_id, '2026-06-20', 'Starbucks Coffee', -6.50, 'Dining', 'seed_h3_' + str(user_id), 'system_seed'),
        (user_id, '2026-06-21', 'Chevron Gas Station', -45.00, 'Connectivity', 'seed_h4_' + str(user_id), 'system_seed'),
        (user_id, '2026-06-22', 'Amazon.com Retail', -89.99, 'Shopping', 'seed_h5_' + str(user_id), 'system_seed')
    ])


# ----------------- AUTH ENDPOINTS -----------------

@app.post("/api/auth/register")
def register(user_data: UserAuthSchema):
    username = user_data.username.strip()
    password = user_data.password
    
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
            
        pwd_hash = hash_password(password)
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, pwd_hash))
            user_id = cursor.lastrowid
            
            # Seed default mock data for new user
            seed_user_mock_data(conn, user_id)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
            
    return {"message": "User registered successfully. You can now log in."}

@app.post("/api/auth/login")
def login(user_data: UserAuthSchema, response: Response):
    username = user_data.username.strip()
    password = user_data.password
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        
    if not row or not verify_password(password, row['password_hash']):
        raise HTTPException(status_code=400, detail="Invalid username or password")
        
    user_id = row['id']
    session_id = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    with get_db() as conn:
        conn.execute("INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
                     (session_id, user_id, expires_at.isoformat()))
        conn.commit()
        
    response.set_cookie(
        key="session_token",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/"
    )
    return {"message": "Logged in successfully", "username": username}

@app.post("/api/auth/logout")
def logout(response: Response, session_token: Optional[str] = Cookie(None)):
    if session_token:
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_token,))
            conn.commit()
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


# ----------------- FINANCIAL API ENDPOINTS -----------------

# Dashboard Aggregation API
@app.get("/api/dashboard")
def get_dashboard_summary(month: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        service = FinanceService(DB_PATH, user_id)
        cash_flow = service.calculate_unified_cash_flow()
        net_worth = service.get_net_worth()
        
        # Get details for individual components
        with get_db() as conn:
            debts_rows = conn.execute("""
                SELECT d.*, 
                       COALESCE((SELECT SUM(t.amount) 
                                 FROM transactions t 
                                 WHERE t.account_id = d.id AND t.amount > 0 AND t.user_id = ?
                                 AND (? IS NULL OR SUBSTR(t.transaction_date, 1, 7) = ?)), 0.0) as actual_payment
                FROM debt_accounts d
                WHERE d.user_id = ?
            """, (user_id, month, month, user_id)).fetchall()
            debts = [dict(row) for row in debts_rows]
            
            savings_rows = conn.execute("""
                SELECT s.*,
                       COALESCE((SELECT SUM(t.amount)
                                 FROM transactions t
                                 WHERE t.description LIKE '%' || s.account_name || '%' AND t.amount > 0 AND t.user_id = ?
                                 AND (? IS NULL OR SUBSTR(t.transaction_date, 1, 7) = ?)), 0.0) as actual_contribution
                FROM savings_accounts s
                WHERE s.user_id = ?
            """, (user_id, month, month, user_id)).fetchall()
            savings = [dict(row) for row in savings_rows]
            
            income = [dict(row) for row in conn.execute("SELECT * FROM income_sources WHERE user_id = ?", (user_id,)).fetchall()]
            
            # Calculate dynamic actuals per fixed spending item if month is provided
            fixed = []
            for row in conn.execute("SELECT * FROM fixed_spending WHERE user_id = ?", (user_id,)).fetchall():
                item = dict(row)
                if month:
                    sub_total = conn.execute("""
                        SELECT SUM(ABS(amount)) 
                        FROM transactions 
                        WHERE user_id = ? 
                        AND category = ? 
                        AND SUBSTR(transaction_date, 1, 7) = ? 
                        AND (description LIKE '%' || ? || '%' OR ? LIKE '%' || description || '%')
                    """, (user_id, item['category'], month, item['subcategory'], item['subcategory'])).fetchone()[0]
                    
                    if sub_total is None:
                        sibling_count = conn.execute("SELECT COUNT(*) FROM fixed_spending WHERE user_id = ? AND category = ?", (user_id, item['category'])).fetchone()[0]
                        if sibling_count == 1:
                            cat_total = conn.execute("""
                                SELECT SUM(ABS(amount)) 
                                FROM transactions 
                                WHERE user_id = ? 
                                AND category = ? 
                                AND SUBSTR(transaction_date, 1, 7) = ?
                            """, (user_id, item['category'], month)).fetchone()[0]
                            sub_total = cat_total or 0.0
                        else:
                            sub_total = 0.0
                    item['actual_spent'] = round(sub_total, 2)
                fixed.append(item)
                
            disc = []
            for row in conn.execute("SELECT * FROM discretionary_spending WHERE user_id = ?", (user_id,)).fetchall():
                item = dict(row)
                if month:
                    sub_total = conn.execute("""
                        SELECT SUM(ABS(amount)) 
                        FROM transactions 
                        WHERE user_id = ? 
                        AND category = ? 
                        AND SUBSTR(transaction_date, 1, 7) = ? 
                        AND (description LIKE '%' || ? || '%' OR ? LIKE '%' || description || '%')
                    """, (user_id, item['category'], month, item['subcategory'], item['subcategory'])).fetchone()[0]
                    
                    if sub_total is None:
                        sibling_count = conn.execute("SELECT COUNT(*) FROM discretionary_spending WHERE user_id = ? AND category = ?", (user_id, item['category'])).fetchone()[0]
                        if sibling_count == 1:
                            cat_total = conn.execute("""
                                SELECT SUM(ABS(amount)) 
                                FROM transactions 
                                WHERE user_id = ? 
                                AND category = ? 
                                AND SUBSTR(transaction_date, 1, 7) = ?
                            """, (user_id, item['category'], month)).fetchone()[0]
                            sub_total = cat_total or 0.0
                        else:
                            sub_total = 0.0
                    item['actual_spent'] = round(sub_total, 2)
                disc.append(item)
            
        return {
            "summary": {
                "net_worth": net_worth,
                "total_income": cash_flow["total_income"],
                "fixed_spending": cash_flow["fixed_spending"],
                "discretionary_spending": cash_flow["discretionary_spending"],
                "debt_obligations": cash_flow["debt_obligations"],
                "savings_contributions": cash_flow["savings_contributions"],
                "net_remaining_cash_flow": cash_flow["net_remaining_cash_flow"]
            },
            "actuals": service.get_actuals(month),
            "debts": debts,
            "savings": savings,
            "income": income,
            "fixed_spending_items": fixed,
            "discretionary_spending_items": disc
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/months")
def get_available_months(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT DISTINCT SUBSTR(transaction_date, 1, 7) as month_val
                FROM transactions
                WHERE user_id = ? AND transaction_date LIKE '____-__-__'
                ORDER BY month_val DESC
            """, (user_id,)).fetchall()
            months = [row['month_val'] for row in rows]
            
            # Ensure the current month is in the list
            current_month = datetime.utcnow().strftime("%Y-%m")
            if current_month not in months:
                months.append(current_month)
                months.sort(reverse=True)
                
            return months
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/months/process")
def process_month_rollover(request: RolloverRequestSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        import calendar
        with get_db() as conn:
            cursor = conn.cursor()
            # Verify savings account
            cursor.execute("SELECT account_name FROM savings_accounts WHERE id = ? AND user_id = ?", 
                           (request.savings_account_id, user_id))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Savings account not found.")
            account_name = row['account_name']
            
            # Determine date of transaction (last day of month)
            try:
                year, month_num = map(int, request.month.split("-"))
                last_day = calendar.monthrange(year, month_num)[1]
                tx_date = f"{request.month}-{last_day:02d}"
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
                
            # Create rollover transaction
            desc = f"Rollover Surplus Deposit to {account_name}"
            # Unique hash input
            import time
            hash_input = f"{tx_date}_{desc}_{request.amount}_{time.time()}_{user_id}"
            tx_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
            
            cursor.execute("""
                INSERT INTO transactions (user_id, transaction_date, description, amount, category, source_file, tx_hash)
                VALUES (?, ?, ?, ?, 'Savings', 'Month Rollover', ?)
            """, (user_id, tx_date, desc, request.amount, tx_hash))
            
            # Update savings account balance
            cursor.execute("""
                UPDATE savings_accounts 
                SET current_balance = current_balance + ? 
                WHERE id = ? AND user_id = ?
            """, (request.amount, request.savings_account_id, user_id))
            
            conn.commit()
            return {"message": f"Successfully rolled over ${request.amount:.2f} surplus to {account_name}."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports/historical")
def get_historical_reports(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        service = FinanceService(DB_PATH, user_id)
        
        # Simple math to get last 6 months
        months = []
        now = datetime.utcnow()
        for i in range(5, -1, -1):
            y = now.year
            m = now.month - i
            while m <= 0:
                m += 12
                y -= 1
            months.append(f"{y:04d}-{m:02d}")
            
        reports = []
        for m in months:
            actuals = service.get_actuals(month=m)
            reports.append({
                "month": m,
                "income": actuals["income"],
                "spending": actuals["fixed"] + actuals["discretionary"],
                "savings": actuals["savings"],
                "debt_payments": actuals["debt_payments"],
                "net_cash_flow": round(actuals["income"] - (actuals["fixed"] + actuals["discretionary"] + actuals["savings"] + actuals["debt_payments"]), 2)
            })
            
        return reports
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Growth Projection API
@app.get("/api/projection")
def get_growth_projection(account_name: str = Query(...), years: int = Query(10), current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        service = FinanceService(DB_PATH, user_id)
        return service.get_growth_projection(account_name, years)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ETL CSV Upload API
@app.post("/api/etl/import")
async def import_csv_statement(
    file: UploadFile = File(...),
    date_col: str = Form("Date"),
    desc_col: str = Form("Description"),
    amount_col: str = Form("Amount"),
    category_col: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    temp_filename = f"temp_upload_{user_id}_{file.filename}"
    try:
        # Save uploaded file temporarily in workspace
        with open(temp_filename, "wb") as f:
            f.write(await file.read())
            
        etl = TransactionETL(DB_PATH)
        mapping = {
            'date': date_col,
            'description': desc_col,
            'amount': amount_col,
            'category': category_col
        }
        
        inserted, skipped = etl.import_csv(temp_filename, mapping, user_id)
        
        # Clean up temp file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
        return {
            "message": "CSV Ingested Successfully",
            "inserted": inserted,
            "skipped_duplicates": skipped
        }
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=400, detail=f"ETL Parsing failed: {str(e)}")

# Get Recent Transactions
@app.get("/api/transactions")
def get_transactions(limit: int = 50, month: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            query = "SELECT * FROM transactions WHERE user_id = ?"
            params = [user_id]
            if month:
                query += " AND SUBSTR(transaction_date, 1, 7) = ?"
                params.append(month)
            query += " ORDER BY transaction_date DESC, id DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Clear transactions
@app.delete("/api/transactions")
def clear_transactions(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM transactions WHERE user_id = ? AND source_file != 'system_seed'", (user_id,))
            conn.commit()
        return {"message": "User-imported transactions cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transactions")
def add_transaction(tx: TransactionSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        from datetime import datetime
        try:
            datetime.strptime(tx.transaction_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
            
        with get_db() as conn:
            cursor = conn.cursor()
            
            import time
            hash_input = f"{tx.transaction_date}_{tx.description}_{tx.amount}_{time.time()}_{user_id}"
            tx_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
            
            cursor.execute("""
                INSERT INTO transactions (user_id, transaction_date, description, amount, category, account_id, source_file, tx_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, tx.transaction_date, tx.description, tx.amount, tx.category, tx.account_id, "Manual Entry", tx_hash))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Transaction added successfully."}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id))
            conn.commit()
        return {"message": "Transaction deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: DEBT
@app.post("/api/debts")
def add_debt(debt: DebtAccountSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO debt_accounts (user_id, account_name, institution, debt_type, total_credit_line, current_balance, monthly_payment, interest_rate, remaining_payments, original_amount, loan_length_months, lender_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, debt.account_name, debt.institution, debt.debt_type, debt.total_credit_line, debt.current_balance, debt.monthly_payment, debt.interest_rate, debt.remaining_payments, debt.original_amount, debt.loan_length_months, debt.lender_type))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Debt account added successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Debt account name already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/debts/{debt_id}")
def delete_debt(debt_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM debt_accounts WHERE id = ? AND user_id = ?", (debt_id, user_id))
            conn.commit()
        return {"message": "Debt account deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/debts/{debt_id}")
def update_debt(debt_id: int, debt: DebtAccountSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM debt_accounts WHERE id = ? AND user_id = ?", (debt_id, user_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Debt account not found.")
            cursor.execute("""
                UPDATE debt_accounts 
                SET account_name = ?, institution = ?, debt_type = ?, total_credit_line = ?, 
                    current_balance = ?, monthly_payment = ?, interest_rate = ?, 
                    remaining_payments = ?, original_amount = ?, loan_length_months = ?, lender_type = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (debt.account_name, debt.institution, debt.debt_type, debt.total_credit_line, 
                  debt.current_balance, debt.monthly_payment, debt.interest_rate, 
                  debt.remaining_payments, debt.original_amount, debt.loan_length_months, debt.lender_type, debt_id, user_id))
            conn.commit()
            return {"message": "Debt account updated successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Debt account name already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: SAVINGS
@app.post("/api/savings")
def add_savings(savings: SavingsAccountSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO savings_accounts (user_id, account_name, account_type, monthly_contribution, current_balance, annual_yield)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, savings.account_name, savings.account_type, savings.monthly_contribution, savings.current_balance, savings.annual_yield))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Savings account added successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Savings account name already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/savings/{savings_id}")
def delete_savings(savings_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM savings_accounts WHERE id = ? AND user_id = ?", (savings_id, user_id))
            conn.commit()
        return {"message": "Savings account deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/savings/{savings_id}")
def update_savings(savings_id: int, savings: SavingsAccountSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM savings_accounts WHERE id = ? AND user_id = ?", (savings_id, user_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Savings account not found.")
            cursor.execute("""
                UPDATE savings_accounts 
                SET account_name = ?, account_type = ?, monthly_contribution = ?, 
                    current_balance = ?, annual_yield = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (savings.account_name, savings.account_type, savings.monthly_contribution, 
                  savings.current_balance, savings.annual_yield, savings_id, user_id))
            conn.commit()
            return {"message": "Savings account updated successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Savings account name already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: INCOME
@app.post("/api/income")
def add_income(income: IncomeSourceSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO income_sources (user_id, source_name, recipient, amount, frequency)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, income.source_name, income.recipient, income.amount, income.frequency))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Income source added successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/income/{income_id}")
def delete_income(income_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM income_sources WHERE id = ? AND user_id = ?", (income_id, user_id))
            conn.commit()
        return {"message": "Income source deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: FIXED SPENDING
@app.post("/api/fixed")
def add_fixed(fixed: FixedSpendingSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fixed_spending (user_id, category, subcategory, monthly_amount, linked_debt_id, actual_spent)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, fixed.category, fixed.subcategory, fixed.monthly_amount, fixed.linked_debt_id, fixed.actual_spent))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Fixed spending item added successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/fixed/{fixed_id}")
def update_fixed(fixed_id: int, fixed: FixedSpendingSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            exists = conn.execute("SELECT id FROM fixed_spending WHERE id = ? AND user_id = ?", (fixed_id, user_id)).fetchone()
            if not exists:
                raise HTTPException(status_code=404, detail="Fixed spending item not found.")
            conn.execute("""
                UPDATE fixed_spending
                SET category = ?, subcategory = ?, monthly_amount = ?, linked_debt_id = ?, actual_spent = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (fixed.category, fixed.subcategory, fixed.monthly_amount, fixed.linked_debt_id, fixed.actual_spent, fixed_id, user_id))
            conn.commit()
        return {"status": "success", "message": "Fixed spending updated successfully."}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/fixed/{fixed_id}")
def delete_fixed(fixed_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM fixed_spending WHERE id = ? AND user_id = ?", (fixed_id, user_id))
            conn.commit()
        return {"message": "Fixed spending item deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: DISCRETIONARY SPENDING
@app.post("/api/discretionary")
def add_discretionary(disc: DiscretionarySpendingSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO discretionary_spending (user_id, category, subcategory, monthly_amount, actual_spent)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, disc.category, disc.subcategory, disc.monthly_amount, disc.actual_spent))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Discretionary spending item added successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/discretionary/{disc_id}")
def update_discretionary(disc_id: int, disc: DiscretionarySpendingSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            exists = conn.execute("SELECT id FROM discretionary_spending WHERE id = ? AND user_id = ?", (disc_id, user_id)).fetchone()
            if not exists:
                raise HTTPException(status_code=404, detail="Discretionary spending item not found.")
            conn.execute("""
                UPDATE discretionary_spending
                SET category = ?, subcategory = ?, monthly_amount = ?, actual_spent = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (disc.category, disc.subcategory, disc.monthly_amount, disc.actual_spent, disc_id, user_id))
            conn.commit()
        return {"status": "success", "message": "Discretionary spending updated successfully."}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/discretionary/{disc_id}")
def delete_discretionary(disc_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM discretionary_spending WHERE id = ? AND user_id = ?", (disc_id, user_id))
            conn.commit()
        return {"message": "Discretionary spending item deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/clear-all")
def clear_all_data(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM income_sources WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM fixed_spending WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM discretionary_spending WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM savings_accounts WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM debt_accounts WHERE user_id = ?", (user_id,))
            conn.commit()
        return {"message": "All data has been cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve static web pages
app.mount("/", StaticFiles(directory="static", html=True), name="static")
