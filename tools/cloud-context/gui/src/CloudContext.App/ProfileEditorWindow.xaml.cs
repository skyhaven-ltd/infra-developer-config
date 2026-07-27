using System.IO;
using System.Windows;
using CloudContext.Core;

namespace CloudContext.App;

public partial class ProfileEditorWindow : Window
{
    public ProfileEditorWindow(CloudProfile? profile)
    {
        InitializeComponent();
        Profile = profile ?? new CloudProfile();
        NameBox.Text = Profile.Name;
        DisplayNameBox.Text = Profile.DisplayName;
        UsernameBox.Text = Profile.Identity.Username;
        TenantBox.Text = Profile.Identity.TenantId;
        SubscriptionsBox.Text = Lines(Profile.Connections.Azure?.SubscriptionIds);
        GitHubHostBox.Text = Profile.Connections.GitHub?.Host ?? string.Empty;
        GitHubUserBox.Text = Profile.Connections.GitHub?.User ?? string.Empty;
        GitHubOrganisationsBox.Text = Lines(Profile.Connections.GitHub?.Organisations);
        AzureDevOpsBox.Text = Lines(Profile.Connections.AzureDevOps?.Organisations);
        DataverseBox.Text = Lines(Profile.Connections.Dataverse?.Environments);
        LogAnalyticsBox.Text = Lines(Profile.Connections.LogAnalytics?.Workspaces);
    }

    public CloudProfile Profile { get; private set; }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        List<string> subscriptions = Values(SubscriptionsBox.Text);
        List<string> githubOrganisations = Values(GitHubOrganisationsBox.Text);
        List<string> azureDevOpsOrganisations = Values(AzureDevOpsBox.Text);
        List<string> dataverseEnvironments = Values(DataverseBox.Text);
        List<string> workspaces = Values(LogAnalyticsBox.Text);
        bool hasGitHub = !string.IsNullOrWhiteSpace(GitHubHostBox.Text) ||
                         !string.IsNullOrWhiteSpace(GitHubUserBox.Text) ||
                         githubOrganisations.Count > 0;

        CloudProfile candidate = new()
        {
            Name = NameBox.Text.Trim(),
            DisplayName = DisplayNameBox.Text.Trim(),
            Identity = new CloudIdentity
            {
                Username = UsernameBox.Text.Trim(),
                TenantId = TenantBox.Text.Trim()
            },
            Connections = new CloudConnections
            {
                Azure = subscriptions.Count == 0 ? null : new AzureConnection { SubscriptionIds = subscriptions },
                GitHub = !hasGitHub ? null : new GitHubConnection
                {
                    Host = string.IsNullOrWhiteSpace(GitHubHostBox.Text) ? "github.com" : GitHubHostBox.Text.Trim(),
                    User = GitHubUserBox.Text.Trim(),
                    Organisations = githubOrganisations
                },
                AzureDevOps = azureDevOpsOrganisations.Count == 0 ? null : new AzureDevOpsConnection { Organisations = azureDevOpsOrganisations },
                Dataverse = dataverseEnvironments.Count == 0 ? null : new DataverseConnection { Environments = dataverseEnvironments },
                LogAnalytics = workspaces.Count == 0 ? null : new LogAnalyticsConnection { Workspaces = workspaces }
            }
        };

        try
        {
            ProfileStore.ValidateProfile(candidate);
            Profile = candidate;
            DialogResult = true;
        }
        catch (InvalidDataException error)
        {
            MessageBox.Show(this, error.Message, "Invalid profile", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }

    private static List<string> Values(string text) => text
        .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToList();

    private static string Lines(IEnumerable<string>? values) => string.Join(Environment.NewLine, values ?? []);
}
