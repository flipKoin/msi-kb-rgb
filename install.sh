#!/bin/bash
set -e

INSTALL_DIR="/opt/msi-kb-rgb"

if [ "$1" = "--uninstall" ]; then
    echo "Uninstalling MSI Keyboard RGB..."
    sudo systemctl disable msi-kb-rgb.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/msi-kb-rgb.service
    sudo rm -f /usr/share/applications/msi-kb-rgb.desktop
    sudo rm -f /usr/share/polkit-1/actions/com.msi.kb.rgb.policy
    sudo rm -rf "$INSTALL_DIR"
    sudo systemctl daemon-reload
    echo "Done! Config preserved at ~/.config/msi-kb-rgb/"
    exit 0
fi

echo "Installing MSI Keyboard RGB..."

# Copy files
sudo mkdir -p "$INSTALL_DIR"
sudo cp msi-kb-rgb-gui.py msi-kb-rgb-cli.py msi-kb-rgb-apply.py "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR"/*.py

# Install systemd service
sudo cp msi-kb-rgb.service /etc/systemd/system/
sudo sed -i "s|/root/msi-kb-rgb-apply.py|$INSTALL_DIR/msi-kb-rgb-apply.py|" /etc/systemd/system/msi-kb-rgb.service
sudo systemctl daemon-reload
sudo systemctl enable msi-kb-rgb.service

# Install desktop shortcut
sudo cp msi-kb-rgb.desktop /usr/share/applications/
sudo sed -i "s|/root/msi-kb-rgb-gui.py|$INSTALL_DIR/msi-kb-rgb-gui.py|" /usr/share/applications/msi-kb-rgb.desktop

# Install polkit policy (allows GUI launch via pkexec)
sudo tee /usr/share/polkit-1/actions/com.msi.kb.rgb.policy > /dev/null << 'POLICY'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="com.msi.kb.rgb">
    <description>Run MSI Keyboard RGB Control</description>
    <message>Authentication is required to control keyboard LEDs</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/python3</annotate>
    <annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate>
  </action>
</policyconfig>
POLICY

echo ""
echo "Installed! You can now:"
echo "  - Launch from app menu: 'MSI Keyboard RGB'"
echo "  - Run CLI: sudo python3 $INSTALL_DIR/msi-kb-rgb-cli.py static FF0000"
echo "  - LEDs will auto-restore on boot/wake"
