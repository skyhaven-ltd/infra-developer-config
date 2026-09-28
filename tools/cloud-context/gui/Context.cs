using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace CloudContext;

internal sealed record Profile(string Name, string Tenant, string Subscription, string Dataverse)
{
    public static Profile From(JsonObject item) => new(
        (string?)item["name"] ?? "", (string?)item["azureTenantId"] ?? "",
        (string?)item["azureSubscriptionId"] ?? "", (string?)item["dataverseUrl"] ?? "");

    public static void ValidateName(string name)
    {
        if (!Regex.IsMatch(name, @"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\z") || name.EndsWith('.'))
            throw new InvalidOperationException("Use a profile name of 1 to 64 letters, numbers, dots, underscores or hyphens. Start with a letter or number and don't end with a dot.");
    }

    public void Validate()
    {
        ValidateName(Name);
        if (!Guid.TryParse(Tenant, out _))
            throw new InvalidOperationException("Enter the tenant ID as a GUID.");
        if (Subscription.Length > 0 && !Guid.TryParse(Subscription, out _))
            throw new InvalidOperationException("Enter the subscription ID as a GUID, or leave it blank for tenant-only access.");
        if (Dataverse.Length > 0 && (!Uri.TryCreate(Dataverse, UriKind.Absolute, out var uri)
            || uri.Scheme != "https" || uri.UserInfo.Length > 0 || uri.Query.Length > 0
            || uri.Fragment.Length > 0 || uri.AbsolutePath != "/" || !uri.IsDefaultPort
            || !Regex.IsMatch(uri.Host, @"\A[a-zA-Z0-9.-]+\z")))
            throw new InvalidOperationException("Enter the Dataverse environment URL as https://your-org.crm.dynamics.com, without an API path, query or credentials.");
    }
}

internal sealed record ProfileStatus(string State, long? ExpiresOn, long CheckedAt, string Message)
{
    public const string Ready = "ready", SignInNeeded = "signin", SignedOut = "signedout";

    public static ProfileStatus Now(string state, DateTimeOffset? expiresOn = null, string message = "") =>
        new(state, expiresOn?.ToUnixTimeSeconds(), DateTimeOffset.UtcNow.ToUnixTimeSeconds(), message);
}

