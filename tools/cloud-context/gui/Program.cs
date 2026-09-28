using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace CloudContext;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}

internal sealed class MainForm : Form
{
    private static readonly Color Green = Color.FromArgb(22, 163, 74);
    private static readonly Color Red = Color.FromArgb(220, 38, 38);
    private static readonly Color Amber = Color.FromArgb(217, 119, 6);
    private static readonly Color Grey = Color.FromArgb(156, 163, 175);
    private static readonly Regex GuidPattern = new(@"[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}");

    private readonly ContextStore store = new(ContextStore.DefaultRoot);
    private readonly AzureCli cli;
    private readonly SplitContainer split = new() { Dock = DockStyle.Fill, FixedPanel = FixedPanel.Panel1, SplitterWidth = 6 };
    private readonly ListBox profiles = new()
    {
        Dock = DockStyle.Fill, DrawMode = DrawMode.OwnerDrawFixed, ItemHeight = 32, IntegralHeight = false,
        BorderStyle = BorderStyle.None, DisplayMember = "Name"
    };
    private readonly Button newButton = new() { Text = "+ New profile", AutoSize = true, Dock = DockStyle.Fill };
    private readonly ContextMenuStrip profileMenu = new();
    private readonly ToolTip tip = new();
    private readonly Label title = new() { AutoSize = true, Font = new Font("Segoe UI Semibold", 16), Margin = new Padding(0, 0, 0, 6) };
    private readonly Label dot = new() { Text = "●", AutoSize = true, Font = new Font("Segoe UI", 13), Margin = new Padding(0, 0, 4, 0) };
    private readonly Label status = new() { AutoSize = true, MaximumSize = new Size(640, 0), Margin = new Padding(0, 5, 0, 0) };
    private readonly Label notice = new() { AutoSize = true, MaximumSize = new Size(640, 0), Margin = new Padding(0, 4, 0, 8) };
    private readonly Button signIn = new() { AutoSize = true, Font = new Font("Segoe UI Semibold", 10) };
    private readonly Button signOut = new() { Text = "Sign out", AutoSize = true };
    private readonly Button more = new() { Text = "More ▾", AutoSize = true };
    private readonly Button cancel = new() { Text = "Cancel", AutoSize = true, Visible = false };
    private readonly ContextMenuStrip moreMenu = new();
    private readonly TextBox name = new() { Dock = DockStyle.Fill };
    private readonly TextBox tenant = new() { Dock = DockStyle.Fill, PlaceholderText = "00000000-0000-0000-0000-000000000000" };
    private readonly ComboBox subscription = new() { Dock = DockStyle.Fill };
    private readonly TextBox dataverse = new() { Dock = DockStyle.Fill, PlaceholderText = "https://your-org.crm11.dynamics.com (optional)" };
    private readonly Button save = new() { Text = "Save changes", AutoSize = true, Anchor = AnchorStyles.Left };
    private readonly LinkLabel logToggle = new() { Text = "Show activity", AutoSize = true, Margin = new Padding(0, 12, 0, 4) };
    private readonly TextBox log = new() { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, Dock = DockStyle.Fill, Visible = false };
    private readonly System.Windows.Forms.Timer clock = new() { Interval = 1000 };
    private readonly System.Windows.Forms.Timer refreshTimer = new() { Interval = 10 * 60 * 1000 };
    private readonly CancellationTokenSource closing = new();
    private Dictionary<string, ProfileStatus> statuses;
    private CancellationTokenSource? operation;
    private Task refreshing = Task.CompletedTask;
    private Profile? selected;
    private string? checking;
    private string? busyProfile;
    private string busyText = "";
    private string? hovered;

    [DllImport("user32.dll")]
    private static extern bool AllowSetForegroundWindow(int processId);

    public MainForm()
    {
        cli = new AzureCli(store);
        statuses = store.Statuses();
        Text = "Cloud Context";
        Font = new Font("Segoe UI", 10);
        Size = new Size(1080, 720);
        MinimumSize = new Size(760, 520);
        StartPosition = FormStartPosition.CenterScreen;
        try { Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!); } catch (Exception) { }

