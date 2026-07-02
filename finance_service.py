import sqlite3
from typing import Dict, Any, List

class FinanceService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        import os
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Ensure schema is loaded
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
            if not cursor.fetchone():
                schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
                if os.path.exists(schema_path):
                    with open(schema_path, "r") as f:
                        conn.executescript(f.read())
        except Exception as e:
            print(f"Error ensuring schema in FinanceService: {e}")
            
        return conn

    def get_monthly_income(self) -> float:
        """Calculates total monthly income normalized across various frequencies."""
        query = "SELECT amount, frequency FROM income_sources"
        total_monthly_income = 0.0
        
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            
        for row in rows:
            amount = row['amount']
            freq = row['frequency']
            # Normalize to monthly values
            if freq == 'weekly':
                monthly_val = amount * 52 / 12
            elif freq == 'bi-weekly':
                monthly_val = amount * 26 / 12
            elif freq == 'semi-monthly':
                monthly_val = amount * 2
            elif freq == 'monthly':
                monthly_val = amount
            elif freq == 'annually':
                monthly_val = amount / 12
            else:
                monthly_val = 0.0
            total_monthly_income += monthly_val
            
        return round(total_monthly_income, 2)

    def get_monthly_debt_obligations(self) -> float:
        """Calculates combined monthly minimum debt obligations."""
        query = "SELECT SUM(monthly_payment) as total FROM debt_accounts"
        with self._get_connection() as conn:
            row = conn.execute(query).fetchone()
            return round(row['total'] or 0.0, 2)

    def get_monthly_savings_contributions(self) -> float:
        """Calculates total monthly savings/investments objectives."""
        query = "SELECT SUM(monthly_contribution) as total FROM savings_accounts"
        with self._get_connection() as conn:
            row = conn.execute(query).fetchone()
            return round(row['total'] or 0.0, 2)

    def get_monthly_fixed_spending(self) -> float:
        """Calculates total monthly fixed spending.
        Note: Fixed spending includes housing, connectivity, utilities, insurances, and groceries.
        """
        query = "SELECT SUM(monthly_amount) as total FROM fixed_spending"
        with self._get_connection() as conn:
            row = conn.execute(query).fetchone()
            return round(row['total'] or 0.0, 2)

    def get_monthly_discretionary_spending(self) -> float:
        """Calculates total monthly discretionary spending."""
        query = "SELECT SUM(monthly_amount) as total FROM discretionary_spending"
        with self._get_connection() as conn:
            row = conn.execute(query).fetchone()
            return round(row['total'] or 0.0, 2)

    def calculate_unified_cash_flow(self) -> Dict[str, float]:
        """
        Computes the unified cash flow equation:
        Unified Cash Flow = Total Income - Total Fixed - Total Discretionary - Debt Payments - Savings
        """
        income = self.get_monthly_income()
        debt_payments = self.get_monthly_debt_obligations()
        savings = self.get_monthly_savings_contributions()
        
        # Avoid double-counting fixed spending items that are linked to debt accounts
        # (e.g. mortgage payments that are tracked both under fixed_spending and debt_accounts)
        with self._get_connection() as conn:
            linked_fixed_total_row = conn.execute(
                "SELECT SUM(monthly_amount) as total FROM fixed_spending WHERE linked_debt_id IS NOT NULL"
            ).fetchone()
            linked_fixed_total = linked_fixed_total_row['total'] or 0.0
            
        raw_fixed = self.get_monthly_fixed_spending()
        # Deduct linked fixed expenses since they are paid as debt obligations
        unlinked_fixed = max(0.0, raw_fixed - linked_fixed_total)
        
        discretionary = self.get_monthly_discretionary_spending()
        
        total_spending = unlinked_fixed + discretionary
        net_cash_flow = income - total_spending - debt_payments - savings
        
        return {
            "total_income": income,
            "fixed_spending": unlinked_fixed,
            "discretionary_spending": discretionary,
            "debt_obligations": debt_payments,
            "savings_contributions": savings,
            "net_remaining_cash_flow": round(net_cash_flow, 2)
        }

    def get_net_worth(self) -> float:
        """Calculates current net worth: Total Savings - Total Debt."""
        with self._get_connection() as conn:
            savings_val = conn.execute("SELECT SUM(current_balance) FROM savings_accounts").fetchone()[0] or 0.0
            debt_val = conn.execute("SELECT SUM(current_balance) FROM debt_accounts").fetchone()[0] or 0.0
        return round(savings_val - debt_val, 2)

    def get_growth_projection(self, account_name: str, years: int) -> List[Dict[str, Any]]:
        """
        Forecasts future balance for a savings/investment account over a number of years,
        assuming monthly compounding interest:
        A = P(1 + r/n)^(nt) + PMT * [((1 + r/n)^(nt) - 1) / (r/n)]
        """
        query = "SELECT current_balance, monthly_contribution, annual_yield FROM savings_accounts WHERE account_name = ?"
        with self._get_connection() as conn:
            row = conn.execute(query, (account_name,)).fetchone()
            
        if not row:
            raise ValueError(f"Account '{account_name}' not found.")
            
        current_balance = row['current_balance']
        monthly_contribution = row['monthly_contribution']
        annual_yield = row['annual_yield'] / 100.0  # Convert percentage to decimal
        
        r = annual_yield
        n = 12  # Compounded monthly
        
        projection = []
        
        for year in range(0, years + 1):
            t = year
            if r == 0:
                # Direct addition if no yield
                balance = current_balance + (monthly_contribution * 12 * t)
            else:
                # Standard compounding interest formula with monthly contributions
                compound_principal = current_balance * ((1 + r/n)**(n*t))
                annuity = monthly_contribution * (((1 + r/n)**(n*t) - 1) / (r/n))
                balance = compound_principal + annuity
                
            projection.append({
                "year": year,
                "projected_balance": round(balance, 2)
            })
            
        return projection

    def get_actuals(self) -> Dict[str, float]:
        """
        Aggregates imported transactions to calculate actual monthly flow numbers.
        """
        actuals = {
            "income": 0.0,
            "fixed": 0.0,
            "discretionary": 0.0,
            "debt_payments": 0.0,
            "savings": 0.0
        }
        
        with self._get_connection() as conn:
            # Sum manual actual spent for fixed and discretionary spending
            fixed_val = conn.execute("SELECT SUM(actual_spent) FROM fixed_spending").fetchone()[0] or 0.0
            disc_val = conn.execute("SELECT SUM(actual_spent) FROM discretionary_spending").fetchone()[0] or 0.0
            actuals["fixed"] = fixed_val
            actuals["discretionary"] = disc_val
            
            rows = conn.execute("SELECT amount, category, account_id FROM transactions").fetchall()
            
        for row in rows:
            amount = row['amount']
            cat = row['category']
            acc_id = row['account_id']
            
            if amount > 0:
                # Positive transaction: Income, Debt Payment inflow, or Savings Deposit
                if cat == 'Savings' or (cat and 'savings' in cat.lower()):
                    actuals["savings"] += amount
                elif cat == 'Debt Payment' or (cat and 'debt' in cat.lower()) or acc_id is not None:
                    actuals["debt_payments"] += amount
                else:
                    actuals["income"] += amount
            else:
                # Negative transaction: Spending outflow, or Savings Withdrawal
                abs_amt = abs(amount)
                if cat == 'Savings' or (cat and 'savings' in cat.lower()):
                    actuals["savings"] += abs_amt
                elif cat == 'Debt Payment' or (cat and 'debt' in cat.lower()) or acc_id is not None:
                    actuals["debt_payments"] += abs_amt
                    
        return {k: round(v, 2) for k, v in actuals.items()}
