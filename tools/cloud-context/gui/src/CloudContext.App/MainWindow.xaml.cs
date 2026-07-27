using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using CloudContext.Core;

namespace CloudContext.App;

public partial class MainWindow : Window
{
    private readonly ProfileStore _profileStore;
    private readonly CliOrchestrator _cli;
    private readonly ObservableCollection<CloudProfile> _profiles = [];
    private readonly ObservableCollection<ConnectionStatus> _statuses = [];

    public MainWindow()
    {
        InitializeComponent();
        string? configuredRoot = Environment.GetEnvironmentVariable("CLOUD_CONTEXT_HOME");
        _profileStore = new ProfileStore(configuredRoot);
        _cli = new CliOrchestrator(_profileStore);
        ProfilesList.ItemsSource = _profiles;
        ConnectionsGrid.ItemsSource = _statuses;
        LoadProfiles();
    }

    private CloudProfile? SelectedProfile => ProfilesList.SelectedItem as CloudProfile;

    private void LoadProfiles(string? selectName = null)
    {
        try
        {
            CloudProfileStore store = _profileStore.Load();
            _profiles.Clear();
            foreach (CloudProfile profile in store.Profiles.OrderBy(profile => profile.Label, StringComparer.CurrentCultureIgnoreCase))
            {
                _profiles.Add(profile);
            }

            ProfilesList.SelectedItem = _profiles.FirstOrDefault(profile =>
                profile.Name.Equals(selectName, StringComparison.OrdinalIgnoreCase)) ?? _profiles.FirstOrDefault();
            if (_profiles.Count == 0)
            {
                ShowProfile(null);
            }
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            ShowError("Unable to load profiles", error.Message);
        }
    }

    private void SaveProfiles()
    {
        _profileStore.Save(new CloudProfileStore { Profiles = [.. _profiles] });
    }

    private void ShowProfile(CloudProfile? profile)
    {
        _statuses.Clear();
        if (profile is null)
        {
            ProfileNameText.Text = "Select a profile";
            IdentityText.Text = "Add a profile to get started.";
            SetActionsEnabled(false);
            return;
        }

        ProfileNameText.Text = profile.Label;
        IdentityText.Text = string.Join("  •  ", new[] { profile.Identity.Username, profile.Identity.TenantId }.Where(value => !string.IsNullOrWhiteSpace(value)));
        PopulateConfiguredStatuses(profile);
        SetActionsEnabled(true);
        AzureSignInButton.IsEnabled = profile.Connections.Azure is not null;
        GitHubSignInButton.IsEnabled = profile.Connections.GitHub is not null;
        DataverseSignInButton.IsEnabled = profile.Connections.Dataverse?.Environments.Count > 0;
    }

    private void PopulateConfiguredStatuses(CloudProfile profile)
    {
        AddConfigured(ConnectionKind.Azure, profile.Connections.Azure?.SubscriptionIds);
        AddConfigured(ConnectionKind.GitHub, profile.Connections.GitHub?.Organisations, profile.Connections.GitHub?.Host);
        AddConfigured(ConnectionKind.AzureDevOps, profile.Connections.AzureDevOps?.Organisations);
        AddConfigured(ConnectionKind.Dataverse, profile.Connections.Dataverse?.Environments);
        AddConfigured(ConnectionKind.LogAnalytics, profile.Connections.LogAnalytics?.Workspaces);
    }

    private void AddConfigured(ConnectionKind kind, IEnumerable<string>? values, string? fallback = null)
    {
        List<string> targets = values?.ToList() ?? [];
        if (targets.Count == 0 && !string.IsNullOrWhiteSpace(fallback))
        {
            targets.Add(fallback);
        }

        foreach (string target in targets)
        {
            _statuses.Add(new ConnectionStatus(kind, target, ConnectionState.NotChecked, "Configured; access has not been checked."));
        }
    }

    private void SetActionsEnabled(bool enabled)
    {
        foreach (Button button in FindVisualChildren<Button>(this))
        {
            if (button.Content?.ToString() is "Add" or "Open data folder")
            {
                continue;
            }

            button.IsEnabled = enabled;
        }
    }

    private void ProfilesList_SelectionChanged(object sender, SelectionChangedEventArgs e) => ShowProfile(SelectedProfile);

    private void AddProfile_Click(object sender, RoutedEventArgs e)
    {
        ProfileEditorWindow editor = new(null) { Owner = this };
        if (editor.ShowDialog() != true)
        {
            return;
        }

        if (_profiles.Any(profile => profile.Name.Equals(editor.Profile.Name, StringComparison.OrdinalIgnoreCase)))
        {
            ShowError("Profile already exists", $"A profile named '{editor.Profile.Name}' already exists.");
            return;
        }

        _profiles.Add(editor.Profile);
        SaveProfiles();
        LoadProfiles(editor.Profile.Name);
    }

