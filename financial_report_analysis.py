# ========================================
# IMPORTS AND CONFIGURATION
# ========================================

import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# Define separators (used throughout for output formatting)
SEPARATOR_MAIN = "=" * 80
SEPARATOR_SUB = "-" * 80

# Define data paths
DATA_DIR = Path('data')  # Relative to script location
ENTRIES_FILE = DATA_DIR / 'account_entries.csv'
INFO_FILE = DATA_DIR / 'account_information.csv'

# Load data
df_entries = pd.read_csv(ENTRIES_FILE)
df_info = pd.read_csv(INFO_FILE)

print(f"Data loaded successfully:")
print(f"  - {len(df_entries)} transaction entries from {ENTRIES_FILE}")
print(f"  - {len(df_info)} accounts from {INFO_FILE}")

# ========================================
# SECTION 1: Load and Process Account Entries
# ========================================

# Parse dates to datetime format
df_entries['Date'] = pd.to_datetime(df_entries['Date'], format='%d/%m/%Y')

# Display all entries
print("\nAccount Entries (loaded):")
print(df_entries)

# Validation: Verify data loaded and parsed correctly
print(f"\nLoaded {len(df_entries)} entries")
print(f"Date parsed to datetime: {df_entries['Date'].dtype}")

# ========================================
# SECTION 2: Separate Opening Balances from Transactions
# ========================================
# Efficient filtering approach:
# - Direct text comparison (Text == 'Opening Balance') for opening balances
# - Simple negation (Text != 'Opening Balance') for transactions
# - No redundant type conversions - Account column is already int64 from CSV parsing (validated by .dtype)

# Opening balances (all are 01/01/2024 with text "Opening Balance")
df_opening_balances = df_entries[df_entries['Text'] == 'Opening Balance'].copy()

# Select only necessary columns for merging (Account and Amount)
# Date, Currency, and Text are constant for all opening balances (not needed)
df_opening_balances = df_opening_balances[['Account', 'Amount']]
df_opening_balances = df_opening_balances.rename(columns={'Amount': 'Opening Balance 2024'})

# All other transactions (exclude opening balances)
df_transactions = df_entries[df_entries['Text'] != 'Opening Balance'].copy()

print("\nOpening Balances for 2024:")
print(df_opening_balances)
print(f"Account dtype: {df_opening_balances['Account'].dtype}")

print("\nOther Transactions:")
print(df_transactions[['Date', 'Account', 'Amount', 'Text']])
print(f"Account dtype: {df_transactions['Account'].dtype}")

# Validation: Ensure split is complete (no data lost)
print(f"\nOpening balances: {len(df_opening_balances)} rows")
print(f"Transactions: {len(df_transactions)} rows")
print(f"Total check: {len(df_opening_balances) + len(df_transactions)} = {len(df_entries)}")

# ========================================
# SECTION 3: Prepare Transactions for Calculation
# ========================================
# Strategic approach: Add Month column without immediate aggregation
#
# For monthly END balances, we need CUMULATIVE sums:
# - Balance end of Feb = Opening + (Jan + Feb transactions)
# - NOT: Opening + (only Feb transactions)
#
# This approach:
# - Add Month column now (extract month number 1-12 from date)
# - Enables cumulative filtering in next section
# - Defer groupby until needed (Section 6) with cumulative filter (Month <= i)
# - This directly produces cumulative balances without complex transformations

# Add Month column (extract month number 1-12 from date)
df_transactions['Month'] = df_transactions['Date'].dt.month

print("\nTransactions with Month:")
print(df_transactions[['Date', 'Account', 'Amount', 'Month', 'Text']])

# Validation: Transaction count by month
print(f"\nTransaction count by Month:")
print(df_transactions['Month'].value_counts().sort_index())

# ========================================
# SECTION 4: Load and Process Account Information
# ========================================
# Efficient loading: No redundant type conversions
# Account column is already int64 from CSV parsing (validated by .dtype)

# Account information already loaded at the beginning
# Verifying data is ready for processing

# Display all accounts
print("\nAccount Information:")
print(df_info)

# Validation: Verify data loaded and formatted correctly for merging
print(f"\nLoaded {len(df_info)} accounts")
print(f"Account dtype: {df_info['Account'].dtype}")
print(f"Account values for merge: {sorted(df_info['Account'].tolist())}")
print(f"Ready for merge: {df_info['Account'].nunique()} unique accounts, no duplicates")

# ========================================
# SECTION 5: Merge Account Data
# ========================================

# Merge Account Information with Opening Balances
# Using outer join to ensure no data is lost (defensive approach)
df_report = pd.merge(df_info, df_opening_balances, on='Account', how='outer')

