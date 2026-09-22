using System.Diagnostics;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace CloudContext;

internal sealed record Profile(string Name, string Tenant, string Subscription, string Dataverse)
{
    public static Profile From(JsonObject item) => new(
        (string?)item["name"] ?? "", (string?)item["azureTenantId"] ?? "",
        (string?)item["azureSubscriptionId"] ?? "", (string?)item["dataverseUrl"] ?? "");

    public void Validate()
    {
        if (!Regex.IsMatch(Name, @"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\z") || Name.EndsWith('.'))
            throw new InvalidOperationException("Use a profile name of 1–64 letters, numbers, dots, underscores or hyphens, starting with a letter or number and not ending with a dot.");
        if (!Guid.TryParse(Tenant, out _))
            throw new InvalidOperationException("Enter the directory (tenant) ID as a GUID.");
        if (Subscription.Length > 0 && !Guid.TryParse(Subscription, out _))
            throw new InvalidOperationException("Enter the subscription ID as a GUID, or leave it blank for tenant-only access.");
        if (Dataverse.Length > 0 && (!Uri.TryCreate(Dataverse, UriKind.Absolute, out var uri)
            || uri.Scheme != "https" || uri.UserInfo.Length > 0 || uri.Query.Length > 0
            || uri.Fragment.Length > 0 || uri.AbsolutePath != "/" || !uri.IsDefaultPort
            || !Regex.IsMatch(uri.Host, @"\A[a-zA-Z0-9.-]+\z")))
            throw new InvalidOperationException("Enter the Dataverse HTTPS environment URL without an API path, query or credentials.");
    }
}

internal sealed class ContextStore(string root)
{
    public string Root { get; } = Path.GetFullPath(root);
    public static string DefaultRoot => Environment.GetEnvironmentVariable("CLOUD_CONTEXT_HOME")
        ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".config", "cloud-context");
    private string StorePath => Path.Combine(Root, "profiles.json");

    private JsonObject Read()
    {
        if (!File.Exists(StorePath)) return new JsonObject { ["profiles"] = new JsonArray() };
        var store = JsonNode.Parse(File.ReadAllText(StorePath)) as JsonObject;
        if (store?["profiles"] is not JsonArray)
            throw new InvalidOperationException("profiles.json must contain a profiles array.");
        return store;
    }

    public List<Profile> Profiles() => ((JsonArray)Read()["profiles"]!).Select(item =>
        Profile.From(item as JsonObject ?? throw new InvalidOperationException("Invalid profile entry.")))
        .OrderBy(item => item.Name).ToList();

    public void Save(Profile profile, bool replace)
    {
        profile.Validate();
        Directory.CreateDirectory(Root);
        using var storeLock = new FileStream(Path.Combine(Root, "profiles.lock"), FileMode.OpenOrCreate,
            FileAccess.ReadWrite, FileShare.None);
        var store = Read();
        var profiles = (JsonArray)store["profiles"]!;
        var item = profiles.OfType<JsonObject>().FirstOrDefault(item =>
            string.Equals((string?)item["name"], profile.Name, StringComparison.OrdinalIgnoreCase));
        if (item != null && !replace) throw new InvalidOperationException("That profile name already exists. Select it to edit it.");
        if (item == null)
        {
            item = new JsonObject { ["githubHost"] = "github.com", ["githubOrg"] = "", ["githubUser"] = "" };
            profiles.Add(item);
        }
        item["name"] = profile.Name;
        item["azureTenantId"] = profile.Tenant;
        item["azureSubscriptionId"] = profile.Subscription;
        item["dataverseUrl"] = profile.Dataverse.TrimEnd('/');
        var temporary = StorePath + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temporary, store.ToJsonString(new() { WriteIndented = true }));
            File.Move(temporary, StorePath, true);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    public Dictionary<string, string> EnvironmentFor(Profile profile)
    {
        profile.Validate();
        var cache = Path.Combine(Root, "cli", "azure", profile.Name);
        Directory.CreateDirectory(cache);
        return new()
        {
            ["CLOUD_CONTEXT_HOME"] = Root, ["CLOUD_PROFILE"] = profile.Name,
            ["AZURE_CONFIG_DIR"] = cache, ["AZURE_TENANT_ID"] = profile.Tenant,
            ["AZURE_SUBSCRIPTION_ID"] = profile.Subscription, ["ARM_TENANT_ID"] = profile.Tenant,
            ["ARM_SUBSCRIPTION_ID"] = profile.Subscription, ["DATAVERSE_URL"] = profile.Dataverse,
            ["AZURE_CORE_LOGIN_EXPERIENCE_V2"] = "off"
        };
    }
}

