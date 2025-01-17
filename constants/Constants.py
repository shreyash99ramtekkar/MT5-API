
import os
from dotenv import load_dotenv
from sqlalchemy.ext.declarative import declarative_base

BASE = declarative_base()
# load .env file to environment
load_dotenv()

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


DATABASE_URL = "mysql+pymysql://" + os.getenv("DB_USERNAME") + ":" + os.getenv("DB_PASS") + "@" + os.getenv("DB_HOST") + "/" + os.getenv("DB")