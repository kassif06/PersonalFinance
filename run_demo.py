import os
import sqlite3
from finance_service import FinanceService
from etl_pipeline import TransactionETL

DB_PATH = "personal_finance.db"
SCHEMA_PATH = "schema.sql"
CSV_PATH = "sample_credit_card_statement.csv"

def init_db():
    print("[1/5] Initializing Database using schema.sql...")
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
        
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema_sql)
    print("      Database schema loaded successfully.")

def seed_db():
    print("[2/5] Seeding Database with required modules data...")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Clear old seed data to prevent duplicates
        cursor.execute("DELETE FROM debt_accounts;")
        cursor.execute("DELETE FROM savings_accounts;")
        cursor.execute("DELETE FROM income_sources;")
        cursor.execute("DELETE FROM fixed_spending;")
        cursor.execute("DELETE FROM discretionary_spending;")
        
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

        # 2. Fixed Spending Module (Housing Mortgage is linked to debt account)
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
        conn.commit()
    print("      Mock database seeded with full core module values.")

def create_mock_csv():
    print("[3/5] Creating mock credit card statement CSV file...")
    csv_content = """Date,Description,Amount
06/15/2026,Netflix Subscription,$15.99
06/18/2026,Trader Joe's Supermarket,$142.50
06/20/2026,Starbucks Coffee,$6.50
06/21/2026,Chevron Gas Station,$45.00
06/22/2026,Amazon.com Retail,$89.99
06/25/2026,Target Store,$110.20
06/25/2026,Target Store,$110.20
"""
    with open(CSV_PATH, "w") as f:
        f.write(csv_content.strip())
    print(f"      Mock CSV statement created at {CSV_PATH} (includes duplicate row).")

def run_etl():
    print("[4/5] Running ETL Import Pipeline on statement...")
    etl = TransactionETL(DB_PATH)
    mapping = {
        'date': 'Date',
        'description': 'Description',
        'amount': 'Amount'
    }
    inserted, skipped = etl.import_csv(CSV_PATH, mapping)
    print(f"      ETL run completed: {inserted} transactions inserted, {skipped} duplicate entries skipped.")

def run_aggregations():
    print("[5/5] Performing financial aggregations and projections...\n")
    service = FinanceService(DB_PATH)
    
    # Unified cash flow calculation
    cash_flow = service.calculate_unified_cash_flow()
    net_worth = service.get_net_worth()
    
    # Format console output beautifully
    print("=" * 60)
    print("                 PERSONAL FINANCE DASHBOARD REPORT             ")
    print("=" * 60)
    print(f"Net Worth:                 ${net_worth:,.2f}")
    print("-" * 60)
    print(f"Total Monthly Income:      ${cash_flow['total_income']:,.2f}")
    print(f"Fixed Spending (Unlinked): ${cash_flow['fixed_spending']:,.2f}")
    print(f"Discretionary Spending:    ${cash_flow['discretionary_spending']:,.2f}")
    print(f"Monthly Debt Payments:     ${cash_flow['debt_obligations']:,.2f}")
    print(f"Monthly Savings Goal:      ${cash_flow['savings_contributions']:,.2f}")
    print("-" * 60)
    print(f"UNIFIED MONTHLY CASH FLOW: ${cash_flow['net_remaining_cash_flow']:+,.2f}")
    print("=" * 60)
    
    # Growth Projection
    print("\n[VANGUARD ROTH IRA - 10-YEAR GROWTH PROJECTION]")
    print(f"Starting Balance: $24,000.00 | Monthly Contribution: $500.00 | Yield: 7.50% APY")
    print("-" * 60)
    projections = service.get_growth_projection("Vanguard Roth IRA", 10)
    for p in projections[::2]:  # Show every 2 years
        print(f"Year {p['year']:02d}: Projected Balance = ${p['projected_balance']:,.2f}")
    print("=" * 60)

    # Ingested transactions preview
    print("\n[RECENT INGESTED TRANSACTIONS PREVIEW]")
    print("-" * 60)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT transaction_date, description, amount, category FROM transactions LIMIT 5").fetchall()
        for row in rows:
            print(f"{row['transaction_date']} | {row['description'][:25]:<25} | ${row['amount']:>6.2f} | {row['category']}")
    print("=" * 60)

if __name__ == "__main__":
    init_db()
    seed_db()
    create_mock_csv()
    run_etl()
    run_aggregations()
    
    # Cleanup files
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(CSV_PATH):
        os.remove(CSV_PATH)
    print("\nTemporary demonstration database and CSV file cleaned up.")
