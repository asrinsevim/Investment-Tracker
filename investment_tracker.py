# investment_tracker.py
# Final version supporting both automatic and manual value entries.
# This version does not send emails and only updates Google Sheets.

import pandas as pd
import yfinance as yf
from tefas import Crawler
from datetime import datetime, timedelta
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import time

# --- Configuration for Google Sheets ---
CREDENTIALS_FILE = "credentials.json"
INVESTMENTS_SHEET_NAME = "My_Investments"
PERFORMANCE_SHEET_NAME = "Performance_Log"
ASSETS_WORKSHEET_NAME = "Assets"
LOG_WORKSHEET_NAME = "Daily_Log"

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
    """Fetches the latest price for a TEFAS fund."""
    date_to_try = datetime.now() - timedelta(days=1)
    for _ in range(5):
        try:
            data = tefas_crawler.fetch(start=date_to_try.strftime('%Y-%m-%d'), end=date_to_try.strftime('%Y-%m-%d'), code=ticker, columns=['date', 'price'])
            if not data.empty:
                return data['price'].iloc[-1]
        except:
            pass
        date_to_try -= timedelta(days=1)
    print(f"ERROR: Could not fetch TEFAS price for {ticker} in the last 5 days.")
    return None

def calculate_time_deposit_value(principal, annual_rate, start_date_str):
    """Calculates the current value of a time deposit account with simple interest."""
    try:
        start_date_obj = pd.to_datetime(start_date_str).to_pydatetime()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if start_date_obj > today: return principal
        days_passed = (today - start_date_obj).days
        daily_rate = annual_rate / 365 / 100
        interest_earned = principal * daily_rate * days_passed
        return principal + interest_earned
    except Exception as e:
        print(f"ERROR: Could not calculate time deposit value. Error: {e}")
        return principal

def update_performance_log(gc, daily_data_row):
    """Writes or updates the daily performance data to the Google Sheet log."""
    try:
        sheet = gc.open(PERFORMANCE_SHEET_NAME)
        try:
            worksheet = sheet.worksheet(LOG_WORKSHEET_NAME)
            df = get_as_dataframe(worksheet).dropna(how='all')
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=LOG_WORKSHEET_NAME, rows="100", cols="20")
            df = pd.DataFrame(columns=daily_data_row.keys())

        today_str = daily_data_row['Date']
        if 'Date' in df.columns:
            df = df[df.Date != today_str]

        new_row_df = pd.DataFrame([daily_data_row])
        df = pd.concat([df, new_row_df], ignore_index=True).sort_values(by='Date', ascending=False)
        worksheet.clear()
        set_with_dataframe(worksheet, df)
        print(f"'{PERFORMANCE_SHEET_NAME}' was successfully updated.")
    except Exception as e:
        print(f"ERROR: Failed to update the performance log. Error: {e}")

def main():
    """Main function to run the tracker."""
    print("Starting the Investment Tracker script...")
    gc = connect_to_google_sheets()
    if not gc: return

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

    usd_try_rate = get_fx_rate('USD')
    if not usd_try_rate:
        print("CRITICAL ERROR: Cannot proceed without FX rate.")
        return

    processed_rows = []
    for index, row in assets_df.iterrows():
        current_row = row.to_dict()
        current_value_try = 0; total_cost_try = 0

        if 'Manual_Current_Value' in row and row['Manual_Current_Value'] > 0:
            print(f"Processing Manual Entry: {row.get('Ticker', 'N/A')}")
            manual_value = row['Manual_Current_Value']
            current_value_try = manual_value * usd_try_rate if row['Currency'] == 'USD' else manual_value
            total_cost_try = row['Manual_Total_Cost_TRY'] if 'Manual_Total_Cost_TRY' in row else 0
        else:
            asset_type = row['Asset_Type']; ticker = row['Ticker']; quantity = row['Quantity']; purchase_price = row['Purchase_Price']
            print(f"Processing Auto Fetch: {ticker} ({asset_type})")
            time.sleep(0.5)
            price = 0
            
            if asset_type in ['Stock (US)', 'Crypto', 'Döviz']:
                price_data = yf.Ticker(ticker).history(period="1d")
                if not price_data.empty: price = price_data['Close'].iloc[0]
            elif asset_type == 'Fund (TEFAS)':
                price = get_tefas_price(ticker)
            elif asset_type == 'Time Deposit':
                current_value_try = calculate_time_deposit_value(quantity, row['Annual_Interest_Rate'], row['Start_Date'])
            
            if asset_type != 'Time Deposit' and price is not None and price > 0:
                current_value_try = quantity * price
                if row['Currency'] == 'USD': current_value_try *= usd_try_rate
            
            total_cost_try = quantity * purchase_price
            if row['Currency'] == 'USD': total_cost_try *= usd_try_rate
        
        current_row['Current_Value_TRY'] = current_value_try
        current_row['Total_Cost_TRY'] = total_cost_try
        current_row['Profit_Loss_TRY'] = current_value_try - total_cost_try
        processed_rows.append(current_row)

    final_df = pd.DataFrame(processed_rows)
    total_current_value = final_df['Current_Value_TRY'].sum()
    total_cost = final_df['Total_Cost_TRY'].sum()
    total_profit_loss = final_df['Profit_Loss_TRY'].sum()
    total_return_pct = (total_profit_loss / total_cost) * 100 if total_cost != 0 else 0

    today_data = {'Date': datetime.now().strftime('%Y-%m-%d'), 'Total_Value_TRY': total_current_value, 'Total_Cost_TRY': total_cost, 'Total_Profit_Loss_TRY': total_profit_loss, 'Total_Return_Pct': total_return_pct}
    update_performance_log(gc, today_data)

    print("\n--- PORTFOLIO SUMMARY ---"); print(f"Total Current Value: {total_current_value:,.2f} TRY"); print(f"Total Cost:          {total_cost:,.2f} TRY"); print(f"Total Profit/Loss:   {total_profit_loss:,.2f} TRY"); print(f"Total Return:        {total_return_pct:.2f}%"); print("-------------------------\n"); print("Script finished successfully.")

if __name__ == "__main__":
    main()