        var sidebar = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4, Padding = new Padding(12, 16, 4, 12) };
        sidebar.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        sidebar.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        sidebar.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        sidebar.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        sidebar.Controls.Add(new Label { Text = "Profiles", AutoSize = true, Font = new Font("Segoe UI Semibold", 10), Margin = new Padding(3, 0, 3, 6) }, 0, 0);
        sidebar.Controls.Add(profiles, 0, 1);
        var legend = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, Margin = new Padding(0, 6, 0, 6) };
        foreach (var (colour, meaning) in new[] { (Green, "signed in"), (Red, "needs sign-in"), (Amber, "checking"), (Grey, "not checked") })
        {
            var entry = new FlowLayoutPanel { AutoSize = true, WrapContents = false, Margin = new Padding(0, 0, 8, 0) };
            entry.Controls.Add(new Label { Text = "●", ForeColor = colour, AutoSize = true, Font = new Font("Segoe UI", 8), Margin = new Padding(0) });
            entry.Controls.Add(new Label { Text = meaning, ForeColor = SystemColors.GrayText, AutoSize = true, Font = new Font("Segoe UI", 8), Margin = new Padding(0) });
            legend.Controls.Add(entry);
        }
        sidebar.Controls.Add(legend, 0, 2);
        sidebar.Controls.Add(newButton, 0, 3);
        split.Panel1.Controls.Add(sidebar);

        var header = new FlowLayoutPanel { AutoSize = true, WrapContents = false, Dock = DockStyle.Fill };
        header.Controls.Add(dot);
        header.Controls.Add(status);
        var buttons = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, Margin = new Padding(0, 10, 0, 0) };
        buttons.Controls.AddRange([signIn, signOut, more, cancel]);
        var fields = new TableLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, ColumnCount = 2, Margin = new Padding(0, 8, 0, 0) };
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        AddField(fields, "Profile name", name);
        AddField(fields, "Tenant ID", tenant);
        AddField(fields, "Subscription", subscription);
        AddField(fields, "Dataverse URL", dataverse);
        fields.Controls.Add(new Label(), 0, fields.RowCount);
        fields.Controls.Add(save, 1, fields.RowCount++);
        var detail = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 7, Padding = new Padding(20, 16, 20, 16) };
        for (var row = 0; row < 6; row++) detail.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        detail.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        detail.Controls.Add(title, 0, 0);
        detail.Controls.Add(header, 0, 1);
        detail.Controls.Add(buttons, 0, 2);
        detail.Controls.Add(notice, 0, 3);
        detail.Controls.Add(fields, 0, 4);
        detail.Controls.Add(logToggle, 0, 5);
        detail.Controls.Add(log, 0, 6);
        split.Panel2.Controls.Add(detail);
        Controls.Add(split);

        profileMenu.Items.Add("Sign in", null, (_, _) => SignIn(false));
        profileMenu.Items.Add("Check now", null, (_, _) => RunAction("Checking sign-in...", CheckNow));
        profileMenu.Items.Add(new ToolStripSeparator());
        profileMenu.Items.Add("Remove...", null, (_, _) => RemoveSelected());
        moreMenu.Items.Add("Sign in with a code", null, (_, _) => SignIn(true));
        moreMenu.Items.Add("Check now", null, (_, _) => RunAction("Checking sign-in...", CheckNow));
        moreMenu.Items.Add("Load subscriptions", null, (_, _) => RunAction("Loading subscriptions...", token => LoadSubscriptions(false, token)));
        moreMenu.Items.Add(new ToolStripSeparator());
        moreMenu.Items.Add("Copy instructions for an agent", null, (_, _) => RunAction("", _ => CopyInstructions()));
        moreMenu.Items.Add("Open PowerShell with this profile", null, (_, _) => RunAction("", _ => OpenShell()));
        moreMenu.Items.Add(new ToolStripSeparator());
        moreMenu.Items.Add("Remove profile...", null, (_, _) => RemoveSelected());

        profiles.DrawItem += DrawProfile;
        profiles.Resize += (_, _) => profiles.Invalidate();
        profiles.SelectedIndexChanged += (_, _) => LoadProfile(profiles.SelectedItem as Profile);
        profiles.MouseDown += (_, e) =>
        {
            if (e.Button != MouseButtons.Right || operation != null) return;
            var index = profiles.IndexFromPoint(e.Location);
            if (index < 0) return;
            profiles.SelectedIndex = index;
            profileMenu.Show(profiles, e.Location);
        };
        profiles.MouseMove += (_, e) =>
        {
            var index = profiles.IndexFromPoint(e.Location);
            var item = index >= 0 ? (Profile)profiles.Items[index] : null;
            if (item?.Name == hovered) return;
            hovered = item?.Name;
            tip.SetToolTip(profiles, item == null ? "" : item.Name + ": " + Describe(item.Name).Text);
        };
        profiles.KeyDown += (_, e) => { if (e.KeyCode == Keys.Delete) RemoveSelected(); };
        newButton.Click += (_, _) => { profiles.ClearSelected(); LoadProfile(null); name.Focus(); };
        signIn.Click += (_, _) => SignIn(false);
        signOut.Click += (_, _) => RunAction("Signing out...", SignOut);
        more.Click += (_, _) => moreMenu.Show(more, new Point(0, more.Height));
        cancel.Click += (_, _) => operation?.Cancel();
        save.Click += (_, _) => RunAction("", _ => { Save(); return Task.CompletedTask; });
        logToggle.LinkClicked += (_, _) => ShowLog(!log.Visible);
        foreach (Control field in new Control[] { name, tenant, subscription, dataverse })
            field.TextChanged += (_, _) => UpdateButtons();
        clock.Tick += (_, _) => UpdateStatus();
        refreshTimer.Tick += (_, _) => StartRefresh();
        Shown += (_, _) =>
        {
            split.Panel1MinSize = 160;
            split.SplitterDistance = Math.Clamp(store.SidebarWidth() ?? 300, 160, Math.Max(160, ClientSize.Width - 480));
            try { Reload(); } catch (Exception error) { Notify(error.Message, true); }
            if (profiles.Items.Count > 0) profiles.SelectedIndex = 0;
            clock.Start();
            refreshTimer.Start();
            StartRefresh();
        };
        FormClosing += (_, _) =>
        {
            closing.Cancel();
            operation?.Cancel();
            try { store.SaveSidebarWidth(split.SplitterDistance); } catch (IOException) { }
        };
        LoadProfile(null);
    }

    private static void AddField(TableLayoutPanel panel, string label, Control control)
    {
        panel.Controls.Add(new Label { Text = label, AutoSize = true, Anchor = AnchorStyles.Left, Margin = new Padding(0, 8, 16, 8) }, 0, panel.RowCount);
        control.Margin = new Padding(0, 6, 0, 6);
        panel.Controls.Add(control, 1, panel.RowCount++);
    }

    private void DrawProfile(object? sender, DrawItemEventArgs e)
    {
        e.DrawBackground();
        if (e.Index < 0) return;
        var profile = (Profile)profiles.Items[e.Index];
        var bullet = new Rectangle(e.Bounds.X + 8, e.Bounds.Y + (e.Bounds.Height - 10) / 2, 10, 10);
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using (var brush = new SolidBrush(Describe(profile.Name).Color)) e.Graphics.FillEllipse(brush, bullet);
        var text = new Rectangle(bullet.Right + 8, e.Bounds.Y, e.Bounds.Right - bullet.Right - 12, e.Bounds.Height);
        var colour = (e.State & DrawItemState.Selected) != 0 ? SystemColors.HighlightText : SystemColors.ControlText;
        TextRenderer.DrawText(e.Graphics, profile.Name, e.Font, text, colour,
            TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
        e.DrawFocusRectangle();
    }

    private (Color Color, string Text) Describe(string profile)
    {
        if (profile == busyProfile && busyText.Length > 0) return (Amber, busyText);
        if (profile == checking) return (Amber, "Checking sign-in...");
        if (!statuses.TryGetValue(profile, out var saved)) return (Grey, "Not checked yet.");
        var checkedAt = " Checked " + Ago(DateTimeOffset.FromUnixTimeSeconds(saved.CheckedAt)) + ".";
        if (saved.State == ProfileStatus.SignedOut) return (Grey, "Signed out." + checkedAt);
        if (saved.State != ProfileStatus.Ready)
            return (Red, "Sign-in needed. " + FirstLine(saved.Message) + checkedAt);
        var expires = DateTimeOffset.FromUnixTimeSeconds(saved.ExpiresOn ?? 0);
        var left = expires - DateTimeOffset.Now;
        if (left <= TimeSpan.Zero)
            return (Amber, $"Signed in, but the access token expired at {expires.LocalDateTime:HH:mm}. It renews silently at the next check." + checkedAt);
        return (Green, $"Signed in. Access token valid until {expires.LocalDateTime:HH:mm} ({Span(left)} left)." + checkedAt);
    }

    private static string FirstLine(string text)
    {
        var line = text.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).FirstOrDefault() ?? "";
        if (line.StartsWith("ERROR: ", StringComparison.Ordinal)) line = line[7..];
        return line.Length > 180 ? line[..180] + "..." : line;
    }

    private static string Span(TimeSpan span) => span.TotalHours >= 1 ? $"{(int)span.TotalHours}h {span.Minutes}m" : $"{span.Minutes}m {span.Seconds}s";

    private static string Ago(DateTimeOffset time)
    {
        var span = DateTimeOffset.Now - time;
        if (span < TimeSpan.FromMinutes(1)) return "just now";
        if (span < TimeSpan.FromHours(1)) return $"{(int)span.TotalMinutes}m ago";
        if (span < TimeSpan.FromDays(1)) return $"{(int)span.TotalHours}h ago";
        return "on " + time.LocalDateTime.ToString("d MMM HH:mm");
    }

    private void UpdateStatus()
    {
        if (selected == null)
        {
            dot.ForeColor = Grey;
            status.Text = "Enter a name and tenant ID, then sign in. Subscription and Dataverse URL are optional.";
            return;
        }
        var (colour, text) = Describe(selected.Name);
        dot.ForeColor = colour;
        status.Text = text;
    }

    private void UpdateButtons()
    {
        var idle = operation == null;
        var ready = selected != null && statuses.TryGetValue(selected.Name, out var saved) && saved.State == ProfileStatus.Ready;
        signIn.Text = ready ? "Sign in again" : "Sign in";
        signIn.Enabled = idle;
        signOut.Enabled = idle && selected != null;
        more.Enabled = idle;
        foreach (ToolStripItem item in moreMenu.Items)
            if (item.Text is "Check now" or "Load subscriptions" or "Remove profile...") item.Enabled = selected != null;
        cancel.Visible = !idle;
        save.Enabled = idle && (selected == null
            ? name.Text.Length > 0 || tenant.Text.Length > 0
            : SubscriptionId() != selected.Subscription || tenant.Text.Trim() != selected.Tenant
                || dataverse.Text.Trim().TrimEnd('/') != selected.Dataverse);
        profiles.Enabled = newButton.Enabled = name.Enabled = tenant.Enabled = subscription.Enabled = dataverse.Enabled = idle;
        UseWaitCursor = !idle;
    }

    private void Notify(string text, bool error = false)
    {
        if (IsDisposed) return;
        if (InvokeRequired) { BeginInvoke(() => Notify(text, error)); return; }
        notice.ForeColor = error ? Red : SystemColors.ControlText;
        notice.Text = FirstLine(text);
        Append(text);
    }

    private void Append(string text)
    {
        if (IsDisposed || Disposing) return;
        if (InvokeRequired) { BeginInvoke(() => Append(text)); return; }
        log.AppendText($"[{DateTime.Now:HH:mm:ss}] {text.Trim()}{Environment.NewLine}");
    }

    private void ShowLog(bool visible)
    {
        log.Visible = visible;
        logToggle.Text = visible ? "Hide activity" : "Show activity";
    }

    private void Reload(string? select = null)
    {
        var list = store.Profiles();
        profiles.DataSource = list;
        profiles.SelectedIndex = -1;
        if (select != null) profiles.SelectedItem = list.FirstOrDefault(item => item.Name == select);
    }

    private void LoadProfile(Profile? profile)
    {
        selected = profile;
        title.Text = profile?.Name ?? "New profile";
        name.Text = profile?.Name ?? "";
        name.ReadOnly = profile != null;
        tenant.Text = profile?.Tenant ?? "";
        subscription.Items.Clear();
        subscription.Text = profile?.Subscription ?? "";
        dataverse.Text = profile?.Dataverse ?? "";
        notice.Text = "";
        UpdateStatus();
        UpdateButtons();
    }

    private string SubscriptionId()
    {
        var match = GuidPattern.Match(subscription.Text);
        return match.Success ? match.Value : subscription.Text.Trim();
    }

    private void SetStatus(string profile, ProfileStatus value)
    {
        statuses[profile] = value;
        try { store.SaveStatus(profile, value); } catch (IOException error) { Append("Couldn't save the status cache: " + error.Message); }
        profiles.Invalidate();
        UpdateStatus();
        UpdateButtons();
    }

    private void StartRefresh()
    {
        if (!refreshing.IsCompleted || operation != null) return;
        refreshing = RefreshAll();
    }

    private async Task RefreshAll()
    {
        try
        {
            foreach (var profile in store.Profiles())
            {
                if (operation != null || closing.IsCancellationRequested) return;
                checking = profile.Name;
                profiles.Invalidate();
                UpdateStatus();
                SetStatus(profile.Name, await cli.Status(profile, closing.Token));
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception error) { Append("Background check failed: " + error.Message); }
        finally
        {
            checking = null;
            if (!IsDisposed) { profiles.Invalidate(); UpdateStatus(); }
        }
    }

    private async void RunAction(string text, Func<CancellationToken, Task> action)
    {
        if (operation != null) return;
        using var source = new CancellationTokenSource(TimeSpan.FromMinutes(10));
        operation = source;
        busyProfile = selected?.Name ?? name.Text.Trim();
        busyText = text;
        notice.Text = "";
        UpdateButtons();
        UpdateStatus();
        profiles.Invalidate();
        try
        {
            await refreshing;
            await action(source.Token);
        }
        catch (OperationCanceledException) { Notify("Stopped. Nothing else changed.", true); }
        catch (Exception error) { Notify(error.Message, true); }
        finally
        {
            operation = null;
            busyProfile = null;
            busyText = "";
            if (!IsDisposed)
            {
                UpdateButtons();
                UpdateStatus();
                profiles.Invalidate();
            }
        }
    }

    private void SignIn(bool deviceCode)
    {
        var force = selected != null && statuses.TryGetValue(selected.Name, out var saved) && saved.State == ProfileStatus.Ready;
        RunAction(deviceCode ? "Waiting for you to enter the code in Chrome..." : "Waiting for you to sign in. Use the Chrome window that just opened.", async token =>
        {
            var profile = Save();
            AllowSetForegroundWindow(-1);
            try
            {
                await cli.Connect(profile, force || deviceCode, deviceCode, Append, token, (url, code) => BeginInvoke(() =>
                {
                    Clipboard.SetText(code);
                    Browser.Open(url);
                    Notify($"Your sign-in code is {code}. It's on the clipboard, so paste it into the Chrome window.");
                }));
            }
            catch (InvalidOperationException error)
            {
                SetStatus(profile.Name, ProfileStatus.Now(ProfileStatus.SignInNeeded, message: error.Message));
                throw;
            }
            SetStatus(profile.Name, await cli.Status(profile, token));
            Notify("Signed in. CLI commands can use this profile now.");
            if (profile.Subscription.Length == 0) await LoadSubscriptions(true, token);
        });
    }

    private async Task SignOut(CancellationToken token)
    {
        var profile = selected!;
        await cli.SignOut(profile, token);
        SetStatus(profile.Name, ProfileStatus.Now(ProfileStatus.SignedOut));
        Notify($"Signed out of {profile.Name}. The profile settings are still saved.");
    }

    private async Task CheckNow(CancellationToken token)
    {
        var profile = Save();
        var result = await cli.Status(profile, token);
        SetStatus(profile.Name, result);
        Notify(result.State == ProfileStatus.Ready ? "Sign-in works." : "Sign-in needed. " + FirstLine(result.Message), result.State != ProfileStatus.Ready);
    }

    private void RemoveSelected()
    {
        if (selected == null || operation != null) return;
        var profile = selected;
        var answer = MessageBox.Show(this,
            $"Remove {profile.Name}?\n\nThis deletes the profile and its saved Azure and GitHub sign-ins on this computer. You can't undo this.",
            "Remove profile", MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2);
        if (answer != DialogResult.Yes) return;
        RunAction("Removing...", _ =>
        {
            store.Remove(profile.Name);
            statuses.Remove(profile.Name);
            Reload();
            LoadProfile(null);
            Notify($"Removed {profile.Name} and its saved sign-ins.");
            return Task.CompletedTask;
        });
    }

    private Profile Save()
    {
        var profile = new Profile(name.Text.Trim(), tenant.Text.Trim(), SubscriptionId(), dataverse.Text.Trim().TrimEnd('/'));
        if (profile == selected) return profile;
        var subscriptions = subscription.Items.Cast<object>().ToArray();
        store.Save(profile, selected != null);
        Reload(profile.Name);
        subscription.Items.AddRange(subscriptions);
        Notify($"Saved {profile.Name}.");
        return profile;
    }

    private async Task LoadSubscriptions(bool quiet, CancellationToken token)
    {
        var profile = Save();
        var result = JsonNode.Parse(await cli.Run(profile, ["account", "list", "--all", "--output", "json"], null, token))!.AsArray();
        var current = subscription.Text;
        subscription.Items.Clear();
        foreach (var account in result.Where(item => string.Equals((string?)item?["tenantId"], profile.Tenant, StringComparison.OrdinalIgnoreCase)))
            subscription.Items.Add($"{account!["name"]} ({account["id"]})");
        subscription.Text = current;
        if (subscription.Items.Count > 0)
        {
            Notify($"Found {subscription.Items.Count} subscription(s). Pick one from the Subscription list, then save.");
            if (!quiet) subscription.DroppedDown = true;
        }
        else if (!quiet) Notify("No subscriptions found in this tenant. Sign in first, or leave Subscription blank for tenant-only access.");
    }

    private Task CopyInstructions(CancellationToken _ = default)
    {
        var profile = Save();
        var command = profile.Dataverse.Length > 0
            ? $"az rest --method get --url {profile.Dataverse}/api/data/v9.2/WhoAmI --resource {profile.Dataverse}"
            : "az account show";
        Clipboard.SetText($"Use cloud profile '{profile.Name}'. Prefix every Azure CLI command with cloud-profile {profile.Name} --. "
            + $"Do not use a different CLI cache. Example: cloud-profile {profile.Name} -- {command}"
            + $"\nThe profile store is {store.Root}. Set CLOUD_CONTEXT_HOME to this path if your process uses a different location.");
        Notify("Copied agent instructions. They need the cloud-profile launcher on PATH.");
        return Task.CompletedTask;
    }

    private Task OpenShell(CancellationToken _ = default)
    {
        var profile = Save();
        var info = new ProcessStartInfo("powershell.exe") { UseShellExecute = false };
        info.ArgumentList.Add("-NoProfile");
        info.ArgumentList.Add("-NoExit");
        foreach (var pair in store.EnvironmentFor(profile)) info.Environment[pair.Key] = pair.Value;
        Process.Start(info)?.Dispose();
        Notify($"Opened PowerShell with {profile.Name}. Terminals that were already open keep their old profile.");
        return Task.CompletedTask;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            clock.Dispose();
            refreshTimer.Dispose();
            closing.Dispose();
        }
        base.Dispose(disposing);
    }
}