    private void EditProfile_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? selected = SelectedProfile;
        if (selected is null)
        {
            return;
        }

        ProfileEditorWindow editor = new(selected) { Owner = this };
        if (editor.ShowDialog() != true)
        {
            return;
        }

        if (_profiles.Any(profile => !ReferenceEquals(profile, selected) && profile.Name.Equals(editor.Profile.Name, StringComparison.OrdinalIgnoreCase)))
        {
            ShowError("Profile already exists", $"A profile named '{editor.Profile.Name}' already exists.");
            return;
        }

        int index = _profiles.IndexOf(selected);
        _profiles[index] = editor.Profile;
        SaveProfiles();
        LoadProfiles(editor.Profile.Name);
    }

    private void RemoveProfile_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? selected = SelectedProfile;
        if (selected is null || MessageBox.Show(
                this,
                $"Remove profile '{selected.Label}'? Native CLI credential directories will be retained.",
                "Remove profile",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning) != MessageBoxResult.Yes)
        {
            return;
        }

        _profiles.Remove(selected);
        SaveProfiles();
        ShowProfile(ProfilesList.SelectedItem as CloudProfile);
    }

    private async void ValidateAll_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null)
        {
            return;
        }

        await RunBusyAsync("Validating configured connections…", async () =>
        {
            IReadOnlyList<ConnectionStatus> statuses = await _cli.ValidateAllAsync(profile);
            _statuses.Clear();
            foreach (ConnectionStatus status in statuses)
            {
                _statuses.Add(status);
            }

            ActivityText.Text = $"Validation completed: {statuses.Count(status => status.State == ConnectionState.Connected)} of {statuses.Count} connected.";
        });
    }

    private async void AzureSignIn_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null)
        {
            return;
        }

        await RunCommandAsync("Signing in to Azure…", () => _cli.ConnectAzureAsync(profile));
    }

    private async void GitHubSignIn_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null)
        {
            return;
        }

        await RunCommandAsync("Signing in to GitHub…", () => _cli.ConnectGitHubAsync(profile));
    }

    private async void DataverseSignIn_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        string? environment = ConnectionsGrid.SelectedItem is ConnectionStatus { Kind: ConnectionKind.Dataverse } selected
            ? selected.Target
            : profile?.Connections.Dataverse?.Environments.FirstOrDefault();
        if (profile is null || environment is null)
        {
            return;
        }

        await RunCommandAsync($"Connecting Dataverse environment {environment}…", () => _cli.ConnectDataverseAsync(profile, environment));
    }

    private async Task RunCommandAsync(string activity, Func<Task<CommandResult>> action)
    {
        await RunBusyAsync(activity, async () =>
        {
            CommandResult result = await action();
            ActivityText.Text = result.Succeeded ? "Authentication completed." : $"Command failed with exit code {result.ExitCode}.";
            if (!result.Succeeded)
            {
                ShowError("Authentication failed", string.IsNullOrWhiteSpace(result.StandardError) ? ActivityText.Text : result.StandardError);
            }
        });
    }

    private async Task RunBusyAsync(string activity, Func<Task> action)
    {
        IsEnabled = false;
        ActivityText.Text = activity;
        try
        {
            await action();
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            ActivityText.Text = "Operation failed.";
            ShowError("Cloud Context", error.Message);
        }
        finally
        {
            IsEnabled = true;
        }
    }

    private void OpenPowerShell_Click(object sender, RoutedEventArgs e)
    {
        if (SelectedProfile is CloudProfile profile)
        {
            _cli.OpenPowerShell(profile);
            ActivityText.Text = $"Opened PowerShell for {profile.Label}.";
        }
    }

    private void OpenDataFolder_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(_profileStore.Root);
        Process.Start(new ProcessStartInfo("explorer.exe", _profileStore.Root) { UseShellExecute = true });
    }

    private void ShowError(string title, string message) =>
        MessageBox.Show(this, message.Trim(), title, MessageBoxButton.OK, MessageBoxImage.Error);

    private static IEnumerable<T> FindVisualChildren<T>(DependencyObject root) where T : DependencyObject
    {
        for (int index = 0; index < System.Windows.Media.VisualTreeHelper.GetChildrenCount(root); index++)
        {
            DependencyObject child = System.Windows.Media.VisualTreeHelper.GetChild(root, index);
            if (child is T match)
            {
                yield return match;
            }

            foreach (T descendant in FindVisualChildren<T>(child))
            {
                yield return descendant;
            }
        }
    }
}
