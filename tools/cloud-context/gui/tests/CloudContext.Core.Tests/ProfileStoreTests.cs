using System.Text.Json;
using CloudContext.Core;
using Xunit;

namespace CloudContext.Core.Tests;

public sealed class ProfileStoreTests : IDisposable
{
    private readonly string _root = Path.Combine(Path.GetTempPath(), "cloud-context-tests", Guid.NewGuid().ToString("N"));

    [Fact]
    public void LoadMigratesLegacyProfileWithoutCredentials()
    {
        Directory.CreateDirectory(_root);
        File.WriteAllText(
            Path.Combine(_root, "profiles.json"),
            """
            {
              "profiles": [{
                "name": "customer-prod",
                "azureTenantId": "tenant-id",
                "azureSubscriptionId": "subscription-id",
                "githubHost": "github.com",
                "githubOrg": "customer",
                "githubUser": "liam"
              }]
            }
            """);

        CloudProfile profile = new ProfileStore(_root).Load().Profiles.Single();

        Assert.Equal("tenant-id", profile.Identity.TenantId);
        Assert.Equal("subscription-id", profile.Connections.Azure!.SubscriptionIds.Single());
        Assert.Equal("customer", profile.Connections.GitHub!.Organisations.Single());
        Assert.DoesNotContain("token", JsonSerializer.Serialize(profile), StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("password", JsonSerializer.Serialize(profile), StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void SaveWritesVersionedStoreAtomically()
    {
        ProfileStore profileStore = new(_root);
        profileStore.Save(new CloudProfileStore
        {
            Profiles = [Profile()]
        });

        string json = File.ReadAllText(profileStore.FilePath);

        Assert.Contains("\"schemaVersion\": 2", json, StringComparison.Ordinal);
        Assert.False(File.Exists(profileStore.FilePath + ".tmp"));
        Assert.Equal("customer-prod", profileStore.Load().Profiles.Single().Name);
    }

    [Fact]
    public void SaveRejectsDuplicateNamesIgnoringCase()
    {
        CloudProfile duplicate = Profile();
        duplicate.Name = "CUSTOMER-PROD";

        InvalidDataException error = Assert.Throws<InvalidDataException>(() =>
            new ProfileStore(_root).Save(new CloudProfileStore { Profiles = [Profile(), duplicate] }));

        Assert.Contains("duplicated", error.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void EnvironmentUsesPerProfileCliDirectories()
    {
        ProfileStore store = new(_root);
        IReadOnlyDictionary<string, string> environment = new CliOrchestrator(store).BuildEnvironment(Profile());

        Assert.Equal(Path.Combine(_root, "cli", "azure", "customer-prod"), environment["AZURE_CONFIG_DIR"]);
        Assert.Equal(Path.Combine(_root, "cli", "github", "customer-prod"), environment["GH_CONFIG_DIR"]);
        Assert.Equal("tenant-id", environment["AZURE_TENANT_ID"]);
        Assert.Equal("subscription-id", environment["AZURE_SUBSCRIPTION_ID"]);
        Assert.Equal("customer", environment["GH_ORG"]);
    }

    [Fact]
    public async Task AzureConnectionCanRunWindowsCommandShim()
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        string tools = Path.Combine(_root, "tools with spaces");
        string log = Path.Combine(_root, "az-invocations.txt");
        Directory.CreateDirectory(tools);
        await File.WriteAllTextAsync(
            Path.Combine(tools, "az.cmd"),
            $"@echo off\r\necho %*>>\"{log}\"\r\nexit /b 0\r\n",
            TestContext.Current.CancellationToken);
        string? originalPath = Environment.GetEnvironmentVariable("PATH");
        Environment.SetEnvironmentVariable("PATH", tools + Path.PathSeparator + originalPath);
        try
        {
            CommandResult result = await new CliOrchestrator(new ProfileStore(_root))
                .ConnectAzureAsync(Profile(), TestContext.Current.CancellationToken);

            Assert.True(result.Succeeded);
            string[] invocations = await File.ReadAllLinesAsync(log, TestContext.Current.CancellationToken);
            Assert.Contains(invocations, value => value.Contains("login --tenant tenant-id", StringComparison.Ordinal));
            Assert.Contains(invocations, value => value.Contains("account set --subscription subscription-id", StringComparison.Ordinal));
        }
        finally
        {
            Environment.SetEnvironmentVariable("PATH", originalPath);
        }
    }

    [Fact]
    public async Task AzureUsernameIsReadAndValidatedAgainstProfile()
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        string tools = Path.Combine(_root, "identity tools with spaces");
        Directory.CreateDirectory(tools);
        await File.WriteAllTextAsync(
            Path.Combine(tools, "az.cmd"),
            "@echo off\r\necho {\"tenantId\":\"tenant-id\",\"id\":\"subscription-id\",\"user\":{\"name\":\"actual@example.com\"}}\r\nexit /b 0\r\n",
            TestContext.Current.CancellationToken);
        string? originalPath = Environment.GetEnvironmentVariable("PATH");
        Environment.SetEnvironmentVariable("PATH", tools + Path.PathSeparator + originalPath);
        try
        {
            CloudProfile profile = AzureOnlyProfile();
            CliOrchestrator cli = new(new ProfileStore(_root));

            string? username = await cli.GetAzureUsernameAsync(profile, TestContext.Current.CancellationToken);
            IReadOnlyList<ConnectionStatus> statuses = await cli.ValidateAllAsync(profile, TestContext.Current.CancellationToken);

            Assert.Equal("actual@example.com", username);
            Assert.Equal(ConnectionState.Misconfigured, Assert.Single(statuses).State);
            Assert.Contains("actual@example.com", statuses[0].Detail, StringComparison.Ordinal);
        }
        finally
        {
            Environment.SetEnvironmentVariable("PATH", originalPath);
        }
    }

    [Fact]
    public async Task GitHubIdentityAndOrganisationProduceSingleStatus()
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        string tools = Path.Combine(_root, "github tools with spaces");
        Directory.CreateDirectory(tools);
        await File.WriteAllTextAsync(
            Path.Combine(tools, "gh.cmd"),
            "@echo off\r\nif \"%4\"==\"user\" echo developer\r\nexit /b 0\r\n",
            TestContext.Current.CancellationToken);
        string? originalPath = Environment.GetEnvironmentVariable("PATH");
        Environment.SetEnvironmentVariable("PATH", tools + Path.PathSeparator + originalPath);
        try
        {
            CloudProfile profile = new()
            {
                Name = "github-only",
                Connections = new CloudConnections
                {
                    GitHub = new GitHubConnection
                    {
                        Host = "github.com",
                        User = "developer",
                        Organisations = ["customer-org"]
                    }
                }
            };

            IReadOnlyList<ConnectionStatus> statuses = await new CliOrchestrator(new ProfileStore(_root))
                .ValidateAllAsync(profile, TestContext.Current.CancellationToken);

            ConnectionStatus status = Assert.Single(statuses);
            Assert.Equal("customer-org", status.Target);
            Assert.Equal(ConnectionState.Connected, status.State);
            Assert.Contains("Signed in as developer", status.Detail, StringComparison.Ordinal);
            Assert.Contains("Organisation access verified", status.Detail, StringComparison.Ordinal);
        }
        finally
        {
            Environment.SetEnvironmentVariable("PATH", originalPath);
        }
    }

    [Theory]
    [InlineData("")]
    [InlineData("bad profile")]
    [InlineData("-leading")]
    public void ValidateRejectsUnsafeProfileNames(string name)
    {
        CloudProfile profile = Profile();
        profile.Name = name;

        Assert.Throws<InvalidDataException>(() => ProfileStore.ValidateProfile(profile));
    }

    [Fact]
    public void ConnectionsCanBeAddedAndRemovedIndividually()
    {
        CloudProfile profile = Profile();

        bool added = ProfileConnections.Add(
            profile,
            new ConnectionInput(ConnectionKind.Dataverse, "https://second.crm.dynamics.com"));
        bool removed = ProfileConnections.Remove(
            profile,
            ConnectionKind.Dataverse,
            "https://customer.crm.dynamics.com");

        Assert.True(added);
        Assert.True(removed);
        Assert.Equal(["https://second.crm.dynamics.com"], profile.Connections.Dataverse!.Environments);
    }

    [Fact]
    public void RemovingLastTargetRemovesConnectorButRetainsIdentity()
    {
        CloudProfile profile = Profile();

        bool removed = ProfileConnections.Remove(profile, ConnectionKind.GitHub, "customer");

        Assert.True(removed);
        Assert.Null(profile.Connections.GitHub);
        Assert.Equal("liam@example.com", profile.Identity.Username);
        Assert.Equal("tenant-id", profile.Identity.TenantId);
    }

    [Fact]
    public void DuplicateConnectionIsNotAdded()
    {
        CloudProfile profile = Profile();

        bool added = ProfileConnections.Add(
            profile,
            new ConnectionInput(ConnectionKind.AzureDevOps, "HTTPS://DEV.AZURE.COM/CUSTOMER"));

        Assert.False(added);
        Assert.Single(profile.Connections.AzureDevOps!.Organisations);
    }

    [Fact]
    public void DuplicateGitHubConnectionDoesNotAlterExistingIdentityMetadata()
    {
        CloudProfile profile = Profile();

        bool added = ProfileConnections.Add(
            profile,
            new ConnectionInput(ConnectionKind.GitHub, "CUSTOMER", "github.example.com", "someone-else"));

        Assert.False(added);
        Assert.Equal("github.com", profile.Connections.GitHub!.Host);
        Assert.Equal("liam", profile.Connections.GitHub.User);
    }

    [Fact]
    public void ConnectionCanBeEditedWithoutRemovingItFirst()
    {
        CloudProfile profile = Profile();

        ProfileConnections.Update(
            profile,
            ConnectionKind.Dataverse,
            "https://customer.crm.dynamics.com",
            new ConnectionInput(ConnectionKind.Dataverse, "https://replacement.crm.dynamics.com"));

        Assert.Equal(["https://replacement.crm.dynamics.com"], profile.Connections.Dataverse!.Environments);
    }

    [Fact]
    public void FailedConnectionEditRestoresOriginalConfiguration()
    {
        CloudProfile profile = Profile();
        profile.Connections.Dataverse!.Environments.Add("https://existing.crm.dynamics.com");

        Assert.Throws<InvalidDataException>(() => ProfileConnections.Update(
            profile,
            ConnectionKind.Dataverse,
            "https://customer.crm.dynamics.com",
            new ConnectionInput(ConnectionKind.Dataverse, "https://existing.crm.dynamics.com")));

        Assert.Equal(
            ["https://customer.crm.dynamics.com", "https://existing.crm.dynamics.com"],
            profile.Connections.Dataverse.Environments);
    }

    [Fact]
    public void EditingGitHubConnectionCanClearExpectedUser()
    {
        CloudProfile profile = Profile();

        ProfileConnections.Update(
            profile,
            ConnectionKind.GitHub,
            "customer",
            new ConnectionInput(ConnectionKind.GitHub, "customer", "github.example.com"));

        Assert.Equal("github.example.com", profile.Connections.GitHub!.Host);
        Assert.Equal(string.Empty, profile.Connections.GitHub.User);
    }

    [Fact]
    public void EditingConnectionCannotChangeItsTypeOrLoseTheOriginal()
    {
        CloudProfile profile = Profile();

        Assert.Throws<InvalidDataException>(() => ProfileConnections.Update(
            profile,
            ConnectionKind.Azure,
            "subscription-id",
            new ConnectionInput(ConnectionKind.Dataverse, "https://replacement.crm.dynamics.com")));

        Assert.Equal(["subscription-id"], profile.Connections.Azure!.SubscriptionIds);
        Assert.Equal(["https://customer.crm.dynamics.com"], profile.Connections.Dataverse!.Environments);
    }

    [Fact]
    public void LegacyHostOnlyGitHubConnectionCanBeEdited()
    {
        CloudProfile profile = Profile();
        profile.Connections.GitHub = new GitHubConnection
        {
            Host = "github.old.example",
            User = "old-user"
        };

        ProfileConnections.Update(
            profile,
            ConnectionKind.GitHub,
            "github.old.example",
            new ConnectionInput(ConnectionKind.GitHub, "github.new.example", "github.old.example", "new-user"));

        Assert.Equal("github.new.example", profile.Connections.GitHub!.Host);
        Assert.Equal("new-user", profile.Connections.GitHub.User);
        Assert.Empty(profile.Connections.GitHub.Organisations);
    }

    [Theory]
    [InlineData("Customers/Highways/Production", "Customers/Highways/Production")]
    [InlineData(" Customers\\Highways ", "Customers/Highways")]
    [InlineData("", "")]
    public void FolderPathsAreNormalised(string value, string expected)
    {
        Assert.Equal(expected, ProfileStore.NormalizeFolder(value));
    }

    [Theory]
    [InlineData("Customers//Production")]
    [InlineData("Customers/../Production")]
    public void UnsafeFolderPathsAreRejected(string value)
    {
        Assert.Throws<InvalidDataException>(() => ProfileStore.NormalizeFolder(value));
    }

    [Fact]
    public void MicrosoftConnectionRequiresTenantBeforeMutation()
    {
        CloudProfile profile = new() { Name = "no-tenant" };

        Assert.Throws<InvalidDataException>(() => ProfileConnections.Add(
            profile,
            new ConnectionInput(ConnectionKind.Azure, "subscription-id")));
        Assert.Null(profile.Connections.Azure);
    }

    [Fact]
    public void ActiveProfileUsesExistingPowerShellRestoreContract()
    {
        ProfileStore store = new(_root);
        store.Save(new CloudProfileStore { Profiles = [Profile()] });

        store.SetActiveProfile("CUSTOMER-PROD");

        Assert.Equal("customer-prod", store.GetActiveProfileName());
        Assert.Equal("customer-prod", File.ReadAllText(store.ActiveProfilePath).Trim());
        store.ClearActiveProfile();
        Assert.Null(store.GetActiveProfileName());
    }

    [Fact]
    public void UnknownProfileCannotBecomeActive()
    {
        ProfileStore store = new(_root);
        store.Save(new CloudProfileStore { Profiles = [Profile()] });

        Assert.Throws<InvalidDataException>(() => store.SetActiveProfile("missing"));
        Assert.Null(store.GetActiveProfileName());
    }

    [Fact]
    public void RenamingActiveProfilePreservesActiveSelection()
    {
        ProfileStore store = new(_root);
        CloudProfile profile = Profile();
        store.Save(new CloudProfileStore { Profiles = [profile] });
        store.SetActiveProfile(profile.Name);
        string originalName = profile.Name;
        profile.Name = "customer-renamed";
        store.Save(new CloudProfileStore { Profiles = [profile] });

        store.UpdateActiveProfileName(originalName, profile.Name);

        Assert.Equal("customer-renamed", store.GetActiveProfileName());
    }

    public void Dispose()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, true);
        }
    }

    private static CloudProfile Profile() => new()
    {
        Name = "customer-prod",
        DisplayName = "Customer Production",
        Identity = new CloudIdentity { Username = "liam@example.com", TenantId = "tenant-id" },
        Connections = new CloudConnections
        {
            Azure = new AzureConnection { SubscriptionIds = ["subscription-id"] },
            GitHub = new GitHubConnection { Host = "github.com", User = "liam", Organisations = ["customer"] },
            AzureDevOps = new AzureDevOpsConnection { Organisations = ["https://dev.azure.com/customer"] },
            Dataverse = new DataverseConnection { Environments = ["https://customer.crm.dynamics.com"] },
            LogAnalytics = new LogAnalyticsConnection { Workspaces = ["workspace-id"] }
        }
    };

    private static CloudProfile AzureOnlyProfile() => new()
    {
        Name = "azure-only",
        Identity = new CloudIdentity { Username = "expected@example.com", TenantId = "tenant-id" },
        Connections = new CloudConnections
        {
            Azure = new AzureConnection { SubscriptionIds = ["subscription-id"] }
        }
    };
}
