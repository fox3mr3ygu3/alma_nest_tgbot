import psycopg2
import os
from dotenv import load_dotenv
from datetime import date, timedelta
import random

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)


def init_db():
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            client_id TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            children_count INTEGER,
            package_type TEXT,
            visits_remaining INTEGER,
            start_date DATE,
            expire_date DATE
        );
    """)
    conn.commit()
    cur.close()


def add_client(full_name, children_count, package_type):
    cur = conn.cursor()
    visits = package_type
    start = date.today()
    expire = start + timedelta(days=30)

    while True:
        client_id = f"{random.randint(0, 9999):04}"
        cur.execute("SELECT 1 FROM clients WHERE client_id = %s", (client_id,))
        if not cur.fetchone():
            break

    while True:
        password = f"{random.randint(0, 999999):06}"
        cur.execute("SELECT 1 FROM clients WHERE password = %s", (password,))
        if not cur.fetchone():
            break

    cur.execute("""
        INSERT INTO clients (client_id, password, full_name, children_count, package_type, visits_remaining, start_date, expire_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (client_id, password, full_name, children_count, package_type, visits, start, expire))
    conn.commit()
    cur.close()
    return client_id, password, start, expire


def get_all_clients():
    cur = conn.cursor()
    cur.execute("SELECT full_name, children_count, package_type, visits_remaining, expire_date FROM clients ORDER BY full_name")
    result = cur.fetchall()
    cur.close()
    return result


def get_client(client_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE client_id = %s", (client_id,))
    result = cur.fetchone()
    cur.close()
    return result


def validate_password(client_id, password):
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE client_id = %s AND password = %s", (client_id, password))
    result = cur.fetchone()
    cur.close()
    return result


def decrement_visit(client_id):
    cur = conn.cursor()
    cur.execute("UPDATE clients SET visits_remaining = visits_remaining - 1 WHERE client_id = %s AND visits_remaining > 0", (client_id,))
    conn.commit()
    cur.close()



