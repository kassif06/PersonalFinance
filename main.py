# Personal Finance Application Backend
import os
import sqlite3
import hashlib
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
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

# Pydantic schemas for request validation
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

class DiscretionarySpendingSchema(BaseModel):
    category: str
    subcategory: str
    monthly_amount: float

# Helper to get DB connection
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Ensure tables exist (handles cases where the db file is deleted or cleared at runtime)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if not cursor.fetchone():
            with open(SCHEMA_PATH, "r") as f:
                conn.executescript(f.read())
    except Exception as e:
        print(f"Error ensuring database schema: {e}")
        
    return conn

# Database setup on startup
@app.on_event("startup")
def startup_event():
    db_exists = os.path.exists(DB_PATH)
    # Open DB (which will auto-generate tables if missing) and check if data needs to be seeded
    with get_db() as conn:
        if not db_exists:
            print("Initializing database and seeding mock data...")
            cursor = conn.cursor()
            # 1. Debt Tracker Module
            cursor.executemany("""
                INSERT INTO debt_accounts 
                (account_name, institution, debt_type, total_credit_line, current_balance, monthly_payment, interest_rate, remaining_payments, original_amount, loan_length_months, lender_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                ('Capital One Quicksilver', 'Capital One', 'Credit Card', 5000.0, 1200.0, 35.0, 22.99, None, None, None, 'N/A'),
                ('Affirm MacBook Pro', 'Affirm', 'BNPL', None, 480.0, 120.0, 0.0, 4, 1200.0, 10, 'N/A'),
                ('Chase Auto Loan', 'Chase Bank', 'Car Loan', None, 18500.0, 350.0, 4.5, 24, 25000.0, 72, 'N/A'),
                ('Family Loan', 'Uncle Robert', 'Personal Loan', None, 4000.0, 200.0, 2.0, 20, 10000.0, 50, 'Family'),
                ('Wells Fargo Mortgage', 'Wells Fargo', 'Mortgage', None, 285000.0, 1800.0, 4.25, 300, 320000.0, 360, 'Institution')
            ])
            
            # Get mortgage ID to cross-link
            cursor.execute("SELECT id FROM debt_accounts WHERE account_name = 'Wells Fargo Mortgage'")
            mortgage_id = cursor.fetchone()[0]

            # 2. Fixed Spending Module
            cursor.executemany("""
                INSERT INTO fixed_spending (category, subcategory, monthly_amount, linked_debt_id)
                VALUES (?, ?, ?, ?)
            """, [
                ('Housing', 'Mortgage Payment', 1800.0, mortgage_id),
                ('Connectivity', 'Cell Phone Plan', 80.0, None),
                ('Connectivity', 'Home Wi-Fi', 60.0, None),
                ('Utilities', 'Electricity', 120.0, None),
                ('Utilities', 'Water', 50.0, None),
                ('Utilities', 'Gas', 40.0, None),
                ('Insurances', 'Health Insurance', 300.0, None),
                ('Insurances', 'Auto Insurance', 150.0, None),
                ('Insurances', 'Homeowners Insurance', 40.0, None),
                ('Groceries', 'Estimated Grocery Budget', 600.0, None)
            ])
            
            # 3. Discretionary Spending Module
            cursor.executemany("""
                INSERT INTO discretionary_spending (category, subcategory, monthly_amount)
                VALUES (?, ?, ?)
            """, [
                ('Family Overseas', 'Remittance Stipend', 300.0),
                ('Dining', 'Restaurants and Bars', 400.0),
                ('Shopping', 'Retail and Clothing', 250.0),
                ('Subscriptions', 'Netflix & Spotify', 25.0),
                ('Subscriptions', 'Gym Membership', 50.0)
            ])
            
            # 4. Savings & Investment Module
            cursor.executemany("""
                INSERT INTO savings_accounts (account_name, account_type, monthly_contribution, current_balance, annual_yield)
                VALUES (?, ?, ?, ?, ?)
            """, [
                ('Vanguard Roth IRA', 'Roth IRA', 500.0, 24000.0, 7.5),
                ('Standard Savings Account', 'Standard Savings', 300.0, 12000.0, 4.25)
            ])
            
            # 5. Income Module
            cursor.executemany("""
                INSERT INTO income_sources (source_name, recipient, amount, frequency)
                VALUES (?, ?, ?, ?)
            """, [
                ('Primary Salary', 'Self', 4200.0, 'bi-weekly'),
                ('Wife Salary', 'Partner', 3500.0, 'monthly'),
                ('Dividends and Side Hustle', 'Joint', 400.0, 'monthly')
            ])
            
            # Seed a few transaction logs as well
            cursor.executemany("""
                INSERT INTO transactions (transaction_date, description, amount, category, tx_hash, source_file)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                ('2026-06-15', 'Netflix Subscription', -15.99, 'Subscriptions', 'seed_h1', 'system_seed'),
                ('2026-06-18', 'Trader Joes Supermarket', -142.50, 'Groceries', 'seed_h2', 'system_seed'),
                ('2026-06-20', 'Starbucks Coffee', -6.50, 'Dining', 'seed_h3', 'system_seed'),
                ('2026-06-21', 'Chevron Gas Station', -45.00, 'Connectivity', 'seed_h4', 'system_seed'),
                ('2026-06-22', 'Amazon.com Retail', -89.99, 'Shopping', 'seed_h5', 'system_seed')
            ])
            conn.commit()
            print("Database seeded successfully.")

