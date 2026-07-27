# Cloud Context portable application

Cloud Context is a standard-user Windows application. Extract the complete ZIP
to a user-writable directory and run `CloudContext.exe`. It does not request
administrator privileges and includes its own .NET runtime.

The application stores non-secret profile metadata and isolated native CLI
state beneath `%USERPROFILE%\.config\cloud-context` by default. Set
`CLOUD_CONTEXT_HOME` before launching it to select another user-writable data
directory.

Cloud Context uses native command-line authentication so that Microsoft Entra
MFA and Conditional Access remain effective. Install the tools required by the
connections you use:

- Azure CLI (`az`) for Azure, Azure DevOps, and Log Analytics. Microsoft offers
  a user-local ZIP distribution for machines where administrative privileges
  are unavailable.
- GitHub CLI (`gh`) for GitHub.
- Power Platform CLI (`pac`) for Dataverse.

The application never writes passwords, client secrets, personal access
tokens, or bearer tokens to `profiles.json`.
