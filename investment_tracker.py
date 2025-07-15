# investment_tracker.py
# Final version with support for automatic and manual value entries,
# and detailed 1D, 1W, 1M performance tracking for each asset.
# This version logs data to Google Sheets and does not send emails.

import pandas as pd
import yfinance as yf
from tefas import Crawler
from datetime import datetime, timedelta
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import time
import numpy as np

# --- Configuration for Google Sheets ---
CREDENTIALS_FILE = "credentials.json"
INVESTMENTS_SHEET_NAME = "My_Investments"
PERFORMANCE_SHEET_NAME = "Performance_Log"
ASSETS_WORKSHEET_NAME = "Assets"
LOG_WORKSHEET_NAME = "Daily_Log" # Logs the history of each asset

# --- Global variables ---
currency_cache = {}
tefas_crawler = Crawler()

def connect_to_google_sheets():
    """Connects to Google Sheets using service account credentials."""
    try:
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        print("Successfully connected to Google Sheets.")
        return gc
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to Google Sheets. Check your '{CREDENTIALS_FILE}' file and API permissions. Error: {e}")
        return None

def get_fx_rate(currency='USD'):
    """Fetches and caches the foreign exchange rate to TRY."""
    if currency in currency_cache:
        return currency_cache[currency]
    try:
        ticker = f"{currency}TRY=X"
        rate = yf.Ticker(ticker).history(period="1d")['Close'].iloc[0]
        currency_cache[currency] = rate
        print(f"Current {currency}/TRY rate: {rate:.4f}")
        return rate
    except Exception as e:
        print(f"ERROR: Could not fetch FX rate for {currency}. Error: {e}")
        return None

def get_tefas_price(ticker):
    """Fetches the latest price for a TEFAS fund by checking the last 5 days."""
    date_to_try = datetime.now() - timedelta(days=1)
    for _ in range(5):
        try:
            data = tefas_crawler.fetch(start=date_to_try.strftime('%Y-%m-%d'), end=date_to_try.strftime('%Y-%m-%d'), code=ticker, columns=['date', 'price'])
            if not data.empty:
                return data['price'].iloc[-1]
        except Exception:
            pass # Ignore error for a single day and try the previous one
        date_to_try -= timedelta(days=1)
    print(f"ERROR: Could not fetch TEFAS price for {ticker} in the last 5 days.")
    return None

def calculate_time_deposit_value(principal, annual_rate, start_date_str):
    """Calculates the current value of a time deposit account with simple interest."""
    try:
        start_date_obj = pd.to_datetime(start_date_str).to_pydatetime()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if start_date_obj > today:
            return principal
        days_passed = (today - start_date_obj).days
        daily_rate = annual_rate / 365 / 100
        interest_earned = principal * daily_rate * days_passed
        return principal + interest_earned
    except Exception as e:
        print(f"ERROR: Could not calculate time deposit value for Start Date '{start_date_str}'. Error: {e}")
        return principal

def calculate_individual_performance(history_df, ticker, current_value):
    """Calculates 1D, 1W, and 1M performance for a single asset."""
    # Default values
    performance = { '1D_Return_%': 0.0, '1W_Return_%': 0.0, '1M_Return_%': 0.0, '1D_Return_TRY': 0.0, '1W_Return_TRY': 0.0, '1M_Return_TRY': 0.0 }
    if history_df.empty:
        return performance

    asset_history = history_df[history_df['Ticker'] == ticker].sort_values(by='Date', ascending=False)
    if asset_history.empty:
        return performance

    def get_past_value(days):
        target_date = pd.to_datetime('today').normalize() - timedelta(days=days)
        past_data = asset_history[asset_history['Date'] <= target_date]
        return past_data['Current_Value_TRY'].iloc[0] if not past_data.empty else np.nan

    val_1d_ago = get_past_value(1)
    val_7d_ago = get_past_value(7)
    val_30d_ago = get_past_value(30)

    last_known_value = asset_history['Current_Value_TRY'].iloc[0]
    val_1d_ago = val_1d_ago if pd.notna(val_1d_ago) else last_known_value
    val_7d_ago = val_7d_ago if pd.notna(val_7d_ago) else last_known_value
    val_30d_ago = val_30d_ago if pd.notna(val_30d_ago) else last_known_value

    performance['1D_Return_TRY'] = current_value - val_1d_ago if pd.notna(val_1d_ago) else 0.0
    performance['1W_Return_TRY'] = current_value - val_7d_ago if pd.notna(val_7d_ago) else 0.0
    performance['1M_Return_TRY'] = current_value - val_30d_ago if pd.notna(val_30d_ago) else 0.0
    
    performance['1D_Return_%'] = (performance['1D_Return_TRY'] / val_1d_ago) * 100 if pd.notna(val_1d_ago) and val_1d_ago != 0 else 0.0
    performance['1W_Return_%'] = (performance['1W_Return_TRY'] / val_7d_ago) * 100 if pd.notna(val_7d_ago) and val_7d_ago != 0 else 0.0
    performance['1M_Return_%'] = (performance['1M_Return_TRY'] / val_30d_ago) * 100 if pd.notna(val_30d_ago) and val_30d_ago != 0 else 0.0
    
    return performance

