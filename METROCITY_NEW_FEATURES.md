# Nigerian Legacy RP — New Features and Commands

## 🏪 Virtual Store

Admins can manage a persistent in-game store. Store purchases use wallet funds and the money is deposited into the National Treasury.

### Slash commands
- `/store` — View available items.
- `/buy <item_id> [quantity]` — Buy an item.
- `/store-add <name> <price> [description] [stock]` — Add an item. Use `-1` for unlimited stock.
- `/store-remove <item_id>` — Hide an item from the store.

### Prefix commands
- `!store`
- `!buy <item_id> [quantity]`
- `!storeadd <name> <price> [stock] [description]`
- `!storeremove <item_id>`

Example:
`/store-add Passport 25000 Official citizen passport -1`

## 💼 Recurring Role Income

Admins can create a Discord role and attach recurring income to it. Every member with that role receives the payment directly into their **bank balance**.

### Slash commands
- `/role-income-create <role_name> <income> <interval_hours>` — Create/find a role and configure its income.
- `/role-income-list` — View schedules and IDs.
- `/role-income-toggle <schedule_id> <enabled>` — Turn a schedule on or off.

### Prefix commands
- `!roleincome <hours> <income> <role name>`
- `!roleincomelist`
- `!roleincometoggle <schedule_id> <true/false>`

Example:
`/role-income-create Admin 500000 2`

This pays members with the **Admin** role ₦500,000 in their bank every 2 hours. Payments are checked automatically every minute and are recorded in transaction history.

## 🎟️ Shareable Multi-Game Betting Slips

Players can create a virtual betting slip containing **1 to 10 games**. The bot generates the virtual fixtures, odds, and a unique code. Other users can use the code to play the exact same games and picks.

### Slash commands
- `/slip-create <amount> <selections>` — Create a slip.
- `/slip-play <code> <amount>` — Copy another user's slip.
- `/slip-info <code>` — View the games and selections in a slip.

### Prefix commands
- `!slipcreate <amount> <selections>`
- `!slipplay <code> <amount>`
- `!slipinfo <code>`

Selections are comma-separated and can be `home`, `draw`, or `away`.

Example:
`/slip-create 10000 home,draw,away,home`

Share the returned code, for example `MC8A31F0C2`, and another user can play:
`/slip-play MC8A31F0C2 25000`

Slips settle automatically after 5 minutes. A slip wins only when all selected games win. Payout is calculated from the combined odds with the configured 5% house edge.

## ⚙️ Betting Maximum

Admins can increase the maximum stake for normal bets and multi-game slips:

- `/bet-max <amount>`
- `!betmax <amount>`

The minimum stake remains ₦1,000. The default maximum is ₦5,000,000.

## 🔐 Permissions

- Store management, role-income management, betting maximum changes, and betting start/stop/cancel require **Server Administrator** permission.
- Store viewing, buying, creating slips, copying slips, and viewing slip information are available to all members.
- Role income is paid into bank balances, not wallets.

## Existing Betting Commands

- `/bet-start` / `!betstart` — Start the original five-minute football match cycle.
- `/bet-stop` / `!betstop` — Stop the original cycle.
- `/bet-status` / `!betstatus` — Check status.
- `/bet-cancel` / `!betcancel` — Cancel and refund the current original match.
- `/bet-history` / `!bethistory` — View individual bet history.
- `/bet-stats` / `!betstats` — View betting statistics.