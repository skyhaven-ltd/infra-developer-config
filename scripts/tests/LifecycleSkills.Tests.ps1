$lifecycleRoot = Join-Path $PSScriptRoot "..\..\skills\lifecycle"
$expectedSkills = @("build", "cycle", "review", "scope", "ship")

Describe "Lifecycle skill set" {
    It "contains exactly the lifecycle skills" {
        $names = @(Get-ChildItem -LiteralPath $lifecycleRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.Name } | Sort-Object)
        ($names -join ",") | Should Be ($expectedSkills -join ",")
    }
}

foreach ($skill in $expectedSkills) {
    $skillRoot = Join-Path $lifecycleRoot $skill
    $skillFile = Join-Path $skillRoot "SKILL.md"
    $openAiFile = Join-Path $skillRoot "agents\openai.yaml"

    Describe "Lifecycle skill $skill" {
        It "has a SKILL.md" {
            Test-Path -LiteralPath $skillFile | Should Be $true
        }

        It "names itself in frontmatter and disables model invocation" {
            $text = Get-Content -LiteralPath $skillFile -Raw -ErrorAction SilentlyContinue
            $text | Should Match "(?m)\A---\r?\nname: $skill\r?\n"
            $text | Should Match "(?m)^disable-model-invocation: true\r?$"
        }

        It "disables implicit invocation for Codex" {
            $yaml = Get-Content -LiteralPath $openAiFile -Raw -ErrorAction SilentlyContinue
            $yaml | Should Match "allow_implicit_invocation: false"
        }

        It "keeps SKILL.md within 8KB" {
            (Get-Item -LiteralPath $skillFile -ErrorAction SilentlyContinue).Length | Should BeLessThan 8193
        }

        It "keeps each reference within 6KB" {
            $oversized = @(Get-ChildItem -LiteralPath (Join-Path $skillRoot "references") -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 6144 } | ForEach-Object { $_.Name })
            ($oversized -join ",") | Should Be ""
        }

        It "does not reference plugin or legacy artefact paths" {
            $files = @(Get-ChildItem -LiteralPath $skillRoot -Recurse -File -ErrorAction SilentlyContinue)
            $legacy = @($files | Select-String -Pattern "agent-skills:", "TODO\.md", "SPEC\.md", "PLAN\.md", "tasks/" -SimpleMatch:$false | ForEach-Object { "$($_.Filename):$($_.LineNumber)" })
            ($legacy -join ",") | Should Be ""
        }

        It "has Reads, Writes and Exit sections" {
            $text = Get-Content -LiteralPath $skillFile -Raw -ErrorAction SilentlyContinue
            $text | Should Match "(?m)^## Reads\r?$"
            $text | Should Match "(?m)^## Writes\r?$"
            $text | Should Match "(?m)^## Exit\r?$"
        }

        It "writes its own artefact" {
            $text = Get-Content -LiteralPath $skillFile -Raw -ErrorAction SilentlyContinue
            $writes = [regex]::Match($text, "(?ms)^## Writes\r?$(.*?)(?=^## |\z)").Groups[1].Value
            $writes | Should Match ([regex]::Escape("$($skill.ToUpperInvariant()).md"))
        }
    }
}
