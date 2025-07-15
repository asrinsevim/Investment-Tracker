Automated Investment Portfolio Tracker
A Python-based, fully automated script that tracks a multi-asset investment portfolio using Google Sheets. It runs daily via GitHub Actions to fetch live market data, calculate portfolio value, track historical performance, and generate detailed daily reports.

Key Features
Multi-Asset Tracking: Supports stocks (US, TR), cryptocurrencies, TEFAS funds, foreign exchange (FX), time deposits, and manually entered asset values.

Live Market Data: Fetches real-time prices and foreign exchange rates using yfinance and tefas-crawler APIs.

Google Sheets Integration: Uses Google Sheets as a database for both input (My_Investments) and historical logging (Performance_Log).

Detailed Performance Metrics: Automatically calculates and reports the 1-Day, 1-Week, and 1-Month return for each asset, in both percentage (%) and absolute TRY value.

Cloud-Based Automation: Runs on a daily schedule using GitHub Actions, making it completely independent of a local machine.

Robust and Resilient: Designed to handle API errors, and missing historical data, and includes a secure method for handling credentials.

How It Works
The workflow is straightforward and fully automated:

Scheduled Trigger: A GitHub Actions workflow runs on a daily schedule (cron).

Secure Authentication: The script securely authenticates with Google APIs using a service account key stored in GitHub Secrets.

Read Portfolio: It reads the list of assets from your My_Investments Google Sheet.

Fetch & Calculate: For each asset, it fetches the latest market price, calculates its current value in TRY, and determines its total cost basis. For manual entries, it uses the user-provided values.

Calculate Performance: It reads the historical log, compares current values with past values, and calculates 1D, 1W, and 1M returns for each asset.

Log History: The script saves a snapshot of each asset's current value and ticker to the Performance_Log sheet, building a historical database over time.

Generate Report: A final, detailed report showing the performance of each asset is saved to a separate worksheet (Latest_Report) for easy viewing.

Technology Stack
Language: Python 3.11

Core Libraries:

pandas: For data manipulation and analysis.

gspread & gspread-dataframe: For interacting with Google Sheets.

yfinance: For fetching stock, crypto, and FX data.

tefas-crawler: For fetching Turkish TEFAS mutual fund data.

Platform:

Google Sheets: As the user-facing database.

Google Cloud Platform: For API access and service account management.

GitHub Actions: For scheduled, cloud-based automation.
