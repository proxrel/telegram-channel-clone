# Contributing

Thanks for your interest in contributing! This is a small project, so the process is kept simple.

## Reporting bugs / suggestions

Open a new entry in [Issues](../../issues). Please include:

- What you were trying to do
- Expected vs. actual result
- The full error message, if any (please **do not** share personal info like your `API_ID` or `API_HASH`)
- Your Python version and operating system

## Code contributions (Pull Requests)

1. Fork the repository and create a new branch:
   ```bash
   git checkout -b feature/short-description
   ```
2. Make your changes. Try to stay consistent with the existing code style
   (docstrings, `snake_case` naming). Console messages are in Turkish by
   design, since that's the target audience for this tool — please keep new
   user-facing console output in Turkish for consistency, unless discussed
   otherwise in an issue.
3. Before submitting, make sure the files still compile:
   ```bash
   python -m py_compile main.py list_ids.py check_dest.py
   ```
4. **Never** commit your own `.env`, `.session`, `state.json`, or
   `topic_map.json` files (these are already in `.gitignore`, but double-check
   with `git status` anyway).
5. In your pull request description, briefly explain what you changed and why.

## Reporting a security issue

Please don't open a public Issue for security vulnerabilities. Instead,
contact the repository owner directly.
