using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace CloudContext.Core;

public sealed partial class ProfileStore
{
    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    public ProfileStore(string? root = null)
    {
        Root = string.IsNullOrWhiteSpace(root)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".config", "cloud-context")
            : Path.GetFullPath(Environment.ExpandEnvironmentVariables(root));
    }

    public string Root { get; }

    public string FilePath => Path.Combine(Root, "profiles.json");

    public CloudProfileStore Load()
    {
        if (!File.Exists(FilePath))
        {
            return new CloudProfileStore();
        }

        JsonNode root = JsonNode.Parse(File.ReadAllText(FilePath))
            ?? throw new InvalidDataException($"Profile store '{FilePath}' is empty.");

        int schemaVersion = root["schemaVersion"]?.GetValue<int>() ?? 1;
        CloudProfileStore store = schemaVersion >= 2
            ? root.Deserialize<CloudProfileStore>(SerializerOptions)
                ?? throw new InvalidDataException($"Profile store '{FilePath}' is invalid.")
            : MigrateLegacy(root);

        ValidateStore(store);
        return store;
    }

    public void Save(CloudProfileStore store)
    {
        ValidateStore(store);
        Directory.CreateDirectory(Root);
        string temporaryPath = FilePath + ".tmp";
        File.WriteAllText(temporaryPath, JsonSerializer.Serialize(store, SerializerOptions));
        File.Move(temporaryPath, FilePath, true);
    }

    public static void ValidateProfile(CloudProfile profile)
    {
        if (profile.Identity is null || profile.Connections is null)
        {
            throw new InvalidDataException("Each profile must contain identity and connections objects.");
        }

        if (!ProfileNamePattern().IsMatch(profile.Name))
        {
            throw new InvalidDataException(
                "Profile names must start with a letter or number, contain only letters, numbers, '.', '_' or '-', and be at most 64 characters.");
        }

        if (string.IsNullOrWhiteSpace(profile.Identity.TenantId) &&
            (profile.Connections.Azure is not null ||
             profile.Connections.AzureDevOps is not null ||
             profile.Connections.Dataverse is not null ||
             profile.Connections.LogAnalytics is not null))
        {
            throw new InvalidDataException("A Microsoft Entra tenant ID is required for Microsoft connections.");
        }

        RejectEmpty(profile.Connections.Azure?.SubscriptionIds, "Azure subscription IDs");
        RejectEmpty(profile.Connections.GitHub?.Organisations, "GitHub organisations");
        RejectEmpty(profile.Connections.AzureDevOps?.Organisations, "Azure DevOps organisations");
        RejectEmpty(profile.Connections.Dataverse?.Environments, "Dataverse environments");
        RejectEmpty(profile.Connections.LogAnalytics?.Workspaces, "Log Analytics workspaces");
    }

    private static void ValidateStore(CloudProfileStore store)
    {
        if (store.SchemaVersion != 2)
        {
            throw new InvalidDataException($"Unsupported profile schema version '{store.SchemaVersion}'.");
        }

        if (store.Profiles is null)
        {
            throw new InvalidDataException("The profile store must contain a profiles array.");
        }

        foreach (CloudProfile profile in store.Profiles)
        {
            profile.Connections.Azure?.SubscriptionIds ??= [];
            profile.Connections.GitHub?.Organisations ??= [];
            profile.Connections.AzureDevOps?.Organisations ??= [];
            profile.Connections.Dataverse?.Environments ??= [];
            profile.Connections.LogAnalytics?.Workspaces ??= [];
            ValidateProfile(profile);
        }

        string? duplicate = store.Profiles
            .GroupBy(profile => profile.Name, StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault(group => group.Count() > 1)?.Key;
        if (duplicate is not null)
        {
            throw new InvalidDataException($"Cloud profile '{duplicate}' is duplicated.");
        }
    }

    private static CloudProfileStore MigrateLegacy(JsonNode root)
    {
        CloudProfileStore migrated = new();
        foreach (JsonNode? item in root["profiles"]?.AsArray() ?? [])
        {
            if (item is null)
            {
                continue;
            }

            string name = Text(item, "name");
            string subscription = Text(item, "azureSubscriptionId");
            string organisation = Text(item, "githubOrg");
            migrated.Profiles.Add(new CloudProfile
            {
                Name = name,
                DisplayName = name,
                Identity = new CloudIdentity
                {
                    TenantId = Text(item, "azureTenantId")
                },
                Connections = new CloudConnections
                {
                    Azure = string.IsNullOrWhiteSpace(subscription)
                        ? null
                        : new AzureConnection { SubscriptionIds = [subscription] },
                    GitHub = string.IsNullOrWhiteSpace(Text(item, "githubHost")) &&
                             string.IsNullOrWhiteSpace(organisation)
                        ? null
                        : new GitHubConnection
                        {
                            Host = Text(item, "githubHost", "github.com"),
                            User = Text(item, "githubUser"),
                            Organisations = string.IsNullOrWhiteSpace(organisation) ? [] : [organisation]
                        }
                }
            });
        }

        return migrated;
    }

    private static string Text(JsonNode item, string property, string fallback = "") =>
        item[property]?.GetValue<string>() ?? fallback;

    private static void RejectEmpty(List<string>? values, string label)
    {
        if (values?.Any(string.IsNullOrWhiteSpace) == true)
        {
            throw new InvalidDataException($"{label} cannot contain empty values.");
        }
    }

    [GeneratedRegex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", RegexOptions.CultureInvariant)]
    private static partial Regex ProfileNamePattern();
}
