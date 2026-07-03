-- Enable foreign key support in SQLite (must be run per connection)
PRAGMA foreign_keys = ON;

-- 1. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. SESSIONS TABLE
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. DEBT ACCOUNTS
CREATE TABLE IF NOT EXISTS debt_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_name TEXT NOT NULL,
    institution TEXT NOT NULL,
    debt_type TEXT CHECK(debt_type IN ('BNPL', 'Credit Card', 'Car Loan', 'Personal Loan', 'Mortgage')) NOT NULL,
    total_credit_line REAL, -- Relevant for Credit Cards
    current_balance REAL NOT NULL DEFAULT 0.0 CHECK(current_balance >= 0.0),
    monthly_payment REAL NOT NULL DEFAULT 0.0 CHECK(monthly_payment >= 0.0),
    interest_rate REAL CHECK(interest_rate >= 0.0), -- Annual interest rate (e.g. 5.25 for 5.25%)
    remaining_payments INTEGER CHECK(remaining_payments >= 0), -- For BNPL, Car Loans, Mortgages
    original_amount REAL CHECK(original_amount >= 0.0), -- For Loans
    loan_length_months INTEGER CHECK(loan_length_months >= 0), -- Total duration of the loan
    lender_type TEXT CHECK(lender_type IN ('Institution', 'Family', 'N/A')) DEFAULT 'N/A', -- For Personal Loans
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, account_name)
);

-- 4. SAVINGS & INVESTMENT ACCOUNTS
CREATE TABLE IF NOT EXISTS savings_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT CHECK(account_type IN ('Roth IRA', 'Standard Savings', 'Brokerage', 'Other')) NOT NULL,
    monthly_contribution REAL NOT NULL DEFAULT 0.0 CHECK(monthly_contribution >= 0.0),
    current_balance REAL NOT NULL DEFAULT 0.0 CHECK(current_balance >= 0.0),
    annual_yield REAL NOT NULL DEFAULT 0.0 CHECK(annual_yield >= 0.0), -- e.g., 4.5 for 4.5% APY
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, account_name)
);

-- 5. INCOME SOURCES
CREATE TABLE IF NOT EXISTS income_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    recipient TEXT CHECK(recipient IN ('Self', 'Partner', 'Joint')) NOT NULL DEFAULT 'Self',
    amount REAL NOT NULL CHECK(amount > 0.0),
    frequency TEXT CHECK(frequency IN ('weekly', 'bi-weekly', 'semi-monthly', 'monthly', 'annually')) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 6. FIXED SPENDING
CREATE TABLE IF NOT EXISTS fixed_spending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT CHECK(category IN ('Housing', 'Connectivity', 'Utilities', 'Insurances', 'Groceries')) NOT NULL,
    subcategory TEXT NOT NULL, -- e.g., Rent, Electric, Water, Auto Insurance, etc.
    monthly_amount REAL NOT NULL CHECK(monthly_amount >= 0.0),
    actual_spent REAL NOT NULL DEFAULT 0.0 CHECK(actual_spent >= 0.0),
    linked_debt_id INTEGER, -- Optional link to a mortgage or car loan in debt_accounts
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (linked_debt_id) REFERENCES debt_accounts(id) ON DELETE SET NULL
);

-- 7. DISCRETIONARY SPENDING
CREATE TABLE IF NOT EXISTS discretionary_spending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT CHECK(category IN ('Family Overseas', 'Dining', 'Shopping', 'Subscriptions')) NOT NULL,
    subcategory TEXT NOT NULL, -- e.g., Netflix, Gym, Restaurants
    monthly_amount REAL NOT NULL CHECK(monthly_amount >= 0.0),
    actual_spent REAL NOT NULL DEFAULT 0.0 CHECK(actual_spent >= 0.0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 8. TRANSACTION LOGS (ETL Destination)
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    transaction_date TEXT NOT NULL, -- Format: YYYY-MM-DD
    description TEXT NOT NULL,
    amount REAL NOT NULL, -- Negative for spending, positive for income
    category TEXT NOT NULL DEFAULT 'Uncategorized',
    account_id INTEGER, -- Associated debt or savings account (if any)
    source_file TEXT, -- Name of the ingested CSV file
    tx_hash TEXT NOT NULL, -- For deduplication (hash of date + desc + amount)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES debt_accounts(id) ON DELETE SET NULL,
    UNIQUE (user_id, tx_hash)
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_user_hash ON transactions(user_id, tx_hash);
CREATE INDEX IF NOT EXISTS idx_debt_user_type ON debt_accounts(user_id, debt_type);
CREATE INDEX IF NOT EXISTS idx_fixed_user_category ON fixed_spending(user_id, category);
CREATE INDEX IF NOT EXISTS idx_discretionary_user_category ON discretionary_spending(user_id, category);
