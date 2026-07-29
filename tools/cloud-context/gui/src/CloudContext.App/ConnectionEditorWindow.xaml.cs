using System.IO;
using System.Windows;
using System.Windows.Controls;
using CloudContext.Core;

namespace CloudContext.App;

public partial class ConnectionEditorWindow : Window
{
    private readonly CloudProfile _profile;

    public ConnectionEditorWindow(CloudProfile profile, ConnectionStatus? existing = null)
    {
        InitializeComponent();
        _profile = profile;
        KindBox.ItemsSource = Enum.GetValues<ConnectionKind>();
        KindBox.SelectedItem = existing?.Kind ?? ConnectionKind.Azure;
        if (existing is not null)
        {
            Title = "Edit connection";
            HeadingText.Text = "Edit connection";
            SaveButton.Content = "Save";
            KindBox.IsEnabled = false;
            TargetBox.Text = existing.Target;
            if (existing.Kind == ConnectionKind.GitHub)
            {
                HostBox.Text = profile.Connections.GitHub?.Host ?? "github.com";
                UserBox.Text = profile.Connections.GitHub?.User ?? string.Empty;
                if (profile.Connections.GitHub?.Organisations.Count == 0)
                {
                    TargetLabel.Text = "GitHub host";
                    HelpText.Text = "Updates this legacy host-only GitHub connection.";
                    HostField.Visibility = Visibility.Collapsed;
                }
            }
        }
    }

    public ConnectionInput Connection { get; private set; } = new(ConnectionKind.Azure, string.Empty);

    private void KindBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (KindBox.SelectedItem is not ConnectionKind kind)
        {
            return;
        }

        (TargetLabel.Text, HelpText.Text) = kind switch
        {
            ConnectionKind.Azure => ("Subscription ID", "Adds an Azure subscription beneath this Entra identity."),
            ConnectionKind.GitHub => ("Organisation", "Adds a GitHub organisation and the native GitHub CLI identity used for it."),
            ConnectionKind.AzureDevOps => ("Organisation URL", "Example: https://dev.azure.com/customer"),
            ConnectionKind.Dataverse => ("Environment URL", "Example: https://customer.crm.dynamics.com"),
            ConnectionKind.LogAnalytics => ("Workspace ID", "Adds a Log Analytics workspace for resource-specific access validation."),
            _ => ("Target", string.Empty)
        };
        GitHubFields.Visibility = kind == ConnectionKind.GitHub ? Visibility.Visible : Visibility.Collapsed;
        if (kind == ConnectionKind.GitHub)
        {
            HostBox.Text = _profile.Connections.GitHub?.Host ?? "github.com";
            UserBox.Text = _profile.Connections.GitHub?.User ?? string.Empty;
        }
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        if (KindBox.SelectedItem is not ConnectionKind kind || string.IsNullOrWhiteSpace(TargetBox.Text))
        {
            MessageBox.Show(this, "Enter a connection target.", "Invalid connection", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        ConnectionInput candidate = new(
            kind,
            TargetBox.Text.Trim(),
            HostBox.Text.Trim(),
            UserBox.Text.Trim());
        try
        {
            if (kind is not ConnectionKind.GitHub && string.IsNullOrWhiteSpace(_profile.Identity.TenantId))
            {
                throw new InvalidDataException("Add a Microsoft Entra tenant ID to the identity first.");
            }

            Connection = candidate;
            DialogResult = true;
        }
        catch (InvalidDataException error)
        {
            MessageBox.Show(this, error.Message, "Invalid connection", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }
}
