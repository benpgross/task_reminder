#!/usr/bin/env python3

"""
See the read me for the full background: https://github.com/benpgross/task_reminder/blob/master/README.md
Goal: make an easily adjustable reminder system to keep myself and my roomates accountable
for our task/chores throughout the semester

Implementation:
-pull from google sheets
-parse data from sheet 
-determine if reminder messages need to be sent
-if yes - connect to gmail api
-determine cell number to email conversion
-format messages in MIMEtext to send through gmail api 
-send reminders
(runs weekly via Launchd on my mac)

Areas for improvment:
-more logging & comments
    -fix this bug equiv in your code: https://github.com/googleapis/google-api-python-client/issues/325
-allow recipients of text to text back
-run on remote server instead of locally
"""

from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from email.mime.text import MIMEText
import base64
import requests
import json
import hidden_variables
import pandas as pd
import logging
import sys
import time


# The ID and range of a sample spreadsheet.
TASKS_SPREADSHEET_ID = hidden_variables.TASKS_SPREADSHEET_ID
SPREADSHEET_RANGE = 'Sheet1!A1:E'
key=hidden_variables.key
number_dictionary = hidden_variables.numbers

def connect_to_sheets():
    """
    Connects to the google sheets api and pulls in the info from the sheet
    to be further processed

    Args: None
    Returns: sheet_data - a dictionary of values
    """
   
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('/Users/benjamingross/Desktop/tasks_reminder_project/token.pickle'):
        with open('/Users/benjamingross/Desktop/tasks_reminder_project/token.pickle', 'rb') as token:
            creds = pickle.load(token)
    else:
        logging.error("No token.pickle file found")
        sys.exit()


    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    #print(sheet.values())
    result = sheet.values().get(spreadsheetId=TASKS_SPREADSHEET_ID,
                                range=SPREADSHEET_RANGE).execute()
    sheet_data = result.get('values', [])
    return sheet_data
   
def process_task_data(sheet_data):
    emails_to_send = []

    if not sheet_data:
        logging.info('No data found.')
        sys.exit()


    column_names = sheet_data.pop(0)
   # print(type(keys))
   # print(keys)
    #order data by the person who needs to do the chore, then by the order the chores are due 
    full_dataset = pd.DataFrame(sheet_data, columns=column_names).sort_values(["Name","Due Date"])
    full_dataset['Completed'] = full_dataset['Completed'].str.strip()
    full_dataset['Completed'] = full_dataset['Completed'].str.lower()
    #separate out the tasks that were completed
    only_undone_tasks = pd.DataFrame(full_dataset[full_dataset['Completed'] != 'done'])
    #remove accidental pre or post spaces in the name, make the text lowercase 
    only_undone_tasks['Name'] = only_undone_tasks['Name'].str.strip()
    only_undone_tasks['Name'] = only_undone_tasks['Name'].str.lower()
    only_undone_tasks['Due Date']=pd.to_datetime(only_undone_tasks['Due Date'])
    only_undone_tasks['Completed']=only_undone_tasks['Completed'].str.lower()
    only_undone_tasks['Completed']=only_undone_tasks['Completed'].str.strip()

    #get the set of people who need to do each task
    names = only_undone_tasks.Name.unique()

    for name in names:
        message = ""
        #find tasks that are overdue 
        vals = only_undone_tasks.loc[(only_undone_tasks['Name']==name) &(only_undone_tasks['Due Date'] < pd.to_datetime('today'))]
        outstanding_count = len(vals)
        if(outstanding_count > 0):
            latest = vals.iloc[-1:]
            task_or_tasks = "task"
            if(outstanding_count>1):
                task_or_tasks = "tasks"
                message = message + f"""you have {outstanding_count} {task_or_tasks} outstanding. The most recent one is: {latest['Task'].item().strip()} - due {latest['Due Date'].item().strftime('%b %d %Y')}. """
            else: 
                message = message + f"""you have {outstanding_count} {task_or_tasks} outstanding. It is:{latest['Task'].item().strip()} - due {latest['Due Date'].item().strftime('%b %d %Y')}. """
        vals2 = only_undone_tasks.loc[(only_undone_tasks['Name']==name) & (only_undone_tasks['Due Date'] > pd.to_datetime('today'))]
        to_do = len(vals2)
        if(to_do > 0):
            newest = vals2.iloc[:1]
            Your_or_your = "your"
            if message!="":
                Your_or_your = 'Your'
            message = message + f"""{Your_or_your} next task is: {newest['Task'].item().strip()} due {newest['Due Date'].item().strftime('%b %d %Y')}."""

        else:
            message = message + "You have no upcoming scheduled Tasks."
        emails_to_send.append(make_new_email(name,message))

    return emails_to_send


