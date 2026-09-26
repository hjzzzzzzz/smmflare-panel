# SMMflare Client

Desktop GUI for the [SMMflare](https://smmflare.com/) SMM panel API. Check your balance, browse services, place orders, and check order status without opening the website.

## Features

- View account balance
- Browse and search services with pricing
- Place orders (service ID, link, quantity)
- Check order status
- Refill balance (opens SMMflare's deposit page in your browser panel APIs don't support deposits directly)

## Requirements

- Python 3.8+
- `tkinter` (included with most Python installs; on Linux you may need `sudo apt install python3-tk`)

## Setup

```bash
pip install -r requirements.txt
python smmflare_client.py
```

On first run you'll be prompted for your SMMflare API key (found in your account's API settings). It's saved locally to `smmflare_config.json`, which is gitignored and never committed.

## Building a Windows executable

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name SMMflareClient smmflare_client.py
```

The executable will be at `dist/SMMflareClient.exe`.

## Notes

- Your API key stays local — it's stored in `smmflare_config.json` next to the script, not in the source code.
- SMM panel APIs don't expose a deposit endpoint (this is universal across panels, for payment-security reasons), so refilling balance opens the website's payment page in your browser instead of doing it in-app.

## License

MIT — see [LICENSE](LICENSE).
