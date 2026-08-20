"""
Configuration constants for the Nigerian Government RP Economy Bot.
"""

# ── Currency ──────────────────────────────────────────────────────────────────
CURRENCY = "₦"
CURRENCY_NAME = "Naira"

# ── Economy knobs ─────────────────────────────────────────────────────────────
STARTING_BALANCE   = 50_000      # ₦ given to every new citizen
DAILY_STIPEND      = 10_000      # /daily payout
DAILY_COOLDOWN_H   = 20          # hours between /daily claims
WORK_COOLDOWN_H    = 4           # hours between /work uses
TAX_RATE           = 0.075       # 7.5 % default VAT
INTEREST_RATE      = 0.02        # 2 % per 24 h on loans
LOAN_MAX_RATIO     = 5.0         # can borrow up to 5× wallet balance
BANK_TRANSFER_FEE  = 0.005       # 0.5 % on /pay transfers
MAX_TRANSFER       = 10_000_000  # single transfer cap

# ── National Treasury seed ────────────────────────────────────────────────────
TREASURY_SEED = 500_000_000      # ₦500 million starting treasury

# ── Job definitions ────────────────────────────────────────────────────────────
# name -> { monthly_salary, work_per_use, role_required }
JOBS = {
    "President":           {"monthly": 5_000_000, "work": 200_000, "role": "President"},
    "Vice President":      {"monthly": 3_500_000, "work": 150_000, "role": "Vice President"},
    "Governor":            {"monthly": 2_000_000, "work": 100_000, "role": "Governor"},
    "Minister":            {"monthly": 1_500_000, "work":  80_000, "role": "Minister"},
    "Senator":             {"monthly": 1_200_000, "work":  60_000, "role": "Senator"},
    "Police Officer":      {"monthly":   400_000, "work":  20_000, "role": "Police Officer"},
    "Judge":               {"monthly":   800_000, "work":  40_000, "role": "Judge"},
    "Lawyer":              {"monthly":   600_000, "work":  30_000, "role": "Lawyer"},
    "Doctor":              {"monthly":   700_000, "work":  35_000, "role": "Doctor"},
    "Business Owner":      {"monthly":   500_000, "work":  25_000, "role": "Business Owner"},
    "Citizen":             {"monthly":   150_000, "work":   5_000, "role": None},
}

# ── Roles that unlock government-only commands ─────────────────────────────────
GOV_ROLES = {
    "President",
    "Vice President",
    "Governor",
    "Minister",
    "Minister of Finance",
    "Accountant General",
    "CBN Governor",
    "INEC Chairman",
    "Senator",
}

# Roles created automatically when the bot joins a server or an admin runs
# /setup-roles. Existing roles with these exact names are reused.
REQUIRED_DISCORD_ROLES = [
    "President",
    "Vice President",
    "Governor",
    "Minister",
    "Minister of Finance",
    "Accountant General",
    "CBN Governor",
    "INEC Chairman",
    "Senator",
    "Police Officer",
    "Judge",
    "Lawyer",
    "Doctor",
    "Business Owner",
    "Immigration Officer",
    "Visa Holder",
    "Jail Inmate",
    "Citizen",
]

JUDICIARY_ROLES = {"Judge", "President"}
POLICE_ROLES    = {"Police Officer", "President", "Governor"}
FINANCE_ROLES   = {"Minister of Finance", "President", "Accountant General"}
CBN_ROLES       = {"CBN Governor", "President"}

# ── Embed colours ─────────────────────────────────────────────────────────────
COLOR_SUCCESS = 0x00B300   # green
COLOR_ERROR   = 0xCC0000   # red
COLOR_INFO    = 0x008751   # Nigerian green
COLOR_GOLD    = 0xFFD700   # gold / treasury
COLOR_WARN    = 0xFF8C00   # orange
COLOR_BET     = 0x1A1A2E   # dark navy for betting embeds

# ── Football Betting ───────────────────────────────────────────────────────────
# Timing (seconds)
BET_WINDOW_SECS   = 180   # 3 min betting window
BET_WARNING_SECS  = 30    # warn at 30s remaining
BET_RESULT_PAUSE  = 30    # pause before result after close
BET_CYCLE_SECS    = 300   # total cycle: 5 minutes

# Min/max single bet
BET_MIN = 1_000
BET_MAX = 5_000_000

# House edge applied to odds (multiplier on winnings, keeps house profitable)
HOUSE_EDGE = 0.95   # winners receive 95% of true odds payout

# Nigerian League + international clubs for variety
FOOTBALL_TEAMS = [
    # Nigerian Professional Football League
    {"name": "Enyimba FC",            "emoji": "🔵", "league": "NPFL"},
    {"name": "Rivers United",         "emoji": "🟢", "league": "NPFL"},
    {"name": "Kano Pillars",          "emoji": "🟡", "league": "NPFL"},
    {"name": "Lobi Stars",            "emoji": "🔴", "league": "NPFL"},
    {"name": "Nasarawa United",       "emoji": "🟣", "league": "NPFL"},
    {"name": "Shooting Stars",        "emoji": "⭐", "league": "NPFL"},
    {"name": "Rangers International", "emoji": "🟢", "league": "NPFL"},
    {"name": "Heartland FC",          "emoji": "❤️",  "league": "NPFL"},
    {"name": "Akwa United",           "emoji": "🟠", "league": "NPFL"},
    {"name": "Plateau United",        "emoji": "🏔️",  "league": "NPFL"},
    {"name": "Sunshine Stars",        "emoji": "☀️",  "league": "NPFL"},
    {"name": "Remo Stars",            "emoji": "⚡", "league": "NPFL"},
    {"name": "Bendel Insurance",      "emoji": "🔵", "league": "NPFL"},
    {"name": "El-Kanemi Warriors",    "emoji": "⚔️",  "league": "NPFL"},
    {"name": "Niger Tornadoes",       "emoji": "🌪️",  "league": "NPFL"},
    {"name": "Kwara United",          "emoji": "🟤", "league": "NPFL"},
    # African clubs
    {"name": "Al Ahly",              "emoji": "🔴", "league": "CAF"},
    {"name": "Wydad AC",             "emoji": "🔴", "league": "CAF"},
    {"name": "Mamelodi Sundowns",    "emoji": "🟡", "league": "CAF"},
    {"name": "TP Mazembe",           "emoji": "🔴", "league": "CAF"},
    # International
    {"name": "Manchester City",      "emoji": "🔵", "league": "EPL"},
    {"name": "Arsenal",              "emoji": "🔴", "league": "EPL"},
    {"name": "Chelsea",              "emoji": "🔵", "league": "EPL"},
    {"name": "Manchester United",    "emoji": "🔴", "league": "EPL"},
    {"name": "Real Madrid",          "emoji": "⚪", "league": "La Liga"},
    {"name": "Barcelona",            "emoji": "🔵", "league": "La Liga"},
    {"name": "PSG",                  "emoji": "🔵", "league": "Ligue 1"},
    {"name": "Bayern Munich",        "emoji": "🔴", "league": "Bundesliga"},
]
