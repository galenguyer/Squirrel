import os
import sys
import json
import time
import argparse
from os.path import join, dirname
from datetime import datetime

from inotify import adapters, calls
from dotenv import load_dotenv
from pymongo import MongoClient

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)
conn_str = os.getenv("SQUIRREL_MONGO_URI")
client = MongoClient(conn_str)
db = client["dump1090"]
aircraft = db["aircraft"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--agent", help="Run the agent instead of the CLI", action="store_true"
    )
    args = parser.parse_args()

    if args.agent:
        agent()
    else:
        cli()


def cli():
    print("Total documents stored: {}".format(aircraft.count_documents({})))

    latest = list(aircraft.aggregate([{"$sort": {"now": -1}}, {"$limit": 1}]))[0]
    # TODO: Use local time?
    print(
        "Latest stored timestamp: {}".format(
            datetime.utcfromtimestamp(int(latest["now"])).strftime(
                "%Y-%m-%d %H:%M:%S+00:00 (UTC)"
            )
        )
    )

    furthest_24h()


def furthest_24h():
    lat = os.getenv("SQUIRREL_LAT")
    lon = os.getenv("SQUIRREL_LON")
    if lat is None or len(lat) < 1:
        print("SQUIRREL_LAT is not set - exiting")
    if lon is None or len(lon) < 1:
        print("SQUIRREL_LON is not set - exiting")
    if lat is None or len(lat) < 1 or lon is None or len(lon) < 1:
        sys.exit(1)

    furthest = aircraft.aggregate(
        [
            {"$match": {"now": {"$gt": int(time.time() - (24 * 60 * 60))}}},
            {"$unwind": {"path": "$aircraft"}},
            {
                "$addFields": {
                    "approxDist": {
                        "$let": {
                            "vars": {
                                "x": {"$subtract": ["$aircraft.lat", float(lat)]},
                                "y": {
                                    "$multiply": [
                                        {"$subtract": ["$aircraft.lon", float(lon)]},
                                        {"$cos": {"$degreesToRadians": float(lon)}},
                                    ]
                                },
                            },
                            "in": {
                                "$multiply": [
                                    110.25,
                                    {
                                        "$sqrt": {
                                            "$add": [
                                                {"$pow": ["$$x", 2]},
                                                {"$pow": ["$$y", 2]},
                                            ]
                                        }
                                    },
                                ]
                            },
                        }
                    }
                }
            },
            {"$sort": {"approxDist": -1}},
            {"$limit": 100},
        ]
    )
    print(list(furthest))


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
                            item = aircraft.insert_one(data)
                            last_now = int(data["now"])
                            print(
                                "inserted [{}] with id [{}]".format(
                                    data["now"], item.inserted_id
                                )
                            )
            except:
                print("whoops, raced")


if __name__ == "__main__":
    main()
