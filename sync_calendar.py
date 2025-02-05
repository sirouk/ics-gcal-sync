from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import icalendar
import datetime
import os
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
import time
import json
from zoneinfo import ZoneInfo

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']

def load_or_create_config():
    config_file = 'config.json'
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        # Check if required fields exist in config, if not, prompt for them
        required_fields = {
            'sync_months': "\nHow many months of past events should be synced?\n(Enter a number, e.g. 3 for three months)",
            'timezone': "\nWhat timezone are you in?\n(e.g., America/New_York, America/Los_Angeles, Europe/London)\nSee: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        }
        
        updated = False
        for field, prompt in required_fields.items():
            if field not in config:
                print(prompt)
                if field == 'sync_months':
                    config[field] = int(input().strip())
                else:
                    while True:
                        try:
                            tz = input().strip()
                            # Validate timezone
                            ZoneInfo(tz)
                            config[field] = tz
                            break
                        except Exception:
                            print("Invalid timezone. Please enter a valid timezone name.")
                updated = True
        
        # Save updated config if needed
        if updated:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=4)
                
        return config
    
    print("\nFirst time setup - please provide the following information:")
    print("\nEnter the ICS calendar URL (e.g., https://example.com/calendar.ics):")
    ics_url = input().strip()
    
    print("\nEnter your Google Calendar ID.")
    print("(You can find this in Google Calendar settings under 'Integrate calendar')")
    print("It looks like: xxx@group.calendar.google.com")
    calendar_id = input().strip()
    
    print("\nEnter the path to your Google OAuth client secret JSON file")
    print("(Download this from Google Cloud Console -> Credentials)")
    client_secret_file = input().strip()
    
    print("\nHow many months of past events should be synced?")
    print("(Enter a number, e.g. 3 for three months)")
    months = int(input().strip())
    
    print("\nWhat timezone are you in?")
    print("(e.g., America/New_York, America/Los_Angeles, Europe/London)")
    print("See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones")
    while True:
        try:
            timezone = input().strip()
            # Validate timezone
            ZoneInfo(timezone)
            break
        except Exception:
            print("Invalid timezone. Please enter a valid timezone name.")
    
    config = {
        'ics_url': ics_url,
        'calendar_id': calendar_id,
        'client_secret_file': client_secret_file,
        'sync_months': months,
        'timezone': timezone
    }
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)
    
    return config

def get_calendar_service():
    """Authenticate using OAuth 2.0 with token caching"""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, 
                SCOPES,
                redirect_uri='http://localhost'
            )
            # Get the authorization URL
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                prompt='consent'
            )
            print('\nPlease go to this URL and authorize the application:')
            print(auth_url)
            print('\nEnter the authorization code: ')
            code = input().strip()
            flow.fetch_token(code=code)
            creds = flow.credentials
            
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)

