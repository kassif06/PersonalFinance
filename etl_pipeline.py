import csv
import hashlib
import sqlite3
from datetime import datetime
from typing import Dict, Any, Tuple

class TransactionETL:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def generate_tx_hash(self, date_str: str, description: str, amount: float) -> str:
        """Generates a unique deterministic SHA-256 hash for deduplication."""
        raw_payload = f"{date_str}||{description.strip().lower()}||{amount:.2f}"
        return hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()

    def clean_date(self, raw_date: str) -> str:
        """Normalizes various date formats (e.g. MM/DD/YYYY, YYYY/MM/DD) to ISO format (YYYY-MM-DD)."""
        cleaned = raw_date.strip()
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"Unable to parse date format: {raw_date}")

    def clean_amount(self, raw_amount: str) -> float:
        """Cleans currency strings, strips symbols like $ or commas, and converts to float."""
        cleaned = raw_amount.replace('$', '').replace(',', '').strip()
        return float(cleaned)

    def rule_based_category(self, description: str) -> str:
        """Categorizes transactions based on keyword matching."""
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ('netflix', 'spotify', 'hulu', 'gym', 'fitness')):
            return 'Subscriptions'
        if any(kw in desc_lower for kw in ('uber', 'lyft', 'chevron', 'shell', 'gas station')):
            return 'Connectivity'
        if any(kw in desc_lower for kw in ('kroger', 'safeway', 'walmart', 'trader joe', 'costco', 'supermarket')):
            return 'Groceries'
        if any(kw in desc_lower for kw in ('mcdonald', 'starbucks', 'restaurant', 'pub', 'bar', 'grill', 'diners')):
            return 'Dining'
        if any(kw in desc_lower for kw in ('amazon', 'target', 'clothing', 'store', 'mall', 'retail')):
            return 'Shopping'
        return 'Uncategorized'

    def import_csv(self, file_path: str, column_mapping: Dict[str, str]) -> Tuple[int, int]:
        """
        Parses the CSV, cleans records, hashes them, and inserts them.
        column_mapping must map CSV header keys to keys: 'date', 'description', 'amount'.
        Returns (rows_inserted, rows_skipped_duplicates).
        """
        inserted_count = 0
        skipped_count = 0
        
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            with sqlite3.connect(self.db_path) as conn:
                # Enable foreign keys
                conn.execute("PRAGMA foreign_keys = ON;")
                cursor = conn.cursor()
                
                for row in reader:
                    try:
                        # Extract columns using mapping
                        raw_date = row[column_mapping['date']]
                        raw_desc = row[column_mapping['description']]
                        raw_amount = row[column_mapping['amount']]
                        
                        # Transform Phase
                        date_str = self.clean_date(raw_date)
                        description = raw_desc.strip()
                        amount = self.clean_amount(raw_amount)
                        
                        # Extract category if mapped and present
                        if 'category' in column_mapping and column_mapping['category'] and column_mapping['category'] in row and row[column_mapping['category']]:
                            category = row[column_mapping['category']].strip()
                        else:
                            category = self.rule_based_category(description)
                        
                        # Generate Unique Transaction Hash
                        tx_hash = self.generate_tx_hash(date_str, description, amount)
                        
                        # Load Phase (Insert Ignore or UPSERT via unique tx_hash constraint)
                        cursor.execute("""
                            INSERT INTO transactions (transaction_date, description, amount, category, tx_hash, source_file)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (date_str, description, amount, category, tx_hash, file_path))
                        
                        # Auto-link and adjust account balance if transaction description matches an account
                        tx_id = cursor.lastrowid
                        self.auto_link_and_update_balance(cursor, tx_id, description, amount)
                        
                        inserted_count += 1
                    except sqlite3.IntegrityError:
                        # Catch unique hash constraint violations (already imported)
                        skipped_count += 1
                        continue
                    except Exception as e:
                        # Log error or skip corrupted rows
                        print(f"Skipping row due to error: {e}")
                        continue
                conn.commit()
                
        return inserted_count, skipped_count

    def auto_link_and_update_balance(self, cursor: sqlite3.Cursor, tx_id: int, description: str, amount: float):
        """
        Attempts to match the transaction description to a debt or savings account,
        links it (if a debt account), and updates the account balance.
        """
        desc_lower = description.lower()
        
        # 1. Match against Debt Accounts
        cursor.execute("SELECT id, account_name, institution, current_balance FROM debt_accounts")
        debt_accounts = cursor.fetchall()
        for d_id, name, inst, current_bal in debt_accounts:
            # Match on account name or institution
            if (name and name.lower() in desc_lower) or (inst and inst.lower() in desc_lower):
                cursor.execute("UPDATE transactions SET account_id = ? WHERE id = ?", (d_id, tx_id))
                # For debts: charges (negative amount) increase balance; payments (positive amount) decrease balance.
                new_bal = max(0.0, current_bal - amount)
                cursor.execute("UPDATE debt_accounts SET current_balance = ? WHERE id = ?", (new_bal, d_id))
                return
                
        # 2. Match against Savings Accounts
        cursor.execute("SELECT id, account_name, current_balance FROM savings_accounts")
        savings_accounts = cursor.fetchall()
        for s_id, name, current_bal in savings_accounts:
            if name and name.lower() in desc_lower:
                # For savings: deposits (positive amount) increase balance; withdrawals (negative amount) decrease balance.
                new_bal = max(0.0, current_bal + amount)
                cursor.execute("UPDATE savings_accounts SET current_balance = ? WHERE id = ?", (new_bal, s_id))
                return
