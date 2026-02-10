"""
Unit tests for financial report calculations
Run with: pytest tests/test_calculations.py
"""

import pytest
import pandas as pd
from pathlib import Path

# ========================================
# FIXTURES (data loading)
# ========================================

@pytest.fixture
def data_dir():
    """Path to data directory"""
    return Path(__file__).parent.parent / 'data'

@pytest.fixture
def df_entries(data_dir):
    """Load and process account entries"""
    df = pd.read_csv(data_dir / 'account_entries.csv')
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y')
    return df

@pytest.fixture
def df_info(data_dir):
    """Load account information"""
    return pd.read_csv(data_dir / 'account_information.csv')

@pytest.fixture
def df_opening_balances(df_entries):
    """Extract opening balances"""
    df = df_entries[df_entries['Text'] == 'Opening Balance'].copy()
    df = df[['Account', 'Amount']]
    df = df.rename(columns={'Amount': 'Opening Balance 2024'})
    return df

@pytest.fixture
def df_transactions(df_entries):
    """Extract transactions"""
    df = df_entries[df_entries['Text'] != 'Opening Balance'].copy()
    df['Month'] = df['Date'].dt.month
    return df

@pytest.fixture
def df_report(df_info, df_opening_balances, df_transactions):
    """Create full report with monthly balances"""
    # Merge
    df = pd.merge(df_info, df_opening_balances, on='Account', how='outer')
    
    # Calculate monthly balances
    month_names = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    for month_num in range(1, 13):
        month_name = month_names[month_num - 1]
        trans_up_to_month = df_transactions[df_transactions['Month'] <= month_num]
        trans_sum = trans_up_to_month.groupby('Account')['Amount'].sum()
        column_name = f'Balance end of {month_name}'
        df[column_name] = df['Opening Balance 2024'] + df['Account'].map(trans_sum).fillna(0)
    
    # Add YTD
    trans_ytd = df_transactions.groupby('Account')['Amount'].sum()
    df['Sum of Transactions YTD'] = df['Account'].map(trans_ytd).fillna(0)
    
    return df

@pytest.fixture
def df_final_report(df_report):
    """Create final report with correct column order"""
    df = df_report.drop(columns=['OpenDate', 'CloseDate'], errors='ignore')
    
    month_names = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    final_columns = [
        'Account',
        'AccountName',
        'Opening Balance 2024'
    ] + [f'Balance end of {month}' for month in month_names] + [
        'Sum of Transactions YTD'
    ]
    
    return df[final_columns]

# ========================================
# TEST 1: Load and Process Account Entries
# ========================================

class TestAccountEntries:
    """Tests for account entries loading and processing"""
    
    def test_entries_count(self, df_entries):
        """Test correct number of entries loaded"""
        assert len(df_entries) == 16, "Expected 16 entries"
    
    def test_date_parsing(self, df_entries):
        """Test date column parsed to datetime"""
        assert pd.api.types.is_datetime64_any_dtype(df_entries['Date']), "Date should be datetime"
    
    def test_no_missing_values(self, df_entries):
        """Test no missing values in critical columns"""
        critical_cols = ['Date', 'Account', 'Amount', 'Text']
        for col in critical_cols:
            assert df_entries[col].notna().all(), f"Missing values in {col}"
    
    def test_data_split(self, df_opening_balances, df_transactions, df_entries):
        """Test split into opening balances and transactions"""
        assert len(df_opening_balances) == 4, "Expected 4 opening balances"
        assert len(df_transactions) == 12, "Expected 12 transactions"
        assert len(df_opening_balances) + len(df_transactions) == len(df_entries), "Split incomplete"

# ========================================
# TEST 2: Load and Process Account Information
# ========================================

class TestAccountInformation:
    """Tests for account information loading"""
    
    def test_account_count(self, df_info):
        """Test correct number of accounts loaded"""
        assert len(df_info) == 4, "Expected 4 accounts"
    
    def test_required_columns(self, df_info):
        """Test all required columns present"""
        required_cols = ['Account', 'AccountName', 'OpenDate', 'CloseDate']
        for col in required_cols:
            assert col in df_info.columns, f"Missing column: {col}"
    
    def test_account_dtype(self, df_info):
        """Test Account column is int64"""
        assert df_info['Account'].dtype == 'int64', "Account should be int64"
    
    def test_no_duplicates(self, df_info):
        """Test no duplicate accounts"""
        assert df_info['Account'].nunique() == len(df_info), "Duplicate accounts found"

# ========================================
# TEST 3: Merge Account Data
# ========================================

class TestMergeData:
    """Tests for data merging operations"""
    
    def test_merge_completeness(self, df_report, df_info):
        """Test merge preserves all accounts"""
        assert len(df_report) == len(df_info), "Merge should preserve all accounts"
    
    def test_no_missing_balances(self, df_report):
        """Test no missing opening balances after merge"""
        assert df_report['Opening Balance 2024'].notna().all(), "Missing opening balances"
    
    def test_no_missing_account_names(self, df_report):
        """Test no missing account names after merge"""
        assert df_report['AccountName'].notna().all(), "Missing account name info"
    
    def test_all_accounts_present(self, df_report, df_info):
        """Test all original accounts present after merge"""
        for account in df_info['Account']:
            assert account in df_report['Account'].values, f"Account {account} missing after merge"

# ========================================
# TEST 4: Final Report
# ========================================

class TestFinalReport:
    """Tests for final report structure and calculations"""
    
    def test_report_structure(self, df_final_report):
        """Test report has correct dimensions"""
        assert len(df_final_report) == 4, "Final report should have 4 rows"
        assert len(df_final_report.columns) == 16, "Final report should have 16 columns"
    
    def test_monthly_columns(self, df_final_report):
        """Test all 12 monthly balance columns exist"""
        month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
        for month in month_names:
            col_name = f'Balance end of {month}'
            assert col_name in df_final_report.columns, f"Missing column: {col_name}"
    
    def test_ytd_column(self, df_final_report):
        """Test YTD column exists"""
        assert 'Sum of Transactions YTD' in df_final_report.columns, "Missing YTD column"
    
    def test_balance_accuracy(self, df_final_report):
        """Test balance calculation accuracy (Dec = Opening + YTD)"""
        for _, row in df_final_report.iterrows():
            expected = row['Opening Balance 2024'] + row['Sum of Transactions YTD']
            actual = row['Balance end of December']
            assert abs(expected - actual) < 0.01, f"Balance mismatch for {row['AccountName']}"
    
    def test_no_missing_values(self, df_final_report):
        """Test no missing values in final report"""
        assert df_final_report.notna().all().all(), "Missing values in final report"
    
    def test_data_types(self, df_final_report):
        """Test data types are correct"""
        assert df_final_report['Account'].dtype == 'int64', "Account should be int64"
        assert df_final_report['Opening Balance 2024'].dtype == 'float64', "Balances should be float64"
    
    def test_financial_totals(self, df_final_report):
        """Test financial totals are consistent"""
        total_opening = df_final_report['Opening Balance 2024'].sum()
        total_ytd = df_final_report['Sum of Transactions YTD'].sum()
        total_closing = df_final_report['Balance end of December'].sum()
        assert abs(total_closing - (total_opening + total_ytd)) < 0.01, "Total balance mismatch"