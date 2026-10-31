# PARLEY — Cooperative Chess

A working **real-time, server-authoritative multiplayer chess game** for groups of 2, 4, 6, or 8 people (1v1, 2v2, 3v3, or 4v4).

## Game loop

1. Host creates a room and shares the room code/link.
2. Guests join and are automatically assigned equally to White and Black.
3. Host starts once all participants are online.
4. Only the active team sees its legal moves. Teammates use the **private team chat** to deliberate and each selects a move on their own screen.
5. Every teammate presses **Confirm move**. The authoritative server executes the move only if all teammates are online and have confirmed the **exact same legal move**.
6. Disagreement cannot move the board. Team members can withdraw/change votes, talk, and try again.
7. Players can reconnect, inspect move history, and vote for a rematch after the game ends.

## Features

- Equal teams of 1–4 people, 2–8 total, no odd room sizes.
- Full normal chess legality, castling, en passant, four promotion options, check/checkmate, stalemate, insufficient material, automatic 75-move and fivefold repetition draws.
- Move notation, last move highlighting, keyboard-accessible 64-square board, board flip, team member roster, live vote status.
- Room invite links, teammates-only chat, names and connection status, host-only start.
- All game decisions verified on the Python server; a client never directly changes FEN.
- Mobile and desktop layouts; touch-based tap-to-select controls. No paid API or third-party chess engine required.

## Run locally

Requires **Python 3.11+**.

```bash
cd parley-chess
python -m pip install -r requirements.txt
python server.py
```

Open **http://localhost:8080**. For LAN play, friends can open `http://YOUR-COMPUTER-LAN-IP:8080` if reachable through the firewall. The server listens on `0.0.0.0` and obeys the `PORT` environment variable.

## Testing

```bash
cd parley-chess
python -m unittest discover -s test -p 'test_*.py' -v
```

The multiplayer test starts a temporary server and verifies four real WebSocket clients; the other tests validate chess legality, unanimity, even-sized teams, privacy, disconnections and browser interactions. Reference mobile and desktop screenshots are included in `artifacts/`.

## Deploy to Render

This is a **WebSocket web service**. Do **not** deploy `public/index.html` alone to a static host such as Vercel: players would see a board but matchmaking/chat/voting would fail.

1. Create a GitHub repository containing this `parley-chess` folder’s files at the repository root (not nested under a second `parley-chess` folder).
2. On Render, **New → Web Service** (or **New → Blueprint** with `render.yaml`), select the repository.
3. Choose Python, build command `pip install -r requirements.txt`, start command `python server.py`.
4. Pick a suitable plan (the included `render.yaml` requests free, if available on your Render account).
5. Health check: `/api/health`. The browser uses the same HTTPS origin and upgrades to WSS automatically.

Important: **match data is currently stored in process memory**. Games survive an individual player refreshing/reconnecting, but **not** server restarts, redeployments, or multi-instance scaling. Free services may sleep or restart. For reliable permanent public use, add durable storage and an appropriate deployment plan.

## Known scope boundaries

- The implementation currently supports mandatory automatic draws. Optional claimed threefold repetition and 50-move draws are not yet exposed to player voting.
- No clocks, public spectator mode, ratings, user accounts, moderation backend, or persistent match archive yet.
- Invites use short room codes and browser-local session identity; a server restart clears room membership.
- The project is intended for a single WebSocket-capable Python instance rather than serverless functions.

## Project layout

- `server.py` — WebSocket room management and server-side consensus
- `chess_engine.py` — authoritative chess rules engine
- `public/index.html` — responsive user interface
- `test/` — chess, multiplayer, UI and edge-case tests
- `render.yaml` — Render configuration
