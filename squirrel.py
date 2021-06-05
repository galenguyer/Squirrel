import inotify.adapters


def main():
    i = inotify.adapters.Inotify()

    i.add_watch("/run/dump1090-fa/")

    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event

        if filename == "aircraft.json":
            print(
                "PATH=[{}] FILENAME=[{}] EVENT_TYPES={}".format(
                    path, filename, type_names
                )
            )


if __name__ == "__main__":
    main()
