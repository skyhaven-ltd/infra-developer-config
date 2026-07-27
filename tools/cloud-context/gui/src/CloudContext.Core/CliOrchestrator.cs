using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace CloudContext.Core;

public sealed class CliOrchestrator(ProfileStore store)
{
    private readonly ProfileStore _store = store;

    public IReadOnlyDictionary<string, string> BuildEnvironment(CloudProfile profile)
    {
        Dictionary<string, string> environment = new(StringComparer.OrdinalIgnoreCase)
        {
            ["CLOUD_PROFILE"] = profile.Name,
            ["AZURE_CONFIG_DIR"] = Path.Combine(_store.Root, "cli", "azure", profile.Name),
            ["GH_CONFIG_DIR"] = Path.Combine(_store.Root, "cli", "github", profile.Name)
        };

        if (!string.IsNullOrWhiteSpace(profile.Identity.TenantId))
        {
            environment["AZURE_TENANT_ID"] = profile.Identity.TenantId;
            environment["ARM_TENANT_ID"] = profile.Identity.TenantId;
        }

        string? subscription = profile.Connections.Azure?.SubscriptionIds.FirstOrDefault();
        if (!string.IsNullOrWhiteSpace(subscription))
        {
            environment["AZURE_SUBSCRIPTION_ID"] = subscription;
            environment["ARM_SUBSCRIPTION_ID"] = subscription;
        }

        GitHubConnection? github = profile.Connections.GitHub;
        if (github is not null)
        {
            environment["GH_HOST"] = github.Host;
            string? organisation = github.Organisations.FirstOrDefault();
            if (!string.IsNullOrWhiteSpace(organisation))
            {
                environment["GH_ORG"] = organisation;
            }
        }

        foreach (string directory in environment
                     .Where(pair => pair.Key.EndsWith("_DIR", StringComparison.OrdinalIgnoreCase))
                     .Select(pair => pair.Value))
        {
            Directory.CreateDirectory(directory);
        }

        return environment;
    }

    public async Task<CommandResult> ConnectAzureAsync(CloudProfile profile, CancellationToken cancellationToken = default)
    {
        CommandResult login = await RunInteractiveAsync(
            "az", ["login", "--tenant", profile.Identity.TenantId], profile, cancellationToken);
        if (!login.Succeeded)
        {
            return login;
        }

        string? subscription = profile.Connections.Azure?.SubscriptionIds.FirstOrDefault();
        return string.IsNullOrWhiteSpace(subscription)
            ? login
            : await RunCapturedAsync("az", ["account", "set", "--subscription", subscription], profile, cancellationToken);
    }

    public Task<CommandResult> ConnectGitHubAsync(CloudProfile profile, CancellationToken cancellationToken = default)
    {
        GitHubConnection github = profile.Connections.GitHub
            ?? throw new InvalidOperationException("GitHub is not configured for this profile.");
        return RunInteractiveAsync("gh", ["auth", "login", "--hostname", github.Host], profile, cancellationToken);
    }

    public Task<CommandResult> ConnectDataverseAsync(
        CloudProfile profile,
        string environment,
        CancellationToken cancellationToken = default) =>
        RunInteractiveAsync(
            "pac",
            ["auth", "create", "--name", DataverseProfileName(profile, environment), "--environment", environment, "--tenant", profile.Identity.TenantId],
            profile,
            cancellationToken);