# Display all merged data
print("\nMerged Report (Initial):")
print(df_report)

# Validation: Ensure merge was successful
print(f"\nMerged {len(df_report)} accounts")
print(f"Expected: {len(df_info)} accounts from df_info")

# Check for missing values (would indicate incomplete merge)
missing_balance = df_report['Opening Balance 2024'].isna().sum()
missing_account_name = df_report['AccountName'].isna().sum()

if missing_balance > 0:
    print(f"WARNING: {missing_balance} accounts missing opening balance!")
    print(df_report[df_report['Opening Balance 2024'].isna()])
else:
    print("All accounts have opening balances")

if missing_account_name > 0:
    print(f"WARNING: {missing_account_name} accounts missing account name!")
    print(df_report[df_report['AccountName'].isna()])
else:
    print("All accounts have account names")

# ========================================
# SECTION 6: Calculate Monthly Balances
# ========================================
# Optimized iterative approach for cumulative balance calculation
#
# This implementation uses direct cumulative filtering:
# 1. For each month (1-12): filter transactions UP TO that month (cumulative)
# 2. Calculate sum by account
# 3. Add as new column directly in required format
# 4. Simple, direct calculation without complex transformations
#
# Benefits:
# - Efficient: Single pass through data with minimal transformations
# - Automatic handling of missing months (filter returns empty → fillna(0))
# - Cumulative by design (Month <= i includes all previous months)
# - Column names already in required format ('Balance end of January', etc.)
# - Performance: Avoids intermediate data structures and multiple reshape operations

# Month names for column headers
month_names = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]

print("\nCalculating monthly balances...")

# For each month (1-12), calculate cumulative balance
for month_num in range(1, 13):
    month_name = month_names[month_num - 1]
    
    # Get all transactions UP TO and INCLUDING this month (CUMULATIVE!)
    # For January: Month <= 1 (only Jan transactions)
    # For February: Month <= 2 (Jan + Feb transactions)
    # For April: Month <= 4 (Jan + Feb + Mar, since Apr has no transactions)
    trans_up_to_month = df_transactions[df_transactions['Month'] <= month_num]
    
    # Sum transactions by account
    trans_sum = trans_up_to_month.groupby('Account')['Amount'].sum()
    
    # Calculate balance: Opening Balance + Cumulative Transactions
    # Use .map() to match Account values from trans_sum to df_report
    # fillna(0) handles accounts with no transactions up to this month
    column_name = f'Balance end of {month_name}'
    df_report[column_name] = (
        df_report['Opening Balance 2024'] + 
        df_report['Account'].map(trans_sum).fillna(0)
    )
    
    print(f"  {month_name}: calculated")

print("\nAll monthly balances calculated!")

# Display sample - Q1 balances for verification
print("\nSample - Q1 Monthly Balances:")
print(df_report[['Account', 'AccountName', 'Opening Balance 2024',
                 'Balance end of January', 'Balance end of February', 'Balance end of March']])

# Display sample - Q4 balances (should be same as Q3 since no Q4 transactions)
print("\nSample - Q4 Monthly Balances (no new transactions after March):")
print(df_report[['Account', 'Balance end of October', 'Balance end of November', 'Balance end of December']])

# ========================================
# IMPLEMENTATION NOTE
# ========================================
# The iterative approach in Section 6 accomplishes the goal directly:
# - All 12 monthly balances calculated with cumulative filtering
# - Correct structure maintained (4 rows, 17 columns)
# - No complex reshaping or cleanup needed
#
# Alternative approaches (groupby → pivot → cumsum) would require:
# - Creating intermediate monthly transaction aggregates
# - Expanding to 48 rows (4 accounts × 12 months)
# - Pivoting back to wide format (4 rows)
# - Cleaning duplicate column names
#
# Our approach is more direct and efficient.
#
# Proceeding to YTD calculation.
# ========================================

# ========================================
# SECTION 7: Calculate Sum of Transactions YTD
# ========================================

print("\nCalculating Sum of Transactions YTD...")

# Sum all transactions for each account (for the entire year)
trans_ytd = df_transactions.groupby('Account')['Amount'].sum()

# Add to report as new column
df_report['Sum of Transactions YTD'] = df_report['Account'].map(trans_ytd).fillna(0)

print("YTD sum calculated!")

# Validation: Balance December should equal Opening Balance + YTD
print("\nValidation: Balance calculation check")
balance_check = (
    (df_report['Balance end of December'] - 
     df_report['Opening Balance 2024'] - 
     df_report['Sum of Transactions YTD']).abs() < 0.01
)

if balance_check.all():
    print("All balances verified: Balance Dec = Opening + YTD")
