using System.Diagnostics;
using System.Text.Json.Nodes;

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
    private readonly ContextStore store = new(ContextStore.DefaultRoot);
    private readonly ListBox profiles = new() { Dock = DockStyle.Fill, DisplayMember = "Name" };
    private readonly TextBox name = new() { Dock = DockStyle.Fill };
    private readonly TextBox tenant = new() { Dock = DockStyle.Fill };
    private readonly ComboBox subscription = new() { Dock = DockStyle.Fill };
    private readonly TextBox dataverse = new() { Dock = DockStyle.Fill, PlaceholderText = "https://your-org.crm11.dynamics.com" };
    private readonly CheckBox deviceCode = new() { Text = "Use device-code sign-in", AutoSize = true };
    private readonly TextBox cache = new() { ReadOnly = true, Dock = DockStyle.Fill };
    private readonly Label expiry = new() { AutoSize = true, MaximumSize = new Size(660, 0) };
    private readonly TextBox log = new() { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, Dock = DockStyle.Fill };
    private readonly FlowLayoutPanel actions = new() { AutoSize = true, Dock = DockStyle.Fill };
    private readonly Button cancel = new() { Text = "Cancel", AutoSize = true, Enabled = false };
    private readonly System.Windows.Forms.Timer timer = new() { Interval = 1000 };
    private readonly AzureCli cli;
    private CancellationTokenSource? operation;
    private Profile? selected;
    private DateTimeOffset? expiresAt;

    public MainForm()
    {
        cli = new AzureCli(store);
        Text = "Cloud Context — Azure & Dataverse";
        Font = new Font("Segoe UI", 10);
        Size = new Size(1120, 760);
        MinimumSize = new Size(960, 680);
        StartPosition = FormStartPosition.CenterScreen;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(18), ColumnCount = 2, RowCount = 1 };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 240));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        var sidebar = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 3, ColumnCount = 1, Padding = new Padding(0, 0, 16, 0) };
        sidebar.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        sidebar.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        sidebar.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        sidebar.Controls.Add(new Label { Text = "Saved environments", AutoSize = true }, 0, 0);
        sidebar.Controls.Add(profiles, 0, 1);
        var newButton = new Button { Text = "New environment", AutoSize = true };
        newButton.Click += (_, _) => { profiles.ClearSelected(); LoadProfile(null); };
        sidebar.Controls.Add(newButton, 0, 2);
        layout.Controls.Add(sidebar, 0, 0);
        var detail = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 15 };
        for (var row = 0; row < 14; row++) detail.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        detail.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        detail.Controls.Add(new Label { Text = "Choose an environment. Keep its sign-in ready for your local CLI.", AutoSize = true }, 0, 0);
        AddField(detail, "Profile name", name, 1);
        AddField(detail, "Directory (tenant) ID", tenant, 3);
        AddField(detail, "Subscription ID (optional for Dataverse / tenant-only access)", subscription, 5);
        AddField(detail, "Dataverse environment URL (optional)", dataverse, 7);
        detail.Controls.Add(deviceCode, 0, 9);
        AddAction("Save", () => { Save(); return Task.CompletedTask; });
        AddAction("Connect", () => Connect(false));
        AddAction("Sign in again", () => Connect(true));
        AddAction("Check access / expiry", Check);
        AddAction("Load subscriptions", LoadSubscriptions);
        AddAction("Copy Codex instructions", CopyInstructions);
        AddAction("Open PowerShell", OpenShell);
        detail.Controls.Add(actions, 0, 10);
        detail.Controls.Add(new Label { Text = "Azure CLI credential-cache directory (separate for each profile)", AutoSize = true }, 0, 11);
        detail.Controls.Add(cache, 0, 12);
        var status = new FlowLayoutPanel { AutoSize = true, FlowDirection = FlowDirection.TopDown, Dock = DockStyle.Fill };
        status.Controls.Add(expiry);
        status.Controls.Add(new Label { Text = "Access tokens can renew silently. Sign-in session expiry depends on tenant policy and is not exposed.", AutoSize = true, MaximumSize = new Size(660, 0) });
        status.Controls.Add(cancel);
        detail.Controls.Add(status, 0, 13);
        detail.Controls.Add(log, 0, 14);
        layout.Controls.Add(detail, 1, 0);
        Controls.Add(layout);
        profiles.SelectedIndexChanged += (_, _) => LoadProfile(profiles.SelectedItem as Profile);
        cancel.Click += (_, _) => operation?.Cancel();
        FormClosing += (_, _) => operation?.Cancel();
        timer.Tick += (_, _) => UpdateExpiry();
        foreach (Control field in new Control[] { name, tenant, subscription, dataverse })
            field.TextChanged += (_, _) => { expiresAt = null; UpdateExpiry(); };
        timer.Start();
        Shown += (_, _) => { try { Reload(); } catch (Exception error) { Append(error.Message); } };
        UpdateExpiry();
    }

    private static void AddField(TableLayoutPanel panel, string label, Control control, int row)
    {
        panel.Controls.Add(new Label { Text = label, AutoSize = true, Margin = new Padding(3, 10, 3, 3) }, 0, row);
        panel.Controls.Add(control, 0, row + 1);
    }

    private void AddAction(string text, Func<Task> action)
    {
        var button = new Button { Text = text, AutoSize = true };
        button.Click += async (_, _) =>
        {
            using var source = new CancellationTokenSource(TimeSpan.FromMinutes(10));
            operation = source;
            SetBusy(true);
            try { await action(); }
            catch (OperationCanceledException) { Append("Operation cancelled or timed out. Check access before retrying."); expiresAt = null; }
            catch (Exception error) { Append(error.Message); expiresAt = null; }
            finally { operation = null; if (!IsDisposed) { SetBusy(false); UpdateExpiry(); } }
        };
        actions.Controls.Add(button);
    }

    private void SetBusy(bool busy)
    {
        actions.Enabled = profiles.Enabled = name.Enabled = tenant.Enabled = subscription.Enabled = dataverse.Enabled = deviceCode.Enabled = !busy;
        foreach (Control control in profiles.Parent!.Controls) if (control is Button) control.Enabled = !busy;
        cancel.Enabled = busy;
        UseWaitCursor = busy;
    }

    private void Append(string text)
    {
        if (IsDisposed || Disposing) return;
        if (InvokeRequired) { BeginInvoke(() => Append(text)); return; }
        log.AppendText(text + Environment.NewLine);
    }

    private void Reload(string? select = null)
    {
        profiles.DataSource = store.Profiles();
        profiles.SelectedIndex = -1;
        if (select != null)
            profiles.SelectedItem = ((List<Profile>)profiles.DataSource).FirstOrDefault(item => item.Name == select);
    }

    private void LoadProfile(Profile? profile)
    {
        selected = profile;
        name.Text = profile?.Name ?? "";
        name.ReadOnly = profile != null;
        tenant.Text = profile?.Tenant ?? "";
        subscription.Items.Clear();
        subscription.Text = profile?.Subscription ?? "";
        dataverse.Text = profile?.Dataverse ?? "";
        cache.Text = profile == null ? "Save an environment to create its cache." : Path.Combine(store.Root, "cli", "azure", profile.Name);
        expiresAt = null;
        log.Clear();
        UpdateExpiry();
    }

    private Profile Save()
    {
        var profile = new Profile(name.Text.Trim(), tenant.Text.Trim(), subscription.Text.Trim(), dataverse.Text.Trim().TrimEnd('/'));
        store.Save(profile, selected != null);
        selected = profile;
        Reload(profile.Name);
        Append("Saved " + profile.Name + ". Credentials remain in Azure CLI's native cache.");
        return profile;
    }

    private async Task Connect(bool force)
    {
        var profile = Save();
        await cli.Connect(profile, force, deviceCode.Checked, Append, operation!.Token);
        await ShowExpiry(profile);
    }

    private async Task Check()
    {
        var profile = Save();
        await cli.Check(profile, operation!.Token);
        Append(profile.Dataverse.Length > 0 ? "Dataverse WhoAmI succeeded." : "Azure tenant, subscription and token verified.");
        await ShowExpiry(profile);
    }

    private async Task ShowExpiry(Profile profile)
    {
        expiresAt = await cli.Expiry(profile, operation!.Token);
        UpdateExpiry();
        var files = Directory.GetFiles(cache.Text, "*", SearchOption.TopDirectoryOnly)
            .Where(path => Path.GetFileName(path).Contains("token", StringComparison.OrdinalIgnoreCase)
                || Path.GetFileName(path).Contains("msal", StringComparison.OrdinalIgnoreCase));
        foreach (var file in files) Append("Cache file: " + file);
        Append("Expiry checked for " + (profile.Dataverse.Length > 0 ? profile.Dataverse : "Azure Resource Manager") + ". Checking may silently renew an expired token.");
    }

    private void UpdateExpiry()
    {
        if (expiresAt == null) { expiry.Text = "Token expiry: not checked. Connect or check access to retrieve it."; return; }
        var remaining = expiresAt.Value - DateTimeOffset.Now;
        expiry.Text = $"Access token expires: {expiresAt.Value.LocalDateTime:yyyy-MM-dd HH:mm:ss} (local)\n"
            + (remaining > TimeSpan.Zero ? $"Time remaining: {(int)remaining.TotalHours}h {remaining.Minutes}m {remaining.Seconds}s"
                : "Access token expired. Check access to attempt silent renewal.");
    }

    private async Task LoadSubscriptions()
    {
        var profile = Save();
        var result = JsonNode.Parse(await cli.Run(profile, ["account", "list", "--all", "--output", "json"], null, operation!.Token))!.AsArray();
        subscription.Items.Clear();
        foreach (var account in result.Where(item => string.Equals((string?)item?["tenantId"], profile.Tenant, StringComparison.OrdinalIgnoreCase)))
        {
            subscription.Items.Add((string)account!["id"]!);
            Append($"{account["name"]}: {account["id"]}");
        }
        Append("Choose a subscription ID, save, then connect. Sign in first if no subscriptions are listed.");
    }

    private Task CopyInstructions()
    {
        var profile = Save();
        var command = profile.Dataverse.Length > 0
            ? $"az rest --method get --url {profile.Dataverse}/api/data/v9.2/WhoAmI --resource {profile.Dataverse}"
            : "az account show";
        Clipboard.SetText($"Use cloud profile '{profile.Name}'. Prefix every Azure CLI command with cloud-profile {profile.Name} --. "
            + $"Do not use a different CLI cache. Example: cloud-profile {profile.Name} -- {command}"
            + $"\nThe profile store is {store.Root}. Set CLOUD_CONTEXT_HOME to this path if your process uses a different location.");
        Append("Copied instructions for Codex. The cloud-profile launcher must be installed on PATH.");
        return Task.CompletedTask;
    }

    private Task OpenShell()
    {
        var profile = Save();
        var info = new ProcessStartInfo("powershell.exe") { UseShellExecute = false };
        info.ArgumentList.Add("-NoProfile");
        info.ArgumentList.Add("-NoExit");
        foreach (var pair in store.EnvironmentFor(profile)) info.Environment[pair.Key] = pair.Value;
        Process.Start(info)?.Dispose();
        Append("Opened PowerShell with this environment. Existing terminals keep their previous context.");
        return Task.CompletedTask;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) timer.Dispose();
        base.Dispose(disposing);
    }
}