# ----------------- API ENDPOINTS -----------------

# Dashboard Aggregation API
@app.get("/api/dashboard")
def get_dashboard_summary():
    try:
        service = FinanceService(DB_PATH)
        cash_flow = service.calculate_unified_cash_flow()
        net_worth = service.get_net_worth()
        
        # Get details for individual components
        with get_db() as conn:
            debts_rows = conn.execute("""
                SELECT d.*, 
                       COALESCE((SELECT SUM(t.amount) 
                                 FROM transactions t 
                                 WHERE t.account_id = d.id AND t.amount > 0), 0.0) as actual_payment
                FROM debt_accounts d
            """).fetchall()
            debts = [dict(row) for row in debts_rows]
            
            savings_rows = conn.execute("""
                SELECT s.*,
                       COALESCE((SELECT SUM(t.amount)
                                 FROM transactions t
                                 WHERE t.description LIKE '%' || s.account_name || '%' AND t.amount > 0), 0.0) as actual_contribution
                FROM savings_accounts s
            """).fetchall()
            savings = [dict(row) for row in savings_rows]
            
            income = [dict(row) for row in conn.execute("SELECT * FROM income_sources").fetchall()]
            fixed = [dict(row) for row in conn.execute("SELECT * FROM fixed_spending").fetchall()]
            disc = [dict(row) for row in conn.execute("SELECT * FROM discretionary_spending").fetchall()]
            
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
            "actuals": service.get_actuals(),
            "debts": debts,
            "savings": savings,
            "income": income,
            "fixed_spending_items": fixed,
            "discretionary_spending_items": disc
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Growth Projection API
@app.get("/api/projection")
def get_growth_projection(account_name: str = Query(...), years: int = Query(10)):
    try:
        service = FinanceService(DB_PATH)
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
    category_col: Optional[str] = Form(None)
):
    try:
        # Save uploaded file temporarily in workspace
        temp_filename = f"temp_upload_{file.filename}"
        with open(temp_filename, "wb") as f:
            f.write(await file.read())
            
        etl = TransactionETL(DB_PATH)
        mapping = {
            'date': date_col,
            'description': desc_col,
            'amount': amount_col,
            'category': category_col
        }
        
        inserted, skipped = etl.import_csv(temp_filename, mapping)
        
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
def get_transactions(limit: int = 50):
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY transaction_date DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Clear transactions
@app.delete("/api/transactions")
def clear_transactions():
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM transactions WHERE source_file != 'system_seed'")
            conn.commit()
        return {"message": "User-imported transactions cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: DEBT
@app.post("/api/debts")
def add_debt(debt: DebtAccountSchema):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO debt_accounts (account_name, institution, debt_type, total_credit_line, current_balance, monthly_payment, interest_rate, remaining_payments, original_amount, loan_length_months, lender_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (debt.account_name, debt.institution, debt.debt_type, debt.total_credit_line, debt.current_balance, debt.monthly_payment, debt.interest_rate, debt.remaining_payments, debt.original_amount, debt.loan_length_months, debt.lender_type))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Debt account added successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Debt account name already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/debts/{debt_id}")
def delete_debt(debt_id: int):
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM debt_accounts WHERE id = ?", (debt_id,))
            conn.commit()
        return {"message": "Debt account deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/debts/{debt_id}")
def update_debt(debt_id: int, debt: DebtAccountSchema):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM debt_accounts WHERE id = ?", (debt_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Debt account not found.")
            cursor.execute("""
                UPDATE debt_accounts 
                SET account_name = ?, institution = ?, debt_type = ?, total_credit_line = ?, 
                    current_balance = ?, monthly_payment = ?, interest_rate = ?, 
                    remaining_payments = ?, original_amount = ?, loan_length_months = ?, lender_type = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (debt.account_name, debt.institution, debt.debt_type, debt.total_credit_line, 
                  debt.current_balance, debt.monthly_payment, debt.interest_rate, 
                  debt.remaining_payments, debt.original_amount, debt.loan_length_months, debt.lender_type, debt_id))
            conn.commit()
            return {"message": "Debt account updated successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Debt account name already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: SAVINGS
@app.post("/api/savings")
def add_savings(savings: SavingsAccountSchema):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO savings_accounts (account_name, account_type, monthly_contribution, current_balance, annual_yield)
                VALUES (?, ?, ?, ?, ?)
            """, (savings.account_name, savings.account_type, savings.monthly_contribution, savings.current_balance, savings.annual_yield))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Savings account added successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Savings account name already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/savings/{savings_id}")
