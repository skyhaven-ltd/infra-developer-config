using CloudContext;
using System.Text.Json.Nodes;

var root = Path.Combine(Path.GetTempPath(), "cloud-context-tests-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
var originalPath = Environment.GetEnvironmentVariable("PATH");
var passed = 0;
void Assert(bool condition, string message)
{
    if (!condition) throw new Exception(message);
    passed++;
}
void Reject(Action action, string message)
{
    try { action(); }
    catch (InvalidOperationException) { passed++; return; }
    throw new Exception(message);
}
try
{
    var store = new ContextStore(root);
    var profile = new Profile("example", "11111111-1111-1111-1111-111111111111", "", "https://example.crm11.dynamics.com");
    Assert(store.Profiles().Count == 0, "Fresh store should be empty");
    Reject(() => (profile with { Name = "../escape" }).Validate(), "Traversal accepted");
    Reject(() => (profile with { Name = "example." }).Validate(), "Trailing dot accepted");
    Reject(() => (profile with { Dataverse = "https://example.com/api/data" }).Validate(), "API path accepted");
    Reject(() => (profile with { Dataverse = "https://user:password@example.com" }).Validate(), "Credentials accepted");
    Reject(() => (profile with { Tenant = "tenant & command" }).Validate(), "Invalid tenant accepted");
    store.Save(profile, false);
    Reject(() => store.Save(profile with { Name = "EXAMPLE" }, false), "Duplicate accepted");
    var json = JsonNode.Parse(File.ReadAllText(Path.Combine(root, "profiles.json")))!;
    json["customMetadata"] = "retained";
    json["profiles"]![0]!["githubOrg"] = "original-org";
    File.WriteAllText(Path.Combine(root, "profiles.json"), json.ToJsonString());
    store.Save(profile with { Subscription = "22222222-2222-2222-2222-222222222222" }, true);
    json = JsonNode.Parse(File.ReadAllText(Path.Combine(root, "profiles.json")))!;
    Assert((string?)json["customMetadata"] == "retained", "Unknown store metadata lost");
    Assert((string?)json["profiles"]![0]!["githubOrg"] == "original-org", "GitHub metadata lost");
    Assert(!File.ReadAllText(Path.Combine(root, "profiles.json")).Contains("accessToken"), "Token persisted");
    var env = store.EnvironmentFor(profile);
    Assert(env["AZURE_CONFIG_DIR"] == Path.Combine(root, "cli", "azure", "example"), "Cache path mismatch");
    Assert(env["DATAVERSE_URL"] == profile.Dataverse, "Dataverse URL missing");
    Assert(env["AZURE_CORE_ENABLE_BROKER_ON_WINDOWS"] == "false", "Windows broker sign-in not disabled");
    Assert(Browser.Chrome() == null || env["BROWSER"].Contains("--incognito --new-window %s"), "Chrome sign-in not configured");
    Assert(AzureCli.DeviceCode("To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code ABC123XYZ to authenticate.")
        == ("https://microsoft.com/devicelogin", "ABC123XYZ"), "Device code not parsed");
    Assert(AzureCli.DeviceCode("Retrieving tenants and subscriptions") == null, "Device code parsed from unrelated output");
    Assert(store.Statuses().Count == 0, "Fresh status cache should be empty");
    store.SaveStatus("example", ProfileStatus.Now(ProfileStatus.Ready, DateTimeOffset.FromUnixTimeSeconds(2000000000)));
    Assert(new ContextStore(root).Statuses()["EXAMPLE"].ExpiresOn == 2000000000, "Status not cached across instances");
    File.WriteAllText(Path.Combine(root, "status.json"), "not json");
    Assert(store.Statuses().Count == 0, "Corrupt status cache should be ignored");
    Assert(store.SidebarWidth() == null, "Sidebar width should default");
    store.SaveSidebarWidth(320);
    Assert(store.SidebarWidth() == 320, "Sidebar width not saved");
    Reject(() => AzureCli.StartInfo("az.cmd", ["%UNSAFE%"]), "Shell expansion accepted");
    File.WriteAllText(Path.Combine(root, "az.cmd"), """
@echo off
if not "%CLOUD_PROFILE%"=="example" exit /b 9
if "%~1"=="login" exit /b 8
if "%~1"=="rest" (
  goto rest
)
if "%~2"=="clear" exit /b 0
if "%~2"=="show" (
  echo {"tenantId":"11111111-1111-1111-1111-111111111111","id":"22222222-2222-2222-2222-222222222222"}
  exit /b 0
)
if "%~2"=="get-access-token" (
  if "%~7"=="--query" echo 2000000000
  exit /b 0
)
exit /b 7
:rest
if not exist "%AZURE_CONFIG_DIR%\deny" exit /b 0
echo Access denied 1>&2
exit /b 3
""".Replace("\n", "\r\n"));
    Environment.SetEnvironmentVariable("PATH", root + Path.PathSeparator + originalPath);
    var cli = new AzureCli(store);
    var messages = new List<string>();
    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
    await cli.Connect(profile, false, false, messages.Add, timeout.Token);
    Assert(messages.Any(message => message.Contains("Already signed in")), "Cached session not reused");
    Assert(await cli.Expiry(profile, timeout.Token) == DateTimeOffset.FromUnixTimeSeconds(2000000000), "Expiry parsed incorrectly");
    var ready = await cli.Status(profile, timeout.Token);
    Assert(ready.State == ProfileStatus.Ready && ready.ExpiresOn == 2000000000, "Status did not report a working sign-in");
    await cli.SignOut(profile, timeout.Token);
    try
    {
        await cli.Check(profile with { Subscription = "33333333-3333-3333-3333-333333333333" }, timeout.Token);
        throw new Exception("Wrong subscription accepted");
    }
    catch (InvalidOperationException) { passed++; }
    File.WriteAllText(Path.Combine(env["AZURE_CONFIG_DIR"], "deny"), "");
    try
    {
        await cli.Check(profile, timeout.Token);
        throw new Exception("Dataverse access denial ignored");
    }
    catch (InvalidOperationException error) { Assert(error.Message.Contains("Access denied"), "Lost CLI error"); }
    var denied = await cli.Status(profile, timeout.Token);
    Assert(denied.State == ProfileStatus.SignInNeeded && denied.Message.Contains("Access denied"), "Status hid the failure");
    store.SaveStatus("example", denied);
    Directory.CreateDirectory(Path.Combine(root, "cli", "github", "example"));
    store.Remove("example");
    Assert(store.Profiles().Count == 0, "Profile not removed");
    Assert(!Directory.Exists(env["AZURE_CONFIG_DIR"]) && !Directory.Exists(Path.Combine(root, "cli", "github", "example")), "Sign-in caches not deleted");
    Assert(!store.Statuses().ContainsKey("example"), "Status not removed");
    Reject(() => store.Remove("example"), "Missing profile removal accepted");
    Reject(() => store.Remove(".."), "Traversal removal accepted");
    Console.WriteLine($"Passed {passed} assertions, including real Windows command-shim execution.");
}
finally
{
    Environment.SetEnvironmentVariable("PATH", originalPath);
    Directory.Delete(root, true);
}