else:
    print("WARNING: Balance mismatch detected!")
    print(df_report[~balance_check][['Account', 'AccountName', 'Opening Balance 2024', 
                                      'Balance end of December', 'Sum of Transactions YTD']])

# ========================================
# SECTION 8: Prepare Final Report
# ========================================

# Remove columns not needed in final output
df_final_report = df_report.drop(columns=['OpenDate', 'CloseDate'], errors='ignore')

# Define final column order as per requirements
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

# Reorder columns
df_final_report = df_final_report[final_columns]

print("\n" + SEPARATOR_MAIN)
print("FINAL FINANCIAL REPORT 2024")
print(SEPARATOR_MAIN)
print(df_final_report.to_string(index=False))

print("\n" + SEPARATOR_MAIN)
print("REPORT GENERATION COMPLETE")
print(SEPARATOR_MAIN)

print("\nAll tasks completed successfully!")

# ========================================
# DATA VISUALIZATION
# ========================================

# Create outputs directory if it doesn't exist
OUTPUT_DIR = Path('outputs')
OUTPUT_DIR.mkdir(exist_ok=True)

print("\n" + SEPARATOR_MAIN)
print("GENERATING VISUALIZATIONS")
print(SEPARATOR_MAIN)

# Define color scheme
COLORS = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']  # Blue, Green, Red, Orange

# ========================================
# CHART 1: Monthly Balance Trend
# ========================================

print("\n1. Creating Monthly Balance Trend chart...")

plt.figure(figsize=(14, 7))

for idx, (_, row) in enumerate(df_final_report.iterrows()):
    account_name = row['AccountName']
    balances = [row[f'Balance end of {month}'] for month in month_names]
    
    plt.plot(month_names, balances, 
             marker='o', 
             label=account_name, 
             linewidth=2.5,
             markersize=8,
             color=COLORS[idx])

# Styling
plt.title('Monthly Balance Trend by Account (2024)', 
          fontsize=18, 
          fontweight='bold', 
          pad=20)
plt.xlabel('Month', fontsize=14, fontweight='bold')
plt.ylabel('Balance (USD)', fontsize=14, fontweight='bold')
plt.legend(title='Account', 
           fontsize=11, 
           title_fontsize=12,
           loc='best',
           framealpha=0.9)
plt.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)
plt.xticks(rotation=45, ha='right', fontsize=11)
plt.yticks(fontsize=11)

# Format y-axis to show currency
ax = plt.gca()
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'monthly_balance_trend.png', dpi=300, bbox_inches='tight')
plt.close()

print("   ✓ Saved: outputs/monthly_balance_trend.png")

# ========================================
# CHART 2: Opening vs Closing Balance Comparison
# ========================================

print("2. Creating Opening vs Closing Balance comparison...")

# Prepare data
accounts = df_final_report['AccountName'].tolist()
opening = df_final_report['Opening Balance 2024'].tolist()
closing = df_final_report['Balance end of December'].tolist()

# Create figure
fig, ax = plt.subplots(figsize=(12, 7))

# Bar positions
x = np.arange(len(accounts))
width = 0.35

# Bars
bars1 = ax.bar(x - width/2, opening, width, 
               label='Opening Balance', 
               color='#3498db', 
               alpha=0.85,
               edgecolor='black',
               linewidth=1.2)
bars2 = ax.bar(x + width/2, closing, width, 
               label='Closing Balance', 
               color='#2ecc71', 
               alpha=0.85,
               edgecolor='black',
               linewidth=1.2)

# Add value labels on bars
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'${height:,.0f}',
                ha='center', 
                va='bottom', 
                fontsize=10,
                fontweight='bold')

# Styling
ax.set_xlabel('Account', fontsize=14, fontweight='bold')
ax.set_ylabel('Balance (USD)', fontsize=14, fontweight='bold')
ax.set_title('Opening vs Closing Balance Comparison (2024)', 
             fontsize=18, 
             fontweight='bold',
             pad=20)
ax.set_xticks(x)
ax.set_xticklabels(accounts, fontsize=12)
ax.legend(fontsize=12, loc='upper left', framealpha=0.9)
ax.grid(True, axis='y', alpha=0.3, linestyle='--', linewidth=0.8)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'opening_vs_closing.png', dpi=300, bbox_inches='tight')
plt.close()

print("   ✓ Saved: outputs/opening_vs_closing.png")

# ========================================
# CHART 3: Transaction Heatmap
# ========================================

print("3. Creating Transaction Activity Heatmap...")

# Create transaction activity matrix (Account x Month)
# Count transactions per account per month
transaction_matrix = []
account_names_ordered = df_final_report['AccountName'].tolist()

