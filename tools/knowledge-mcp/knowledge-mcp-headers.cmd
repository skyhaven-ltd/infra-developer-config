@echo off
rem Claude Code headersHelper for the knowledge MCP server. Emits the
rem Authorization header from the KNOWLEDGE_MCP_TOKEN user environment
rem variable so the bearer token is never persisted in ~/.claude.json.
if not defined KNOWLEDGE_MCP_TOKEN (
    echo {}
    exit /b 0
)
echo {"Authorization": "Bearer %KNOWLEDGE_MCP_TOKEN%"}