def download_ics(url, file_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            f.write(response.content)
        print("ICS file downloaded successfully.")
    else:
        print("Failed to download ICS file.")

def parse_ics(file_path, months_to_sync, timezone):
    with open(file_path, 'rb') as f:
        calendar = icalendar.Calendar.from_ical(f.read())

    events = []
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30.44 * months_to_sync)
    
    # Use configured timezone
    tz = ZoneInfo(timezone)

    # Use subcomponents instead of walk() to avoid recursion
    for component in calendar.subcomponents:
        if component.name == "VEVENT":
            start = component.get('dtstart').dt
            summary = str(component.get('summary'))
            
            # Skip old events
            if isinstance(start, datetime.datetime):
                if start < cutoff_date:
                    continue
            elif isinstance(start, datetime.date):
                if datetime.datetime.combine(start, datetime.datetime.min.time()) < cutoff_date:
                    continue
            
            end = component.get('dtend').dt if component.get('dtend') else start + datetime.timedelta(hours=1)
            description = str(component.get('description', ''))
            
            # Convert to datetime if it's a date-only value or if time is midnight
            needs_time_parsing = (
                isinstance(start, datetime.date) and not isinstance(start, datetime.datetime)
            ) or (
                isinstance(start, datetime.datetime) and 
                start.hour == 0 and 
                start.minute == 0 and 
                start.second == 0
            )
            
            if needs_time_parsing:
                try:
                    if "Starts:" in description and "Ends:" in description:
                        desc_lines = description.split('\n')
                        for line in desc_lines:
                            if "Starts:" in line and "Ends:" in line:
                                try:
                                    _, times_part = line.split("Starts:")
                                    start_part, end_part = times_part.split("Ends:")
                                    
                                    start_str = start_part.strip()
                                    if '@' not in start_str:
                                        print(f"Warning: Invalid time format in description for {summary}")
                                        raise ValueError("Missing @ in time string")
                                        
                                    start_date, start_time = start_str.split('@')
                                    start_time = parse_time_str(start_date.strip(), start_time.strip(), start.year)
                                    
                                    end_str = end_part.strip()
                                    if '@' not in end_str:
                                        print(f"Warning: Invalid time format in description for {summary}")
                                        raise ValueError("Missing @ in time string")
                                        
                                    end_date, end_time = end_str.split('@')
                                    end_time = parse_time_str(end_date.strip(), end_time.strip(), end.year)
                                    
                                    start = start_time.replace(tzinfo=tz)
                                    end = end_time.replace(tzinfo=tz)
                                    break
                                except ValueError as e:
                                    print(f"Error parsing time format for {summary}: {str(e)}")
                                    raise
                except Exception as e:
                    print(f"Error parsing times from description for {summary}: {str(e)}")
                    if isinstance(start, datetime.date):
                        start = datetime.datetime.combine(start, datetime.datetime.min.time())
                    if isinstance(end, datetime.date):
                        end = datetime.datetime.combine(end, datetime.datetime.min.time())
            
            events.append({
                'start': start,
                'end': end,
                'summary': summary,
                'description': description
            })
    return events

def parse_time_str(date_str, time_str, year):
    """Parse date and time strings into datetime object"""
    # Extract date parts from "05/28" format
    month, day = date_str.split('/')
    
    # Extract time parts from "08:00 AM" format
    time_str = time_str.replace('@', '').strip()
    
    # Handle special case where 3:00 PM is written as 03:00 AM
    if "AM" in time_str:
        hour = int(time_str.split(':')[0])
        # For school/business hours, if it's AM and between 1-6, assume it should be PM
        if 1 <= hour <= 6:
            time_str = time_str.replace("AM", "PM")
    
    # Handle times without AM/PM
    if "AM" not in time_str and "PM" not in time_str:
        hour = int(time_str.split(':')[0])
        if hour < 7 or (hour < 12 and hour > 0):  # 1:00-6:59
            time_str += " PM"
        elif hour == 12:
            time_str += " PM"
        else:  # 7:00-11:59
            time_str += " AM"
            
    time = datetime.datetime.strptime(time_str, "%I:%M %p")
    
    # Combine into full datetime using the provided year
    dt = datetime.datetime(
        year,
        int(month),
        int(day),
        time.hour,
        time.minute
    )
    
    return dt