def delete_savings(savings_id: int):
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM savings_accounts WHERE id = ?", (savings_id,))
            conn.commit()
        return {"message": "Savings account deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/savings/{savings_id}")
def update_savings(savings_id: int, savings: SavingsAccountSchema):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM savings_accounts WHERE id = ?", (savings_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Savings account not found.")
            cursor.execute("""
                UPDATE savings_accounts 
                SET account_name = ?, account_type = ?, monthly_contribution = ?, 
                    current_balance = ?, annual_yield = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (savings.account_name, savings.account_type, savings.monthly_contribution, 
                  savings.current_balance, savings.annual_yield, savings_id))
            conn.commit()
            return {"message": "Savings account updated successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Savings account name already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: INCOME
@app.post("/api/income")
def add_income(income: IncomeSourceSchema):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO income_sources (source_name, recipient, amount, frequency)
                VALUES (?, ?, ?, ?)
            """, (income.source_name, income.recipient, income.amount, income.frequency))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Income source added successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/income/{income_id}")
def delete_income(income_id: int):
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM income_sources WHERE id = ?", (income_id,))
            conn.commit()
        return {"message": "Income source deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: FIXED SPENDING
@app.post("/api/fixed")
def add_fixed(fixed: FixedSpendingSchema):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fixed_spending (category, subcategory, monthly_amount, linked_debt_id)
                VALUES (?, ?, ?, ?)
            """, (fixed.category, fixed.subcategory, fixed.monthly_amount, fixed.linked_debt_id))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Fixed spending item added successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/fixed/{fixed_id}")
def delete_fixed(fixed_id: int):
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM fixed_spending WHERE id = ?", (fixed_id,))
            conn.commit()
        return {"message": "Fixed spending item deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CRUD: DISCRETIONARY SPENDING
@app.post("/api/discretionary")
def add_discretionary(disc: DiscretionarySpendingSchema):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO discretionary_spending (category, subcategory, monthly_amount)
                VALUES (?, ?, ?)
            """, (disc.category, disc.subcategory, disc.monthly_amount))
            conn.commit()
            return {"id": cursor.lastrowid, "message": "Discretionary spending item added successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/discretionary/{disc_id}")
def delete_discretionary(disc_id: int):
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM discretionary_spending WHERE id = ?", (disc_id,))
            conn.commit()
        return {"message": "Discretionary spending item deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/clear-all")
def clear_all_data():
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM income_sources")
            conn.execute("DELETE FROM fixed_spending")
            conn.execute("DELETE FROM discretionary_spending")
            conn.execute("DELETE FROM savings_accounts")
            conn.execute("DELETE FROM debt_accounts")
            conn.commit()
        return {"message": "All data has been cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve static web pages
app.mount("/", StaticFiles(directory="static", html=True), name="static")
