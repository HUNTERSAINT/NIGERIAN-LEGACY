# 🇳🇬 Nigerian Legacy RP Economy Bot — Full Command Reference
### For Admin & Staff Use Only

---

## 👤 CITIZEN COMMANDS
> Available to all members

| Command | Description |
|---|---|
| `/balance [@user]` | View your wallet, bank balance, and net worth. Tag someone to check theirs. |
| `/pay @user <amount>` | Send money from your wallet to another member (0.5% fee goes to Treasury). |
| `/deposit <amount or all>` | Move cash from your wallet into your bank account. |
| `/withdraw <amount or all>` | Move cash from your bank to your wallet. |
| `/work` | Earn income based on your job. Cooldown: **4 hours**. |
| `/daily` | Claim your daily government stipend of ₦10,000. Cooldown: **20 hours**. |
| `/history` | View your last 10 transactions. |
| `/inventory` | View your full profile — job, balances, fines, loans, businesses. |
| `/fines` | View your unpaid fines. |
| `/payfine <fine_id>` | Pay an outstanding fine from your wallet to the Treasury. |
| `/leaderboard` | See the top 10 richest citizens and economy stats. |

---

## 💼 JOB SYSTEM

| Command | Who Can Use | Description |
|---|---|---|
| `/jobs` | Everyone | List all jobs, salaries, and required roles. |
| `/myjob` | Everyone | View your current job and earnings. |
| `/setjob @member <job>` | **Admin / President / VP / Governor** | Assign a job to a member. |

**Available Jobs & Monthly Salaries:**
- 🏛 President — ₦5,000,000/month
- 🏛 Vice President — ₦3,500,000/month
- 🏛 Governor — ₦2,000,000/month
- 🏛 Minister — ₦1,500,000/month
- 🏛 Senator — ₦1,200,000/month
- ⚖️ Judge — ₦800,000/month
- 👨‍⚕️ Doctor — ₦700,000/month
- ⚖️ Lawyer — ₦600,000/month
- 🏢 Business Owner — ₦500,000/month
- 🚔 Police Officer — ₦400,000/month
- 👤 Citizen — ₦150,000/month

---

## 🏛 GOVERNMENT COMMANDS
> Requires government role OR Server Administrator

| Command | Required Role | Description |
|---|---|---|
| `/treasury` | Everyone | View the National Treasury balance and ministry stats. |
| `/grant @user <amount> <reason>` | Finance / Admin | Issue emergency funding from Treasury to a citizen. |
| `/fine @user <amount> <reason>` | Police / Judge / Admin | Issue an official fine to a citizen. |
| `/salary-pay @user <job> [override]` | Finance / Admin | Pay a government salary from the Treasury. |
| `/tax-collect @user <amount> [reason]` | Finance / Admin | Collect taxes from a citizen's wallet into Treasury. |
| `/request-allocation <ministry> <amount> <purpose>` | Gov Role / Admin | Submit a ministry budget request. |
| `/approve-allocation <id>` | Finance / Admin | Approve a pending allocation from Treasury to a ministry. |
| `/deny-allocation <id> [reason]` | Finance / Admin | Reject a pending allocation request. |
| `/allocations` | Gov Role / Admin | List all pending budget allocation requests. |
| `/contract-award <title> @user <amount> [ministry]` | Gov Role / Admin | Award a government contract and pay the recipient. |
| `/contracts` | Everyone | View recently awarded government contracts. |
| `/ministries` | Everyone | List all ministries and their budgets. |
| `/ministry-create <name> [@head]` | Gov Role / Admin | Establish a new federal ministry. |
| `/deposit-treasury <amount>` | Finance / Admin | Deposit personal funds into the National Treasury. |

---

## 🏦 BANKING & CBN COMMANDS

| Command | Required Role | Description |
|---|---|---|
| `/loan-request <amount>` | Everyone | Request a CBN loan (up to 5× net worth, 2%/day interest, 30-day term). |
| `/loan-status` | Everyone | View your active loans and outstanding balances. |
| `/loan-repay <loan_id> <amount>` | Everyone | Repay part or all of an active loan. |
| `/interest-rates` | Everyone | View current CBN rates and loan terms. |
| `/cbn-print <amount> <reason>` | **CBN Governor / Admin** | Mint new money directly into the National Treasury. |
| `/cbn-seize @user <amount> <reason>` | **CBN Governor / Admin** | Seize funds from a citizen's wallet and bank. |

---

## 🏢 BUSINESS COMMANDS