def sync_events(events, timezone):
    service = get_calendar_service()
    existing_events = service.events().list(calendarId=CALENDAR_ID).execute().get('items', [])
    existing_summaries = {event['summary']: event['id'] for event in existing_events}

    for event in events:
        start_time = event['start']
        end_time = event['end']

        # Convert date to datetime if needed
        if isinstance(start_time, datetime.date) and not isinstance(start_time, datetime.datetime):
            start_time = datetime.datetime.combine(start_time, datetime.datetime.min.time())
        if isinstance(end_time, datetime.date) and not isinstance(end_time, datetime.datetime):
            end_time = datetime.datetime.combine(end_time, datetime.datetime.min.time())

        # Ensure timezone info exists
        if not start_time.tzinfo:
            # Use configured timezone
            start_time = start_time.replace(tzinfo=ZoneInfo(timezone))
            end_time = end_time.replace(tzinfo=ZoneInfo(timezone))

        event_data = {
            'summary': event['summary'],
            'description': event['description'],
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': timezone
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': timezone
            }
        }
        
        # Debug print
        print(f"\nTrying to add/update event:")
        print(f"Summary: {event['summary']}")
        print(f"Start: {event_data['start']}")
        print(f"End: {event_data['end']}")
        
        while True:
            try:
                if event['summary'] in existing_summaries:
                    event_id = existing_summaries[event['summary']]
                    service.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=event_data).execute()
                    print(f"Updated: {event['summary']}")
                else:
                    service.events().insert(calendarId=CALENDAR_ID, body=event_data).execute()
                    print(f"Added: {event['summary']}")
                break  # Success, exit retry loop
            except Exception as e:
                if "Rate Limit Exceeded" in str(e):
                    print(f"Rate limit hit, waiting 5 seconds...")
                    time.sleep(5)  # Wait 5 seconds before retrying
                    continue
                print(f"Error with event {event['summary']}: {str(e)}")
                break  # Exit on non-rate-limit errors

def remove_duplicates_from_ics(file_path):
    """Remove duplicate events from ICS file based on summary and start time"""
    try:
        with open(file_path, 'rb') as f:
            calendar = icalendar.Calendar.from_ical(f.read())
        
        # Track unique events using summary + start time as key
        unique_events = {}
        components = []
        event_count = 0
        
        # First, collect all direct components
        for component in calendar.subcomponents:
            if component.name == "VEVENT":
                event_count += 1
                start = component.get('dtstart').dt
                summary = str(component.get('summary'))
                
                # Create unique key from summary and start time
                event_key = f"{summary}_{start}"
                
                if event_key not in unique_events:
                    unique_events[event_key] = True
                    components.append(component)
                else:
                    print(f"Removing duplicate event: {summary} at {start}")
            else:
                components.append(component)
        
        # Create new calendar with unique events
        new_calendar = icalendar.Calendar()
        
        # Copy over any calendar properties
        for attr in calendar.property_items():
            new_calendar.add(attr[0], attr[1])
        
        # Add all unique components
        for component in components:
            new_calendar.add_component(component)
        
        # Write back to file
        with open(file_path, 'wb') as f:
            f.write(new_calendar.to_ical())
        
        return event_count - len(unique_events)
        
    except Exception as e:
        print(f"Error in remove_duplicates_from_ics: {str(e)}")
        # If there's an error, return 0 to indicate no duplicates were removed
        return 0

if __name__ == '__main__':
    config = load_or_create_config()
    
    # Update global variables with config values
    global ICS_URL, CALENDAR_ID, CLIENT_SECRET_FILE
    ICS_URL = config['ics_url']
    CALENDAR_ID = config['calendar_id']
    CLIENT_SECRET_FILE = config['client_secret_file']
    
    print("\nCalendar sync script started. Press Ctrl+C to stop.")
    
    while True:
        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{current_time}] Starting sync...")
            
            ics_path = 'stored_cal.ics'
            download_ics(ICS_URL, ics_path)
            
            # Remove duplicates before processing
            duplicates_removed = remove_duplicates_from_ics(ics_path)
            if duplicates_removed > 0:
                print(f"Removed {duplicates_removed} duplicate events from ICS file")
            
            events = parse_ics(ics_path, config['sync_months'], config['timezone'])
            sync_events(events, config['timezone'])
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sync complete.")
            print("Waiting 15 minutes until next sync...")
            time.sleep(900)  # 900 seconds = 15 minutes
            
        except KeyboardInterrupt:
            print("\nSync script stopped by user.")
            break
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            print("Will retry in 15 minutes...")
            time.sleep(900)