    public async Task<IReadOnlyList<ConnectionStatus>> ValidateAllAsync(
        CloudProfile profile,
        CancellationToken cancellationToken = default)
    {
        List<ConnectionStatus> statuses = [];
        if (profile.Connections.Azure is not null)
        {
            foreach (string subscription in profile.Connections.Azure.SubscriptionIds)
            {
                statuses.Add(await ValidateAzureAsync(profile, subscription, cancellationToken));
            }
        }

        if (profile.Connections.GitHub is not null)
        {
            statuses.Add(await ValidateGitHubAsync(profile, cancellationToken));
            foreach (string organisation in profile.Connections.GitHub.Organisations)
            {
                statuses.Add(await ValidateGitHubOrganisationAsync(profile, organisation, cancellationToken));
            }
        }

        foreach (string organisation in profile.Connections.AzureDevOps?.Organisations ?? [])
        {
            statuses.Add(await ValidateAzureDevOpsAsync(profile, organisation, cancellationToken));
        }

        foreach (string environment in profile.Connections.Dataverse?.Environments ?? [])
        {
            statuses.Add(await ValidateDataverseAsync(profile, environment, cancellationToken));
        }

        foreach (string workspace in profile.Connections.LogAnalytics?.Workspaces ?? [])
        {
            statuses.Add(await ValidateLogAnalyticsAsync(profile, workspace, cancellationToken));
        }

        return statuses;
    }

    public Process OpenPowerShell(CloudProfile profile)
    {
        ProcessStartInfo startInfo = CreateStartInfo("powershell.exe", [], profile, capture: false);
        startInfo.UseShellExecute = false;
        return Process.Start(startInfo) ?? throw new InvalidOperationException("PowerShell did not start.");
    }

    public bool IsAvailable(string executable) => ResolveExecutable(executable) is not null;

    private async Task<ConnectionStatus> ValidateAzureAsync(
        CloudProfile profile,
        string subscription,
        CancellationToken cancellationToken)
    {
        if (!IsAvailable("az"))
        {
            return Status(ConnectionKind.Azure, "Azure CLI", ConnectionState.Unavailable, "Azure CLI was not found.");
        }

        CommandResult result = await RunCapturedAsync(
            "az", ["account", "show", "--subscription", subscription, "--output", "json"], profile, cancellationToken);
        if (!result.Succeeded)
        {
            return Status(ConnectionKind.Azure, "Azure CLI", ConnectionState.NeedsSignIn, SafeError(result));
        }

        try
        {
            using JsonDocument account = JsonDocument.Parse(result.StandardOutput);
            string tenant = account.RootElement.GetProperty("tenantId").GetString() ?? string.Empty;
            string returnedSubscription = account.RootElement.GetProperty("id").GetString() ?? string.Empty;
            bool matches = tenant.Equals(profile.Identity.TenantId, StringComparison.OrdinalIgnoreCase) &&
                           returnedSubscription.Equals(subscription, StringComparison.OrdinalIgnoreCase);
            return matches
                ? Status(ConnectionKind.Azure, subscription, ConnectionState.Connected, "Tenant and subscription match.")
                : Status(ConnectionKind.Azure, subscription, ConnectionState.Misconfigured, "The returned tenant or subscription does not match this profile.");
        }
        catch (JsonException)
        {
            return Status(ConnectionKind.Azure, "Azure CLI", ConnectionState.Misconfigured, "Azure CLI returned an invalid account response.");
        }
    }

    private async Task<ConnectionStatus> ValidateGitHubAsync(CloudProfile profile, CancellationToken cancellationToken)
    {
        GitHubConnection github = profile.Connections.GitHub!;
        if (!IsAvailable("gh"))
        {
            return Status(ConnectionKind.GitHub, github.Host, ConnectionState.Unavailable, "GitHub CLI was not found.");
        }

        CommandResult result = await RunCapturedAsync(
            "gh", ["api", "--hostname", github.Host, "user", "--jq", ".login"], profile, cancellationToken);
        string login = result.StandardOutput.Trim();
        if (!result.Succeeded)
        {
            return Status(ConnectionKind.GitHub, github.Host, ConnectionState.NeedsSignIn, SafeError(result));
        }

        return string.IsNullOrWhiteSpace(github.User) || login.Equals(github.User, StringComparison.OrdinalIgnoreCase)
            ? Status(ConnectionKind.GitHub, $"{github.Host} identity", ConnectionState.Connected, $"Signed in as {login}.")
            : Status(ConnectionKind.GitHub, github.Host, ConnectionState.Misconfigured, $"Signed in as {login}; expected {github.User}.");
    }

