using System.Collections.ObjectModel;
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
    private readonly ObservableCollection<ProfileTreeNode> _treeNodes = [];
    private readonly ObservableCollection<ConnectionStatus> _statuses = [];
    private readonly Dictionary<string, List<ConnectionStatus>> _statusCache = new(StringComparer.OrdinalIgnoreCase);

    public MainWindow()
    {
        InitializeComponent();
        string? configuredRoot = Environment.GetEnvironmentVariable("CLOUD_CONTEXT_HOME");
        _profileStore = new ProfileStore(configuredRoot);
        _cli = new CliOrchestrator(_profileStore);
        ProfilesTree.ItemsSource = _treeNodes;
        ConnectionsGrid.ItemsSource = _statuses;
        LoadProfiles();
    }

    private CloudProfile? SelectedProfile => (ProfilesTree.SelectedItem as ProfileTreeNode)?.Profile;

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

            BuildProfileTree();
            CloudProfile? profileToSelect = _profiles.FirstOrDefault(profile =>
                profile.Name.Equals(selectName, StringComparison.OrdinalIgnoreCase)) ?? _profiles.FirstOrDefault();
            ProfileTreeNode? nodeToSelect = profileToSelect is null ? null : FindProfileNode(_treeNodes, profileToSelect.Name);
            if (nodeToSelect is not null)
            {
                nodeToSelect.IsSelected = true;
            }
            ShowProfile(profileToSelect);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            ShowError("Unable to load profiles", error.Message);
        }
    }

    private void BuildProfileTree()
    {
        _treeNodes.Clear();
        foreach (CloudProfile profile in _profiles)
        {
            ObservableCollection<ProfileTreeNode> level = _treeNodes;
            string folder = ProfileStore.NormalizeFolder(profile.Folder);
            foreach (string segment in folder.Split('/', StringSplitOptions.RemoveEmptyEntries))
            {
                ProfileTreeNode? folderNode = level.FirstOrDefault(node =>
                    node.Profile is null && node.Name.Equals(segment, StringComparison.CurrentCultureIgnoreCase));
                if (folderNode is null)
                {
                    folderNode = new ProfileTreeNode(segment);
                    level.Add(folderNode);
                }

                level = folderNode.Children;
            }

            level.Add(new ProfileTreeNode(profile.Label, profile));
        }

        SortTree(_treeNodes);
    }

    private static void SortTree(ObservableCollection<ProfileTreeNode> nodes)
    {
        List<ProfileTreeNode> ordered = nodes
            .OrderBy(node => node.Profile is null ? 0 : 1)
            .ThenBy(node => node.Name, StringComparer.CurrentCultureIgnoreCase)
            .ToList();
        nodes.Clear();
        foreach (ProfileTreeNode node in ordered)
        {
            SortTree(node.Children);
            nodes.Add(node);
        }
    }

    private static ProfileTreeNode? FindProfileNode(IEnumerable<ProfileTreeNode> nodes, string profileName)
    {
        foreach (ProfileTreeNode node in nodes)
        {
            if (node.Profile?.Name.Equals(profileName, StringComparison.OrdinalIgnoreCase) == true)
            {
                return node;
            }

            ProfileTreeNode? match = FindProfileNode(node.Children, profileName);
            if (match is not null)
            {
                return match;
            }
        }

        return null;
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
            ActiveProfileText.Text = ActiveProfileDescription(null);
            SetActionsEnabled(false);
            return;
        }

        ProfileNameText.Text = profile.Label;
        IdentityText.Text = string.Join("  •  ", new[] { profile.Identity.Username, profile.Identity.TenantId }.Where(value => !string.IsNullOrWhiteSpace(value)));
        ActiveProfileText.Text = ActiveProfileDescription(profile);
        if (_statusCache.TryGetValue(profile.Name, out List<ConnectionStatus>? cachedStatuses))
        {
            foreach (ConnectionStatus status in cachedStatuses)
            {
                _statuses.Add(status);
            }
        }
        else
        {
            PopulateConfiguredStatuses(profile);
        }
        SetActionsEnabled(true);
        AzureSignInButton.Visibility = profile.Connections.Azure is not null ? Visibility.Visible : Visibility.Collapsed;
        GitHubSignInButton.Visibility = profile.Connections.GitHub is not null ? Visibility.Visible : Visibility.Collapsed;
        DataverseSignInButton.Visibility = profile.Connections.Dataverse?.Environments.Count > 0 ? Visibility.Visible : Visibility.Collapsed;
        EditConnectionButton.IsEnabled = false;
        RemoveConnectionButton.IsEnabled = false;
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
            _statuses.Add(new ConnectionStatus(kind, target, ConnectionState.NotChecked, "Configured; access has not been checked.", true));
        }
    }

    private void SetActionsEnabled(bool enabled)
    {
        EditProfileButton.IsEnabled = enabled;
        RemoveProfileButton.IsEnabled = enabled;
        ValidateSelectedButton.IsEnabled = enabled;
        AddConnectionButton.IsEnabled = enabled;
        MakeActiveButton.IsEnabled = enabled;
        OpenPowerShellButton.IsEnabled = enabled;
        ValidateEveryProfileButton.IsEnabled = _profiles.Count > 0;
        AzureSignInButton.Visibility = Visibility.Collapsed;
        GitHubSignInButton.Visibility = Visibility.Collapsed;
        DataverseSignInButton.Visibility = Visibility.Collapsed;
        EditConnectionButton.IsEnabled = false;
        RemoveConnectionButton.IsEnabled = false;
    }

    private void ProfilesTree_SelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e) => ShowProfile(SelectedProfile);

    private void ConnectionsGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        bool canChange = ConnectionsGrid.SelectedItem is ConnectionStatus { CanRemove: true } && SelectedProfile is not null;
        EditConnectionButton.IsEnabled = canChange;
        RemoveConnectionButton.IsEnabled = canChange;
    }

    private void AddConnection_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null)
        {
            return;
        }

        ConnectionEditorWindow editor = new(profile) { Owner = this };
        if (editor.ShowDialog() != true)
        {
            return;
        }

        try
        {
            bool added = ProfileConnections.Add(profile, editor.Connection);
            InvalidateStatus(profile);
            SaveProfiles();
            ShowProfile(profile);
            ActivityText.Text = added
                ? $"Added {editor.Connection.Kind} connection '{editor.Connection.Target}'."
                : "That connection is already configured.";
        }
        catch (InvalidDataException error)
        {
            ShowError("Unable to add connection", error.Message);
        }
    }

    private void RemoveConnection_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null || ConnectionsGrid.SelectedItem is not ConnectionStatus { CanRemove: true } selected)
        {
            return;
        }

        if (MessageBox.Show(
                this,
                $"Remove {selected.Kind} connection '{selected.Target}'? Native CLI credentials will be retained.",
                "Remove connection",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning) != MessageBoxResult.Yes)
        {
            return;
        }

        if (!ProfileConnections.Remove(profile, selected.Kind, selected.Target))
        {
            ShowError("Unable to remove connection", "The selected configured target was not found.");
            return;
        }

        InvalidateStatus(profile);
        SaveProfiles();
        ShowProfile(profile);
        ActivityText.Text = $"Removed {selected.Kind} connection '{selected.Target}'. Native credentials were retained.";
    }

    private void EditConnection_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null || ConnectionsGrid.SelectedItem is not ConnectionStatus { CanRemove: true } selected)
        {
            return;
        }

        ConnectionEditorWindow editor = new(profile, selected) { Owner = this };
        if (editor.ShowDialog() != true)
        {
            return;
        }

        try
        {
            ProfileConnections.Update(profile, selected.Kind, selected.Target, editor.Connection);
            InvalidateStatus(profile);
            SaveProfiles();
            ShowProfile(profile);
            ActivityText.Text = $"Updated {selected.Kind} connection to '{editor.Connection.Target}'.";
        }
        catch (InvalidDataException error)
        {
            ShowError("Unable to edit connection", error.Message);
        }
    }

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
        _statusCache.Remove(selected.Name);
        _profiles[index] = editor.Profile;
        InvalidateStatus(editor.Profile);
        SaveProfiles();
        _profileStore.UpdateActiveProfileName(selected.Name, editor.Profile.Name);
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

        bool wasActive = selected.Name.Equals(_profileStore.GetActiveProfileName(), StringComparison.OrdinalIgnoreCase);
        _statusCache.Remove(selected.Name);
        _profiles.Remove(selected);
        SaveProfiles();
        if (wasActive)
        {
            _profileStore.ClearActiveProfile();
        }
        LoadProfiles();
    }

    private async void MakeActive_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null)
        {
            return;
        }

        try
        {
            _profileStore.SetActiveProfile(profile.Name);
            ActiveProfileText.Text = ActiveProfileDescription(profile);
            string detail = $"{profile.Label} is now active for new or restored PowerShell sessions.";
            if (ConnectionsGrid.SelectedItem is ConnectionStatus selected)
            {
                CommandResult? selectionResult = selected.Kind switch
                {
                    ConnectionKind.Azure => await _cli.SelectAzureSubscriptionAsync(profile, selected.Target),
                    ConnectionKind.Dataverse => await _cli.SelectDataverseAsync(profile, selected.Target),
                    _ => null
                };
                if (selectionResult is not null)
                {
                    detail += selectionResult.Succeeded
                        ? $" Selected {selected.Kind} target '{selected.Target}'."
                        : $" The {selected.Kind} target could not be selected; sign in first.";
                }
            }
            ActivityText.Text = detail;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            ShowError("Unable to set active profile", error.Message);
        }
    }

    private async void ValidateSelected_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null)
        {
            return;
        }

        await RunBusyAsync("Validating configured connections…", async () =>
        {
            IReadOnlyList<ConnectionStatus> statuses = await _cli.ValidateAllAsync(profile);
            _statusCache[profile.Name] = [.. statuses];
            _statuses.Clear();
            foreach (ConnectionStatus status in statuses)
            {
                _statuses.Add(status);
            }

            ActivityText.Text = $"Validation completed: {statuses.Count(status => status.State == ConnectionState.Connected)} of {statuses.Count} connected.";
        });
    }

    private async void ValidateEveryProfile_Click(object sender, RoutedEventArgs e)
    {
        if (_profiles.Count == 0)
        {
            return;
        }

        CloudProfile? selectedProfile = SelectedProfile;
        await RunBusyAsync("Validating every identity and configured connection…", async () =>
        {
            int connectionCount = 0;
            int connectedCount = 0;
            foreach (CloudProfile profile in _profiles)
            {
                IReadOnlyList<ConnectionStatus> statuses = await _cli.ValidateAllAsync(profile);
                _statusCache[profile.Name] = [.. statuses];
                connectionCount += statuses.Count;
                connectedCount += statuses.Count(status => status.State == ConnectionState.Connected);
            }

            ShowProfile(selectedProfile);
            ActivityText.Text = $"Validated {_profiles.Count} identities: {connectedCount} of {connectionCount} connections connected.";
        });
    }

    private async void AzureSignIn_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null)
        {
            return;
        }

        await RunBusyAsync("Signing in to Azure…", async () =>
        {
            CommandResult result = await _cli.ConnectAzureAsync(profile);
            if (!result.Succeeded)
            {
                ActivityText.Text = $"Azure sign-in failed with exit code {result.ExitCode}.";
                ShowError("Authentication failed", ActivityText.Text);
                return;
            }

            InvalidateStatus(profile);
            string? signedInUsername = await _cli.GetAzureUsernameAsync(profile);
            if (string.IsNullOrWhiteSpace(signedInUsername))
            {
                ActivityText.Text = "Azure authentication completed, but the signed-in username could not be read.";
                return;
            }

            if (string.IsNullOrWhiteSpace(profile.Identity.Username))
            {
                profile.Identity.Username = signedInUsername;
                SaveProfiles();
                ShowProfile(profile);
                ActivityText.Text = $"Azure authentication completed and associated with {signedInUsername}.";
                return;
            }

            if (!profile.Identity.Username.Equals(signedInUsername, StringComparison.OrdinalIgnoreCase))
            {
                ShowProfile(profile);
                ActivityText.Text = $"Signed in as {signedInUsername}; this profile expects {profile.Identity.Username}.";
                ShowError("Wrong Azure identity", ActivityText.Text);
                return;
            }

            ShowProfile(profile);
            ActivityText.Text = $"Azure authentication completed as {signedInUsername}.";
        });
    }

    private async void GitHubSignIn_Click(object sender, RoutedEventArgs e)
    {
        CloudProfile? profile = SelectedProfile;
        if (profile is null)
        {
            return;
        }

        if (await RunCommandAsync("Signing in to GitHub…", () => _cli.ConnectGitHubAsync(profile)))
        {
            InvalidateStatus(profile);
            ShowProfile(profile);
        }
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

        if (await RunCommandAsync($"Connecting Dataverse environment {environment}…", () => _cli.ConnectDataverseAsync(profile, environment)))
        {
            InvalidateStatus(profile);
            ShowProfile(profile);
        }
    }

    private async Task<bool> RunCommandAsync(string activity, Func<Task<CommandResult>> action)
    {
        bool succeeded = false;
        await RunBusyAsync(activity, async () =>
        {
            CommandResult result = await action();
            succeeded = result.Succeeded;
            ActivityText.Text = result.Succeeded ? "Authentication completed." : $"Command failed with exit code {result.ExitCode}.";
            if (!result.Succeeded)
            {
                ShowError("Authentication failed", string.IsNullOrWhiteSpace(result.StandardError) ? ActivityText.Text : result.StandardError);
            }
        });
        return succeeded;
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
            ShowError("Cloud Connect", error.Message);
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

    private void ShowError(string title, string message) =>
        MessageBox.Show(this, message.Trim(), title, MessageBoxButton.OK, MessageBoxImage.Error);

    private string ActiveProfileDescription(CloudProfile? selected)
    {
        string? activeName = _profileStore.GetActiveProfileName();
        if (activeName is null)
        {
            return "No default active profile; scoped commands remain explicit.";
        }

        return selected?.Name.Equals(activeName, StringComparison.OrdinalIgnoreCase) == true
            ? "Active for new or restored PowerShell sessions."
            : $"Selected only • Active profile: {activeName}";
    }

    private void InvalidateStatus(CloudProfile profile) => _statusCache.Remove(profile.Name);

}
