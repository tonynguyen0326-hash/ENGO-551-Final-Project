import os
import csv
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=ENV_PATH)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError(f"DATABASE_URL not found. Check your .env file at: {ENV_PATH}")

engine = create_engine(database_url)
db = scoped_session(sessionmaker(bind=engine))

def main():
    food = open(os.path.join(BASE_DIR, "data", "Food.csv"), encoding="utf-8")
    libraries = open(os.path.join(BASE_DIR, "data", "Libraries.csv"), encoding="utf-8")
    roads = open(os.path.join(BASE_DIR, "data", "Major_Roads.csv"), encoding="utf-8")
    transit = open(os.path.join(BASE_DIR, "data", "Transit.csv"), encoding="utf-8")
    uni = open(os.path.join(BASE_DIR, "data", "Uni_Buildings.csv"), encoding="utf-8")
    reddit = open(os.path.join(BASE_DIR, "data", "Reddit_Comments.csv"), encoding="utf-8")

    food_reader = csv.reader(food)
    libraries_reader = csv.reader(libraries)
    roads_reader = csv.reader(roads)
    transit_reader = csv.reader(transit)
    uni_reader = csv.reader(uni)
    reddit_reader = csv.reader(reddit)

    next(food_reader)
    next(libraries_reader)
    next(roads_reader)
    next(transit_reader)
    next(uni_reader)
    next(reddit_reader)

    for bus_id, name, address, community, license, status, coords, *rest in food_reader:
        db.execute(
            text("""
                INSERT INTO food (bus_id, name, address, community, license, status, coords)
                VALUES (:bus_id, :name, :address, :community, :license, :status, ST_GeomFromText(:coords, 4326))
                ON CONFLICT (bus_id) DO NOTHING
            """),
            {
                "bus_id": bus_id,
                "name": name,
                "address": address,
                "community": community,
                "license": license,
                "status": status,
                "coords": coords
            }
        )
    db.commit()

    for name, coords, address in libraries_reader:
        db.execute(
            text("""
                INSERT INTO libraries (name, coords, address)
                VALUES (:name, ST_GeomFromText(:coords, 4326), :address)
                ON CONFLICT (name) DO NOTHING
            """),
            {
                "name": name,
                "coords": coords,
                "address": address
            }
        )
    db.commit()

    for coords, type, name in roads_reader:
        db.execute(
            text("""
                INSERT INTO roads (coords, type, name)
                VALUES (ST_GeomFromText(:coords, 4326), :type, :name)
                ON CONFLICT (name) DO NOTHING
            """),
            {
                "coords": coords,
                "type": type,
                "name": name
            }
        )
    db.commit()

    for stop_id, name, coords in transit_reader:
        db.execute(
            text("""
                INSERT INTO transit (stop_id, name, coords)
                VALUES (:stop_id, :name, ST_GeomFromText(:coords, 4326))
                ON CONFLICT (stop_id) DO NOTHING
            """),
            {
                "stop_id": stop_id,
                "name": name,
                "coords": coords
            }
        )
    db.commit()

    for name, coords in uni_reader:
        db.execute(
            text("""
                INSERT INTO uni (name, coords)
                VALUES (:name, ST_GeomFromText(:coords, 4326))
                ON CONFLICT (name) DO NOTHING
            """),
            {
                "name": name,
                "coords": coords
            }
        )
    db.commit()

    for location, comment, source in reddit_reader:
        db.execute(
            text("""
                INSERT INTO reddit (location, comment, source)
                VALUES (:location, :comment, :source)
                ON CONFLICT (comment) DO NOTHING
            """),
            {
                "location": location,
                "comment": comment,
                "source": source
            }
        )
    db.commit()

    print("Data import completed successfully.")

if __name__ == "__main__":
    main()