    private async Task<ConnectionStatus> ValidateGitHubOrganisationAsync(
        CloudProfile profile,
        string organisation,
        CancellationToken cancellationToken)
    {
        GitHubConnection github = profile.Connections.GitHub!;
        if (!IsAvailable("gh"))
        {
            return Status(ConnectionKind.GitHub, organisation, ConnectionState.Unavailable, "GitHub CLI was not found.");
        }

        CommandResult result = await RunCapturedAsync(
            "gh", ["api", "--hostname", github.Host, $"orgs/{organisation}", "--silent"], profile, cancellationToken);
        return FromCommand(ConnectionKind.GitHub, organisation, result);
    }

    private async Task<ConnectionStatus> ValidateAzureDevOpsAsync(
        CloudProfile profile,
        string organisation,
        CancellationToken cancellationToken)
    {
        if (!IsAvailable("az"))
        {
            return Status(ConnectionKind.AzureDevOps, organisation, ConnectionState.Unavailable, "Azure CLI was not found.");
        }

        CommandResult result = await RunCapturedAsync(
            "az", ["devops", "project", "list", "--organization", organisation, "--top", "1", "--output", "none"], profile, cancellationToken);
        return FromCommand(ConnectionKind.AzureDevOps, organisation, result);
    }

    private async Task<ConnectionStatus> ValidateDataverseAsync(
        CloudProfile profile,
        string environment,
        CancellationToken cancellationToken)
    {
        if (!IsAvailable("pac"))
        {
            return Status(ConnectionKind.Dataverse, environment, ConnectionState.Unavailable, "Power Platform CLI was not found.");
        }

        CommandResult selection = await RunCapturedAsync(
            "pac", ["auth", "select", "--name", DataverseProfileName(profile, environment)], profile, cancellationToken);
        if (!selection.Succeeded)
        {
            return Status(ConnectionKind.Dataverse, environment, ConnectionState.NeedsSignIn, SafeError(selection));
        }

        CommandResult result = await RunCapturedAsync("pac", ["auth", "who"], profile, cancellationToken);
        return FromCommand(ConnectionKind.Dataverse, environment, result);
    }

    private async Task<ConnectionStatus> ValidateLogAnalyticsAsync(
        CloudProfile profile,
        string workspace,
        CancellationToken cancellationToken)
    {
        if (!IsAvailable("az"))
        {
            return Status(ConnectionKind.LogAnalytics, workspace, ConnectionState.Unavailable, "Azure CLI was not found.");
        }

        string url = $"https://api.loganalytics.io/v1/workspaces/{Uri.EscapeDataString(workspace)}/query?query=print%20CloudContextProbe%3D1";
        CommandResult result = await RunCapturedAsync(
            "az", ["rest", "--method", "get", "--resource", "https://api.loganalytics.io", "--url", url, "--output", "none"], profile, cancellationToken);
        return FromCommand(ConnectionKind.LogAnalytics, workspace, result);
    }

    private Task<CommandResult> RunCapturedAsync(
        string executable,
        IReadOnlyList<string> arguments,
        CloudProfile profile,
        CancellationToken cancellationToken) =>
        RunAsync(executable, arguments, profile, capture: true, cancellationToken);

    private Task<CommandResult> RunInteractiveAsync(
        string executable,
        IReadOnlyList<string> arguments,
        CloudProfile profile,
        CancellationToken cancellationToken) =>
        RunAsync(executable, arguments, profile, capture: false, cancellationToken);

