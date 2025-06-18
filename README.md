# Alma Nest Bot 

Alma Nest Bot is a Telegram bot designed to manage client bookings for a child development center or educational program. It handles visit-based packages, tracks visit usage, and provides admin features for managing clients.

---

## Features

### For Clients:
- Unique 4-digit ID and 6-digit password for login
- Packages with fixed visit limits (e.g., 8, 10, 12 visits)
- Validity for 30 days or until visits are used up
- Visit confirmation through inline buttons
- Session persistence — users don’t need to re-login every time

### For Admin:
- Add new clients with full details
- Generate ID/password automatically
- View all active clients
- Book offline clients manually (superuser mode)
- Track visit history and remaining visits
- Delete expired or fully used accounts automatically

---

## Technologies Used

- Python 3.10+
- `python-telegram-bot`
- PostgreSQL (via `psycopg2`)
- Flask (for webhook if deployed)
- `asyncio`
