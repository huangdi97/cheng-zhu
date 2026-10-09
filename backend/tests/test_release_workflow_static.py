from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
POWERSHELL_SCOPES = {"env", "global", "script", "local", "private", "using"}


def test_release_workflow_has_no_ambiguous_powershell_variable_colon():
    """PowerShell parses `$name:` as a scoped variable reference.

    Inside interpolated strings the variable must be delimited as `${name}:`
    unless the prefix is an actual PowerShell scope such as `$env:`.
    """
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    offenders = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*):", line):
            if match.group(1) not in POWERSHELL_SCOPES:
                offenders.append((line_number, match.group(0), line.strip()))
    assert not offenders, f"ambiguous PowerShell variable-colon interpolation: {offenders}"
