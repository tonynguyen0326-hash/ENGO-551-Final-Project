import os
import csv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

# set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def main():
    # read in .csv files
    food = open("Food.csv")
    libraries = open("Libraries.csv")
    roads = open("Major_Roads.csv")
    transit = open("Transit.csv")
    uni = open("Uni_Buildings.csv")
    reddit = open("Reddit_Comments.csv")

    food_reader = csv.reader(food)
    libraries_reader = csv.reader(libraries)
    roads_reader = csv.reader(roads)
    transit_reader = csv.reader(transit)
    uni_reader = csv.reader(uni)
    reddit_reader = csv.reader(reddit)

    # skip header rows
    next(food_reader)
    next(libraries_reader)
    next(roads_reader)
    next(transit_reader)
    next(uni_reader)
    next(reddit_reader)

    # loop through .csv files and populate tables
    for bus_id, name, address, community, license, status, coords, * rest in food_reader:
        db.execute(
            text("INSERT INTO food (bus_id, name, address, community, license, status, coords) VALUES (:bus_id, :name, :address, :community, :license, :status, ST_GeomFromText(:coords, 4326)) ON CONFLICT (bus_id) DO NOTHING"), 
            {"bus_id": bus_id, "name": name, "address": address, "community": community, "license": license, "status": status, "coords": coords}
        )
    db.commit()

    for name, coords, address in libraries_reader:
        db.execute(
            text("INSERT INTO libraries (name, coords, address) VALUES (:name, ST_GeomFromText(:coords, 4326), :address) ON CONFLICT (name) DO NOTHING"),
            {"name": name, "coords": coords, "address": address}
        )
    db.commit()

    for coords, type, name in roads_reader:
        db.execute(
            text("INSERT INTO roads (coords, type, name) VALUES (ST_GeomFromText(:coords, 4326), :type, :name) ON CONFLICT (name) DO NOTHING"),
            {"coords": coords, "type":type, "name": name}
        )
    db.commit()

    for stop_id, name, coords in transit_reader:
        db.execute(
            text("INSERT INTO transit (stop_id, name, coords) VALUES (:stop_id, :name, ST_GeomFromText(:coords, 4326)) ON CONFLICT (stop_id) DO NOTHING"),
            {"stop_id": stop_id, "name": name, "coords": coords}
        )
    db.commit()

    for name, coords in uni_reader:
        db.execute(
            text("INSERT INTO uni (name, coords) VALUES (:name, ST_GeomFromText(:coords, 4326)) ON CONFLICT (name) DO NOTHING"),
            {"name": name, "coords": coords}
        )
    db.commit()

    for location, comment, source in reddit_reader:
        db.execute(
            text("INSERT INTO reddit (location, comment, source) VALUES (:location, :comment, :source) ON CONFLICT (comment) DO NOTHING"),
            {"location": location, "comment": comment, "source": source}
        )
    db.commit()

if __name__ == "__main__":
    main()