internal sealed class AzureCli(ContextStore store)
{
    public async Task<DateTimeOffset> Expiry(Profile profile, CancellationToken token)
    {
        var value = await Run(profile, ["account", "get-access-token", "--tenant", profile.Tenant,
            "--resource", profile.Dataverse.Length > 0 ? profile.Dataverse : "https://management.azure.com/",
            "--query", "expires_on", "--output", "tsv"], null, token);
        if (!long.TryParse(value.Trim(), out var seconds))
            throw new InvalidOperationException("Azure CLI did not return an expiry time. Update Azure CLI to version 2.54 or later.");
        return DateTimeOffset.FromUnixTimeSeconds(seconds);
    }

    public static string Resolve(string name)
    {
        foreach (var directory in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator))
            foreach (var extension in new[] { ".exe", ".cmd", ".bat" })
            {
                var path = Path.Combine(directory.Trim('"'), name + extension);
                if (File.Exists(path)) return Path.GetFullPath(path);
            }
        throw new InvalidOperationException($"{name} was not found on PATH. Install the CLI, then reopen Cloud Context.");
    }

    public static ProcessStartInfo StartInfo(string executable, IEnumerable<string> arguments)
    {
        var info = new ProcessStartInfo(executable)
        {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true
        };
        if (Path.GetExtension(executable).Equals(".cmd", StringComparison.OrdinalIgnoreCase)
            || Path.GetExtension(executable).Equals(".bat", StringComparison.OrdinalIgnoreCase))
        {
            var parts = new[] { executable }.Concat(arguments).ToArray();
            if (parts.Any(part => part.IndexOfAny(['"', '%', '!', '\r', '\n', '&', '|', '<', '>', '^']) >= 0))
                throw new InvalidOperationException("Unsupported shell character in CLI path or argument.");
            info.FileName = Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe";
            info.Arguments = "/d /s /c \"" + string.Join(" ", parts.Select(part => "\"" + part + "\"")) + "\"";
        }
        else foreach (var argument in arguments) info.ArgumentList.Add(argument);
        return info;
    }

    public async Task<string> Run(Profile profile, string[] arguments, Action<string>? output, CancellationToken token)
    {
        var info = StartInfo(Resolve("az"), arguments);
        foreach (var pair in store.EnvironmentFor(profile)) info.Environment[pair.Key] = pair.Value;
        using var process = new Process { StartInfo = info };
        process.Start();
        process.StandardInput.Close();
        using var cancellation = token.Register(() =>
        {
            try { if (!process.HasExited) process.Kill(true); }
            catch (InvalidOperationException) { }
        });
        var stdout = new System.Text.StringBuilder();
        var stderr = new System.Text.StringBuilder();
        async Task Read(StreamReader reader, System.Text.StringBuilder buffer)
        {
            while (await reader.ReadLineAsync(token) is { } line)
            {
                buffer.AppendLine(line);
                output?.Invoke(line);
            }
        }
        await Task.WhenAll(Read(process.StandardOutput, stdout), Read(process.StandardError, stderr), process.WaitForExitAsync(token));
        token.ThrowIfCancellationRequested();
        if (process.ExitCode != 0) throw new InvalidOperationException(stderr.Length > 0 ? stderr.ToString() : "Azure CLI failed. " + stdout);
        return stdout.ToString();
    }

    public async Task Check(Profile profile, CancellationToken token)
    {
        var account = JsonNode.Parse(await Run(profile, ["account", "show", "--output", "json"], null, token))!;
        if (!string.Equals((string?)account["tenantId"], profile.Tenant, StringComparison.OrdinalIgnoreCase)
            || (profile.Subscription.Length > 0 && !string.Equals((string?)account["id"], profile.Subscription, StringComparison.OrdinalIgnoreCase)))
            throw new InvalidOperationException("The cached tenant or subscription does not match this profile. Sign in again.");
        await Run(profile, ["account", "get-access-token", "--tenant", profile.Tenant,
            "--resource", profile.Dataverse.Length > 0 ? profile.Dataverse : "https://management.azure.com/",
            "--output", "none"], null, token);
        if (profile.Dataverse.Length > 0)
            await Run(profile, ["rest", "--method", "get", "--url", profile.Dataverse + "/api/data/v9.2/WhoAmI",
                "--resource", profile.Dataverse, "--output", "none"], null, token);
    }

    public async Task Connect(Profile profile, bool force, bool deviceCode, Action<string> output, CancellationToken token)
    {
        if (!force)
        {
            try { await Check(profile, token); output("Cached session is ready; no sign-in needed."); return; }
            catch (InvalidOperationException) { output("Sign-in is required. Complete the Microsoft sign-in prompt."); }
        }
        var args = new List<string> { "login", "--tenant", profile.Tenant, "--allow-no-subscriptions", "--output", "none" };
        if (profile.Dataverse.Length > 0) args.AddRange(["--scope", profile.Dataverse + "/.default"]);
        if (deviceCode) args.Add("--use-device-code");
        await Run(profile, args.ToArray(), output, token);
        if (profile.Subscription.Length > 0)
            await Run(profile, ["account", "set", "--subscription", profile.Subscription], output, token);
        await Check(profile, token);
        output("Access verified. This profile is ready for CLI queries.");
    }
}
