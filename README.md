# Telegram Channel/Group Cloner

A [Telethon](https://docs.telethon.dev/)-based script that automatically
copies all **topics** and their **messages/media** from a source Telegram
group (a forum-enabled supergroup) to a destination forum group.

- Reads every topic in the source group and creates it in the destination if it doesn't already exist.
- Sends text messages and file/media messages (photos, videos, documents, audio, etc.) in order.
- Remembers where it left off in `state.json` if interrupted, so the same message is never sent twice.
- Supports a `DRY_RUN` mode so you can preview exactly what would happen without sending anything.

> ⚠️ This tool connects via a **user account** (MTProto/Telethon), not the
> Telegram Bot API. That means the script acts as your personal Telegram
> account. Because of this, keeping your API credentials and session file
> private is critical (see [Security Notes](#-security-notes)).

---

## 📋 Requirements

- Python 3.9 or newer
- A Telegram account (phone number)
- You must be a member of the source group and have permission to send messages in the destination group
- The destination group must be a supergroup with **Topics/Forum** enabled

---

## 🔑 How to Get a Telegram API ID and API Hash

This script needs a personal `API_ID` and `API_HASH` pair to connect to
Telegram. These are free and unique to your account.

1. Go to **https://my.telegram.org** in your browser.
2. Enter the **phone number** linked to your Telegram account (with country code) and click "Next".
3. Enter the **login code** sent to your Telegram app.
4. Once logged in, click **"API development tools"**.
5. Fill out the form:
   - **App title**: Any name you like (e.g. `MyCloner`)
   - **Short name**: A short identifier (e.g. `mycloner`)
   - **Platform**: You can select `Desktop`
   - You can leave the other fields blank
6. Click **"Create application"**.
7. On the resulting page you'll see:
   - **`App api_id`** → this is the `API_ID` value for your `.env` file.
   - **`App api_hash`** → this is the `API_HASH` value for your `.env` file.

🔒 **Never share these two values with anyone, and never commit them to
GitHub.** If they leak, someone else could make Telegram API requests on
behalf of your account (see [Security Notes](#-security-notes)).

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/proxrel/telegram-channel-clone.git
cd telegram-channel-clone
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

Copy `.env.example` to `.env`:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Then open `.env` and fill in your own values:

```ini
API_ID=123456                      # API ID from my.telegram.org
API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxx  # API Hash from my.telegram.org
SESSION_NAME=channel_forwarder

SOURCE_CHANNEL=@source_group_or_id
DEST_CHANNEL=@destination_group_or_id

DRY_RUN=true
SILENT_FORWARD=false
POST_DELAY_SECONDS=0.8
RESUME_FILE=state.json
TOPIC_MAP_FILE=topic_map.json
```

> `.env` is listed in `.gitignore`, so it won't be committed automatically.
> Still, it's good practice to run `git status` before committing to double-check.

---

## 🆔 Finding Group IDs

`SOURCE_CHANNEL` and `DEST_CHANNEL` accept either `@username` or a numeric ID
(starting with `-100`). The code for this lives in `list_ids.py`, inside your
project folder (e.g. `~/telegram-channel-clone`).

In Git Bash, from inside the project folder, run:

```bash
python list_ids.py
```

- If you don't need to log in again — i.e. a session file (named after your
  `SESSION_NAME`, e.g. `channel_forwarder.session`) already exists in the
  folder — it will print the group list right away.
- Otherwise, you'll be asked to enter your phone number, the code Telegram
  sends you, and your 2FA password if you have one enabled.

The script lists every **group** you're a member of, along with its ID. Use
these values in your `.env` file.

---

## ▶️ Usage

### 1. Always test with DRY_RUN first

With `DRY_RUN=true` in your `.env`, run:

```bash
python main.py
```

The script won't send anything — it just prints to the console what topics
and messages *would* be sent. Keep testing in this mode until the output
looks right.

### 2. Start the real transfer

Set `DRY_RUN=false` in `.env` and run again:

```bash
python main.py
```

On first run you'll be prompted to log in to your Telegram account (phone
number → SMS/app code → 2FA password if enabled). Once logged in, a
`.session` file is created using the name in `SESSION_NAME`, and you won't be
asked to log in again on future runs.

The script will:
- Walk through every topic in the source group.
- Create a matching topic in the destination if one doesn't already exist.
- Send all messages (text + media) in each topic, oldest first.
- Save its progress to `state.json` as it goes.

### 3. Resuming after an interruption

If the script stops for any reason (flood wait, connection drop, manual
stop, etc.), just run `python main.py` again. Already-sent messages and
completed topics are tracked in `state.json`, so nothing gets sent twice.

### 4. Testing the destination group

To quickly verify that you can actually send messages to the destination
group:

```bash
python check_dest.py
```

This prints information about the destination group and sends a test
message to confirm access.

---

## 🧾 Environment Variables (`.env`) Reference

| Variable              | Description                                                                | Default                |
|------------------------|------------------------------------------------------------------------------|--------------------------|
| `API_ID`               | API ID obtained from my.telegram.org                                        | *(required)*            |
| `API_HASH`             | API Hash obtained from my.telegram.org                                      | *(required)*            |
| `SESSION_NAME`         | Name of the generated `.session` file                                       | `channel_forwarder`     |
| `SOURCE_CHANNEL`       | Source group (`@username` or `-100...` ID)                                  | *(required)*            |
| `DEST_CHANNEL`         | Destination group (`@username` or `-100...` ID)                             | *(required)*            |
| `DRY_RUN`              | If `true`, sends nothing and just simulates the run                         | `true`                  |
| `SILENT_FORWARD`       | If `true`, messages are sent without triggering notifications               | `false`                 |
| `POST_DELAY_SECONDS`   | Delay between messages, in seconds                                          | `0.8`                    |
| `RESUME_FILE`          | Name of the progress/log file                                               | `state.json`             |
| `TOPIC_MAP_FILE`       | File that stores the topic-name → destination-topic-ID mapping              | `topic_map.json`         |

---

## 📁 Project Structure

```
telegram-channel-clone/
├── main.py              # Main transfer script
├── list_ids.py           # Lists the IDs of groups you're a member of
├── check_dest.py          # Verifies access to the destination group
├── requirements.txt       # Python dependencies
├── .env.example            # Example environment variable template
├── .gitignore
└── README.md
```

Files created/updated while the script runs (these are in `.gitignore` and
never get committed):

- `*.session`, `*.session-journal` — Telegram session data
- `state.json` — Record of which messages have been sent
- `topic_map.json` — Topic-name to destination-topic-ID mapping
- `.env` — Your personal API credentials

---

## 🔒 Security Notes

- **Never commit your `.env` file to GitHub.** It contains `API_ID`/`API_HASH`,
  which grant access to the Telegram API on behalf of your account.
- **Never share your `.session` file.** This file lets anyone log in as you
  without needing your phone, code, or 2FA password — it's more sensitive
  than a password. If it's compromised, your account is fully compromised.
- `state.json` and `topic_map.json` may contain the topic titles and message
  previews from the group you're cloning. If that group is private or
  sensitive, don't add these files to a public GitHub repository either.
- Since this script acts as a **user account**, sending too many messages too
  quickly can trigger Telegram's flood/spam protection and temporarily
  restrict your account. Don't lower `POST_DELAY_SECONDS` too aggressively.
- Only use this on groups you **own or have explicit permission** to copy.
  Copying someone else's content without permission may violate Telegram's
  Terms of Service and copyright law.

---

## ❓ Troubleshooting

**"Source group not found" / "Destination group not found" error.**
Make sure the Telegram account you're using is a member of that group and
that the ID is correct. Double-check with `python list_ids.py`.

**"Destination group must be a supergroup with Topics/Forum enabled" error.**
Make sure **Topics** is enabled in the destination group's settings. This
feature is only available on supergroups, not on regular channels or small
groups.

**`FloodWaitError: you need to wait X seconds` error.**
Telegram has temporarily throttled your account for sending requests too
quickly. Wait for the specified time, then run `python main.py` again — the
script will resume where it left off.

**The script keeps asking for my phone number every time.**
Make sure your `.session` file hasn't been deleted or moved, and that
`SESSION_NAME` stays the same across runs.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
