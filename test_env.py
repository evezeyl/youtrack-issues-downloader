import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Get the variables
url = os.getenv("YOUTRACK_URL")
token = os.getenv("YOUTRACK_TOKEN")
project_id = os.getenv("YOUTRACK_PROJECT_ID")

# Print what was loaded
print(f"URL: {url}")
print(f"Token: {token}")
print(f"Project ID: {project_id}")