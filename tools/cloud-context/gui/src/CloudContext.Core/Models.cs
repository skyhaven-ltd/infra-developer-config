using System.Text.Json.Serialization;

namespace CloudContext.Core;

public sealed class CloudProfileStore
{
    [JsonPropertyName("schemaVersion")]
    public int SchemaVersion { get; set; } = 2;

    [JsonPropertyName("profiles")]
    public List<CloudProfile> Profiles { get; set; } = [];
}

public sealed class CloudProfile
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("displayName")]
    public string DisplayName { get; set; } = string.Empty;

    [JsonPropertyName("folder")]
    public string Folder { get; set; } = string.Empty;

    [JsonPropertyName("identity")]
    public CloudIdentity Identity { get; set; } = new();

    [JsonPropertyName("connections")]
    public CloudConnections Connections { get; set; } = new();

    [JsonIgnore]
    public string Label => string.IsNullOrWhiteSpace(DisplayName) ? Name : DisplayName;
}

public sealed class CloudIdentity
{
    [JsonPropertyName("username")]
    public string Username { get; set; } = string.Empty;

    [JsonPropertyName("tenantId")]
    public string TenantId { get; set; } = string.Empty;
}

public sealed class CloudConnections
{
    [JsonPropertyName("azure")]
    public AzureConnection? Azure { get; set; }

    [JsonPropertyName("github")]
    public GitHubConnection? GitHub { get; set; }

    [JsonPropertyName("azureDevOps")]
    public AzureDevOpsConnection? AzureDevOps { get; set; }

    [JsonPropertyName("dataverse")]
    public DataverseConnection? Dataverse { get; set; }

    [JsonPropertyName("logAnalytics")]
    public LogAnalyticsConnection? LogAnalytics { get; set; }
}

public sealed class AzureConnection
{
    [JsonPropertyName("subscriptionIds")]
    public List<string> SubscriptionIds { get; set; } = [];
}

public sealed class GitHubConnection
{
    [JsonPropertyName("host")]
    public string Host { get; set; } = "github.com";

    [JsonPropertyName("user")]
    public string User { get; set; } = string.Empty;

    [JsonPropertyName("organisations")]
    public List<string> Organisations { get; set; } = [];
}

public sealed class AzureDevOpsConnection
{
    [JsonPropertyName("organisations")]
    public List<string> Organisations { get; set; } = [];
}

public sealed class DataverseConnection
{
    [JsonPropertyName("environments")]
    public List<string> Environments { get; set; } = [];
}

public sealed class LogAnalyticsConnection
{
    [JsonPropertyName("workspaces")]
    public List<string> Workspaces { get; set; } = [];
}

public enum ConnectionKind
{
    Azure,
    GitHub,
    AzureDevOps,
    Dataverse,
    LogAnalytics
}

public enum ConnectionState
{
    NotChecked,
    Connected,
    NeedsSignIn,
    Unavailable,
    AccessDenied,
    Misconfigured
}

public sealed record ConnectionStatus(
    ConnectionKind Kind,
    string Target,
    ConnectionState State,
    string Detail,
    bool CanRemove = false);

public sealed record ConnectionInput(
    ConnectionKind Kind,
    string Target,
    string Host = "",
    string User = "");

public sealed record CommandResult(int ExitCode, string StandardOutput, string StandardError)
{
    public bool Succeeded => ExitCode == 0;
}
