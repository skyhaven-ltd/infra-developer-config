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

        string tools = Path.Combine(_root, "tools");
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
}
