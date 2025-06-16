import psycopg2
import os
import random
import json
from dotenv import load_dotenv
from datetime import date, timedelta
from config import SUPERUSER_ID, SUPERUSER_PASSWORD


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
            phone TEXT,
            children_count INTEGER,
            package_type TEXT,
            visits_remaining INTEGER,
            start_date DATE,
            expire_date DATE
        );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS visit_logs (
        id SERIAL PRIMARY KEY,
        client_id TEXT,
        visit_number INTEGER,
        visit_date DATE,
        time_period TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            telegram_id BIGINT PRIMARY KEY,
            client_id TEXT NOT NULL,
            login_time TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
    ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS data JSONB DEFAULT '{}';
    """)
    conn.commit()
    cur.close()


def ensure_superuser():
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE client_id = %s", (SUPERUSER_ID,))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO clients (client_id, password, full_name, phone, package_type, visits_remaining)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (SUPERUSER_ID, SUPERUSER_PASSWORD, 'Offline Superuser', 'N/A', 'super', None))
        conn.commit()
        print("✅ Superuser created in DB.")
    else:
        print("✅ Superuser already exists.")
    cur.close()


def add_client(full_name, phone, children_count, package_type):
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
        INSERT INTO clients (client_id, password, full_name, phone, children_count, package_type, visits_remaining, start_date, expire_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (client_id, password, full_name, phone, children_count, package_type, visits, start, expire))
    conn.commit()
    cur.close()
    return client_id, password, start, expire


def get_all_clients():
    cur = conn.cursor()
    cur.execute("""
        SELECT full_name, phone, children_count, package_type, visits_remaining, expire_date, client_id, password
        FROM clients ORDER BY full_name
    """)
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


def decrement_visit(client_id, visit_number=None, date_value=None, time_period=None):
    cur = conn.cursor()

    # Step 1: Decrement visit
    cur.execute("""
        UPDATE clients SET visits_remaining = visits_remaining - 1
        WHERE client_id = %s AND visits_remaining > 0
    """, (client_id,))

    # Step 2: Log visit
    if visit_number and date_value and time_period:
        cur.execute("""
            INSERT INTO visit_logs (client_id, visit_number, visit_date, time_period)
            VALUES (%s, %s, %s, %s)
        """, (client_id, visit_number, date_value, time_period))

    # Step 3: Commit the decrement so SELECT sees updated value
    conn.commit()

    # Step 4: Check remaining visits and delete if 0
    cur.execute("SELECT visits_remaining FROM clients WHERE client_id = %s", (client_id,))
    row = cur.fetchone()
    if row and row[0] == 0:
        cur.execute("DELETE FROM clients WHERE client_id = %s", (client_id,))
        cur.execute("DELETE FROM sessions WHERE client_id = %s", (client_id,))
        conn.commit()

    cur.close()


def count_bookings_for_period(date_value, time_period):
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM visit_logs
        WHERE visit_date = %s AND time_period = %s
    """, (date_value, time_period))
    count = cur.fetchone()[0]
    cur.close()
    return count


def set_session_value(user_id, key, value):

    try:
        conn.rollback()  # Clean failed transaction state if any
    except:
        pass
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sessions WHERE telegram_id = %s", (user_id,))
    exists = cur.fetchone()
    if exists:
        cur.execute("""
            UPDATE sessions SET data = jsonb_set(data, %s, %s, true)
            WHERE telegram_id = %s
        """, (f'{{{key}}}', json.dumps(value), user_id))
    else:
        # Set dummy client_id for initial insert
        cur.execute("""
            INSERT INTO sessions (telegram_id, client_id, data)
            VALUES (%s, %s, %s)
        """, (user_id, 'temp', json.dumps({key: value})))
    conn.commit()
    cur.close()


def get_session_value(telegram_id, key):
    cur = conn.cursor()
    cur.execute("""
        SELECT data->>%s FROM sessions WHERE telegram_id = %s
    """, (key, telegram_id))
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None


def clear_session_keys(telegram_id, keys):
    cur = conn.cursor()
    for key in keys:
        cur.execute("""
            UPDATE sessions SET data = data - %s WHERE telegram_id = %s
        """, (key, telegram_id))
    conn.commit()
    cur.close()