# Deploying SpectraX

## Linux (systemd)

1. Install MediaMTX and Python ≥3.11.
2. Create user/dirs and install the package into a venv under `/opt/spectrax`.
3. Copy `config/spectrax.yml` → `/etc/spectrax/spectrax.yml` and set:
   ```yaml
   mediamtx:
     managed: false
   ```
4. Set secrets backend:
   ```bash
   export SPECTRAX_STATE_DIR=/var/lib/spectrax
   export SPECTRAX_SECRETS_BACKEND=file
   spectrax admin set-password
   ```
5. Install units from `deploy/systemd/` into `/etc/systemd/system/`, then:
   ```bash
   systemctl daemon-reload
   systemctl enable --now mediamtx spectrax
   ```

## macOS / development

```bash
brew install mediamtx
python3.12 -m venv venv && source venv/bin/activate
pip install -e ".[cv,dev]"
spectrax admin set-password
spectrax doctor
spectrax serve --config config/spectrax.yml
```

Default secrets backend on macOS is the OS keychain (service name
`video-feed-mediamtx` for compatibility).

## Docs

- [README](../README.md)
- [Configuration](../docs/CONFIGURATION_GUIDE.md)
- [API](../docs/API.md)
- [Architecture](../docs/ARCHITECTURE.md)
