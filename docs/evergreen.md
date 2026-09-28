# Evergreen

Evergreen keeps the Teams presence dot green while the machine is idle. It runs
in the system tray; right-click the icon for **Pause**, **Resume** or **Exit**,
or double-click it to toggle pause.

## Install

`.\scripts\Install-DeveloperConfig.ps1` builds `tools\evergreen\dist\Evergreen.exe`
with the .NET Framework 4.x compiler included in Windows, rebuilding when the
source or icon changes, and adds an **Evergreen** Start menu shortcut. Windows
does not allow scripts to pin taskbar items: start Evergreen, then right-click
its taskbar button or Start menu entry and choose **Pin to taskbar**.

To build it by hand:

```powershell
.\tools\evergreen\Build-Evergreen.ps1
```

## Behaviour

While running, Evergreen asks Windows to keep the computer and display awake.
Every 15 seconds it checks for inactivity; after at least 45 seconds idle, it
sends a one-pixel relative mouse movement and its inverse. It sends no clicks
or keystrokes. Pause and Exit release the keep-awake request and stop the
mouse input. There is no automatic startup, network access or saved
configuration.

Evergreen prevents idle detection; it does not control Teams presence. It
cannot override a manually selected status, meetings, calls, a locked
workstation or tenant presence rules, and input can be blocked on locked or
protected desktops. Select **Available** or **Reset status** in Teams first.
The executable is unsigned, so application control policy may block it.
