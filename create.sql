CREATE EXTENSION IF NOT EXISTS postgis;

-- table for user login, can't repeat usernames
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR UNIQUE NOT NULL,
    password VARCHAR NOT NULL
);

-- table for cafe/restaurants
CREATE TABLE IF NOT EXISTS food (
    bus_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    address VARCHAR NOT NULL,
    community VARCHAR NOT NULL,
    license VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    coords GEOMETRY(POINT, 4326) 
);

-- table for public libraries
CREATE TABLE IF NOT EXISTS libraries (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,
    coords GEOMETRY(POINT, 4326),
    address VARCHAR NOT NULL
);

-- table for major roads
CREATE TABLE IF NOT EXISTS roads (
    id SERIAL PRIMARY KEY,
    coords GEOMETRY(LINESTRING, 4326),
    type VARCHAR NOT NULL,
    name VARCHAR UNIQUE NOT NULL
);

-- table for transit stops and stations
CREATE TABLE IF NOT EXISTS transit (
    stop_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    coords GEOMETRY(POINT, 4326)    
);

-- table for University of Calgary buildings
CREATE TABLE IF NOT EXISTS uni (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,
    coords GEOMETRY(POINT, 4326)
);

-- table for Reddit comments
CREATE TABLE IF NOT EXISTS reddit (
    id SERIAL PRIMARY KEY,
    location VARCHAR NOT NULL,
    comment VARCHAR UNIQUE NOT NULL,
    source VARCHAR NOT NULL
);