internal sealed class ContextStore(string root)
{
    public string Root { get; } = Path.GetFullPath(root);
    public static string DefaultRoot => Environment.GetEnvironmentVariable("CLOUD_CONTEXT_HOME")
        ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".config", "cloud-context");
    private string StorePath => Path.Combine(Root, "profiles.json");
    private string StatusPath => Path.Combine(Root, "status.json");
    private string SettingsPath => Path.Combine(Root, "gui.json");
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web) { WriteIndented = true };

    private JsonObject Read()
    {
        if (!File.Exists(StorePath)) return new JsonObject { ["profiles"] = new JsonArray() };
        var store = JsonNode.Parse(File.ReadAllText(StorePath)) as JsonObject;
        if (store?["profiles"] is not JsonArray)
            throw new InvalidOperationException("profiles.json must contain a profiles array.");
        return store;
    }

    public List<Profile> Profiles() => ((JsonArray)Read()["profiles"]!).Select(item =>
        Profile.From(item as JsonObject ?? throw new InvalidOperationException("profiles.json has an entry that isn't a profile.")))
        .OrderBy(item => item.Name).ToList();

    public void Save(Profile profile, bool replace)
    {
        profile.Validate();
        Directory.CreateDirectory(Root);
        using var storeLock = Lock();
        var store = Read();
        var profiles = (JsonArray)store["profiles"]!;
        var item = Find(profiles, profile.Name);
        if (item != null && !replace) throw new InvalidOperationException("A profile with that name already exists. Select it in the list to edit it.");
        if (item == null)
        {
            item = new JsonObject { ["githubHost"] = "github.com", ["githubOrg"] = "", ["githubUser"] = "" };
            profiles.Add(item);
        }
        item["name"] = profile.Name;
        item["azureTenantId"] = profile.Tenant;
        item["azureSubscriptionId"] = profile.Subscription;
        item["dataverseUrl"] = profile.Dataverse.TrimEnd('/');
        Write(StorePath, store.ToJsonString(new() { WriteIndented = true }));
    }

    public void Remove(string name)
    {
        Profile.ValidateName(name);
        using (Lock())
        {
            var store = Read();
            var profiles = (JsonArray)store["profiles"]!;
            var item = Find(profiles, name) ?? throw new InvalidOperationException($"The profile {name} no longer exists.");
            profiles.Remove(item);
            Write(StorePath, store.ToJsonString(new() { WriteIndented = true }));
        }
        foreach (var tool in new[] { "azure", "github" })
        {
            var cache = Path.Combine(Root, "cli", tool, name);
            if (Directory.Exists(cache)) Directory.Delete(cache, true);
        }
        SaveStatus(name, null);
    }

    public Dictionary<string, ProfileStatus> Statuses()
    {
        try
        {
            var statuses = JsonSerializer.Deserialize<Dictionary<string, ProfileStatus>>(File.ReadAllText(StatusPath), JsonOptions);
            return new(statuses ?? new(), StringComparer.OrdinalIgnoreCase);
        }
        catch (Exception error) when (error is IOException or JsonException) { return new(StringComparer.OrdinalIgnoreCase); }
    }

    public void SaveStatus(string name, ProfileStatus? status)
    {
        var statuses = Statuses();
        if (status == null) statuses.Remove(name);
        else statuses[name] = status;
        Directory.CreateDirectory(Root);
        Write(StatusPath, JsonSerializer.Serialize(statuses, JsonOptions));
    }

    public int? SidebarWidth()
    {
        try { return (int?)JsonNode.Parse(File.ReadAllText(SettingsPath))?["sidebarWidth"]; }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or FormatException) { return null; }
    }

    public void SaveSidebarWidth(int width)
    {
        Directory.CreateDirectory(Root);
        Write(SettingsPath, new JsonObject { ["sidebarWidth"] = width }.ToJsonString());
    }

    private FileStream Lock() => new(Path.Combine(Root, "profiles.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);

    private static JsonObject? Find(JsonArray profiles, string name) => profiles.OfType<JsonObject>().FirstOrDefault(item =>
        string.Equals((string?)item["name"], name, StringComparison.OrdinalIgnoreCase));

    private static void Write(string path, string content)
    {
        var temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temporary, content);
            File.Move(temporary, path, true);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    public Dictionary<string, string> EnvironmentFor(Profile profile)
    {
        profile.Validate();
        var cache = Path.Combine(Root, "cli", "azure", profile.Name);
        Directory.CreateDirectory(cache);
        var environment = new Dictionary<string, string>
        {
            ["CLOUD_CONTEXT_HOME"] = Root, ["CLOUD_PROFILE"] = profile.Name,
            ["AZURE_CONFIG_DIR"] = cache, ["AZURE_TENANT_ID"] = profile.Tenant,
            ["AZURE_SUBSCRIPTION_ID"] = profile.Subscription, ["ARM_TENANT_ID"] = profile.Tenant,
            ["ARM_SUBSCRIPTION_ID"] = profile.Subscription, ["DATAVERSE_URL"] = profile.Dataverse,
            ["AZURE_CORE_LOGIN_EXPERIENCE_V2"] = "off", ["AZURE_CORE_ENABLE_BROKER_ON_WINDOWS"] = "false"
        };
        if (Browser.Chrome() is { } chrome) environment["BROWSER"] = $"'{chrome}' {string.Join(" ", Browser.ChromeArguments)} %s";
        return environment;
    }
}

internal static class Browser
{
    public static readonly string[] ChromeArguments = ["--incognito", "--new-window"];

    public static string? Chrome()
    {
        foreach (var hive in new[] { Registry.CurrentUser, Registry.LocalMachine })
        {
            using var key = hive.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe");
            if (key?.GetValue(null) is string path && File.Exists(path.Trim('"'))) return path.Trim('"');
        }
        foreach (var folder in new[] { Environment.SpecialFolder.ProgramFiles, Environment.SpecialFolder.ProgramFilesX86, Environment.SpecialFolder.LocalApplicationData })
        {
            var path = Path.Combine(Environment.GetFolderPath(folder), "Google", "Chrome", "Application", "chrome.exe");
            if (File.Exists(path)) return path;
        }
        return null;
    }

    public static void Open(string url)
    {
        var chrome = Chrome();
        var info = chrome == null ? new ProcessStartInfo(url) { UseShellExecute = true } : new ProcessStartInfo(chrome) { UseShellExecute = false };
        if (chrome != null) foreach (var argument in ChromeArguments.Append(url)) info.ArgumentList.Add(argument);
        Process.Start(info)?.Dispose();
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
            throw new InvalidOperationException("Azure CLI didn't return a token expiry time. Update Azure CLI to version 2.54 or later.");
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
        throw new InvalidOperationException($"Can't find {name} on PATH. Install it, then reopen Cloud Context.");
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
                throw new InvalidOperationException("The CLI path or an argument contains a character the Windows shell can't pass safely.");
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
            throw new InvalidOperationException("The saved sign-in is for a different tenant or subscription. Sign in again.");
        await Run(profile, ["account", "get-access-token", "--tenant", profile.Tenant,
            "--resource", profile.Dataverse.Length > 0 ? profile.Dataverse : "https://management.azure.com/",
            "--output", "none"], null, token);
        if (profile.Dataverse.Length > 0)
            await Run(profile, ["rest", "--method", "get", "--url", profile.Dataverse + "/api/data/v9.2/WhoAmI",
                "--resource", profile.Dataverse, "--output", "none"], null, token);
    }

    public async Task<ProfileStatus> Status(Profile profile, CancellationToken token)
    {
        try
        {
            await Check(profile, token);
            return ProfileStatus.Now(ProfileStatus.Ready, await Expiry(profile, token));
        }
        catch (Exception error) when (error is InvalidOperationException or JsonException)
        {
            token.ThrowIfCancellationRequested();
            return ProfileStatus.Now(ProfileStatus.SignInNeeded, message: error.Message.Trim());
        }
    }

    public Task SignOut(Profile profile, CancellationToken token) => Run(profile, ["account", "clear"], null, token);

    public static (string Url, string Code)? DeviceCode(string line)
    {
        var match = Regex.Match(line, @"(https://\S+)\s+and enter the code\s+([A-Za-z0-9-]+)");
        return match.Success ? (match.Groups[1].Value, match.Groups[2].Value) : null;
    }

    public async Task Connect(Profile profile, bool force, bool deviceCode, Action<string> output, CancellationToken token,
        Action<string, string>? deviceCodeReady = null)
    {
        if (!force)
        {
            try { await Check(profile, token); output("Already signed in. The saved sign-in still works."); return; }
            catch (InvalidOperationException) { output("You need to sign in. Use the Chrome window that just opened."); }
        }
        var args = new List<string> { "login", "--tenant", profile.Tenant, "--allow-no-subscriptions", "--output", "none" };
        if (profile.Dataverse.Length > 0) args.AddRange(["--scope", profile.Dataverse + "/.default"]);
        if (deviceCode) args.Add("--use-device-code");
        await Run(profile, args.ToArray(), line =>
        {
            output(line);
            if (DeviceCode(line) is var (url, code)) deviceCodeReady?.Invoke(url, code);
        }, token);
        if (profile.Subscription.Length > 0)
            await Run(profile, ["account", "set", "--subscription", profile.Subscription], output, token);
        await Check(profile, token);
        output("Signed in. CLI commands can use this profile now.");
    }
}
