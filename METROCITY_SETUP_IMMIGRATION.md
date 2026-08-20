# MetroCity Setup and Immigration

## Server setup

An administrator runs:

- `!setup`
- `/setup`

The bot creates or reuses detailed emoji categories and these channels:

- `✈️ AIRPORT & IMMIGRATION`: `#airport`, `#invite-tracker`, `#immigration-lounge`, `#immigration-office`, `#welcome-and-guide`
- `🏛️ GOVERNMENT`: `#government`
- `💰 ECONOMY & SERVICES`: `#economy`, `#banking`, `#businesses`, `#store`
- `🎮 ENTERTAINMENT`: `#betting`
- `🚓 POLICE DEPARTMENT`: `#police-department`, `#jail`
- `📋 ADMINISTRATION`: `#metrocity-logs`

It also creates any missing standard MetroCity roles, including `Immigration Officer` and `Citizen`.

The logs and invite-tracker channels are private to regular citizens. Immigration Officer
access is granted to `#immigration-office`. New arrivals can see only `#airport`; the
`Visa Holder` role unlocks only `#immigration-lounge`, and the `Citizen` role unlocks the
full RP server after approval.

The bot needs **Manage Channels**, **Manage Roles**, and permission to send messages.
Its highest role must be above roles it needs to create or assign.

## New member welcome

When a new member joins, the bot posts a guide in `#welcome-and-guide` explaining how to
apply for citizenship and use the economy. It also writes the join event to `#metrocity-logs`.

## Citizenship registration

Players must first use `!claimvisa` in `#airport`. After receiving the `Visa Holder` role,
they can use the following only in `#immigration-lounge`:

```text
!register Full Name, Age, State
```

or:

```text
/register full_name:Full Name age:25 state:Lagos
```

Applications accept roleplay ages from 18 to 100 and are stored as `pending`. A request is
posted directly into the private `#immigration-office` with **Approve** and **Decline**
buttons.

## Immigration Officer workflow

An Immigration Officer or server administrator uses:

```text
!immigration-pending
!immigration-approve @player
```

Approval generates and stores:

- A unique National ID
- A unique Tax Identification Number (TIN)
- Approval officer and approval time

The player receives the `Citizen` role automatically. The approval and generated identifiers
are sent to the logs channel.

The player can display the generated card with:

```text
!idcard
!idcard @player
```

The card is shown as a Discord embed with the holder name, National ID, TIN, state, and
verified citizen status.

## Police and jail

Police Officers and administrators can use:

```text
!police
!jail @player [reason]
!unjail @player
```

The slash equivalents are `/police`, `/jail`, and `/unjail`. A jailed player receives the
`Jail Inmate` role, can see the `#jail` channel, and is blocked from economy, wallet,
banking, business, store, loan, work, and betting commands until released.

## Job roles and purchased inventory

Every job is linked to its Discord role. `/setjob` and `!setjob` synchronize the player's
job role. A player cannot use `/work` or `!work` unless they still have the role required by
their assigned job.

Store purchases are aggregated into the existing `/inventory` and `!inventory` profile
commands under **Store Inventory**, showing item names and quantities.