    private async Task<CommandResult> RunAsync(
        string executable,
        IReadOnlyList<string> arguments,
        CloudProfile profile,
        bool capture,
        CancellationToken cancellationToken)
    {
        ProcessStartInfo startInfo = CreateStartInfo(executable, arguments, profile, capture);
        using Process process = Process.Start(startInfo)
            ?? throw new InvalidOperationException($"Unable to start '{executable}'.");

        if (!capture)
        {
            await process.WaitForExitAsync(cancellationToken);
            return new CommandResult(process.ExitCode, string.Empty, string.Empty);
        }

        Task<string> output = process.StandardOutput.ReadToEndAsync(cancellationToken);
        Task<string> error = process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);
        return new CommandResult(process.ExitCode, await output, await error);
    }

    private ProcessStartInfo CreateStartInfo(
        string executable,
        IReadOnlyList<string> arguments,
        CloudProfile profile,
        bool capture)
    {
        string resolved = ResolveExecutable(executable)
            ?? throw new FileNotFoundException($"Required command was not found: {executable}");
        bool isCommandScript = OperatingSystem.IsWindows() &&
                               (resolved.EndsWith(".cmd", StringComparison.OrdinalIgnoreCase) ||
                                resolved.EndsWith(".bat", StringComparison.OrdinalIgnoreCase));
        ProcessStartInfo startInfo = new(isCommandScript
            ? Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe"
            : resolved)
        {
            UseShellExecute = false,
            RedirectStandardOutput = capture,
            RedirectStandardError = capture,
            CreateNoWindow = capture
        };
        if (isCommandScript)
        {
            startInfo.ArgumentList.Add("/d");
            startInfo.ArgumentList.Add("/s");
            startInfo.ArgumentList.Add("/c");
            startInfo.ArgumentList.Add(resolved);
        }
        foreach (string variable in new[]
                 {
                     "AZURE_TENANT_ID",
                     "AZURE_SUBSCRIPTION_ID",
                     "ARM_TENANT_ID",
                     "ARM_SUBSCRIPTION_ID",
                     "GH_HOST",
                     "GH_ORG"
                 })
        {
            startInfo.Environment.Remove(variable);
        }
        foreach (string argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        foreach ((string key, string value) in BuildEnvironment(profile))
        {
            startInfo.Environment[key] = value;
        }

        return startInfo;
    }

    private static string? ResolveExecutable(string name)
    {
        string[] extensions = OperatingSystem.IsWindows() ? [".exe", ".cmd", ".bat", ""] : [""];
        if (Path.IsPathRooted(name) && File.Exists(name))
        {
            return name;
        }

        foreach (string directory in (Environment.GetEnvironmentVariable("PATH") ?? string.Empty).Split(Path.PathSeparator))
        {
            foreach (string extension in extensions)
            {
                string candidate = Path.Combine(directory.Trim(), name.EndsWith(extension, StringComparison.OrdinalIgnoreCase) ? name : name + extension);
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
        }

        return null;
    }

    private static ConnectionStatus FromCommand(ConnectionKind kind, string target, CommandResult result) =>
        result.Succeeded
            ? Status(kind, target, ConnectionState.Connected, "Access verified.")
            : Status(kind, target, ConnectionState.AccessDenied, SafeError(result));

    private static ConnectionStatus Status(ConnectionKind kind, string target, ConnectionState state, string detail) =>
        new(kind, target, state, detail);

    private static string SafeError(CommandResult result)
    {
        string value = string.IsNullOrWhiteSpace(result.StandardError) ? result.StandardOutput : result.StandardError;
        value = value.ReplaceLineEndings(" ").Trim();
        return value.Length switch
        {
            0 => $"Command failed with exit code {result.ExitCode}.",
            > 300 => value[..300] + "…",
            _ => value
        };
    }

    private static string DataverseProfileName(CloudProfile profile, string environment)
    {
        string prefix = profile.Name.Length > 15 ? profile.Name[..15] : profile.Name;
        string hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(environment)))[..8].ToLowerInvariant();
        return $"cloud-{prefix}-{hash}";
    }
}
