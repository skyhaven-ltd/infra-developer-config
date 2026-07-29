namespace CloudContext.Core;

public static class ProfileConnections
{
    public static bool Add(CloudProfile profile, ConnectionInput input)
    {
        string target = input.Target.Trim();
        if (string.IsNullOrWhiteSpace(target))
        {
            throw new InvalidDataException("A connection target is required.");
        }
        if (input.Kind is not ConnectionKind.GitHub && string.IsNullOrWhiteSpace(profile.Identity.TenantId))
        {
            throw new InvalidDataException("Add a Microsoft Entra tenant ID to the identity before adding this connection.");
        }

        bool added = input.Kind switch
        {
            ConnectionKind.Azure => AddAzure(profile, target),
            ConnectionKind.GitHub => AddGitHub(profile, target, input.Host, input.User),
            ConnectionKind.AzureDevOps => AddAzureDevOps(profile, target),
            ConnectionKind.Dataverse => AddDataverse(profile, target),
            ConnectionKind.LogAnalytics => AddLogAnalytics(profile, target),
            _ => throw new ArgumentOutOfRangeException(nameof(input), input.Kind, "Unsupported connection type.")
        };
        ProfileStore.ValidateProfile(profile);
        return added;
    }

    public static bool Remove(CloudProfile profile, ConnectionKind kind, string target)
    {
        bool removed = kind switch
        {
            ConnectionKind.Azure => RemoveFrom(
                profile.Connections.Azure?.SubscriptionIds,
                target,
                () => profile.Connections.Azure = null),
            ConnectionKind.GitHub => RemoveGitHub(profile, target),
            ConnectionKind.AzureDevOps => RemoveFrom(
                profile.Connections.AzureDevOps?.Organisations,
                target,
                () => profile.Connections.AzureDevOps = null),
            ConnectionKind.Dataverse => RemoveFrom(
                profile.Connections.Dataverse?.Environments,
                target,
                () => profile.Connections.Dataverse = null),
            ConnectionKind.LogAnalytics => RemoveFrom(
                profile.Connections.LogAnalytics?.Workspaces,
                target,
                () => profile.Connections.LogAnalytics = null),
            _ => false
        };
        ProfileStore.ValidateProfile(profile);
        return removed;
    }

    public static void Update(CloudProfile profile, ConnectionKind kind, string originalTarget, ConnectionInput input)
    {
        if (input.Kind != kind)
        {
            throw new InvalidDataException("A connection type cannot be changed after it has been created.");
        }

        CloudConnections original = profile.Connections;
        profile.Connections = Clone(original);
        try
        {
            if (kind == ConnectionKind.GitHub && original.GitHub?.Organisations.Count == 0)
            {
                string host = input.Target.Trim();
                if (string.IsNullOrWhiteSpace(host))
                {
                    throw new InvalidDataException("A connection target is required.");
                }

                profile.Connections.GitHub = new GitHubConnection
                {
                    Host = host,
                    User = input.User.Trim()
                };
                ProfileStore.ValidateProfile(profile);
                return;
            }

            if (!Remove(profile, kind, originalTarget))
            {
                throw new InvalidDataException("The connection being edited no longer exists.");
            }

            if (!Add(profile, input))
            {
                throw new InvalidDataException("That connection is already configured.");
            }

            if (kind == ConnectionKind.GitHub)
            {
                profile.Connections.GitHub!.User = input.User.Trim();
            }
        }
        catch
        {
            profile.Connections = original;
            throw;
        }
    }

    private static bool AddAzure(CloudProfile profile, string target)
    {
        profile.Connections.Azure ??= new AzureConnection();
        return AddUnique(profile.Connections.Azure.SubscriptionIds, target);
    }

    private static bool AddGitHub(CloudProfile profile, string target, string host, string user)
    {
        if (profile.Connections.GitHub?.Organisations.Contains(target, StringComparer.OrdinalIgnoreCase) == true)
        {
            return false;
        }

        string resolvedHost = string.IsNullOrWhiteSpace(host) ? "github.com" : host.Trim();
        profile.Connections.GitHub ??= new GitHubConnection();
        profile.Connections.GitHub.Host = resolvedHost;
        if (!string.IsNullOrWhiteSpace(user))
        {
            profile.Connections.GitHub.User = user.Trim();
        }

        return AddUnique(profile.Connections.GitHub.Organisations, target);
    }

    private static bool AddAzureDevOps(CloudProfile profile, string target)
    {
        profile.Connections.AzureDevOps ??= new AzureDevOpsConnection();
        return AddUnique(profile.Connections.AzureDevOps.Organisations, target);
    }

    private static bool AddDataverse(CloudProfile profile, string target)
    {
        profile.Connections.Dataverse ??= new DataverseConnection();
        return AddUnique(profile.Connections.Dataverse.Environments, target);
    }

    private static bool AddLogAnalytics(CloudProfile profile, string target)
    {
        profile.Connections.LogAnalytics ??= new LogAnalyticsConnection();
        return AddUnique(profile.Connections.LogAnalytics.Workspaces, target);
    }

    private static bool RemoveGitHub(CloudProfile profile, string target)
    {
        GitHubConnection? github = profile.Connections.GitHub;
        if (github is null)
        {
            return false;
        }

        if (github.Organisations.Count == 0 && github.Host.Equals(target, StringComparison.OrdinalIgnoreCase))
        {
            profile.Connections.GitHub = null;
            return true;
        }

        return RemoveFrom(github.Organisations, target, () => profile.Connections.GitHub = null);
    }

    private static bool AddUnique(List<string> values, string value)
    {
        if (values.Contains(value, StringComparer.OrdinalIgnoreCase))
        {
            return false;
        }

        values.Add(value);
        return true;
    }

    private static CloudConnections Clone(CloudConnections connections) => new()
    {
        Azure = connections.Azure is null
            ? null
            : new AzureConnection { SubscriptionIds = [.. connections.Azure.SubscriptionIds] },
        GitHub = connections.GitHub is null
            ? null
            : new GitHubConnection
            {
                Host = connections.GitHub.Host,
                User = connections.GitHub.User,
                Organisations = [.. connections.GitHub.Organisations]
            },
        AzureDevOps = connections.AzureDevOps is null
            ? null
            : new AzureDevOpsConnection { Organisations = [.. connections.AzureDevOps.Organisations] },
        Dataverse = connections.Dataverse is null
            ? null
            : new DataverseConnection { Environments = [.. connections.Dataverse.Environments] },
        LogAnalytics = connections.LogAnalytics is null
            ? null
            : new LogAnalyticsConnection { Workspaces = [.. connections.LogAnalytics.Workspaces] }
    };

    private static bool RemoveFrom(List<string>? values, string target, Action removeConnector)
    {
        string? match = values?.FirstOrDefault(value => value.Equals(target, StringComparison.OrdinalIgnoreCase));
        if (match is null)
        {
            return false;
        }

        values!.Remove(match);
        if (values.Count == 0)
        {
            removeConnector();
        }

        return true;
    }
}
