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
from geopy import distance
from rich import print
from rich.console import Console
from rich.table import Table

dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)
conn_str = os.getenv("SQUIRREL_MONGO_URI")
client = MongoClient(conn_str)
db = client["dump1090"]
aircraft = db["aircraft"]
flights = db["flights"]


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
    print("Total documents stored: {}".format(flights.count_documents({})))

    latest = list(flights.aggregate([{"$sort": {"now": -1}}, {"$limit": 1}]))[0]
    # TODO: Use local time?
    print(
        "Latest stored timestamp: {}".format(
            datetime.utcfromtimestamp(int(latest["now"])).strftime(
                "%Y-%m-%d %H:%M:%S+00:00 (UTC)"
            )
        )
    )

    furthest_24h()
    highest()
    fastest()

def highest():
    highest = flights.aggregate(
        [
            {
                "$match": {
                    "alt_baro": {"$exists": True},
                    "alt_geom": {"$exists": True},
                }
            },
            {"$sort": {"alt_geom": -1}},
            {"$group": {"_id": "$hex", "original": {"$first": "$$ROOT"}}},
            {"$sort": {"original.alt_geom": -1}},
            {"$limit": 5},
        ],
        allowDiskUse=True,
    )

    console = Console()
    table = Table(show_header=True, title="Highest 5 Seen Planes")
    table.add_column("Time", justify="right")
    table.add_column("Hex")
    table.add_column("Flight")
    table.add_column("Latitude", justify="right")
    table.add_column("Longitude", justify="right")
    table.add_column("Altitude", justify="right")
    table.add_column("Speed", justify="right")

    for plane in list(highest):
        table.add_row(
            datetime.utcfromtimestamp(plane["original"]["now"]).strftime(
                "%Y-%m-%d %H:%M:%S (UTC)"
            ),
            plane["original"]["hex"],
            plane["original"]["flight"] if "flight" in plane['original'] else "??????",
            str(round(plane["original"]["lat"], 5)) if "lat" in plane['original'] else "??????",
            str(round(plane["original"]["lon"], 5)) if "lon" in plane['original'] else "??????",
            str(plane["original"]["alt_geom"]) + "ft",
            str(plane["original"]["gs"]) + "kts" if "gs" in plane['original'] else "???kts",
        )
    console.print(table)

def fastest():
    fastest = flights.aggregate(
        [
            {
                "$match": {
                    "gs": {"$exists": True}
                }
            },
            {"$sort": {"gs": -1}},
            {"$group": {"_id": "$hex", "original": {"$first": "$$ROOT"}}},
            {"$sort": {"original.gs": -1}},
            {"$limit": 5},
        ],
        allowDiskUse=True,
    )

    console = Console()
    table = Table(show_header=True, title="Fastest 5 Seen Planes")
    table.add_column("Time", justify="right")
    table.add_column("Hex")
    table.add_column("Flight")
    table.add_column("Latitude", justify="right")
    table.add_column("Longitude", justify="right")
    table.add_column("Altitude", justify="right")
    table.add_column("Speed", justify="right")

    for plane in list(fastest):
        table.add_row(
            datetime.utcfromtimestamp(plane["original"]["now"]).strftime(
                "%Y-%m-%d %H:%M:%S (UTC)"
            ),
            plane["original"]["hex"],
            plane["original"]["flight"] if "flight" in plane['original'] else "??????",
            str(round(plane["original"]["lat"], 5)) if "lat" in plane['original'] else "??????",
            str(round(plane["original"]["lon"], 5)) if "lon" in plane['original'] else "??????",
            str(plane["original"]["alt_geom"]) + "ft" if "alt_geom" in plane["original"] else "?????ft",
            str(plane["original"]["gs"]) + "kts" if "gs" in plane['original'] else "???kts",
        )
    console.print(table)


def furthest_24h():
    lat = os.getenv("SQUIRREL_LAT")
    lon = os.getenv("SQUIRREL_LON")
    if lat is None or len(lat) < 1:
        print("SQUIRREL_LAT is not set - exiting")
    if lon is None or len(lon) < 1:
        print("SQUIRREL_LON is not set - exiting")
    if lat is None or len(lat) < 1 or lon is None or len(lon) < 1:
        sys.exit(1)

    furthest = flights.aggregate(
        [
            {
                "$match": {
                    "now": {"$gt": int(time.time() - (24 * 60 * 60))},
                    "flight": {"$exists": True},
                    "lat": {"$exists": True},
                    "lon": {"$exists": True},
                    "alt_geom": {"$exists": True}
                }
            },
            {
                "$addFields": {
                    "approxDist": {
                        "$let": {
                            "vars": {
                                "x": {"$subtract": ["$lat", lat]},
                                "y": {
                                    "$multiply": [
                                        {"$subtract": ["$lon", lon]},
                                        {"$cos": {"$degreesToRadians": lon}},
                                    ]
                                },
                            },
                            "in": {
                                "$multiply": [
                                    69.170725,
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
            {
                "$group": {
                    "_id": "$flight",
                    "dist": {"$first": "$approxDist"},
                    "original": {"$first": "$$ROOT"},
                }
            },
            {"$sort": {"dist": -1}},
            {"$limit": 10},
        ],
        allowDiskUse=True,
    )

    console = Console()
    table = Table(show_header=True, title="Furthest 10 Seen Flights in 24h")
    table.add_column("Time", justify="right")
    table.add_column("Hex")
    table.add_column("Flight")
    table.add_column("Distance (approx)", justify="right")
    table.add_column("Latitude", justify="right")
    table.add_column("Longitude", justify="right")
    table.add_column("Altitude", justify="right")
    table.add_column("Speed", justify="right")

    for plane in list(furthest):
        table.add_row(
            datetime.utcfromtimestamp(plane["original"]["now"]).strftime(
                "%Y-%m-%d %H:%M:%S (UTC)"
            ),
            plane["original"]["hex"],
            plane["original"]["flight"],
            str(round(plane["dist"], 1)) + "mi",
            str(round(plane["original"]["lat"], 5)),
            str(round(plane["original"]["lon"], 5)),
            str(plane["original"]["alt_geom"]) + "ft",
            str(plane["original"]["gs"]) + "kts",
        )
    console.print(table)


def agent():
    last_now = 0

    i = adapters.InotifyTree("/run/")

    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event

        if (
            "dump1090-fa" in path
            and filename == "aircraft.json"
            and "IN_MOVED_TO" in type_names
        ):
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
                            global aircraft
                            global flights
                            # insert raw document
                            # item = aircraft.insert_one(data)
                            # last_now = int(data["now"])
                            # print(
                            #     "inserted [{}] with id [{}]".format(
                            #         data["now"], item.inserted_id
                            #     )
                            # )
                            # insert each aircraft
                            docs = []
                            for _aircraft in data["aircraft"]:
                                if ("alt_baro" not in _aircraft) and (
                                    "lat" not in _aircraft
                                ):
                                    continue
                                _aircraft["now"] = data["now"]
                                docs.append(_aircraft)
                            if len(docs) > 0:
                                result = flights.insert_many(docs)
                                print(
                                    "inserted [{}] with ids ({})".format(
                                        data["now"], len(result.inserted_ids)
                                    )
                                )
            except Exception as e:
                print("Exception caught:", e)


if __name__ == "__main__":
    main()
