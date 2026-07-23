"""
Async SQLite database layer.
All monetary values stored as integers (kobo would be overkill; we use whole Naira).
"""
import aiosqlite
import logging
from typing import Optional

DB_PATH = "nigeria_economy.db"
logger = logging.getLogger("NigeriaRP.DB")


class Database:
    def __init__(self):
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        self._db = await aiosqlite.connect(DB_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()

    async def _create_tables(self):
        await self._db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users (
            user_id     TEXT PRIMARY KEY,
            username    TEXT NOT NULL,
            wallet      INTEGER NOT NULL DEFAULT 50000,
            bank        INTEGER NOT NULL DEFAULT 0,
            job         TEXT    NOT NULL DEFAULT 'Citizen',
            last_work   TEXT,
            last_daily  TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id     TEXT,
            to_id       TEXT,
            amount      INTEGER NOT NULL,
            type        TEXT    NOT NULL,
            note        TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS treasury (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            balance     INTEGER NOT NULL DEFAULT 500000000,
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ministries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            budget      INTEGER NOT NULL DEFAULT 0,
            spent       INTEGER NOT NULL DEFAULT 0,
            head_id     TEXT
        );

        CREATE TABLE IF NOT EXISTS allocations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ministry_id INTEGER NOT NULL REFERENCES ministries(id),
            requested_by TEXT NOT NULL,
            amount      INTEGER NOT NULL,
            purpose     TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            approved_by TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS businesses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id    TEXT NOT NULL,
            name        TEXT UNIQUE NOT NULL,
            industry    TEXT NOT NULL DEFAULT 'General',
            balance     INTEGER NOT NULL DEFAULT 0,
            revenue     INTEGER NOT NULL DEFAULT 0,
            tax_paid    INTEGER NOT NULL DEFAULT 0,
            employees   INTEGER NOT NULL DEFAULT 0,
            registered_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contracts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            awarded_to  TEXT NOT NULL,
            amount      INTEGER NOT NULL,
            ministry    TEXT,
            awarded_by  TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active',
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS loans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id TEXT NOT NULL,
            principal   INTEGER NOT NULL,
            outstanding INTEGER NOT NULL,
            interest_rate REAL NOT NULL DEFAULT 0.02,
            status      TEXT NOT NULL DEFAULT 'active',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            due_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS fines (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            amount      INTEGER NOT NULL,
            reason      TEXT NOT NULL,
            issued_by   TEXT NOT NULL,
            paid        INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        INSERT OR IGNORE INTO treasury (id, balance) VALUES (1, 500000000);
        """)
        await self._db.commit()
        logger.info("Tables ready.")

    # ── Generic helpers ────────────────────────────────────────────────────────

    async def fetchone(self, sql: str, params=()):
        async with self._db.execute(sql, params) as cur:
            return await cur.fetchone()

    async def fetchall(self, sql: str, params=()):
        async with self._db.execute(sql, params) as cur:
            return await cur.fetchall()

    async def execute(self, sql: str, params=()):
        await self._db.execute(sql, params)
        await self._db.commit()

    # ── User ──────────────────────────────────────────────────────────────────

    async def get_user(self, user_id: str):
        return await self.fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))

    async def ensure_user(self, user_id: str, username: str):
        """Create account if it doesn't exist; always update username."""
        existing = await self.get_user(user_id)
        if not existing:
            await self.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username),
            )
            await self.log_transaction(None, user_id, 50_000, "signup_bonus", "Welcome bonus")
        else:
            await self.execute(
                "UPDATE users SET username=? WHERE user_id=?",
                (username, user_id),
            )

    async def get_or_create_user(self, user_id: str, username: str):
        await self.ensure_user(user_id, username)
        return await self.get_user(user_id)

    async def update_wallet(self, user_id: str, delta: int):
        await self.execute(
            "UPDATE users SET wallet = wallet + ? WHERE user_id=?",
            (delta, user_id),
        )

    async def update_bank(self, user_id: str, delta: int):
        await self.execute(
            "UPDATE users SET bank = bank + ? WHERE user_id=?",
            (delta, user_id),
        )

    async def set_job(self, user_id: str, job: str):
        await self.execute("UPDATE users SET job=? WHERE user_id=?", (job, user_id))

    async def set_last_work(self, user_id: str):
        await self.execute(
            "UPDATE users SET last_work=datetime('now') WHERE user_id=?",
            (user_id,),
        )

    async def set_last_daily(self, user_id: str):
        await self.execute(
            "UPDATE users SET last_daily=datetime('now') WHERE user_id=?",
            (user_id,),
        )

    # ── Transactions ───────────────────────────────────────────────────────────

    async def log_transaction(
        self,
        from_id: Optional[str],
        to_id: Optional[str],
        amount: int,
        tx_type: str,
        note: str = "",
    ):
        await self.execute(
            "INSERT INTO transactions (from_id, to_id, amount, type, note) VALUES (?,?,?,?,?)",
            (from_id, to_id, amount, tx_type, note),
        )

    async def get_user_transactions(self, user_id: str, limit: int = 10):
        return await self.fetchall(
            """SELECT * FROM transactions
               WHERE from_id=? OR to_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, user_id, limit),
        )

    # ── Treasury ──────────────────────────────────────────────────────────────

    async def get_treasury(self):
        return await self.fetchone("SELECT * FROM treasury WHERE id=1")

    async def update_treasury(self, delta: int):
        await self.execute(
            "UPDATE treasury SET balance=balance+?, updated_at=datetime('now') WHERE id=1",
            (delta,),
        )

    # ── Ministries ────────────────────────────────────────────────────────────

    async def get_ministry(self, name: str):
        return await self.fetchone("SELECT * FROM ministries WHERE name=?", (name,))

    async def get_all_ministries(self):
        return await self.fetchall("SELECT * FROM ministries ORDER BY name")

    async def create_ministry(self, name: str, head_id: str = None):
        await self.execute(
            "INSERT OR IGNORE INTO ministries (name, head_id) VALUES (?,?)",
            (name, head_id),
        )

    async def update_ministry_budget(self, ministry_id: int, delta: int):
        await self.execute(
            "UPDATE ministries SET budget=budget+? WHERE id=?",
            (delta, ministry_id),
        )

    # ── Allocations ───────────────────────────────────────────────────────────

    async def create_allocation(
        self, ministry_id: int, requested_by: str, amount: int, purpose: str
    ):
        await self.execute(
            """INSERT INTO allocations (ministry_id, requested_by, amount, purpose)
               VALUES (?,?,?,?)""",
            (ministry_id, requested_by, amount, purpose),
        )
        async with self._db.execute("SELECT last_insert_rowid()") as cur:
            row = await cur.fetchone()
            return row[0]

    async def get_pending_allocations(self):
        return await self.fetchall(
            """SELECT a.*, m.name as ministry_name
               FROM allocations a JOIN ministries m ON a.ministry_id=m.id
               WHERE a.status='pending' ORDER BY a.created_at""",
        )

    async def resolve_allocation(self, alloc_id: int, status: str, approved_by: str):
        await self.execute(
            """UPDATE allocations
               SET status=?, approved_by=?, resolved_at=datetime('now')
               WHERE id=?""",
            (status, approved_by, alloc_id),
        )

    # ── Businesses ────────────────────────────────────────────────────────────

    async def get_business(self, name: str):
        return await self.fetchone(
            "SELECT * FROM businesses WHERE LOWER(name)=LOWER(?)", (name,)
        )

    async def get_user_businesses(self, owner_id: str):
        return await self.fetchall(
            "SELECT * FROM businesses WHERE owner_id=?", (owner_id,)
        )

    async def create_business(self, owner_id: str, name: str, industry: str):
        await self.execute(
            "INSERT INTO businesses (owner_id, name, industry) VALUES (?,?,?)",
            (owner_id, name, industry),
        )

    async def update_business_balance(self, biz_id: int, delta: int):
        await self.execute(
            "UPDATE businesses SET balance=balance+? WHERE id=?",
            (delta, biz_id),
        )

    async def top_businesses(self, limit: int = 10):
        return await self.fetchall(
            "SELECT * FROM businesses ORDER BY balance DESC LIMIT ?", (limit,)
        )

    # ── Contracts ─────────────────────────────────────────────────────────────

    async def award_contract(
        self, title: str, awarded_to: str, amount: int, ministry: str, awarded_by: str
    ):
        await self.execute(
            """INSERT INTO contracts (title, awarded_to, amount, ministry, awarded_by)
               VALUES (?,?,?,?,?)""",
            (title, awarded_to, amount, ministry, awarded_by),
        )

    async def get_contracts(self, limit: int = 10):
        return await self.fetchall(
            "SELECT * FROM contracts ORDER BY created_at DESC LIMIT ?", (limit,)
        )

    # ── Loans ─────────────────────────────────────────────────────────────────

    async def create_loan(self, borrower_id: str, amount: int, rate: float):
        await self.execute(
            """INSERT INTO loans (borrower_id, principal, outstanding, interest_rate,
               due_at)
               VALUES (?,?,?,?, datetime('now','+30 days'))""",
            (borrower_id, amount, amount, rate),
        )

    async def get_active_loans(self, borrower_id: str):
        return await self.fetchall(
            "SELECT * FROM loans WHERE borrower_id=? AND status='active'",
            (borrower_id,),
        )

    async def repay_loan(self, loan_id: int, amount: int):
        loan = await self.fetchone("SELECT * FROM loans WHERE id=?", (loan_id,))
        if not loan:
            return None
        new_outstanding = max(0, loan["outstanding"] - amount)
        status = "repaid" if new_outstanding == 0 else "active"
        await self.execute(
            "UPDATE loans SET outstanding=?, status=? WHERE id=?",
            (new_outstanding, status, loan_id),
        )
        return new_outstanding

    # ── Fines ─────────────────────────────────────────────────────────────────

    async def issue_fine(self, user_id: str, amount: int, reason: str, issued_by: str):
        await self.execute(
            "INSERT INTO fines (user_id, amount, reason, issued_by) VALUES (?,?,?,?)",
            (user_id, amount, reason, issued_by),
        )

    async def get_unpaid_fines(self, user_id: str):
        return await self.fetchall(
            "SELECT * FROM fines WHERE user_id=? AND paid=0", (user_id,)
        )

    async def pay_fine(self, fine_id: int):
        await self.execute("UPDATE fines SET paid=1 WHERE id=?", (fine_id,))

    # ── Leaderboard ───────────────────────────────────────────────────────────

    async def richest_users(self, limit: int = 10):
        return await self.fetchall(
            "SELECT * FROM users ORDER BY (wallet+bank) DESC LIMIT ?", (limit,)
        )

    async def total_money_supply(self):
        row = await self.fetchone("SELECT SUM(wallet+bank) as total FROM users")
        return row["total"] or 0

    async def close(self):
        if self._db:
            await self._db.close()