def update_performance_log(gc, current_assets_df):
    """Appends the current state of all assets to the historical log."""
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        log_df = current_assets_df[['Ticker', 'Current_Value_TRY']].copy()
        log_df['Date'] = today_str

        sheet = gc.open(PERFORMANCE_SHEET_NAME)
        try:
            worksheet = sheet.worksheet(LOG_WORKSHEET_NAME)
            history_df = get_as_dataframe(worksheet, evaluate_formulas=True).dropna(how='all')
            if 'Date' in history_df.columns:
                history_df = history_df[history_df['Date'] != today_str]
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=LOG_WORKSHEET_NAME, rows="1000", cols="5")
            history_df = pd.DataFrame()

        combined_df = pd.concat([history_df, log_df], ignore_index=True)
        worksheet.clear()
        set_with_dataframe(worksheet, combined_df)
        print(f"'{PERFORMANCE_SHEET_NAME}' was successfully updated with daily asset details.")
        return history_df
    except Exception as e:
        print(f"ERROR: Failed to update the performance log. Error: {e}")
        return pd.DataFrame()

def main():
    """Main function to run the tracker."""
    print("Starting the Investment Tracker script...")
    gc = connect_to_google_sheets()
    if not gc: return

    # 1. Read and clean master investment data
    try:
        investments_sheet = gc.open(INVESTMENTS_SHEET_NAME)
        assets_worksheet = investments_sheet.worksheet(ASSETS_WORKSHEET_NAME)
        assets_df = get_as_dataframe(assets_worksheet, header=0).dropna(how='all')
        
        numeric_cols = ['Quantity', 'Purchase_Price', 'Annual_Interest_Rate', 'Manual_Current_Value', 'Manual_Total_Cost_TRY']
        for col in numeric_cols:
            if col in assets_df.columns:
                assets_df[col] = pd.to_numeric(assets_df[col], errors='coerce')
        assets_df = assets_df.fillna(0)
        print("Successfully loaded and cleaned asset data.")
    except Exception as e:
        print(f"ERROR: Could not read '{INVESTMENTS_SHEET_NAME}'. Check columns and permissions. Error: {e}")
        return

    # 2. Read historical performance data BEFORE calculations
    history_df = pd.DataFrame()
    try:
        sheet = gc.open(PERFORMANCE_SHEET_NAME)
        worksheet = sheet.worksheet(LOG_WORKSHEET_NAME)
        history_df = get_as_dataframe(worksheet, evaluate_formulas=True).dropna(how='all')
        if not history_df.empty:
            history_df['Date'] = pd.to_datetime(history_df['Date'])
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        print("Performance log not found. Will be created.")
    except Exception as e:
        print(f"Could not read performance history: {e}")

    # 3. Fetch FX rate
    usd_try_rate = get_fx_rate('USD')
    if not usd_try_rate:
        print("CRITICAL ERROR: Cannot proceed without FX rate.")
        return

    # 4. Process each asset to calculate its current state and performance
    processed_rows = []
    for index, row in assets_df.iterrows():
        current_row = row.to_dict()
        current_value_try = 0.0
        total_cost_try = 0.0

        if 'Manual_Current_Value' in row and row['Manual_Current_Value'] > 0:
            print(f"Processing Manual Entry: {row.get('Ticker', 'N/A')}")
            manual_value = row['Manual_Current_Value']
            current_value_try = manual_value * usd_try_rate if row['Currency'] == 'USD' else manual_value
            total_cost_try = row['Manual_Total_Cost_TRY'] if 'Manual_Total_Cost_TRY' in row else 0
        else:
            asset_type = row.get('Asset_Type', '')
            ticker = row.get('Ticker', '')
            quantity = row.get('Quantity', 0)
            purchase_price = row.get('Purchase_Price', 0)
            print(f"Processing Auto Fetch: {ticker} ({asset_type})")
            time.sleep(0.5)

            price = 0
            if asset_type in ['Stock (US)', 'Crypto', 'FX']: # 'Döviz' type translated to 'FX'
                try:
                    price_data = yf.Ticker(ticker).history(period="1d")
                    if not price_data.empty: price = price_data['Close'].iloc[0]
                except Exception as e:
                    print(f"Could not fetch yfinance price for {ticker}: {e}")
            elif asset_type == 'Fund (TEFAS)':
                price = get_tefas_price(ticker)
            elif asset_type == 'Time Deposit':
                current_value_try = calculate_time_deposit_value(quantity, row.get('Annual_Interest_Rate', 0), row.get('Start_Date', ''))
            
            if asset_type != 'Time Deposit':
                if price is not None and price > 0:
                    current_value_try = quantity * price
                    if row['Currency'] == 'USD':
                        current_value_try *= usd_try_rate
            
            total_cost_try = quantity * purchase_price
            if row['Currency'] == 'USD':
                total_cost_try *= usd_try_rate
        
        performance_data = calculate_individual_performance(history_df, row['Ticker'], current_value_try)
        
        current_row.update({
            'Current_Value_TRY': current_value_try,
            'Total_Cost_TRY': total_cost_try,
            'Profit_Loss_TRY': current_value_try - total_cost_try,
            **performance_data
        })
        processed_rows.append(current_row)

    # 5. Create the final DataFrame for today's view and calculate totals
    final_df = pd.DataFrame(processed_rows)
    total_current_value = final_df['Current_Value_TRY'].sum()
    total_cost = final_df['Total_Cost_TRY'].sum()
    total_profit_loss = total_current_value - total_cost
    total_return_pct = (total_profit_loss / total_cost) * 100 if total_cost != 0 else 0

    # 6. Update the performance log with today's values for future calculations
    update_performance_log(gc, final_df)

    # 7. Print summaries to the console
    print("\n--- PORTFOLIO SUMMARY ---")
    print(f"Total Current Value: {total_current_value:,.2f} TRY")
    print(f"Total Cost:          {total_cost:,.2f} TRY")
    print(f"Total Profit/Loss:   {total_profit_loss:,.2f} TRY")
    print(f"Total Return:        {total_return_pct:.2f}%")
    print("-------------------------\n")
    
    print("--- INDIVIDUAL ASSET PERFORMANCE ---")
    display_cols = [
        'Ticker', 'Current_Value_TRY', 'Profit_Loss_TRY', 
        '1D_Return_%', '1D_Return_TRY', 
        '1W_Return_%', '1W_Return_TRY', 
        '1M_Return_%', '1M_Return_TRY'
    ]
    # Ensure all display columns exist before trying to display them
    display_cols_exist = [col for col in display_cols if col in final_df.columns]
    performance_view = final_df[display_cols_exist].copy()
    
    # Format the output for better readability
    for col in performance_view.columns:
        if '_%' in col:
            performance_view[col] = performance_view[col].map('{:+.2f}%'.format)
        elif '_TRY' in col or 'Value' in col:
            performance_view[col] = performance_view[col].map('{:,.2f} TRY'.format)

    print(performance_view.to_string(index=False))
    print("\nScript finished successfully.")

if __name__ == "__main__":
    main()