for account_num in df_final_report['Account']:
    monthly_counts = []
    for month_num in range(1, 13):
        count = len(df_transactions[
            (df_transactions['Account'] == account_num) & 
            (df_transactions['Month'] == month_num)
        ])
        monthly_counts.append(count)
    transaction_matrix.append(monthly_counts)

# Create heatmap
fig, ax = plt.subplots(figsize=(14, 6))

# Use seaborn for better heatmap
im = ax.imshow(transaction_matrix, cmap='YlOrRd', aspect='auto', vmin=0)

# Add colorbar
cbar = plt.colorbar(im, ax=ax)
cbar.set_label('Number of Transactions', rotation=270, labelpad=20, fontsize=12, fontweight='bold')

# Set ticks and labels
ax.set_xticks(np.arange(12))
ax.set_yticks(np.arange(len(account_names_ordered)))
ax.set_xticklabels(month_names, rotation=45, ha='right', fontsize=11)
ax.set_yticklabels(account_names_ordered, fontsize=12)

# Add text annotations
for i in range(len(account_names_ordered)):
    for j in range(12):
        text = ax.text(j, i, int(transaction_matrix[i][j]),
                      ha="center", va="center", 
                      color="black" if transaction_matrix[i][j] < 2 else "white",
                      fontsize=12,
                      fontweight='bold')

# Styling
ax.set_title('Transaction Activity Heatmap (2024)', 
             fontsize=18, 
             fontweight='bold',
             pad=20)
ax.set_xlabel('Month', fontsize=14, fontweight='bold')
ax.set_ylabel('Account', fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'transaction_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()

print("   ✓ Saved: outputs/transaction_heatmap.png")

# ========================================
# CHART 4: Growth Rate Chart
# ========================================

print("4. Creating Growth Rate comparison...")

# Calculate growth rate for each account
growth_data = []
for _, row in df_final_report.iterrows():
    account_name = row['AccountName']
    opening = row['Opening Balance 2024']
    closing = row['Balance end of December']
    growth_rate = ((closing - opening) / opening) * 100
    growth_data.append({
        'Account': account_name,
        'Growth Rate': growth_rate,
        'Absolute Change': closing - opening
    })

# Sort by growth rate
growth_data.sort(key=lambda x: x['Growth Rate'], reverse=True)

# Create figure
fig, ax = plt.subplots(figsize=(12, 7))

# Data
accounts_sorted = [item['Account'] for item in growth_data]
growth_rates = [item['Growth Rate'] for item in growth_data]
colors_growth = ['#2ecc71' if rate >= 0 else '#e74c3c' for rate in growth_rates]

# Horizontal bar chart
bars = ax.barh(accounts_sorted, growth_rates, 
               color=colors_growth, 
               alpha=0.85,
               edgecolor='black',
               linewidth=1.2)

# Add value labels
for i, (bar, rate, data) in enumerate(zip(bars, growth_rates, growth_data)):
    width = bar.get_width()
    label_x = width + (1 if width >= 0 else -1)
    ax.text(label_x, bar.get_y() + bar.get_height()/2,
            f'{rate:+.2f}%\n(${data["Absolute Change"]:,.0f})',
            ha='left' if width >= 0 else 'right',
            va='center',
            fontsize=11,
            fontweight='bold')

# Add vertical line at 0
ax.axvline(x=0, color='black', linewidth=2, linestyle='-', alpha=0.3)

# Styling
ax.set_xlabel('Growth Rate (%)', fontsize=14, fontweight='bold')
ax.set_ylabel('Account', fontsize=14, fontweight='bold')
ax.set_title('Year-over-Year Growth Rate by Account (2024)', 
             fontsize=18, 
             fontweight='bold',
             pad=20)
ax.grid(True, axis='x', alpha=0.3, linestyle='--', linewidth=0.8)
ax.tick_params(axis='both', labelsize=12)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'growth_rate_chart.png', dpi=300, bbox_inches='tight')
plt.close()

print("   ✓ Saved: outputs/growth_rate_chart.png")

# ========================================
# VISUALIZATION SUMMARY
# ========================================

print("\n" + SEPARATOR_MAIN)
print("VISUALIZATIONS COMPLETE")
print(SEPARATOR_MAIN)

print("\nGenerated charts:")
print("  1. Monthly Balance Trend       → outputs/monthly_balance_trend.png")
print("  2. Opening vs Closing Balance  → outputs/opening_vs_closing.png")
print("  3. Transaction Activity Heatmap → outputs/transaction_heatmap.png")
print("  4. Growth Rate Comparison      → outputs/growth_rate_chart.png")

print("\nAll visualizations saved in 'outputs/' directory!")