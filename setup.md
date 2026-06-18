# RailOne Setup

## Prerequisites

Ensure the following are installed before running RailOne:

### Python

```bash
Python 3.12+
```

### PostgreSQL

```bash
PostgreSQL 15+
```

### Git

```bash
git --version
```

---

## Install Dependencies

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux / macOS:

```bash
source venv/bin/activate
```

Install project dependencies:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/railone
RAILONE_ENV=development
```

Adjust values according to your local setup.

---

## Database

Create the database:

```sql
CREATE DATABASE railone;
```

Run migrations:

```bash
alembic upgrade head
```

---

## Run RailOne

```bash
uvicorn main:app --reload
```

---

## Notes for Contributors

- Always update `requirements.txt` when introducing new packages.
- Keep execution flows deterministic.
- Preserve UTT continuity across retries and route mutations.
- RTTs represent execution attempts and may change during replay.
- Do not commit secrets, private keys, or `.env` files.
