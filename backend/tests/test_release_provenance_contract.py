from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
PUBLISHER = ROOT / ".github" / "workflows" / "publish-current-version-on-green-main.yml"


def _section(text: str, start: str, end: str | None = None) -> str:
    i = text.index(start)
    if end is None:
        return text[i:]
    j = text.index(end, i + len(start))
    return text[i:j]


def test_draft_release_does_not_require_a_git_tag_before_publish() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    create = _section(
        text,
        "- name: Create draft GitHub Release for verification",
        "- name: Download-back verification",
    )
    download = _section(
        text,
        "- name: Download-back verification",
        "- name: Publish verified GitHub Release",
    )

    assert "gh release create $tag" in create
    assert "--target $sourceSha" in create
    assert "--draft" in create
    assert "--json targetCommitish" in create
    assert "git/ref/tags/$tag" not in create

    # A draft release has no refs/tags/<tag> yet. Download-back must therefore
    # validate the draft's targetCommitish rather than a non-existent git ref.
    assert "--json targetCommitish,isDraft" in download
    assert "git/ref/tags/$tag" not in download


def test_publication_materializes_and_verifies_the_exact_tag_sha() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    publish = _section(
        text,
        "- name: Publish verified GitHub Release",
        "- name: Upload download-back verification",
    )

    assert "gh release edit $tag --notes-file $publishedBody --draft=false --latest --target $sourceSha" in publish
    edit_i = publish.index("gh release edit $tag --notes-file $publishedBody --draft=false --latest --target $sourceSha")
    tag_i = publish.index('git/ref/tags/$tag')
    assert edit_i < tag_i
    assert "if ($tagSha -ne $sourceSha)" in publish
    assert "scripts/enrich_release_verification.ps1" in publish
    assert "-TagSha $tagSha" in publish
    assert "-ReleaseChannel $releaseChannel" in publish
    assert "-IsPrerelease $isPrerelease" in publish


def test_release_display_body_is_authoritative_before_publish() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    publish = _section(
        text,
        "- name: Publish verified GitHub Release",
        "- name: Upload download-back verification",
    )

    render_i = publish.index("scripts/render_published_release_body.py")
    edit_i = publish.index("gh release edit $tag --notes-file $publishedBody")
    state_i = publish.index("CHENGZHU_PUBLISHED_STATUS_BEGIN")
    assert render_i < edit_i < state_i
    assert "--source-sha" in publish
    assert "$sourceSha" in publish
    assert "--stable-latest" in publish
    assert "published Release body is missing authoritative publication truth" in publish


def test_existing_published_version_repairs_display_only_without_moving_tag() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")
    published = _section(
        text,
        'if [ "$is_draft" = "false" ]; then',
        'echo "$tag exists only as a draft',
    )

    assert "release_target=" in published
    assert "tag_sha=" in published
    assert 'if [ "$release_target" != "$tag_sha" ]; then' in published
    assert "scripts/render_published_release_body.py" in published
    assert 'gh release edit "$tag" --notes-file "$published_body"' in published
    assert "gh workflow run release.yml" not in published
    assert "--target" not in published
    assert "isImmutable" in published
    assert "display truth normalized; nothing to dispatch" in published


def test_release_workflow_executes_published_body_renderer_regression_on_windows() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    regression = _section(
        text,
        "- name: Published Release body regression",
        "- name: Release verification metadata regression",
    )
    assert "python @renderArgs" in regression
    assert "CHENGZHU_PUBLISHED_STATUS_BEGIN" in regression
    assert "Channel: **PRERELEASE**" in regression
    assert "underlying notes were not preserved" in regression


def test_release_verification_enrichment_supports_missing_publication_fields() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    helper = (ROOT / "scripts" / "enrich_release_verification.ps1").read_text(encoding="utf-8")
    regression = _section(
        text,
        "- name: Release verification metadata regression",
        "- name: Upload download-back verification",
    )

    # The pre-publish JSON intentionally does not contain all publication-only
    # fields. Direct assignment to a missing PSCustomObject property is exactly
    # what broke beta.3 after publication, so the helper must use Add-Member.
    assert 'Add-Member -NotePropertyName "tag_sha"' in helper
    assert 'Add-Member -NotePropertyName "release_channel"' in helper
    assert 'Add-Member -NotePropertyName "is_prerelease"' in helper
    assert "-Force" in helper
    assert "scripts/enrich_release_verification.ps1" in regression
    assert "release_channel enrichment regression" in regression


