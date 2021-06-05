import os
from os.path import join, dirname

from inotify import adapters
from dotenv import load_dotenv
from pymongo import MongoClient

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)
conn_str = os.getenv("SQUIRREL_MONGO_URI")


def main():
    client = MongoClient(conn_str)
    db = client.dump1090

    i = adapters.Inotify()

    i.add_watch("/run/dump1090-fa/")

    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event

        if filename == "aircraft.json" and "IN_MOVED_TO" in type_names:
            print(
                "PATH=[{}] FILENAME=[{}] EVENT_TYPES={}".format(
                    path, filename, type_names
                )
            )
            try:
                with open("/run/dump1090-fa/aircraft.json", "r") as file:
                    pass
            except:
                print("whoops, raced")

if __name__ == "__main__":
    main()
