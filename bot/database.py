"""
Async SQLite database layer.
All monetary values stored as integers (kobo would be overkill; we use whole Naira).
"""
import aiosqlite
import json
import logging
import os
import tempfile
from typing import Optional

DB_PATH = "nigeria_economy.db"
PLAYER_DATA_PATH = "player_data.txt"
logger = logging.getLogger("NigeriaRP.DB")


class Database:
    def __init__(self):
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        self._db = await aiosqlite.connect(DB_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()
        await self.sync_players_from_text()
        await self.sync_players_to_text()

    async def _create_tables(self):
        # Migrate databases created before configurable betting limits existed.
        # This must happen before the main script references bet_settings.max_bet.
        try:
            await self._db.execute(
                "ALTER TABLE bet_settings ADD COLUMN max_bet INTEGER NOT NULL DEFAULT 1000000"
            )
            await self._db.commit()
        except Exception:
            # The table may not exist yet, or the column may already exist.
            pass
        try:
            await self._db.execute(
                "ALTER TABLE bet_settings ADD COLUMN matches_enabled INTEGER NOT NULL DEFAULT 1"
            )
            await self._db.commit()
        except Exception:
            pass
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

        CREATE TABLE IF NOT EXISTS matches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team   TEXT NOT NULL,
            away_team   TEXT NOT NULL,
            home_odds   REAL NOT NULL,
            draw_odds   REAL NOT NULL,
            away_odds   REAL NOT NULL,
            status      TEXT NOT NULL DEFAULT 'open',
            result      TEXT,
            home_score  INTEGER,
            away_score  INTEGER,
            channel_id  TEXT,
            finished_at TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id    INTEGER NOT NULL REFERENCES matches(id),
            user_id     TEXT NOT NULL,
            choice      TEXT NOT NULL,
            amount      INTEGER NOT NULL,
            payout      INTEGER,
            settled     INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bet_settings (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            channel_id  TEXT,
            enabled     INTEGER NOT NULL DEFAULT 0,
            max_bet     INTEGER NOT NULL DEFAULT 1000000,
            matches_enabled INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS store_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            price       INTEGER NOT NULL,
            stock       INTEGER NOT NULL DEFAULT -1,
            created_by  TEXT NOT NULL,
            active      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS store_purchases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER NOT NULL REFERENCES store_items(id),
            user_id     TEXT NOT NULL,
            quantity    INTEGER NOT NULL,
            total       INTEGER NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS role_income (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id      TEXT NOT NULL,
            role_id       TEXT NOT NULL,
            role_name     TEXT NOT NULL,
            income        INTEGER NOT NULL,
            interval_hours REAL NOT NULL,
            enabled       INTEGER NOT NULL DEFAULT 1,
            created_by    TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS role_income_payments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL REFERENCES role_income(id),
            guild_id    TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            amount      INTEGER NOT NULL,
            paid_at     TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS betting_slips (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            code          TEXT UNIQUE NOT NULL,
            creator_id    TEXT NOT NULL,
            channel_id    TEXT NOT NULL,
            selections    TEXT NOT NULL,
            stake         INTEGER NOT NULL,
            potential     INTEGER NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            payout        INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            settles_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS robbery_cooldowns (
            user_id       TEXT PRIMARY KEY,
            last_attempt  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS roulette_settings (
            guild_id      TEXT PRIMARY KEY,
            enabled       INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS support_settings (
            guild_id      TEXT PRIMARY KEY,
            role_id       TEXT
        );

        CREATE TABLE IF NOT EXISTS immigration (
            guild_id     TEXT NOT NULL,
            user_id      TEXT NOT NULL,
            full_name    TEXT NOT NULL,
            age          INTEGER NOT NULL,
            state        TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'pending',
            national_id  TEXT UNIQUE,
            tin          TEXT UNIQUE,
            approved_by  TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            approved_at  TEXT,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS jail_records (
            guild_id   TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            reason     TEXT NOT NULL,
            jailed_by  TEXT NOT NULL,
            jailed_at  TEXT NOT NULL DEFAULT (datetime('now')),
            released_at TEXT,
            PRIMARY KEY (guild_id, user_id)
        );

        INSERT OR IGNORE INTO treasury (id, balance) VALUES (1, 500000000);
        INSERT OR IGNORE INTO bet_settings (id, enabled, max_bet, matches_enabled)
            VALUES (1, 0, 5000000, 1);
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
        await self.sync_players_to_text()

    async def sync_players_to_text(self):
        """Keep a readable, atomic text backup of all player account records."""
        rows = await self.fetchall(
            """SELECT user_id, username, wallet, bank, job, last_work,
                      last_daily, created_at
               FROM users ORDER BY user_id"""
        )
        directory = os.path.dirname(os.path.abspath(PLAYER_DATA_PATH))
        fd, temp_path = tempfile.mkstemp(prefix=".player_data.", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as backup:
                for row in rows:
                    backup.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
                backup.flush()
                os.fsync(backup.fileno())
            os.replace(temp_path, PLAYER_DATA_PATH)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    async def sync_players_from_text(self):
        """Restore missing player rows from the text backup without overwriting progress."""
        if not os.path.exists(PLAYER_DATA_PATH):
            return 0
        restored = 0
        with open(PLAYER_DATA_PATH, "r", encoding="utf-8") as backup:
            for line in backup:
                try:
                    player = json.loads(line)
                    required = {"user_id", "username", "wallet", "bank", "job"}
                    if not required.issubset(player):
                        continue
                    cursor = await self._db.execute(
                        """INSERT OR IGNORE INTO users
                           (user_id, username, wallet, bank, job, last_work,
                            last_daily, created_at)
                           VALUES (?,?,?,?,?,?,?,COALESCE(?, datetime('now')))""",
                        (
                            str(player["user_id"]),
                            str(player["username"]),
                            int(player["wallet"]),
                            int(player["bank"]),
                            str(player["job"]),
                            player.get("last_work"),
                            player.get("last_daily"),
                            player.get("created_at"),
                        ),
                    )
                    restored += cursor.rowcount
                except (ValueError, TypeError, json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Skipping invalid player backup row: %s", exc)
        await self._db.commit()
        if restored:
            logger.info("Restored %s missing player record(s) from %s.", restored, PLAYER_DATA_PATH)
        return restored

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
        if getattr(self, "bot", None):
            self.bot.dispatch(
                "financial_activity", from_id, to_id, amount, tx_type, note
            )

    async def get_user_transactions(self, user_id: str, limit: int = 10):
        return await self.fetchall(
            """SELECT * FROM transactions
               WHERE from_id=? OR to_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, user_id, limit),
        )

    # ── Immigration ──────────────────────────────────────────────────────────

    async def get_immigration(self, guild_id: str, user_id: str):
        return await self.fetchone(
            "SELECT * FROM immigration WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )

    async def register_immigration(
        self, guild_id: str, user_id: str, full_name: str, age: int, state: str
    ):
        await self.execute(
            """INSERT INTO immigration
               (guild_id, user_id, full_name, age, state, status)
               VALUES (?,?,?,?,?,'pending')
               ON CONFLICT(guild_id, user_id) DO UPDATE SET
               full_name=excluded.full_name, age=excluded.age,
               state=excluded.state, status='pending',
               national_id=NULL, tin=NULL, approved_by=NULL, approved_at=NULL""",
            (guild_id, user_id, full_name, age, state),
        )
        return await self.get_immigration(guild_id, user_id)

    async def approve_immigration(
        self, guild_id: str, user_id: str, national_id: str, tin: str, approved_by: str
    ):
        await self.execute(
            """UPDATE immigration
               SET status='approved', national_id=?, tin=?,
                   approved_by=?, approved_at=datetime('now')
               WHERE guild_id=? AND user_id=?""",
            (national_id, tin, approved_by, guild_id, user_id),
        )
        return await self.get_immigration(guild_id, user_id)

    async def decline_immigration(self, guild_id: str, user_id: str, declined_by: str):
        await self.execute(
            """UPDATE immigration SET status='declined', approved_by=?
               WHERE guild_id=? AND user_id=?""",
            (declined_by, guild_id, user_id),
        )
        return await self.get_immigration(guild_id, user_id)

    async def get_pending_immigration(self, guild_id: str, limit: int = 25):
        return await self.fetchall(
            """SELECT * FROM immigration
               WHERE guild_id=? AND status='pending'
               ORDER BY created_at ASC LIMIT ?""",
            (guild_id, limit),
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

    # ── Betting ───────────────────────────────────────────────────────────────

    async def create_match(
        self, home: str, away: str,
        home_odds: float, draw_odds: float, away_odds: float,
        channel_id: str,
    ) -> int:
        await self.execute(
            """INSERT INTO matches
               (home_team, away_team, home_odds, draw_odds, away_odds, channel_id)
               VALUES (?,?,?,?,?,?)""",
            (home, away, home_odds, draw_odds, away_odds, channel_id),
        )
        async with self._db.execute("SELECT last_insert_rowid()") as cur:
            row = await cur.fetchone()
            return row[0]

    async def close_match(self, match_id: int):
        await self.execute(
            "UPDATE matches SET status='closed' WHERE id=?", (match_id,)
        )

    async def finish_match(self, match_id: int, result: str, home_score: int, away_score: int):
        await self.execute(
            """UPDATE matches SET status='finished', result=?, home_score=?,
               away_score=?, finished_at=datetime('now') WHERE id=?""",
            (result, home_score, away_score, match_id),
        )

    async def cancel_match(self, match_id: int):
        await self.execute(
            "UPDATE matches SET status='cancelled' WHERE id=?", (match_id,)
        )

    async def place_bet(self, match_id: int, user_id: str, choice: str, amount: int):
        await self.execute(
            "INSERT INTO bets (match_id, user_id, choice, amount) VALUES (?,?,?,?)",
            (match_id, user_id, choice, amount),
        )

    async def get_match_bets(self, match_id: int):
        return await self.fetchall(
            "SELECT * FROM bets WHERE match_id=?", (match_id,)
        )

    async def get_user_match_bet(self, user_id: str, match_id: int):
        return await self.fetchone(
            "SELECT * FROM bets WHERE user_id=? AND match_id=?", (user_id, match_id)
        )

    async def settle_bet(self, bet_id: int, payout: int):
        await self.execute(
            "UPDATE bets SET payout=?, settled=1 WHERE id=?", (payout, bet_id)
        )

    async def get_user_bets(self, user_id: str, limit: int = 10):
        return await self.fetchall(
            "SELECT * FROM bets WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )

    async def get_user_bet_stats(self, user_id: str) -> dict:
        row = await self.fetchone(
            """SELECT
               COUNT(*) as total,
               SUM(CASE WHEN settled=1 AND payout > 0 THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN settled=1 AND payout = 0 THEN 1 ELSE 0 END) as losses,
               COALESCE(SUM(amount), 0) as total_wagered,
               COALESCE(SUM(CASE WHEN settled=1 THEN payout ELSE 0 END), 0) as total_won
               FROM bets WHERE user_id=?""",
            (user_id,),
        )
        return {
            "total":         row["total"]         or 0,
            "wins":          row["wins"]           or 0,
            "losses":        row["losses"]         or 0,
            "total_wagered": row["total_wagered"]  or 0,
            "total_won":     row["total_won"]      or 0,
        }

    async def set_bet_setting(self, channel_id: Optional[str], enabled: bool):
        await self.execute(
            """INSERT INTO bet_settings (id, channel_id, enabled)
               VALUES (1, ?, ?)
               ON CONFLICT(id) DO UPDATE SET channel_id=excluded.channel_id, enabled=excluded.enabled""",
            (channel_id, 1 if enabled else 0),
        )

    async def get_max_bet(self) -> int:
        row = await self.fetchone("SELECT max_bet FROM bet_settings WHERE id=1")
        return int(row["max_bet"]) if row and row["max_bet"] else 1_000_000

    async def set_max_bet(self, amount: int):
        await self.execute(
            "INSERT INTO bet_settings (id, max_bet) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET max_bet=excluded.max_bet",
            (amount,),
        )

    async def get_bet_setting(self):
        return await self.fetchone("SELECT * FROM bet_settings WHERE id=1")

    async def set_matches_enabled(self, enabled: bool):
        await self.execute(
            "UPDATE bet_settings SET matches_enabled=? WHERE id=1",
            (1 if enabled else 0,),
        )

    async def get_matches_enabled(self) -> bool:
        row = await self.fetchone("SELECT matches_enabled FROM bet_settings WHERE id=1")
        return bool(row["matches_enabled"]) if row else True

    async def set_support_role(self, guild_id: str, role_id: str | None):
        await self.execute(
            """INSERT INTO support_settings (guild_id, role_id) VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET role_id=excluded.role_id""",
            (guild_id, role_id),
        )

    async def get_support_role(self, guild_id: str):
        return await self.fetchone(
            "SELECT role_id FROM support_settings WHERE guild_id=?", (guild_id,)
        )

    async def set_roulette_enabled(self, guild_id: str, enabled: bool):
        await self.execute(
            """INSERT INTO roulette_settings (guild_id, enabled) VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET enabled=excluded.enabled""",
            (guild_id, 1 if enabled else 0),
        )

    async def get_roulette_enabled(self, guild_id: str) -> bool:
        row = await self.fetchone(
            "SELECT enabled FROM roulette_settings WHERE guild_id=?", (guild_id,)
        )
        return bool(row["enabled"]) if row else True

    # ── Store ────────────────────────────────────────────────────────────────

    async def create_store_item(self, name: str, description: str, price: int,
                                stock: int, created_by: str):
        await self.execute(
            "INSERT INTO store_items (name, description, price, stock, created_by) "
            "VALUES (?,?,?,?,?)",
            (name, description, price, stock, created_by),
        )

    async def get_store_items(self, active_only: bool = True):
        sql = "SELECT * FROM store_items"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY price ASC"
        return await self.fetchall(sql)

    async def get_store_item(self, item_id: int):
        return await self.fetchone("SELECT * FROM store_items WHERE id=?", (item_id,))

    async def get_user_inventory(self, user_id: str):
        return await self.fetchall(
            """SELECT i.id, i.name, i.description, SUM(p.quantity) AS quantity,
                      SUM(p.total) AS spent
               FROM store_purchases p
               JOIN store_items i ON i.id=p.item_id
               WHERE p.user_id=?
               GROUP BY i.id, i.name, i.description
               ORDER BY i.name""",
            (user_id,),
        )

    # ── Police and jail ──────────────────────────────────────────────────────

    async def get_jail_record(self, guild_id: str, user_id: str):
        return await self.fetchone(
            "SELECT * FROM jail_records WHERE guild_id=? AND user_id=? AND released_at IS NULL",
            (guild_id, user_id),
        )

    async def jail_user(self, guild_id: str, user_id: str, reason: str, jailed_by: str):
        await self.execute(
            """INSERT INTO jail_records (guild_id,user_id,reason,jailed_by)
               VALUES (?,?,?,?)
               ON CONFLICT(guild_id,user_id) DO UPDATE SET
               reason=excluded.reason, jailed_by=excluded.jailed_by,
               jailed_at=datetime('now'), released_at=NULL""",
            (guild_id, user_id, reason, jailed_by),
        )
        return await self.get_jail_record(guild_id, user_id)

    async def release_user(self, guild_id: str, user_id: str):
        await self.execute(
            "UPDATE jail_records SET released_at=datetime('now') WHERE guild_id=? AND user_id=? AND released_at IS NULL",
            (guild_id, user_id),
        )

    async def purchase_store_item(self, item_id: int, user_id: str, quantity: int):
        item = await self.get_store_item(item_id)
        if not item or not item["active"]:
            return None
        if item["stock"] != -1 and item["stock"] < quantity:
            return None
        total = item["price"] * quantity
        await self.execute(
            "UPDATE store_items SET stock=CASE WHEN stock=-1 THEN -1 ELSE stock-? END WHERE id=?",
            (quantity, item_id),
        )
        await self.execute(
            "INSERT INTO store_purchases (item_id,user_id,quantity,total) VALUES (?,?,?,?)",
            (item_id, user_id, quantity, total),
        )
        return total

    async def set_store_item_active(self, item_id: int, active: bool):
        await self.execute("UPDATE store_items SET active=? WHERE id=?", (1 if active else 0, item_id))

    # ── Role income ──────────────────────────────────────────────────────────

    async def upsert_role_income(self, guild_id: str, role_id: str, role_name: str,
                                 income: int, interval_hours: float, created_by: str):
        await self.execute(
            "INSERT INTO role_income "
            "(guild_id,role_id,role_name,income,interval_hours,created_by) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(guild_id,role_id) DO UPDATE SET role_name=excluded.role_name, "
            "income=excluded.income, interval_hours=excluded.interval_hours, enabled=1",
            (guild_id, role_id, role_name, income, interval_hours, created_by),
        )

    async def get_role_income(self, guild_id: str, role_id: str = None):
        if role_id:
            return await self.fetchone(
                "SELECT * FROM role_income WHERE guild_id=? AND role_id=?",
                (guild_id, role_id),
            )
        return await self.fetchall(
            "SELECT * FROM role_income WHERE guild_id=? ORDER BY role_name",
            (guild_id,),
        )

    async def set_role_income_enabled(self, schedule_id: int, enabled: bool):
        await self.execute("UPDATE role_income SET enabled=? WHERE id=?",
                           (1 if enabled else 0, schedule_id))

    async def get_due_role_income(self, guild_id: str):
        return await self.fetchall(
            "SELECT * FROM role_income WHERE guild_id=? AND enabled=1",
            (guild_id,),
        )

    async def get_last_role_payment(self, schedule_id: int, user_id: str):
        return await self.fetchone(
            "SELECT * FROM role_income_payments WHERE schedule_id=? AND user_id=? "
            "ORDER BY paid_at DESC LIMIT 1",
            (schedule_id, user_id),
        )

    async def record_role_payment(self, schedule_id: int, guild_id: str,
                                 user_id: str, amount: int):
        await self.execute(
            "INSERT INTO role_income_payments (schedule_id,guild_id,user_id,amount) "
            "VALUES (?,?,?,?)",
            (schedule_id, guild_id, user_id, amount),
        )

    # ── Shareable betting slips ──────────────────────────────────────────────

    async def create_betting_slip(self, code: str, creator_id: str, channel_id: str,
                                  selections: str, stake: int, potential: int,
                                  settles_at: str):
        await self.execute(
            "INSERT INTO betting_slips "
            "(code,creator_id,channel_id,selections,stake,potential,settles_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (code, creator_id, channel_id, selections, stake, potential, settles_at),
        )

    async def get_betting_slip(self, code: str):
        return await self.fetchone(
            "SELECT * FROM betting_slips WHERE code=?", (code.upper(),)
        )

    async def get_last_robbery(self, user_id: str):
        return await self.fetchone(
            "SELECT last_attempt FROM robbery_cooldowns WHERE user_id=?",
            (user_id,),
        )

    async def set_last_robbery(self, user_id: str):
        await self.execute(
            """INSERT INTO robbery_cooldowns (user_id, last_attempt)
               VALUES (?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET last_attempt=datetime('now')""",
            (user_id,),
        )

    async def settle_betting_slip(self, slip_id: int, status: str, payout: int):
        await self.execute(
            "UPDATE betting_slips SET status=?, payout=? WHERE id=?",
            (status, payout, slip_id),
        )

    async def get_pending_betting_slips(self):
        return await self.fetchall(
            "SELECT * FROM betting_slips WHERE status='pending' "
            "AND datetime(settles_at) <= datetime('now')"
        )

    async def close(self):
        if self._db:
            await self._db.close()
