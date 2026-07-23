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
