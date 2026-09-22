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
    Reject(() => AzureCli.StartInfo("az.cmd", ["%UNSAFE%"]), "Shell expansion accepted");
    File.WriteAllText(Path.Combine(root, "az.cmd"), """
@echo off
if not "%CLOUD_PROFILE%"=="example" exit /b 9
if "%~1"=="login" exit /b 8
if "%~1"=="rest" (
  goto rest
)
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
    Assert(messages.Any(message => message.Contains("no sign-in needed")), "Cached session not reused");
    Assert(await cli.Expiry(profile, timeout.Token) == DateTimeOffset.FromUnixTimeSeconds(2000000000), "Expiry parsed incorrectly");
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
    Console.WriteLine($"Passed {passed} assertions, including real Windows command-shim execution.");
}
finally
{
    Environment.SetEnvironmentVariable("PATH", originalPath);
    Directory.Delete(root, true);
}
