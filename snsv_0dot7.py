"""
@author: kt12
Kenneth Tsuji
2017-07-17

Changes - timer added

"""

import sys, os, logging
from dotenv import load_dotenv
import time
import pymongo
import tweepy
import json

# Set number of tweets to record, sleep between API calls, and subject matter
# Reminder sys.argv comes in as a list

num_tweets = int(sys.argv[1])
sleep = float(sys.argv[2])
subject = sys.argv[3:]
subject_type = (type(subject))

# Append hashtags and de-hashed terms to subject_list
subject_list = []

# Check if input is single string or list of terms or hashtag
if subject_type is str:
    # check hashtag
    if '#' in subject:
        subject_list.extend((subject, subject.replace('#', '')))
    else:
        subject_list.append(subject)

elif subject_type is list:
    # If type is lst and len is 1, must be hashtag
    for k in subject:
        if '#' in k:
            subject_list.extend((k, k.replace('#', '')))
        else:
            subject_list.append(k)

else:
    raise Exception

idioma = input('Enter language to track: ')
languages = []
languages.append(idioma)

# Set up logging
logger = logging.getLogger(__name__)
# Logs at debug level will be recorded
logger.setLevel(logging.DEBUG)

# Include STDOUT in log stream
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
logger.addHandler(console_handler)

# Push formatted logs out to .log file
timestamp = time.strftime("%Y%m%d-%H%M%S")
file_handler = logging.FileHandler('twitter_' + timestamp + '.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.debug('Logger initiated.')

# Credentials must be stored in .env file in same directory.
# Load Twitter credentials
load_dotenv('.env')
CONSUMER_KEY = os.environ.get('consumer_key')
CONSUMER_SECRET = os.environ.get('consumer_secret')
ACCESS_TOKEN = os.environ.get('access_token')
ACCESS_TOKEN_SECRET = os.environ.get('access_token_secret')
logger.debug('Twitter credentials loaded.')

print('The topic(s) you chose to track through Twitter: {}.'.format(subject_list))
logger.debug('Topic decided: {}.'.format(subject_list))


# Set MongoDB local host (on same machine)
host = 'mongodb://127.0.0.1:27017'

# Connect to twitterdb
# Will be created if it doesn't exist
client = pymongo.MongoClient(host)
logger.debug('Mongo connected.')
document_db = client.twitterdb

# Convert subject_list to string and underscores
col_name = '_'.join(k for k in subject_list if '#' not in k)

# Check if collection  name already exists
if col_name in document_db.collection_names():
    logger.debug('Collection {} exists'.format(col_name))
    collection = document_db[col_name]
else:
    document_db.create_collection(col_name)
    logger.debug('New collection {}'.format(col_name))
    collection = document_db[col_name]

print("Tweets will be stored in the MongoDB collection: {}".format(col_name))

# Set up tweepy credentials
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
logger.debug('Tweepy has loaded credentials.')

# Create listener based on tweepy Streamlistener
""" If used as streamer, max_limit and count will impact the
number of tweets collected.  However, as the connection is 
being broken for purpose of refreshing the tweet stream,
they are vestigial"""

class Listener(tweepy.StreamListener):
    def __init__(self, api, subject=subject_list,  max_limit=5, time_limit=1):
        self.api = api
        self.count = 0
        self.limit = max_limit
        self.subject = subject_list
        self.time_limit = time_limit
        self.start_time = time.time()

    def on_status(self, status):
        logger.debug(status.text)

    def on_error(self, status_code):
        logger.debug(status_code)
        if status_code == 420 or status_code == 429:
            # Returning False disconnects the stream
            return False
        else:
            return True

    def on_timeout(self):
        return True

    def on_data(self, data):    
        logger.debug('Pulling in tweets')
        while self.count < self.limit and (time.time() - self.start_time) < self.limit:
            # tweet_json is a dict
            tweet_json = json.loads(data)
            text = tweet_json.get('text')
            if any(k in self.subject for j in text):
                # insert entire dict/JSON into MongoDB
                collection = document_db[col_name]
                collection.insert_one(tweet_json)
                user = tweet_json.get('user',{}).get('screen_name')
                print(user,":", text)
                self.count += 1
                return True
            else:
                return True
        else:
            return False

print('Storing the following tweets:')

for _ in range(num_tweets):
    streamer = tweepy.streaming.Stream(auth=auth, subject=subject_list, listener=Listener(api=tweepy.API(wait_on_rate_limit=True)))
    streamer.filter(track=subject_list, languages=languages, async=True)
    time.sleep(sleep)

logger.debug('Done pulling in tweets.')
print('Done pulling in tweets.')