| Command | Who Can Use | Description |
|---|---|---|
| `/business-register <name> [industry]` | Everyone | Register a business (costs ₦50,000 registration fee). |
| `/business-info <name>` | Everyone | View a business's balance, revenue, tax paid, and owner. |
| `/business-deposit <name> <amount>` | Owner | Fund your business from your personal wallet. |
| `/business-withdraw <name> <amount>` | Owner | Withdraw profit to wallet (7.5% VAT applied). |
| `/business-list` | Everyone | List all businesses you own. |
| `/business-top` | Everyone | View the top 10 wealthiest businesses. |
| `/business-tax <name> <amount> [reason]` | Finance / Admin | Collect corporate tax directly from a business. |

**Available Industries:** Agriculture, Banking, Construction, Education, Energy, Healthcare, ICT, Manufacturing, Media, Mining, Oil & Gas, Real Estate, Retail, Telecoms, Transport, General

---

## ⚽ VIRTUAL FOOTBALL BETTING

| Command | Required Role | Description |
|---|---|---|
| `/bet-start #channel` | **Admin** | Start the betting system. New match every 5 minutes. |
| `/bet-stop` | **Admin** | Stop betting. Refunds all open bets. |
| `/bet-status` | Everyone | Check if betting is active and which channel. |
| `/bet-cancel` | **Admin** | Cancel the current match and refund all placed bets. |
| `/bet <home/draw/away> <amount>` | Everyone | Place a bet on the current open match. |
| `/bet-history` | Everyone | View your last 10 bet results. |
| `/bet-stats` | Everyone | View your total bets, win rate, and net P&L. |

**How Betting Works:**
1. A new virtual match is announced every **5 minutes** in the configured channel.
2. Members have **3 minutes** to place bets using `/bet home`, `/bet draw`, or `/bet away`.
3. A 30-second warning is posted before betting closes.
4. The result is generated and announced — winners are paid out automatically.
5. Payouts = stake × odds × 0.95 (5% house edge).
6. Min bet: **₦1,000** | Max bet: **₦5,000,000**
7. One bet per member per match.

**Teams Featured:** Nigerian Professional Football League clubs (Enyimba FC, Rivers United, Kano Pillars, etc.) + African clubs + EPL/European clubs.

---

## 📊 ADMIN-ONLY COMMANDS
> Requires Server Administrator permission

| Command | Description |
|---|---|
| `/economy-stats` | Full national economy dashboard — treasury, citizens, ministries, top players. |
| `/addmoney @user <amount> [reason]` | Add money directly to a member's wallet. |
| `/removemoney @user <amount> [reason]` | Remove money from a member's wallet. |
| `/resetuser @user` | Reset a member's account to default (₦50,000 wallet, no job history). |
| `/synccommands` | Force re-sync all slash commands to this server. |
| `/help` | Show all commands with categories. |

---

## 🔐 ROLE PERMISSION MATRIX

| Discord Role | Access Level |
|---|---|
| **Server Administrator** | ✅ ALL commands without exception |
| President | All government + finance + fine commands |
| Vice President / Governor | Government commands, salary pay, contracts |
| Minister / Senator | Allocation requests, contracts |
| Minister of Finance | Grant, approve allocations, tax collect, salary |
| Accountant General | Finance commands |
| CBN Governor | `/cbn-print`, `/cbn-seize` |
| Police Officer | `/fine` |
| Judge | `/fine` |
| Everyone | Economy, betting, banking (personal), business, viewing commands |

---

## 💡 SETUP CHECKLIST FOR ADMINS

- [ ] Invite the bot with `bot` + `applications.commands` OAuth2 scopes
- [ ] Run `/synccommands` if slash commands don't appear
- [ ] Create Discord roles matching the names in the table above (exact names required)
- [ ] Use `/setjob` to assign jobs to government officials
- [ ] Use `/ministry-create` to set up your ministries
- [ ] Use `/bet-start #channel` to launch the football betting feature
- [ ] Use `/economy-stats` to monitor the national economy at any time

---

## 💰 ECONOMY DEFAULTS

| Setting | Value |
|---|---|
| Starting balance | ₦50,000 wallet |
| Daily stipend | ₦10,000 |
| Treasury seed | ₦500,000,000 |
| Transfer fee | 0.5% → Treasury |
| VAT on business withdrawals | 7.5% |
| CBN loan rate | 2% / 24h |
| Max loan | 5× net worth |
| Bet house edge | 5% |

---
*Nigerian Legacy RP Economy Bot — Built with discord.py + SQLite*
