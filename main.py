import os
import requests
from newsapi import NewsApiClient
from twilio.rest import Client

def calculate_stock_change(stock_latest,stock_before_latest):
    try:
        close_latest = float(stock_latest['4. close'])
        close_before_latest = float(stock_before_latest['4. close'])

        close_diff = close_latest - close_before_latest
        close_percentage_diff = round(100 * (close_diff/close_latest),2)

        return {
            'increase': close_percentage_diff > 0,
            'percentage': abs(close_percentage_diff)
        }
    except KeyError as key_error_message:
        print(f'There was a problem with calculation stocks difference. Error: {key_error_message}')
        return None

STOCK = "TSLA"
COMPANY_NAME = "Tesla"
STOCK_API_KEY = os.environ.get('STOCK_API_KEY')
STOCK_ENDPOINT = os.environ.get('STOCK_API_ENDPOINT')
stock_params = {
    'symbol': STOCK,
    'apikey': STOCK_API_KEY
}

NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
news_api = NewsApiClient(api_key=NEWS_API_KEY)

ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_SENDER = os.environ.get('TWILIO_SENDER')
MY_PHONE_NUMBER = os.environ.get('MY_PHONE_NUMBER')

twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)

response = requests.get(STOCK_ENDPOINT,params=stock_params)
try:
    response.raise_for_status()
except requests.exceptions.HTTPError as http_error_message:
    print(f"HTTP error occurred: {http_error_message}")

# The stock api free version has a limit of 25 calls per day,
# but it does not raise an exception when the limit is reached.
if 'Information' in response.json():
    api_limit_error = Exception(response.json()['Information'])
    print(f"Stock API limit reached: {api_limit_error}")
    raise SystemExit(api_limit_error)

stock_prices = response.json().get('Time Series (Daily)',{})

# Check is there is enough data to compare change in stocks.
if not len(stock_prices) >= 2:
    raise ValueError("Not enough stock data to continue execution.")

recent_stock_prices = {stock: stock_prices[stock] for stock in list(stock_prices)[:2]}
[yesterday_date, date_before_yesterday] = [*recent_stock_prices.keys()]

stock_diff = calculate_stock_change(recent_stock_prices[yesterday_date],recent_stock_prices[date_before_yesterday])

if stock_diff is None:
    print("Stock change calculation failed. Exiting.")
    raise SystemExit()

if stock_diff['percentage'] > 5:
    top_3_headlines = news_api.get_top_headlines(q=COMPANY_NAME,category='business',language='en',page_size=3)

    if stock_diff['increase']:
        header = f'{STOCK}: 📈 {stock_diff["percentage"]}%'
    else:
        header = f'{STOCK}: 📉 -{stock_diff["percentage"]}%'

    for article in top_3_headlines['articles']:
        # The trial version of the twilio sms service has a limit of around 150 characters per message.
        # If it is exceeded the queue message is cancelled, since it is an asynchronous process,
        # it's better to limit the length of the sms content.
        max_length = 144 - len(header) - len(" Headline: ...")
        sms_content = f'{header} Headline: {article["title"][:max_length]}...'

        # Start sms sending process
        sms = twilio_client.messages.create(body=sms_content,from_=TWILIO_SENDER,to=MY_PHONE_NUMBER)