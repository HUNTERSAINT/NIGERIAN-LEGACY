# MetroCity Setup and Immigration

## Server setup

An administrator runs:

- `!setup`
- `/setup`

The bot creates or reuses the `MetroCity RP` category and these channels:

- `#welcome-and-guide`
- `#immigration`
- `#immigration-office`
- `#government`
- `#economy`
- `#banking`
- `#businesses`
- `#betting`
- `#store`
- `#metrocity-logs`

It also creates any missing standard MetroCity roles, including `Immigration Officer` and `Citizen`.

The logs channel is private to the bot by default. Immigration Officer access is granted to
`#immigration-office` when that role exists.

The bot needs **Manage Channels**, **Manage Roles**, and permission to send messages.
Its highest role must be above roles it needs to create or assign.

## New member welcome

When a new member joins, the bot posts a guide in `#welcome-and-guide` explaining how to
apply for citizenship and use the economy. It also writes the join event to `#metrocity-logs`.

## Citizenship registration

Players can use:

```text
!register Full Name, Age, State
```

or:

```text
/register full_name:Full Name age:25 state:Lagos
```

Applications accept roleplay ages from 18 to 100 and are stored as `pending`.

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