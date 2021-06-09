import os
import json
import time
import argparse
from os.path import join, dirname

from inotify import adapters, calls
from dotenv import load_dotenv
from pymongo import MongoClient

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)
conn_str = os.getenv("SQUIRREL_MONGO_URI")
client = MongoClient(conn_str)
db = client.dump1090


def agent():
    last_now = 0

    i = adapters.Inotify()

    while True:
        try:
            i.add_watch("/run/dump1090-fa/")
        except calls.InotifyError:
            print("/run/dump1090-fa/ not found, retrying in 1 second")
            time.sleep(1)

    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event

        if filename == "aircraft.json" and "IN_MOVED_TO" in type_names:
            try:
                with open("/run/dump1090-fa/aircraft.json", "r") as file:
                    raw = file.read().strip()
                    if len(raw) < 10:
                        print("error reading, skipping")
                    else:
                        data = json.loads(raw)
                        if last_now > int(data["now"]):
                            print(
                                "mismatch: now[{}] less than last_now[{}]".format(
                                    data["now"], last_now
                                )
                            )
                        else:
                            item = db.aircraft.insert_one(data)
                            last_now = int(data["now"])
                            print(
                                "inserted [{}] with id [{}]".format(
                                    data["now"], item.inserted_id
                                )
                            )
            except:
                print("whoops, raced")


if __name__ == "__main__":
    agent()