def make_new_email(name, message):

    """
    Create a message for an email.

    Args:
    name: Name of recipient
    message_text: The text of the email message.

    Returns:
    An object containing a base64url encoded email object.
    """

    message_text = f"{name}, {message}"
    message = MIMEText(message_text)
    message['to'] = get_carrier_return_address(number_dictionary[name])
    #this was an email address I used for a different project that I wasn't nervous about 
    #giving extended send etc. credentials to
    message['from'] = 'hcrifall18@gmail.com'
    #the subject shows up in the text as being within parenthesis so "(Task reminder)"
    message['subject'] = """Task reminder\n"""
    b64_bytes = base64.urlsafe_b64encode(message.as_bytes())
    b64_string = b64_bytes.decode()
    body = {'raw': b64_string}
    return body

def get_carrier_return_address(number):
    """
    Carriers have different configurations for how to send a
    text from an email so I query an API which tells me the carrier
    and then add the appropriate ending.

    Args: (str) a phone number
    Returns: (str) email address that will reach a cellphone 
    """

    #thanks https://stackoverflow.com/a/61241420 for the api
    #sleeps for five seconds to avoid API timeouts since I don't want to pay for an API (no bulk api requests available either)
    time.sleep(5) 
    url='https://api.telnyx.com/v1/phone_number/1' + number
    response=requests.get(url)
    if not response:
        logging.error("request did not return properly: ", url, " ", response)
        sys.exit()
    html = response.text
    carrier_info = json.loads(html)
    #print(carrier_info)
    carrier_name = carrier_info['carrier']['name']

    if carrier_name == "CELLCO PARTNERSHIP DBA VERIZON":
        number = number+'@vtext.com'
    elif carrier_name == "T-MOBILE USA, INC.":
        number = number+'@tmomail.net'
    elif carrier_name == "NEW CINGULAR WIRELESS PCS, LLC":
        number = number + '@txt.att.net'
    else:
        logging.error("Could not find carrier, exiting program")
        sys.exit()

    return number

def connect_to_gmail():
    """
        Connect to the gmail api
        (taken from google api service)
        current scopes = ['https://www.googleapis.com/auth/gmail.send']

        args: none
        returns: gmail service object
    """

    creds = None
    # The file token.pickle2 stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time. (using two different pickle files to hold the authorizations for 
    # for both gmail and sheets apis)
    if os.path.exists('/Users/benjamingross/Desktop/tasks_reminder_project/token2.pickle'):
        with open('/Users/benjamingross/Desktop/tasks_reminder_project/token2.pickle', 'rb') as token:
            creds = pickle.load(token)
    else:
        logging.error("token2.pickle file not found - exiting...")
        sys.exit()
   

    service = build('gmail', 'v1', credentials=creds)
    return service

def send(service, message, user_id='me'):
    """Send an email message.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

    Returns:
    void
    """
    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                   .execute())
        logging.info('Message Id: %s' % message['id'])
        return message
    except Exception as error:
        logging.error ('An error occurred: %s' % error)



if __name__ == '__main__':
    """
        Main control sequence of the app
        1) connect to google sheets and download the data
        2) processs that data and determine what needs to be sent
        3) connect to gmail
        4) send messages 
    """
    #init logging
    handlers = [logging.FileHandler('/Users/benjamingross/Desktop/tasks_reminder_project/task_reminder.log'), logging.StreamHandler()]
    logging.basicConfig(level=logging.INFO, handlers=handlers, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%Y-%M-%d %H:%M')
    logging.info("Task Reminder Beginning")

    task_data = connect_to_sheets()
    logging.info('succesfullly gathered task data')
    messages_to_send = process_task_data(task_data)
    if messages_to_send is None:
        logging.info("No messages to send - program complete.")
        sys.exit()
    gmail_service = connect_to_gmail()
    logging.info("connection to gmail established")
    for message in messages_to_send:
        logging.info(send(gmail_service, message))
    logging.info("~program completed~")