def test_download_back_evidence_is_uploaded_only_after_public_tag_verification() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    publish_i = text.index("- name: Publish verified GitHub Release")
    upload_i = text.index("- name: Upload download-back verification")
    assert publish_i < upload_i


def test_generic_publisher_refuses_a_stale_green_main_sha() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")

    assert "contents: write" in text
    assert "current_main=\"$(gh api \"repos/$GITHUB_REPOSITORY/git/ref/heads/main\" --jq '.object.sha')\"" in text
    assert 'if [ "$current_main" != "$SOURCE_SHA" ]; then' in text
    assert "stale green main" in text
    assert 'if [ -f ".github/RELEASE_HOLD" ]; then' in text
    assert "release hold is active" in text
    stale_i = text.index('if [ "$current_main" != "$SOURCE_SHA" ]; then')
    hold_i = text.index('if [ -f ".github/RELEASE_HOLD" ]; then')
    dispatch_i = text.index("gh workflow run release.yml")
    assert stale_i < hold_i < dispatch_i


def test_release_embedded_provenance_gate_validates_runtime_python_environment_and_artifact_sha() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    verify = _section(
        text,
        "- name: Verify embedded build provenance matches candidate",
        "- name: Stable v2+ human release authorization gate",
    )

    assert "CANDIDATE_BUILD_PROVENANCE.json" in verify
    assert "build/provenance/build-provenance.json" in verify
    assert "CHENGZHU_RUNTIME_FINGERPRINT_SHA256" in verify
    assert "CHENGZHU_PYTHON_ENVIRONMENT_SHA256" in verify
    assert "CHENGZHU_PYTHON_ARTIFACT_PROVENANCE_SHA256" in verify
    assert "$pythonEnvSha -notmatch '^[0-9a-f]{64}$'" in verify
    assert "$pythonArtifactSha -notmatch '^[0-9a-f]{64}$'" in verify
    assert "embedded Python environment SHA256 invalid" in verify
    assert "embedded Python artifact provenance SHA256 invalid" in verify
    assert "WHEEL_SHA256_PINNED" in verify

    # Regression for Release #380: a missing quote/end-anchor in this regex
    # caused a PowerShell ParserError after sidecar build despite green CI.
    assert "$pythonEnvSha -notmatch '^[0-9a-f]{64})" not in verify
    assert "$pythonArtifactSha -notmatch '^[0-9a-f]{64})" not in verify


def test_release_replays_pilot_python_wheel_hashes_before_stable_sidecar_build() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    replay = _section(
        text,
        "- name: Stable v2+ replay pilot Python wheel artifacts",
        "- name: Build backend sidecar",
    )

    assert 'python-version-file: "packaging/sidecar-python-version.txt"' in text
    assert 'python-version-file: "packaging/sidecar-python-version.txt"' in ci
    assert 'python-version: "3.11"' not in text
    assert 'python-version: "3.11"' not in ci

    assert "scripts/stable_python_environment_replay.py" in replay
    assert "--authorization-b64" in replay
    assert "--source-sha" in replay
    assert "--version" in replay
    assert "--runtime-fingerprint-sha256" in replay
    assert "--python-version-file packaging/sidecar-python-version.txt" in replay
    assert "--bootstrap-requirements-out" in replay
    assert "--runtime-requirements-out" in replay
    assert "STABLE_PYTHON_BOOTSTRAP_REQUIREMENTS.txt" in replay
    assert "STABLE_PYTHON_RUNTIME_REQUIREMENTS.txt" in replay
    assert "CHENGZHU_STABLE_PYTHON_BOOTSTRAP_REQUIREMENTS" in replay
    assert "CHENGZHU_STABLE_PYTHON_RUNTIME_REQUIREMENTS" in replay
    assert "CHENGZHU_EXPECTED_PYTHON_ARTIFACT_PROVENANCE_SHA256" in replay
    assert "PIP_CONSTRAINT=" not in replay
    assert "STABLE_PYTHON_ENVIRONMENT_REPLAY.json" in replay

    replay_i = text.index("- name: Stable v2+ replay pilot Python wheel artifacts")
    build_i = text.index("- name: Build backend sidecar")
    verify_i = text.index("- name: Verify embedded build provenance matches candidate")
    auth_i = text.index("- name: Stable v2+ human release authorization gate")
    assert replay_i < build_i < verify_i < auth_i

    assert "python scripts/build_sidecar.py --clean" in text
    assert "python scripts/build_sidecar.py --clean" in ci
