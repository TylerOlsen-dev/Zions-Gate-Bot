import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def db_connection():
    dbc = mysql.connector.connect(
        host="localhost",
        user="ChilledFisher",
        passwd=os.getenv("db_passwd"),
        database="Discord" 
    )
    return dbc
