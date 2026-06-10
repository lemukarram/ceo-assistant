#!/bin/sh
echo "Rebranding Hermes to LOOPS CA..."

WEB_DIST="/opt/hermes/hermes_cli/web_dist"

# 1. Surgical HTML/Title replacement (Safe)
if [ -d "$WEB_DIST" ]; then
  echo "Applying HTML rebranding..."
  find "$WEB_DIST" -type f -name "*.html" -exec sed -i 's/Hermes Agent/LOOPS CA/g' {} +
  find "$WEB_DIST" -type f -name "*.html" -exec sed -i 's/Hermes Dashboard/LOOPS CA Dashboard/g' {} +
  find "$WEB_DIST" -type f -name "*.html" -exec sed -i 's/Hermes/LOOPS CA/g' {} +
else
  echo "Warning: $WEB_DIST not found. Skipping HTML rebranding."
fi

# 2. CEO Assistant Instructions (SOUL.md)
# We now manage SOUL.md via Docker volume mount for persistence and easier editing.
# We only write it if it doesn't exist, to avoid conflicts with read-only mounts.
if [ ! -f "/opt/data/SOUL.md" ]; then
    echo "Initializing default SOUL.md (None found)"
    cat << 'EOF' > /opt/data/SOUL.md
# LOOPS CA - Default Identity
You are LOOPS CA, the Chief Assistant.
EOF
fi

# 3. Install missing Image Processing Dependencies
echo "Installing Python image processing libraries..."
# Use pip to install libraries Hermes might need when using its Terminal tool
pip install Pillow matplotlib requests --quiet || echo "Warning: Failed to install pip dependencies"

echo "Rebranding complete."
