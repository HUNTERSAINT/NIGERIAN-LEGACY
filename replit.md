# 🇳🇬 Nigerian Government RP Economy Bot

A full-featured Discord economy bot built for Nigerian Government RP servers, using **discord.py** and **SQLite**.

## Project Structure

```
main.py                 – Entry point / bot class
bot/
  config.py             – All configurable constants (salaries, rates, roles)
  database.py           – Async SQLite database layer (aiosqlite)
  utils.py              – Shared embed helpers
  cogs/
    economy.py          – Citizen commands (/balance, /pay, /work, /daily, …)
    government.py       – Government commands (/grant, /fine, /salary-pay, …)
    banking.py          – CBN / loan commands (/loan-request, /cbn-print, …)
    business.py         – Business commands (/business-register, …)
    jobs.py             – Job system (/jobs, /setjob, /myjob)
    admin.py            – Admin commands (/economy-stats, /addmoney, …)
nigeria_economy.db      – SQLite database (auto-created on first run)
```

## Required Secret

| Secret name      | Value                         |
|-----------------|-------------------------------|
| `DISCORD_TOKEN` | Your Discord bot token        |

## Running the Bot

```
python main.py
```

## Key Configuration (`bot/config.py`)

- `STARTING_BALANCE` — ₦50,000 for every new citizen
- `DAILY_STIPEND` — ₦10,000 per `/daily`
- `WORK_COOLDOWN_H` — 4 hours between `/work` uses
- `INTEREST_RATE` — 2 % per 24 h on CBN loans
- `TAX_RATE` — 7.5 % VAT on business withdrawals
- `TREASURY_SEED` — ₦500,000,000 starting treasury

## Role Permissions

| Discord Role              | Unlocks                                   |
|---------------------------|-------------------------------------------|
| President                 | All government commands                   |
| Vice President / Governor | Salary pay, contracts, allocations        |
| Minister / Senator        | Allocation requests, contracts            |
| Minister of Finance       | Grant, approve allocations, tax collect   |
| Accountant General        | Finance commands                          |
| CBN Governor              | `/cbn-print`, `/cbn-seize`                |
| Police Officer            | `/fine`                                   |
| Judge                     | `/fine`                                   |
| Server Administrator      | All admin commands, `/setjob`             |

## User Preferences

- Currency symbol: ₦ (Naira)
- Database: SQLite (file: `nigeria_economy.db`)
- Use slash commands (discord.py app_commands)
- Role-based permission checks (no hardcoded user IDs)
