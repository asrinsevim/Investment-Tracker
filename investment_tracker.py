# investment_tracker.py
# Final version with individual asset performance tracking (1D, 1W, 1M).

import pandas as pd
import yfinance as yf
from tefas import Crawler
from datetime import datetime, timedelta
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import time
import numpy as np

# --- Configuration remains the same ---
CREDENTIALS_FILE = "credentials.json"
INVESTMENTS_SHEET_NAME = "My_Investments"
PERFORMANCE_SHEET_NAME = "Performance_Log"
ASSETS_WORKSHEET_NAME = "Assets"
LOG_WORKSHEET_NAME = "Daily_Asset_History" # YENİ: Kayıt sayfasının adı daha anlamlı hale getirildi.

# --- Helper functions remain the same ---
# connect_to_google_sheets, get_fx_rate, get_tefas_price, calculate_time_deposit_value...

# YENİ: Her bir varlığın geçmiş performansını hesaplayan fonksiyon
def calculate_individual_performance(history_df, ticker, current_value, quantity):
    """Calculates 1D, 1W, and 1M performance for a single asset."""
    if history_df.empty or quantity == 0:
        return { '1D_Return_%': 0, '1W_Return_%': 0, '1M_Return_%': 0, '1D_Return_TRY': 0, '1W_Return_TRY': 0, '1M_Return_TRY': 0 }

    # Filter history for the specific asset
    asset_history = history_df[history_df['Ticker'] == ticker].sort_values(by='Date', ascending=False)
    if asset_history.empty:
        return { '1D_Return_%': 0, '1W_Return_%': 0, '1M_Return_%': 0, '1D_Return_TRY': 0, '1W_Return_TRY': 0, '1M_Return_TRY': 0 }

    # Helper to find the closest previous value
    def get_past_value(days):
        target_date = pd.to_datetime('today') - timedelta(days=days)
        past_data = asset_history[asset_history['Date'] <= target_date]
        return past_data['Current_Value_TRY'].iloc[0] if not past_data.empty else np.nan

    # Get past values
    val_1d_ago = get_past_value(1)
    val_7d_ago = get_past_value(7)
    val_30d_ago = get_past_value(30)

    # Fallback to the most recent value if a specific period is not available
    last_known_value = asset_history['Current_Value_TRY'].iloc[0]
    val_1d_ago = val_1d_ago if pd.notna(val_1d_ago) else last_known_value
    val_7d_ago = val_7d_ago if pd.notna(val_7d_ago) else last_known_value
    val_30d_ago = val_30d_ago if pd.notna(val_30d_ago) else last_known_value

    # Calculate returns
    return {
        '1D_Return_%': ((current_value / val_1d_ago) - 1) * 100 if val_1d_ago else 0,
        '1W_Return_%': ((current_value / val_7d_ago) - 1) * 100 if val_7d_ago else 0,
        '1M_Return_%': ((current_value / val_30d_ago) - 1) * 100 if val_30d_ago else 0,
        '1D_Return_TRY': current_value - val_1d_ago if val_1d_ago else 0,
        '1W_Return_TRY': current_value - val_7d_ago if val_7d_ago else 0,
        '1M_Return_TRY': current_value - val_30d_ago if val_30d_ago else 0
    }

# GÜNCELLENDİ: Performans log fonksiyonu artık tüm varlıkların güncel durumunu kaydediyor
def update_performance_log(gc, current_assets_df):
    """Appends the current state of all assets to the historical log."""
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        # Add date column to the current data
        log_df = current_assets_df[['Ticker', 'Current_Value_TRY']].copy()
        log_df['Date'] = today_str

        sheet = gc.open(PERFORMANCE_SHEET_NAME)
        try:
            worksheet = sheet.worksheet(LOG_WORKSHEET_NAME)
            history_df = get_as_dataframe(worksheet).dropna(how='all')
            if 'Date' in history_df.columns:
                # Remove today's data to prevent duplicates on re-run
                history_df = history_df[history_df['Date'] != today_str]
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=LOG_WORKSHEET_NAME, rows="1000", cols="5")
            history_df = pd.DataFrame(columns=['Date', 'Ticker', 'Current_Value_TRY'])

        # Combine old and new data
        combined_df = pd.concat([history_df, log_df], ignore_index=True)
        worksheet.clear()
        set_with_dataframe(worksheet, combined_df)
        print(f"'{PERFORMANCE_SHEET_NAME}' was successfully updated with daily asset details.")
        return history_df # Return the old history for performance calculation
    except Exception as e:
        print(f"ERROR: Failed to update the performance log. Error: {e}")
        return pd.DataFrame() # Return empty dataframe on error


def main():
    """Main function to run the tracker."""
    gc = connect_to_google_sheets()
    if not gc: return

    # 1. Read asset data (same as before)
    # ...

    # YENİ: Önce geçmiş verileri oku
    history_df = pd.DataFrame()
    try:
        sheet = gc.open(PERFORMANCE_SHEET_NAME)
        worksheet = sheet.worksheet(LOG_WORKSHEET_NAME)
        history_df = get_as_dataframe(worksheet).dropna(how='all')
        if not history_df.empty:
            history_df['Date'] = pd.to_datetime(history_df['Date'])
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        print("Performance log not found. Will be created.") # Log not found, will be created later
    except Exception as e:
        print(f"Could not read performance history: {e}")

    # 2. Process each asset (same as before to get current value)
    # ...
    # This loop now also calculates performance for each asset
    processed_rows = []
    for index, row in assets_df.iterrows():
        # ... (Önceki kodda olduğu gibi current_value_try ve total_cost_try hesaplanır)
        
        # YENİ: Her varlık için bireysel performansı hesapla
        performance_data = calculate_individual_performance(history_df, row['Ticker'], current_value_try, row['Quantity'])

        # ... (Hesaplanan değerleri ve performans verilerini birleştir)
        current_row = row.to_dict()
        current_row['Current_Value_TRY'] = current_value_try
        current_row['Total_Cost_TRY'] = total_cost_try
        current_row['Profit_Loss_TRY'] = current_value_try - total_cost_try
        current_row.update(performance_data) # Add performance data to the row
        processed_rows.append(current_row)

    # 3. Create the final DataFrame
    final_df = pd.DataFrame(processed_rows)

    # 4. Update the Performance Log with today's data
    update_performance_log(gc, final_df)

    # 5. Print summary to console
    print("\n--- PORTFOLIO SUMMARY ---")
    # ... (Genel özet aynı kalabilir)

    print("\n--- INDIVIDUAL ASSET PERFORMANCE ---")
    # YENİ: Detaylı performans tablosunu göster
    display_cols = [
        'Ticker', 'Current_Value_TRY', 'Profit_Loss_TRY', 
        '1D_Return_%', '1D_Return_TRY', 
        '1W_Return_%', '1W_Return_TRY', 
        '1M_Return_%', '1M_Return_TRY'
    ]
    # Sadece ilgili sütunları göster ve formatla
    performance_view = final_df[display_cols].copy()
    for col in performance_view.columns:
        if '_%' in col:
            performance_view[col] = performance_view[col].map('{:,.2f}%'.format)
        elif '_TRY' in col or 'Value' in col:
            performance_view[col] = performance_view[col].map('{:,.2f}'.format)
            
    print(performance_view.to_string())

    print("\nScript finished successfully.")


# connect_to_google_sheets, get_fx_rate, get_tefas_price, calculate_time_deposit_value
# ve ana 'if __name__ == "__main__":' bloğu gibi diğer fonksiyonları da eklemeyi unutmayın.
# Bu örnek, ana mantıktaki büyük değişiklikleri göstermektedir.
